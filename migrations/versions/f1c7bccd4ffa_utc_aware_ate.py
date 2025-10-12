"""utc aware date migration

Revision ID: f1c7bccd4ffa
Revises: f4e84c696497
Create Date: 2025-10-12 18:07:35.130679

"""

from typing import Sequence, Union

import sqlalchemy as sa
import sqlmodel
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "f1c7bccd4ffa"
down_revision: Union[str, Sequence[str], None] = "f4e84c696497"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column(
        "chat_invite",
        "expires_at",
        existing_type=postgresql.TIMESTAMP(),
        type_=sa.DateTime(timezone=True),
        postgresql_using="expires_at AT TIME ZONE 'UTC'",
        comment="Stored in UTC. Use AT TIME ZONE 'UTC' during migration.",
        existing_nullable=True,
    )
    op.alter_column(
        "chat_member",
        "left_at",
        existing_type=postgresql.TIMESTAMP(),
        type_=sa.DateTime(timezone=True),
        postgresql_using="left_at AT TIME ZONE 'UTC'",
        comment="Stored in UTC. Use AT TIME ZONE 'UTC' during migration.",
        existing_nullable=True,
    )
    op.alter_column(
        "course_enrollment",
        "completion_date",
        existing_type=postgresql.TIMESTAMP(),
        type_=sa.DateTime(timezone=True),
        postgresql_using="completion_date AT TIME ZONE 'UTC'",
        comment="Stored in UTC. Use AT TIME ZONE 'UTC' during migration.",
        existing_nullable=True,
    )
    op.alter_column(
        "course_progress",
        "start_time",
        existing_type=postgresql.TIMESTAMP(),
        type_=sa.DateTime(timezone=True),
        postgresql_using="start_time AT TIME ZONE 'UTC'",
        comment="Stored in UTC. Use AT TIME ZONE 'UTC' during migration.",
        existing_nullable=True,
    )
    op.alter_column(
        "course_progress",
        "completion_time",
        existing_type=postgresql.TIMESTAMP(),
        type_=sa.DateTime(timezone=True),
        postgresql_using="completion_time AT TIME ZONE 'UTC'",
        comment="Stored in UTC. Use AT TIME ZONE 'UTC' during migration.",
        existing_nullable=True,
    )
    op.alter_column(
        "course_progress",
        "last_active_date",
        existing_type=postgresql.TIMESTAMP(),
        type_=sa.DateTime(timezone=True),
        postgresql_using="last_active_date AT TIME ZONE 'UTC'",
        comment="Stored in UTC. Use AT TIME ZONE 'UTC' during migration.",
        existing_nullable=True,
    )
    op.alter_column(
        "message",
        "edited_at",
        existing_type=postgresql.TIMESTAMP(),
        type_=sa.DateTime(timezone=True),
        postgresql_using="edited_at AT TIME ZONE 'UTC'",
        comment="Stored in UTC. Use AT TIME ZONE 'UTC' during migration.",
        existing_nullable=True,
    )
    op.alter_column(
        "message",
        "deleted_at",
        existing_type=postgresql.TIMESTAMP(),
        type_=sa.DateTime(timezone=True),
        postgresql_using="deleted_at AT TIME ZONE 'UTC'",
        comment="Stored in UTC. Use AT TIME ZONE 'UTC' during migration.",
        existing_nullable=True,
    )
    op.alter_column(
        "provider",
        "expires_at",
        existing_type=postgresql.TIMESTAMP(),
        type_=sa.DateTime(timezone=True),
        postgresql_using="expires_at AT TIME ZONE 'UTC'",
        comment="Stored in UTC. Use AT TIME ZONE 'UTC' during migration.",
        existing_nullable=True,
    )
    op.alter_column(
        "quiz_attempt",
        "completion_time",
        existing_type=postgresql.TIMESTAMP(),
        type_=sa.DateTime(timezone=True),
        postgresql_using="completion_time AT TIME ZONE 'UTC'",
        comment="Stored in UTC. Use AT TIME ZONE 'UTC' during migration.",
        existing_nullable=True,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column(
        "quiz_attempt",
        "completion_time",
        existing_type=sa.DateTime(timezone=True),
        type_=postgresql.TIMESTAMP(),
        comment=None,
        existing_comment="Stored in UTC. Use AT TIME ZONE 'UTC' during migration.",
        existing_nullable=True,
    )
    op.alter_column(
        "provider",
        "expires_at",
        existing_type=sa.DateTime(timezone=True),
        type_=postgresql.TIMESTAMP(),
        comment=None,
        existing_comment="Stored in UTC. Use AT TIME ZONE 'UTC' during migration.",
        existing_nullable=True,
    )
    op.alter_column(
        "message",
        "deleted_at",
        existing_type=sa.DateTime(timezone=True),
        type_=postgresql.TIMESTAMP(),
        comment=None,
        existing_comment="Stored in UTC. Use AT TIME ZONE 'UTC' during migration.",
        existing_nullable=True,
    )
    op.alter_column(
        "message",
        "edited_at",
        existing_type=sa.DateTime(timezone=True),
        type_=postgresql.TIMESTAMP(),
        comment=None,
        existing_comment="Stored in UTC. Use AT TIME ZONE 'UTC' during migration.",
        existing_nullable=True,
    )
    op.alter_column(
        "course_progress",
        "last_active_date",
        existing_type=sa.DateTime(timezone=True),
        type_=postgresql.TIMESTAMP(),
        comment=None,
        existing_comment="Stored in UTC. Use AT TIME ZONE 'UTC' during migration.",
        existing_nullable=True,
    )
    op.alter_column(
        "course_progress",
        "completion_time",
        existing_type=sa.DateTime(timezone=True),
        type_=postgresql.TIMESTAMP(),
        comment=None,
        existing_comment="Stored in UTC. Use AT TIME ZONE 'UTC' during migration.",
        existing_nullable=True,
    )
    op.alter_column(
        "course_progress",
        "start_time",
        existing_type=sa.DateTime(timezone=True),
        type_=postgresql.TIMESTAMP(),
        comment=None,
        existing_comment="Stored in UTC. Use AT TIME ZONE 'UTC' during migration.",
        existing_nullable=True,
    )
    op.alter_column(
        "course_enrollment",
        "completion_date",
        existing_type=sa.DateTime(timezone=True),
        type_=postgresql.TIMESTAMP(),
        comment=None,
        existing_comment="Stored in UTC. Use AT TIME ZONE 'UTC' during migration.",
        existing_nullable=True,
    )
    op.alter_column(
        "chat_member",
        "left_at",
        existing_type=sa.DateTime(timezone=True),
        type_=postgresql.TIMESTAMP(),
        comment=None,
        existing_comment="Stored in UTC. Use AT TIME ZONE 'UTC' during migration.",
        existing_nullable=True,
    )
    op.alter_column(
        "chat_invite",
        "expires_at",
        existing_type=sa.DateTime(timezone=True),
        type_=postgresql.TIMESTAMP(),
        comment=None,
        existing_comment="Stored in UTC. Use AT TIME ZONE 'UTC' during migration.",
        existing_nullable=True,
    )
