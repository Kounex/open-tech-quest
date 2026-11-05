"""Keep original solves immutable while recording valid replacement contributions."""
revision = "quest_0007"
down_revision = "quest_0006"
branch_labels = None
depends_on = None


def upgrade(op):
    from CTFd.plugins.open_tech_quest.recovery_models import QuestRecoverySolve
    QuestRecoverySolve.__table__.create(bind=op.get_bind(), checkfirst=True)

