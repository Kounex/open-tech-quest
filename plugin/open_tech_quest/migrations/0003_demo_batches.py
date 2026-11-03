"""Track explicit organizer-created demo content and original room copy."""
revision = "quest_0003"
down_revision = "quest_0002"
branch_labels = None
depends_on = None


def upgrade(op):
    from CTFd.plugins.open_tech_quest.models import QuestDemoBatch, QuestDemoChallenge
    QuestDemoBatch.__table__.create(bind=op.get_bind(), checkfirst=True)
    QuestDemoChallenge.__table__.create(bind=op.get_bind(), checkfirst=True)
