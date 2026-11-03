"""Add attendance and one-time team naming without changing event history."""
from datetime import datetime
from sqlalchemy import select
revision = "quest_0004"
down_revision = "quest_0003"
branch_labels = None
depends_on = None


def upgrade(op):
    from CTFd.models import Teams
    from CTFd.plugins.open_tech_quest.models import (QuestEvent, QuestOnboarding,
                                                   QuestReadiness, QuestTeamName)
    connection = op.get_bind()
    for model in (QuestOnboarding, QuestReadiness, QuestTeamName):
        model.__table__.create(bind=connection, checkfirst=True)
    if connection.execute(select(QuestOnboarding.id).where(QuestOnboarding.id == 1)).first():
        return
    row = connection.execute(select(QuestEvent.status).where(QuestEvent.id == 1)).first()
    legacy = bool(row and row[0] != "draft")
    connection.execute(QuestOnboarding.__table__.insert().values(
        id=1, phase="finalized" if legacy else "check_in", team_size=5,
        grandfathered=legacy, finalized_at=datetime.utcnow() if legacy else None))
    if legacy:
        for team_id, in connection.execute(select(Teams.id)).fetchall():
            connection.execute(QuestTeamName.__table__.insert().values(team_id=team_id, name_locked=True))
