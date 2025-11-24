import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import BackgroundTasks, HTTPException, WebSocketException
from sqlmodel import and_, col, desc, func, or_, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.common.constants import BASE_URL, PER_PAGE
from app.common.email_utils import send_email
from app.common.enum import ChatType, GroupChatPrivacy, MemberRole, MemberStatus
from app.common.utils import (
    CursorPaginationSerializer,
    generate_base_64_encoded_uuid,
    paginate,
    ws_code_from_http_code,
)
from app.i18n import translation
from app.models.chat_model import Chat, ChatInvite, ChatMember, Message, MessageReaction
from app.models.courses_model import Course, CourseEnrollment
from app.models.notification_model import Notification, NotificationType
from app.models.user_model import Account, Profile
from app.modules.notification.service import NotificationService
from app.schemas.annotations import ChatMessage
from app.schemas.chat import (
    ChatInviteWrite,
    ChatMessageReactionWrite,
    ChatMessageRead,
    ChatMessageUpdate,
    ChatMessageWrite,
    ChatUpdate,
    ChatWrite,
)
from app.schemas.notification import NotificationWrite


class ChatService:
    @staticmethod
    async def get_initial_data(
        chat_id: str, session: AsyncSession, current_user: Account
    ):
        try:
            return await ChatService.list_messages(chat_id, session, current_user)
        except Exception as e:
            if isinstance(e, HTTPException):
                raise WebSocketException(
                    ws_code_from_http_code(e.status_code), e.detail
                )
            raise WebSocketException(
                ws_code_from_http_code(1011), "An internal server error occurred"
            )

    @staticmethod
    async def list_messages(
        chat_id: str,
        session: AsyncSession,
        current_user: Account,
        q: Optional[str] = None,
        last_message_id: Optional[str] = None,
        cursor_type: Optional[str] = None,
        limit: int = PER_PAGE,
    ):
        await ChatService.get_chat_or_raise(chat_id, str(current_user.id), session)
        query = select(Message).where(
            Message.chat_id == chat_id, Message.is_deleted == False
        )

        # total_messages = (
        #     await session.exec(select(func.count()).select_from(query.froms[0]))
        # ).one()

        if last_message_id:
            last_message = (
                await session.exec(select(Message).where(Message.id == last_message_id))
            ).first()

            if last_message and cursor_type == "before":
                query = query.where(Message.created_at < last_message.created_at)
            elif last_message and cursor_type == "after":
                query = query.where(Message.created_at > last_message.created_at)

        if q:
            query = query.where(col(Message.content).ilike(f"%{q}%"))

        query = query.order_by(desc(Message.created_at)).limit(limit)
        messages = (await session.exec(query)).all()
        last_message = messages[len(messages) - 1]
        hasNext = bool(
            (
                await session.exec(
                    select(Message).where(Message.created_at < last_message.created_at)
                )
            ).first()
        )  # even if it is one message then there is a valid next

        return CursorPaginationSerializer(
            messages, messages[len(messages) - 1].id, messages[0].id, hasNext
        )

    @staticmethod
    async def list_chat(
        session: AsyncSession,
        current_user: Account,
        page=1,
        per_page=PER_PAGE,
        q: str | None = None,
    ):
        query = (
            select(Chat)
            .join(ChatMember)
            .where(ChatMember.account_id == current_user.id)
        )

        if q:
            pattern = f"%{q.lower()}%"

            # 2. Basic Text Filters (Chat Name / Description)
            text_filters = or_(
                func.lower(Chat.name).like(pattern),
                func.lower(Chat.description).like(pattern),
            )

            # 3. Subquery: Find IDs of DIRECT chats where OTHER members match the name
            # We select ChatMember.chat_id to get the Chat IDs
            member_subquery = (
                select(ChatMember.chat_id)
                .join(Account, Account.id == ChatMember.account_id)  # type: ignore[arg-type]
                .outerjoin(Profile, Profile.account_id == Account.id)  # type: ignore[arg-type]
                .join(Chat, Chat.id == ChatMember.chat_id)  # type: ignore[arg-type]
                # Join Chat to check the type
                .where(
                    and_(
                        Chat.chat_type
                        == ChatType.DIRECT,  # Condition 1: Must be Direct
                        or_(  # Condition 2: Name matches
                            func.lower(Account.username).like(pattern),
                            func.lower(Profile.display_name).like(pattern),
                        ),
                    )
                )
            )

            # 4. Apply the OR condition
            # (Matches Chat Name) OR (Matches Member Name AND is Direct Chat)
            query = query.where(or_(text_filters, col(Chat.id).in_(member_subquery)))

        query.order_by(desc(Chat.last_message_at))

        res = await paginate(session, query, page, per_page)
        items = res["items"]
        ids: list[uuid.UUID] = [item.id for item in items]

        unread_map = await ChatService.fetch_unread_stats(session, ids, current_user.id)

        modified_res = []
        for item in items:
            stats = unread_map.get(item.id, {"unread_count": 0, "has_reply": False})
            modified_res.append(
                {
                    "chat": item,
                    "unread_count": stats["unread_count"],
                    "has_reply": stats["has_reply"],
                }
            )
        res["items"] = modified_res

        return res

    @staticmethod
    async def list_all_public_chat(
        q: str | None,
        session: AsyncSession,
        current_user: Account,
        page=1,
        per_page=PER_PAGE,
    ):
        """
        Return all public chats where:
        1) The current user is enrolled in the course linked to the chat
        2) OR the current user is the creator of the course linked to the chat
        3) OR the chat has no course attached
        """

        # Base: only PUBLIC chats
        query = select(Chat).where(
            Chat.privacy == GroupChatPrivacy.PUBLIC, Chat.chat_type == ChatType.GROUP
        )

        if q:
            pattern = f"%{q.lower()}%"
            query = query.where(
                or_(
                    func.lower(Chat.description).like(pattern),
                    func.lower(Chat.name).like(pattern),
                )
            )

        # OUTER JOIN so chats without courses are still included
        query = query.outerjoin(
            Course, Chat.course_id == Course.id  # type: ignore[arg-type]
        ).outerjoin(
            CourseEnrollment, CourseEnrollment.course_id == Course.id  # type: ignore[arg-type]
        )

        query = query.where(
            or_(
                # User enrolled in the course
                CourseEnrollment.account_id == current_user.id,
                # User is the creator of the course
                Course.account_id == current_user.id,
                # Chat has no course attached
                col(Chat.course_id).is_(None),
            )
        )

        query.order_by(desc(Chat.last_message_at))

        return await paginate(session, query, page, per_page)

    @staticmethod
    async def create_chat(
        session: AsyncSession, current_user: Account, data: ChatWrite
    ):
        cleaned_data = data.model_dump()
        chat = Chat(**cleaned_data)
        chat.account_id = current_user.id
        session.add(chat)
        await session.flush()

        member = ChatMember(
            role=MemberRole.ADMIN,
            account_id=current_user.id,
            chat_id=chat.id,
            is_creator=True,
        )

        if data.chat_type == ChatType.DIRECT:
            if not data.associate_account:
                raise HTTPException(400, "direct chat must have an associate account")

            account = (
                await session.exec(
                    select(Account).where(Account.id == data.associate_account)
                )
            ).first()

            if not account:
                raise HTTPException(404, "associate account does not exists")

            associate_member = ChatMember(
                role=MemberRole.ADMIN,
                account_id=account.id,
                chat_id=chat.id,
            )
            session.add(associate_member)

        session.add(member)
        await session.commit()
        await session.refresh(chat)

        return chat

    @staticmethod
    async def update_chat(
        session: AsyncSession, current_user: Account, chat_id: str, data: ChatUpdate
    ):
        chat = await ChatService.get_chat_or_raise(
            str(chat_id), str(current_user.id), session
        )

        member = (
            await session.exec(
                select(ChatMember).where(
                    ChatMember.account_id == current_user.id,
                    ChatMember.chat_id == chat.id,
                )
            )
        ).first()

        assert member is not None

        if member.status != MemberRole.ADMIN and not member.is_creator:
            raise HTTPException(403, "permission denied")

        chat.sqlmodel_update(data.model_dump())
        session.add(chat)
        await session.commit()
        await session.refresh(chat)

        return chat

    @staticmethod
    async def make_admin(
        session: AsyncSession, current_user: Account, chat_id: str, member_id: str
    ):
        chat = await ChatService.get_chat_or_raise(
            str(chat_id), str(current_user.id), session
        )

        current_member = (
            await session.exec(
                select(ChatMember).where(
                    ChatMember.account_id == current_user.id,
                    ChatMember.chat_id == chat.id,
                )
            )
        ).first()

        assert current_member is not None

        if current_member.status != MemberRole.ADMIN and not current_member.is_creator:
            raise HTTPException(403, "permission denied")

        member = (
            await session.exec(
                select(ChatMember).where(
                    ChatMember.account_id == member_id,
                    ChatMember.chat_id == chat.id,
                    ChatMember.left_at == None,
                    ChatMember.status == MemberStatus.ACTIVE,
                )
            )
        ).first()

        if not member:
            raise HTTPException(404, "no member found")

        member.role = MemberRole.ADMIN

        session.add(member)
        await session.commit()
        await session.refresh(member)

        return member

    @staticmethod
    async def remove_admin(
        session: AsyncSession, current_user: Account, chat_id: str, member_id: str
    ):
        chat = await ChatService.get_chat_or_raise(
            str(chat_id), str(current_user.id), session
        )

        current_member = (
            await session.exec(
                select(ChatMember).where(
                    ChatMember.account_id == current_user.id,
                    ChatMember.chat_id == chat.id,
                )
            )
        ).first()

        assert current_member is not None

        if current_member.status != MemberRole.ADMIN and not current_member.is_creator:
            raise HTTPException(403, "permission denied")

        member = (
            await session.exec(
                select(ChatMember).where(
                    ChatMember.account_id == member_id,
                    ChatMember.chat_id == chat.id,
                    ChatMember.left_at == None,
                    ChatMember.status == MemberStatus.ACTIVE,
                )
            )
        ).first()

        if not member:
            raise HTTPException(404, "no member found")

        member.role = MemberRole.MEMBER

        session.add(member)
        await session.commit()
        await session.refresh(member)

        return member

    @staticmethod
    async def create_message(
        session: AsyncSession, current_user: Account, data: ChatMessageWrite
    ):
        chat = await ChatService.get_chat_or_raise(
            str(data.chat_id), str(current_user.id), session
        )

        cleaned_data = data.model_dump()
        message = Message(**cleaned_data, sender_id=current_user.id)
        session.add(message)
        await session.flush()

        await session.refresh(chat)

        if message.created_at > chat.last_message_at:
            chat.last_message_at = message.created_at
            session.add(chat)

        await session.commit()

        await session.refresh(message)
        return message

    @staticmethod
    async def update_message(
        session: AsyncSession,
        current_user: Account,
        message_id: str,
        data: ChatMessageUpdate,
    ):

        message = (
            await session.exec(
                select(Message).where(
                    Message.id == message_id,
                    Message.sender_id == current_user.id,
                )
            )
        ).first()

        if not message:
            raise HTTPException(404, "message not found")

        if message.is_deleted:
            raise HTTPException(403, "Invalid operation")

        cleaned_data = data.model_dump()
        message.sqlmodel_update(cleaned_data)
        message.is_edited = True

        session.add(message)
        await session.commit()

        await session.refresh(message)
        return message

    @staticmethod
    async def delete_message(
        session: AsyncSession, current_user: Account, message_id: str
    ):
        message = (
            await session.exec(
                select(Message).where(
                    Message.id == message_id,
                    Message.sender_id == current_user.id,
                )
            )
        ).first()

        if not message:
            raise HTTPException(404, "message not found")

        if message.is_deleted:
            raise HTTPException(403, "Invalid operation")

        message.is_deleted = True
        session.add(message)
        await session.commit()
        await session.refresh(message)
        return message

    @staticmethod
    async def remove_member(
        session: AsyncSession, current_user: Account, chat_id: str, member_id: str
    ):

        chat_member = (
            await session.exec(
                select(ChatMember)
                .where(ChatMember.chat_id == chat_id)
                .where(ChatMember.account_id == member_id)
            )
        ).first()

        if not chat_member:
            raise HTTPException(404, "Chat member not found")

        remover = (
            await session.exec(
                select(ChatMember)
                .where(ChatMember.chat_id == chat_id)
                .where(ChatMember.account_id == current_user.id)
            )
        ).first()

        if not remover:
            raise HTTPException(403, "You must be a member to create invites")

        if remover.role != MemberRole.ADMIN and not remover.is_creator:
            raise HTTPException(403, "Permission denied, only admin can invite")

        await session.delete(chat_member)
        await session.commit()
        return {"OK": True}

    @staticmethod
    async def accept_invite(session: AsyncSession, current_user: Account, token: str):
        """
        Accept a chat invite.
        - decode token → invite_id
        - validate invite exists + active + within expiry
        - check membership limit
        - verify user is invited (if targeted invite)
        - check if enrolled for course (if group chat is course-based)
        - add ChatMember
        """

        invite = (
            await session.exec(
                select(ChatInvite).where(ChatInvite.invite_code == token)
            )
        ).first()
        if not invite or not invite.is_active:
            raise HTTPException(404, "Invite not found or inactive")

        # check expiry
        if invite.expires_at and invite.expires_at < datetime.now(tz=timezone.utc):
            raise HTTPException(400, "Invite expired")

        # check max uses
        if invite.max_uses is not None and invite.current_uses >= invite.max_uses:
            raise HTTPException(400, "Invite usage limit reached")

        chat = await session.get(Chat, invite.chat_id)
        if not chat:
            raise HTTPException(404, "Chat not found")

        # check targeted invite
        if invite.invited_account_id and invite.invited_account_id != current_user.id:
            raise HTTPException(403, "This invite is not for you")

        # check if user is already a member
        existing = (
            await session.exec(
                select(ChatMember)
                .where(ChatMember.account_id == current_user.id)
                .where(ChatMember.chat_id == chat.id)
            )
        ).first()
        if existing:
            raise HTTPException(400, "Already a member")

        # check course enrollment
        if chat.course_id:
            enrollment = (
                await session.exec(
                    select(CourseEnrollment)
                    .where(CourseEnrollment.account_id == current_user.id)
                    .where(CourseEnrollment.course_id == chat.course_id)
                )
            ).first()

            if not enrollment:
                raise HTTPException(403, "You must be enrolled in the course")

        # create ChatMember
        new_member = ChatMember(
            chat_id=chat.id,
            account_id=current_user.id,
            role=MemberRole.MEMBER,
        )
        session.add(new_member)

        # increment invite usage
        invite.current_uses += 1
        await session.commit()
        await session.refresh(new_member)

        return new_member

    @staticmethod
    async def create_invite(
        session: AsyncSession,
        current_user: Account,
        bgTask: BackgroundTasks,
        data: ChatInviteWrite,
        lang: Optional[str] = None,
    ):
        """
        Create an invite.
        - chat must exist
        - current_user must be a member
        - if invited_account_id is provided → targeted invite
        - send notification (placeholder)
        """
        chat = await session.get(Chat, data.chat_id)
        if not chat:
            raise HTTPException(404, "Chat not found")

        # check membership
        member = (
            await session.exec(
                select(ChatMember)
                .where(ChatMember.chat_id == chat.id)
                .where(ChatMember.account_id == current_user.id)
            )
        ).first()
        if not member:
            raise HTTPException(403, "You must be a member to create invites")

        if member.role != MemberRole.ADMIN and not member.is_creator:
            raise HTTPException(403, "Permission denied, only admin can invite")

        target_account = await session.get(Account, data.invited_account_id)
        if not target_account:
            raise HTTPException(404, "Invited account not found")

        cleaned_data = data.model_dump()

        invite = ChatInvite(
            **cleaned_data,
            invited_by_id=member.id,
            is_active=True,
        )

        invite.invite_code = generate_base_64_encoded_uuid()

        session.add(invite)
        await session.commit()
        await session.refresh(invite)

        trans = translation(lang)

        await NotificationService.create_notification(
            session,
            current_user,
            NotificationWrite(
                title=trans.t("chat_invite.title"),
                message=trans.t(
                    "chat_invite.message",
                    inviter=current_user.username,
                ),
                type=NotificationType.INVITE,
            ),
        )

        await send_email(
            bgTask,
            [target_account.email],
            "Chat Invitation",
            "chat.html",
            {
                "logo_url": BASE_URL + "/static/black-logo.png",
                "name": (
                    current_user.profile.display_name or current_user.username
                    if current_user.profile
                    else member.account.username
                ),
                "chat": chat.name,
                "year": datetime.now(timezone.utc).year,
            },
        )

        return invite

    @staticmethod
    async def add_directly(
        session: AsyncSession,
        current_user: Account,
        target_account_id: str,
        course_id: Optional[str] = None,
    ):
        """
        Create a direct chat between two members who share a course.
        Steps:
        - verify target exists
        - verify both are enrolled in same course (required)
        - check if direct chat already exists
        - create chat + members
        """
        # target user exists
        target = await session.get(Account, target_account_id)
        if not target:
            raise HTTPException(404, "Account not found")

        if target.id == current_user.id:
            raise HTTPException(400, "You cannot DM yourself")

        # check enrollment
        if course_id:
            course = await session.get(Course, course_id)
            if not course:
                raise HTTPException(404, "Course not found")

            # user
            me = (
                await session.exec(
                    select(CourseEnrollment)
                    .where(CourseEnrollment.course_id == course_id)
                    .where(CourseEnrollment.account_id == current_user.id)
                )
            ).first()
            if not me and not course.account_id != current_user.id:
                raise HTTPException(403, "You are not enrolled in this course")

            # target
            other = (
                await session.exec(
                    select(CourseEnrollment)
                    .where(CourseEnrollment.course_id == course_id)
                    .where(CourseEnrollment.account_id == target.id)
                )
            ).first()
            if not other and not course.account_id != target.id:
                raise HTTPException(403, "User not enrolled in this course")

        # check if direct chat already exists
        existing = (
            await session.exec(
                select(Chat)
                .where(Chat.chat_type == ChatType.DIRECT)
                .where(col(Chat.members).any(ChatMember.account_id == current_user.id))  # type: ignore
                .where(col(Chat.members).any(ChatMember.account_id == target.id))  # type: ignore
            )
        ).first()

        if existing:
            return existing

        # create direct chat
        chat = Chat(
            chat_type=ChatType.DIRECT,
            account_id=current_user.id,  # creator
            course_id=course_id,
        )
        session.add(chat)
        await session.flush()

        # add 2 members
        session.add(ChatMember(chat_id=chat.id, account_id=current_user.id))
        session.add(ChatMember(chat_id=chat.id, account_id=target.id))

        await session.commit()
        await session.refresh(chat)
        return chat

    @staticmethod
    async def join_public_group(
        session: AsyncSession, chat_id: uuid.UUID, current_user: Account
    ):
        """
        Join a public group chat.
        - chat exists
        - must be PUBLIC
        - if chat has course_id → must be enrolled
        - if already member → return
        """
        chat = await session.get(Chat, chat_id)
        if not chat:
            raise HTTPException(404, "Chat not found")

        if chat.privacy != GroupChatPrivacy.PUBLIC:
            raise HTTPException(403, "This group is not public")

        # check if already member
        existing = (
            await session.exec(
                select(ChatMember)
                .where(ChatMember.chat_id == chat.id)
                .where(ChatMember.account_id == current_user.id)
            )
        ).first()
        if existing:
            return existing

        # check course enrollment
        if chat.course_id:
            enrolled = (
                await session.exec(
                    select(CourseEnrollment)
                    .where(CourseEnrollment.course_id == chat.course_id)
                    .where(CourseEnrollment.account_id == current_user.id)
                )
            ).first()
            if not enrolled:
                raise HTTPException(403, "You are not enrolled in this course")

        member = ChatMember(
            chat_id=chat.id,
            account_id=current_user.id,
            role=MemberRole.MEMBER,
        )
        session.add(member)
        await session.commit()
        await session.refresh(member)

        return member

    @staticmethod
    async def set_last_message_read(
        session: AsyncSession,
        chat_id: uuid.UUID,
        message_id: uuid.UUID,
        current_user: Account,
    ):
        """
        Set last read message.
        - validate user is member
        - validate message exists and belongs to chat
        - update ChatMember.last_read_message_id
        """
        # member check
        member = (
            await session.exec(
                select(ChatMember)
                .where(ChatMember.chat_id == chat_id)
                .where(ChatMember.account_id == current_user.id)
            )
        ).first()
        if not member:
            raise HTTPException(403, "You are not a member of this chat")

        # message exists & belongs to chat
        msg = await session.get(Message, message_id)
        if not msg or msg.chat_id != chat_id:
            raise HTTPException(404, "Message not found in this chat")

        # update read pointer
        member.last_read_message_id = msg.id

        session.add(member)
        await session.commit()
        return {"ok": True}

    @staticmethod
    async def create_delete_reaction(
        session: AsyncSession,
        current_user: Account,
        message_id: str,
        data: ChatMessageReactionWrite,
    ):
        message = (
            await session.exec(select(Message).where(Message.id == message_id))
        ).first()

        if not message:
            raise HTTPException(404, "message not found")

        await ChatService.get_chat_or_raise(
            str(message.chat_id), str(current_user.id), session
        )

        reaction = (
            await session.exec(
                select(MessageReaction).where(
                    MessageReaction.emoji == data.emoji,
                    MessageReaction.account_id == current_user.id,
                )
            )
        ).first()

        if reaction:
            await session.delete(reaction)
            await session.commit()
            await session.refresh(message)
            return message

        reaction = MessageReaction(**data.model_dump())
        reaction.account_id = current_user.id
        reaction.message_id = uuid.UUID(message_id)

        session.add(reaction)
        await session.commit()
        await session.refresh(message)
        return message

    @staticmethod
    async def fetch_unread_stats(
        session, chat_ids: list[uuid.UUID], user_id: uuid.UUID
    ):

        # Subquery: unread messages grouped by chat
        unread_subq = (
            select(
                col(Message.chat_id).label("chat_id"),
                func.count(col(Message.id)).label("unread_count"),
                func.bool_or(col(Message.reply_to_id).isnot(None)).label("has_reply"),
            )
            .join(ChatMember, ChatMember.chat_id == Message.chat_id)  # type: ignore
            .where(
                ChatMember.account_id == user_id,
                (
                    Message.created_at
                    > select(Message.created_at)
                    .where(Message.id == ChatMember.last_read_message_id)
                    .scalar_subquery()
                    if col(ChatMember.last_read_message_id).isnot(None)
                    else True
                ),  # If no last_read, count all messages
            )
            .where(col(Message.chat_id).in_(chat_ids))
            .group_by(col(Message.chat_id))
            .subquery()
        )

        results = await session.exec(
            select(
                unread_subq.c.chat_id,
                unread_subq.c.unread_count,
                unread_subq.c.has_reply,
            )
        )

        rows = results.all()

        # Convert into a dict {chat_id: {unread_count, has_reply}}
        return {
            row.chat_id: {
                "unread_count": row.unread_count,
                "has_reply": row.has_reply,
            }
            for row in rows
        }

    @staticmethod
    async def get_chat_or_raise(
        chat_id: str, account_id: str, session: AsyncSession
    ) -> Chat:
        chat = (
            await session.exec(
                select(Chat)
                .join(ChatMember)
                .where(Chat.id == chat_id, ChatMember.account_id == account_id)
            )
        ).first()
        if not chat:
            raise HTTPException(403, "you are not a member of this chat")

        return chat
