"""Server-side projections of native solves and durable quest history."""
from datetime import datetime, timezone
from sqlalchemy import exists, or_
from CTFd.models import Awards, Challenges, Solves, Submissions, Teams, Unlocks, Users
from .models import (QuestEvent, QuestRoom, QuestStep, QuestStart, QuestPause,
                     QuestExclusion, QuestCorrection)
from .ranking import active_ms, prefix, assign_ranks


def now():
    return datetime.utcnow()


def iso(value):
    return value.isoformat(timespec="milliseconds") + "Z" if value else None


def parse_time(value):
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise ValueError("Timestamps must be ISO 8601 UTC strings")
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("Timestamps must specify a UTC offset")
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


def event(lock=False):
    if lock:
        # Authentication can open a MariaDB REPEATABLE READ snapshot before
        # this lock is acquired. Every mutation calls this boundary before
        # staging changes: discard that read transaction so subsequent checks
        # see the population/history committed by the preceding lock holder.
        from CTFd.models import db
        db.session.rollback()
        if db.engine.dialect.name == "sqlite":
            # SQLite ignores FOR UPDATE. Its writer transaction must start
            # before lifecycle/history reads so native mutations and demo
            # actions cannot interleave with a competition start or cleanup.
            from sqlalchemy import text
            db.session.execute(text("BEGIN IMMEDIATE"))
    query = QuestEvent.query.filter_by(id=1)
    return query.populate_existing().with_for_update().one() if lock else query.one()


def event_data(e=None):
    e = e or event()
    return {"name": e.name, "status": e.status, "start_at": iso(e.start_at),
            "end_at": iso(e.end_at), "paused_at": iso(e.paused_at),
            "rosters_release_at": iso(e.rosters_release_at), "room_clock": e.room_clock,
            "overall_clock": e.overall_clock, "server_now": iso(now()),
            "results_published": e.status == "published"}


def released(e=None):
    e = e or event()
    return e.rosters_release_at is None or now() >= e.rosters_release_at


def room_steps(room):
    return QuestStep.query.filter_by(room_id=room.id).order_by(QuestStep.position).all()


class Projection:
    """One batched read per table, regardless of team/room count.

    No participant credentials or raw submitted flags are selected. Reuse one
    instance throughout a response so every view uses the same input history.
    """
    def __init__(self, e=None):
        self.event = e or event()
        self.at = now()
        self.rooms = QuestRoom.query.order_by(QuestRoom.position, QuestRoom.id).all()
        self.steps = {}
        self.mapped = {}
        for step in QuestStep.query.order_by(QuestStep.position).all():
            self.steps.setdefault(step.room_id, []).append(step)
            self.mapped[step.challenge_id] = step.room_id
        self.challenges = {c.id: c for c in Challenges.query.filter(Challenges.id.in_(list(self.mapped))).all()}
        self.starts = {(s.team_id, s.room_id): s.started_at for s in QuestStart.query.all()}
        self.pauses = [(p.started_at, p.ended_at) for p in QuestPause.query.order_by(QuestPause.started_at).all()]
        self.corrections = {}
        for correction in QuestCorrection.query.all():
            key = correction.team_id, correction.room_id
            self.corrections[key] = self.corrections.get(key, 0) + correction.adjustment_ms
        self.solves = {}
        if not self.event.start_at:
            return
        e = self.event
        # Imported, pre-start, paused, unmapped and after-cutoff solves do not
        # qualify. Never rewrite the native source timestamps to correct time.
        query = Solves.query.with_entities(Solves.team_id, Solves.challenge_id, Solves.date).filter(Solves.team_id.isnot(None), Solves.challenge_id.in_(list(self.mapped)))
        for team_id, challenge_id, at in query.all():
            room_id = self.mapped[challenge_id]
            start = self.starts.get((team_id, room_id))
            if not start or not at or at > self.at or at < max(start, e.start_at) or (e.end_at and at > e.end_at):
                continue
            if any(left <= at < (right or self.at) for left, right in self.pauses):
                continue
            solves = self.solves.setdefault(team_id, {})
            solves[challenge_id] = min(at, solves.get(challenge_id, at))

    def progress(self, room, team_id, solves=None):
        e = self.event
        ids = [s.challenge_id for s in self.steps.get(room.id, [])]
        solves = solves if solves is not None else self.solves.get(team_id, {})
        milestones = prefix(ids, solves)
        start = self.starts.get((team_id, room.id))
        origin = e.start_at if e.room_clock == "event" else start
        milestone = max(milestones) if milestones else None
        elapsed = active_ms(origin, milestone, self.pauses)
        if elapsed is not None:
            elapsed = max(0, elapsed + self.corrections.get((team_id, room.id), 0))
        complete = bool(ids) and len(milestones) == len(ids)
        clock_to = milestone if complete else min(self.at, e.end_at or self.at)
        return {"solved": len(milestones), "total": len(ids), "started_at": iso(start),
                "elapsed_ms": active_ms(origin, clock_to, self.pauses) if start else None,
                "milestone_elapsed_ms": elapsed,
                "status": "complete" if complete else ("active" if start else "not_started")}

    def room(self, room, team_id=None, admin=False):
        e = self.event
        solves = self.solves.get(team_id, {})
        p = self.progress(room, team_id, solves)
        steps = self.steps.get(room.id, [])
        enabled = bool(p["started_at"]) and e.status in ("live", "paused", "closed", "published")
        prefix_open, data = True, []
        for step in steps:
            challenge = self.challenges.get(step.challenge_id)
            if challenge is None:
                continue
            solved = step.challenge_id in solves
            visible = challenge.state == "visible"
            state = "solved" if solved else ("available" if (admin or (enabled and prefix_open and visible)) else "locked")
            data.append({"id": step.challenge_id, "title": challenge.name, "position": step.position,
                         "state": state, "solved_at": iso(solves.get(step.challenge_id))})
            prefix_open = prefix_open and solved
        result = {"id": room.id, "slug": room.slug, "name": room.name, "subtitle": room.subtitle,
                  "description": room.description, "position": room.position, "theme": room.theme,
                  "steps": data, "progress": p}
        if admin:
            result["challenge_ids"] = [s.challenge_id for s in steps]
        return result


