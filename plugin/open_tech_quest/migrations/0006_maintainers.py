"""Persist explicit room-maintainer grants without changing native user types."""
revision = "quest_0006"
down_revision = "quest_0005"
branch_labels = None
depends_on = None


def upgrade(op):
    from CTFd.plugins.open_tech_quest.models import QuestMaintainer
    QuestMaintainer.__table__.create(bind=op.get_bind(), checkfirst=True)
