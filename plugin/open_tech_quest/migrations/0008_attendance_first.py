"""Default new events to generated fixed names, preserving applied old naming."""
import re
import sqlalchemy as sa

revision = "quest_0008"
down_revision = "quest_0007"
branch_labels = None
depends_on = None


def upgrade(op):
    from CTFd.models import Teams
    from CTFd.plugins.open_tech_quest.models import QuestEvent, QuestOnboarding, QuestTeamName
    connection = op.get_bind()
    changed = False
    for table, name in (("quest_onboarding", "allow_team_naming"), ("quest_team_names", "auto_named")):
        columns = {column["name"] for column in sa.inspect(connection).get_columns(table)}
        if name not in columns:
            op.add_column(table, sa.Column(name, sa.Boolean(), nullable=False, server_default=sa.false()))
            changed = True
    # SQLite runs this introspective step at every startup. Only backfill when
    # upgrading old tables; a later restart must never change organizer policy.
    if not changed and connection.dialect.name == "sqlite":
        return
    state = connection.execute(sa.select(QuestOnboarding.phase).where(QuestOnboarding.id == 1)).first()
    event = connection.execute(sa.select(QuestEvent.status).where(QuestEvent.id == 1)).first()
    if not state or not event or event[0] != "draft" or state[0] == "finalized":
        return
    if state[0] == "naming":
        connection.execute(QuestOnboarding.__table__.update().where(QuestOnboarding.id == 1).values(allow_team_naming=True))
    rows = connection.execute(sa.select(Teams.id, Teams.name, QuestTeamName.team_id, QuestTeamName.name_locked,
                                         QuestTeamName.claimed_by, QuestTeamName.claimed_at)
                              .select_from(Teams).outerjoin(QuestTeamName, Teams.id == QuestTeamName.team_id)).fetchall()
    for tid, name, metadata_id, locked, actor, at in rows:
        if not locked and actor is None and at is None and re.fullmatch(r"team\s*\d+", name.strip(), re.IGNORECASE):
            if metadata_id is not None:
                connection.execute(QuestTeamName.__table__.update().where(QuestTeamName.team_id == tid).values(auto_named=True))
            elif state[0] == "naming":
                # Legacy apply created no name row until somebody claimed it.
                connection.execute(QuestTeamName.__table__.insert().values(team_id=tid, name_locked=False, auto_named=True))