def solve_map(e=None):
    return Projection(e).solves


def progress(room, team_id, solves=None, e=None):
    return Projection(e).progress(room, team_id, solves)


def room_data(room, team_id=None, admin=False, e=None):
    return Projection(e).room(room, team_id, admin)


def standings(e=None, public=False):
    e = e or event()
    if e.status == "published" and e.snapshot:
        data = dict(e.snapshot)
        data["event"] = event_data(e)
        if public and not released(e):
            data["teams"], data["room_leaders"] = [], []
        return data
    projection = Projection(e)
    rooms = projection.rooms
    excluded = {x.team_id for x in QuestExclusion.query.all()}
    teams = []
    visible_teams = Teams.query.with_entities(Teams.id, Teams.name).filter_by(banned=False, hidden=False).filter(or_(
        exists().where(Users.team_id == Teams.id),
        exists().where(QuestStart.team_id == Teams.id),
        exists().where(Submissions.team_id == Teams.id),
        exists().where(Awards.team_id == Teams.id),
        exists().where(Unlocks.team_id == Teams.id),
    ))
    for team in visible_teams.all():
        if team.id in excluded:
            continue
        solves = projection.solves.get(team.id, {})
        starts = [at for (tid, rid), at in projection.starts.items() if tid == team.id]
        origin = e.start_at if e.overall_clock == "event" else min(starts, default=None)
        elapsed = active_ms(origin, max(solves.values()) if solves else None, projection.pauses)
        # Corrections adjust room awards only; overall uses the event clock.
        rp = []
        for room in rooms:
            p = projection.progress(room, team.id, solves)
            rp.append({"room_id": room.id, "solved": p["solved"], "total": p["total"],
                       "milestone_elapsed_ms": p["milestone_elapsed_ms"], "rank": None,
                       "complete": p["status"] == "complete"})
        teams.append({"id": team.id, "name": team.name, "total": len(solves), "overall_elapsed_ms": elapsed, "room_progress": rp})
    assign_ranks(teams, "total", "overall_elapsed_ms")
    leaders = []
    by_id = {t["id"]: t for t in teams}
    for room in rooms:
        rows = []
        for team in teams:
            p = next(x for x in team["room_progress"] if x["room_id"] == room.id)
            rows.append(dict(p, id=team["id"], name=team["name"]))
        assign_ranks(rows, "solved", "milestone_elapsed_ms")
        for row in rows:
            next(p for p in by_id[row["id"]]["room_progress"] if p["room_id"] == room.id)["rank"] = row["rank"]
        leaders.append({"room_id": room.id, "room_slug": room.slug,
                        "teams": [row for row in rows if row["rank"] == 1]})
    if public and not released(e):
        teams, leaders = [], []
    return {"event": event_data(e), "rooms": [{"id": r.id, "slug": r.slug, "name": r.name, "total": len(projection.steps.get(r.id, []))} for r in rooms],
            "teams": teams, "room_leaders": leaders, "as_of": iso(projection.at)}
