import uuid
from typing import Optional

from fastapi import HTTPException, WebSocketException
from sqlmodel import Session, and_, col, desc, func, or_, select

from app.common.constants import PER_PAGE
from app.common.enum import ChatType, GroupChatPrivacy, MemberRole, MemberStatus
from app.common.utils import paginate, ws_code_from_http_code
from app.models.chat_model import Chat, ChatMember, Message, MessageReaction
from app.models.courses_model import Course, CourseEnrollment
from app.models.user_model import Account, Profile
from app.schemas.annotations import ChatMessage
from app.schemas.chat import (
    ChatMessageReactionWrite,
    ChatMessageUpdate,
    ChatMessageWrite,
    ChatUpdate,
    ChatWrite,
)


class ChatService:
    @staticmethod
    async def get_initial_data(chat_id: str, session: Session, current_user: Account):
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
        session: Session,
        current_user: Account,
        last_message_id: Optional[int] = None,
        cursor_type: Optional[str] = None,
        limit: int = PER_PAGE,
    ):
        await ChatService.get_chat_or_raise(chat_id, str(current_user.id), session)
        query = select(Message).where(
            Message.chat_id == chat_id, Message.is_deleted == False
        )

        total_messages = session.exec(
            select(func.count()).select_from(query.froms[0])
        ).one()

        if last_message_id:
            last_message = session.exec(
                select(Message).where(Message.id == last_message_id)
            ).first()

            if last_message and cursor_type == "before":
                query = query.where(Message.created_at < last_message.created_at)
            elif last_message and cursor_type == "after":
                query = query.where(Message.created_at > last_message.created_at)

        query = query.order_by(desc(Message.created_at)).limit(limit)
        messages = session.exec(query).all()

        return {
            "items": messages,
            "last_message_id": messages[len(messages) - 1].id,
            "recent_message_id": messages[0].id,
            "next": total_messages <= len(messages),
        }

    @staticmethod
    async def list_chat(
        q: str, session: Session, current_user: Account, page=1, per_page=PER_PAGE
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

        return paginate(session, query, page, per_page)

    @staticmethod
    async def list_all_public_chat(
        q: str | None,
        session: Session,
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

        return paginate(session, query, page, per_page)

    @staticmethod
    async def create_chat(session: Session, current_user: Account, data: ChatWrite):
        cleaned_data = data.model_dump()
        chat = Chat(**cleaned_data)
        chat.account_id = current_user.id
        session.add(chat)
        session.flush()

        member = ChatMember(
            role=MemberRole.ADMIN,
            account_id=current_user.id,
            chat_id=chat.id,
            is_creator=True,
        )

        if data.chat_type == ChatType.DIRECT:
            if not data.associate_account:
                raise HTTPException(400, "direct chat must have an associate account")

            account = session.exec(
                select(Account).where(Account.id == data.associate_account)
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
        session.commit()
        session.refresh(chat)

        return chat

    @staticmethod
    async def update_chat(
        session: Session, current_user: Account, chat_id: str, data: ChatUpdate
    ):
        chat = await ChatService.get_chat_or_raise(
            str(chat_id), str(current_user.id), session
        )

        member = session.exec(
            select(ChatMember).where(
                ChatMember.account_id == current_user.id, ChatMember.chat_id == chat.id
            )
        ).first()

        assert member is not None

        if member.status != MemberRole.ADMIN and not member.is_creator:
            raise HTTPException(403, "permission denied")

        chat.sqlmodel_update(data.model_dump())
        session.add(chat)
        session.commit()
        session.refresh(chat)

        return chat

    @staticmethod
    async def make_admin(
        session: Session, current_user: Account, chat_id: str, member_id: str
    ):
        chat = await ChatService.get_chat_or_raise(
            str(chat_id), str(current_user.id), session
        )

        current_member = session.exec(
            select(ChatMember).where(
                ChatMember.account_id == current_user.id, ChatMember.chat_id == chat.id
            )
        ).first()

        assert current_member is not None

        if current_member.status != MemberRole.ADMIN and not current_member.is_creator:
            raise HTTPException(403, "permission denied")

        member = session.exec(
            select(ChatMember).where(
                ChatMember.account_id == member_id,
                ChatMember.chat_id == chat.id,
                ChatMember.left_at == None,
                ChatMember.status == MemberStatus.ACTIVE,
            )
        ).first()

        if not member:
            raise HTTPException(404, "no member found")

        member.role = MemberRole.ADMIN

        session.add(member)
        session.commit()
        session.refresh(member)

        return member

    @staticmethod
    async def remove_admin(
        session: Session, current_user: Account, chat_id: str, member_id: str
    ):
        chat = await ChatService.get_chat_or_raise(
            str(chat_id), str(current_user.id), session
        )

        current_member = session.exec(
            select(ChatMember).where(
                ChatMember.account_id == current_user.id, ChatMember.chat_id == chat.id
            )
        ).first()

        assert current_member is not None

        if current_member.status != MemberRole.ADMIN and not current_member.is_creator:
            raise HTTPException(403, "permission denied")

        member = session.exec(
            select(ChatMember).where(
                ChatMember.account_id == member_id,
                ChatMember.chat_id == chat.id,
                ChatMember.left_at == None,
                ChatMember.status == MemberStatus.ACTIVE,
            )
        ).first()

        if not member:
            raise HTTPException(404, "no member found")

        member.role = MemberRole.MEMBER

        session.add(member)
        session.commit()
        session.refresh(member)

        return member

    @staticmethod
    async def create_message(
        session: Session, current_user: Account, data: ChatMessageWrite
    ):
        chat = await ChatService.get_chat_or_raise(
            str(data.chat_id), str(current_user.id), session
        )

        cleaned_data = data.model_dump()
        message = Message(**cleaned_data, sender_id=current_user.id)
        session.add(message)
        session.flush()

        session.refresh(chat)

        if message.created_at > chat.last_message_at:
            chat.last_message_at = message.created_at
            session.add(chat)

        session.commit()

        session.refresh(message)
        return message

    @staticmethod
    async def update_message(
        session: Session,
        current_user: Account,
        message_id: str,
        data: ChatMessageUpdate,
    ):

        message = session.exec(
            select(Message).where(
                Message.id == message_id,
                Message.sender_id == current_user.id,
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
        session.commit()

        session.refresh(message)
        return message

    @staticmethod
    async def delete_message(session: Session, current_user: Account, message_id: str):
        message = session.exec(
            select(Message).where(
                Message.id == message_id,
                Message.sender_id == current_user.id,
            )
        ).first()

        if not message:
            raise HTTPException(404, "message not found")

        if message.is_deleted:
            raise HTTPException(403, "Invalid operation")

        message.is_deleted = True
        session.add(message)
        session.commit()
        session.refresh(message)
        return message

    @staticmethod
    async def accept_invite():
        """accept invite
        check the token and then if the expiry date is none or
        not expired
        check if the user is enrolled
        if the user is enrolled for the course then the user can be added
        """

    @staticmethod
    async def create_invite():
        """
        here create an invite
        check if the user account exists
        if it exists then send out a notification
        and an email to the user in question
        """

    @staticmethod
    async def add_directly():
        """
        users in a group should be able to directly chat group members
        or privately message coure creator or other learners via comment
        section

        create a direct chat
        check if account exists and is enrolled in same course
        create a member afterwards by adding the member to the chat
        """

    @staticmethod
    async def join_public_group():
        """
        using the chat_id
        we check if the chat exists
        check if user is enrolled in the course if course is available
        if user is not enrolled in the course then they should get a permission denied
        else a chat member is created
        """

    @staticmethod
    async def set_last_message_read():
        """
        this is used to set the last message read for the chat member
        checks if the member exists and the current user is the memmber
        then checks if the message exists for that chat else raises a 404
        update the last message read id after checks passed
        """

    @staticmethod
    async def create_delete_reaction(
        session: Session,
        current_user: Account,
        message_id: str,
        data: ChatMessageReactionWrite,
    ):
        message = session.exec(select(Message).where(Message.id == message_id)).first()

        if not message:
            raise HTTPException(404, "message not found")

        await ChatService.get_chat_or_raise(
            str(message.chat_id), str(current_user.id), session
        )

        reaction = session.exec(
            select(MessageReaction).where(
                MessageReaction.emoji == data.emoji,
                MessageReaction.account_id == current_user.id,
            )
        ).first()

        if reaction:
            session.delete(reaction)
            session.commit()
            session.refresh(message)
            return message

        reaction = MessageReaction(**data.model_dump())
        reaction.account_id = current_user.id
        reaction.message_id = uuid.UUID(message_id)

        session.add(reaction)
        session.commit()
        session.refresh(message)
        return message

    @staticmethod
    async def get_chat_or_raise(
        chat_id: str, account_id: str, session: Session
    ) -> Chat:
        chat = session.exec(
            select(Chat)
            .join(ChatMember)
            .where(Chat.id == chat_id, ChatMember.account_id == account_id)
        ).first()
        if not chat:
            raise HTTPException(403, "you are not a member of this chat")

        return chat
