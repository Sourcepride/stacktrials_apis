"""admin

Revision ID: aa0d16e83fdb
Revises: 3cbb5d609ee3
Create Date: 2025-10-27 12:08:10.451781

"""

from typing import Sequence, Union

import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "aa0d16e83fdb"
down_revision: Union[str, Sequence[str], None] = "3cbb5d609ee3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1️⃣ Create the enum type first
    userrole_enum = sa.Enum("USER", "ADMIN", name="userrole")
    userrole_enum.create(op.get_bind(), checkfirst=True)

    # 2️⃣ Add the boolean column safely with default false
    op.add_column(
        "account",
        sa.Column(
            "is_super_user",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )

    # 3️⃣ Add the role column with default USER
    op.add_column(
        "account",
        sa.Column("role", userrole_enum, server_default="USER", nullable=False),
    )

    # 4️⃣ Optionally remove defaults afterward
    op.alter_column("account", "is_super_user", server_default=None)
    op.alter_column("account", "role", server_default=None)


def downgrade() -> None:
    op.drop_column("account", "role")
    op.drop_column("account", "is_super_user")

    # Drop the enum type
    sa.Enum(name="userrole").drop(op.get_bind(), checkfirst=True)
