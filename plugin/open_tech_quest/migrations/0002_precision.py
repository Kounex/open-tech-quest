"""Preserve sub-second event clocks on existing MariaDB installations."""
from sqlalchemy.dialects.mysql import DATETIME
revision = "quest_0002"
down_revision = "quest_0001"
branch_labels = None
depends_on = None


def upgrade(op):
    for table, columns in (
        ("quest_events", ("start_at", "end_at", "paused_at", "rosters_release_at")),
        ("quest_starts", ("started_at",)),
        ("quest_pauses", ("started_at", "ended_at")),
        ("quest_corrections", ("created_at",)),
        ("quest_audit", ("created_at",)),
    ):
        for column in columns:
            nullable = table == "quest_events" or column == "ended_at"
            op.alter_column(table, column, existing_type=DATETIME(), type_=DATETIME(fsp=6), existing_nullable=nullable)
