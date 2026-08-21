"""Create the initial smart_bins schema.

Revision ID: 9b7a1e20a036
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "9b7a1e20a036"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "smart_bins",
        sa.Column("bin_id", sa.String(length=50), nullable=False),
        sa.Column("capacity", sa.Float(), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.PrimaryKeyConstraint("bin_id"),
    )


def downgrade() -> None:
    op.drop_table("smart_bins")
