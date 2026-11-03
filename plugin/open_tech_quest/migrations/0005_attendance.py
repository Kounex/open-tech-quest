"""Add a separately controlled attendance window, closed on upgrade."""
import sqlalchemy as sa
from CTFd.plugins.open_tech_quest.models import UTCDateTime

revision = "quest_0005"
down_revision = "quest_0004"
branch_labels = None
depends_on = None


def upgrade(op):
    # quest_0004 creates the current ORM table on fresh installs. Introspect
    # actual columns so fresh and old-table upgrades use this same revision.
    existing = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("quest_onboarding")}
    additions = (
        sa.Column("attendance_open", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("attendance_generation", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("attendance_opened_at", UTCDateTime, nullable=True),
        sa.Column("attendance_closed_at", UTCDateTime, nullable=True),
    )
    for column in additions:
        if column.name not in existing:
            op.add_column("quest_onboarding", column)
