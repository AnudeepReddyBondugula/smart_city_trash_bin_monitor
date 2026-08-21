"""Add zone to smart_bins and backfill existing rows."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0002_add_zone"
down_revision: Union[str, None] = "9b7a1e20a036"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("smart_bins", sa.Column("zone", sa.String(length=20), nullable=True))
    op.execute("UPDATE smart_bins SET zone = 'UNASSIGNED' WHERE zone IS NULL")
    op.alter_column(
        "smart_bins",
        "zone",
        existing_type=sa.String(length=20),
        nullable=False,
    )


def downgrade() -> None:
    op.drop_column("smart_bins", "zone")
