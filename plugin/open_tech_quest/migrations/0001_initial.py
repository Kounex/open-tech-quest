"""Initial durable quest schema. Native plugin migration runner owns revision."""
revision = "quest_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade(op):
    from CTFd.plugins.open_tech_quest.models import (
        QuestEvent, QuestRoom, QuestStep, QuestStart, QuestPause,
        QuestExclusion, QuestCorrection, QuestAudit,
    )
    for model in (QuestEvent, QuestRoom, QuestStep, QuestStart, QuestPause,
                  QuestExclusion, QuestCorrection, QuestAudit):
        model.__table__.create(bind=op.get_bind(), checkfirst=True)
