"""Session-authenticated participant and organizer API."""
import csv
import io
import re
import secrets
import math
from datetime import timezone
from functools import wraps
from urllib.parse import urlsplit
from flask import Blueprint, Response, jsonify, request
from werkzeug.exceptions import HTTPException
from sqlalchemy.exc import IntegrityError
from CTFd.cache import cache, clear_challenges, clear_standings, clear_user_session, clear_team_session
from CTFd.models import Challenges, Configs, Teams, Users, db
from CTFd.utils import _get_config
from CTFd.utils.dates import ctftime
from CTFd.utils.user import get_current_user, is_admin
from .models import (QuestEvent, QuestRoom, QuestStep, QuestStart, QuestPause,
                     QuestExclusion, QuestCorrection, QuestAudit)
from .service import (event, event_data, now, iso, parse_time, released,
                      room_data, room_steps, standings, Projection)

from . import demo

api = Blueprint("quest_api", __name__)


class QuestError(Exception):
    def __init__(self, message, status=400):
        self.message, self.status = message, status


def fail(message, status=400):
    raise QuestError(message, status)


def success(data=None):
    return jsonify(success=True, data=data)


@api.errorhandler(QuestError)
def error(exc):
    db.session.rollback()
    return jsonify(success=False, error=exc.message), exc.status


@api.errorhandler(HTTPException)
def http_error(exc):
    db.session.rollback()
    return jsonify(success=False, error=exc.description), exc.code


@api.errorhandler(IntegrityError)
def conflict(exc):
    db.session.rollback()
    return jsonify(success=False, error="The request conflicts with another change. Refresh and try again."), 409


def native_config(key, value):
    """Stage native lifecycle config in the same transaction as quest history."""
    row = Configs.query.filter_by(key=key).first()
    if row:
        row.value = value
    else:
        db.session.add(Configs(key=key, value=value))


def clear_native_config():
    for key in ("start", "end", "paused"):
        cache.delete_memoized(_get_config, key)


def body():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        fail("A JSON object is required")
    return data


def text(value, label, maximum=512, empty=False):
    if not isinstance(value, str) or (not empty and not value.strip()) or len(value) > maximum:
        fail(f"{label} must be {'a string' if empty else 'non-empty'} (maximum {maximum} characters)")
    return value.strip()


def integer(value, label, lower=1, upper=2147483647):
    if type(value) is not int or not lower <= value <= upper:
        fail(f"{label} must be an integer between {lower} and {upper}")
    return value


def boolean(value, label):
    if type(value) is not bool:
        fail(f"{label} must be true or false")
    return value


def timestamp(value):
    try:
        return parse_time(value)
    except (ValueError, TypeError, OverflowError):
        fail("Use an ISO 8601 timestamp with UTC offset")


def reason(data):
    return text(data.get("reason"), "Reason", 1000)


def audit(action, detail):
    user = get_current_user()
    db.session.add(QuestAudit(actor_id=user.id if user else None, action=action, detail=detail))


def admin(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not get_current_user():
            fail("Sign in as an administrator", 401)
        if not is_admin():
            fail("Administrator access required", 403)
        return fn(*args, **kwargs)
    return wrapper


def draft(e):
    if e.status != "draft":
        fail("This setting is editable only in draft", 409)


def room_by_slug(slug):
    if not isinstance(slug, str) or re.fullmatch(r"[a-z0-9-]{1,32}", slug) is None:
        fail("A valid room slug is required")
    room = QuestRoom.query.filter_by(slug=slug).first()
    if room is None:
        fail("Room not found", 404)
    return room


def viewer():
    user = get_current_user()
    if not user:
        return {"authenticated": False, "id": None, "name": None, "team_id": None, "team_name": None, "admin": False}
    show = is_admin() or released()
    team = Teams.query.get(user.team_id) if user.team_id and show else None
    return {"authenticated": True, "id": user.id, "name": user.name,
            "team_id": user.team_id if show else None, "team_name": team.name if team else None, "admin": is_admin()}


def current_rooms():
    user = get_current_user()
    projection = Projection()
    return [projection.room(room, user.team_id if user else None, is_admin()) for room in projection.rooms]


@api.route("/bootstrap")
def bootstrap():
    return success({"event": event_data(), "viewer": viewer(), "rooms": current_rooms()})


@api.route("/session")
def session_view():
    return success(viewer())


@api.route("/rooms")
def rooms():
    return success(current_rooms())


@api.route("/rooms/<slug>")
def room_view(slug):
    user = get_current_user()
    return success(room_data(room_by_slug(slug), user.team_id if user else None, is_admin()))


@api.route("/rooms/<slug>/start", methods=["POST"])
def start_room(slug):
    user = get_current_user()
    if not user:
        fail("Sign in to start a room", 401)
    if not user.team_id:
        fail("An organizer must assign you to a team", 403)
    e = event(lock=True)
    if e.status != "live" or not ctftime() or (e.end_at and now() >= e.end_at) or not released(e):
        fail("Rooms can start only while the event is live and rosters are released", 409)
    room = room_by_slug(slug)
    if not room_steps(room):
        fail("This room has no challenges yet", 409)
    start = QuestStart.query.filter_by(team_id=user.team_id, room_id=room.id).first()
    if start is None:
        db.session.add(QuestStart(team_id=user.team_id, room_id=room.id, started_at=now()))
        # Unique constraint and event row lock protect teammates and workers.
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            if not QuestStart.query.filter_by(team_id=user.team_id, room_id=room.id).first():
                raise
    else:
        db.session.commit()
    return success(room_data(room, user.team_id, is_admin()))


@api.route("/standings")
def standings_view():
    return success(standings(public=True))


@api.route("/projector")
def projector_view():
    return success(event().projector)


def team_data(team):
    return {"id": team.id, "name": team.name, "user_ids": [u.id for u in team.members],
            "excluded": QuestExclusion.query.get(team.id) is not None}


@api.route("/admin/state")
@admin
def admin_state():
    mapped = {s.challenge_id: s.room_id for s in QuestStep.query.all()}
    room_slugs = {r.id: r.slug for r in QuestRoom.query.all()}
    return success({"event": event_data(), "rooms": current_rooms(),
                    "available_challenges": [{"id": c.id, "name": c.name, "state": c.state, "room_slug": room_slugs.get(mapped.get(c.id))} for c in Challenges.query.order_by(Challenges.id).all()],
                    "teams": [team_data(t) for t in Teams.query.order_by(Teams.id).all()],
                    "participants": [{"id": u.id, "name": u.name, "email": u.email, "team_id": u.team_id} for u in Users.query.filter_by(type="user").order_by(Users.id).all()],
                    "audit": [{"id": a.id, "actor_id": a.actor_id, "action": a.action, "detail": a.detail, "created_at": iso(a.created_at)} for a in QuestAudit.query.order_by(QuestAudit.id.desc()).limit(200).all()],
                    "standings": standings(), "projector": event().projector, "demo": demo.status(event())})


@api.route("/admin/event", methods=["PATCH"])
@admin
def configure_event():
    data, e = body(), event(lock=True)
    allowed = {"name", "start_at", "end_at", "rosters_release_at", "room_clock", "overall_clock"}
    if set(data) - allowed:
        fail("Unknown event setting")
    if any(k in data for k in ("start_at", "end_at", "room_clock", "overall_clock")):
        draft(e)
    if "name" in data:
        e.name = text(data["name"], "Event name", 128)
    for key in ("start_at", "end_at", "rosters_release_at"):
        if key in data:
            setattr(e, key, timestamp(data[key]))
    for key, allowed_values in (("room_clock", ("explicit", "event")), ("overall_clock", ("event", "team"))):
        if key in data:
            if data[key] not in allowed_values:
                fail(f"Invalid {key}")
            setattr(e, key, data[key])
    if e.end_at and (not e.start_at or e.end_at <= e.start_at):
        fail("Event end must be after its configured start")
    audit("event.configure", data)
    db.session.commit()
    return success(event_data(e))


@api.route("/admin/event/action", methods=["POST"])
@admin
def event_action():
    data, e = body(), event(lock=True)
    action, at = data.get("action"), now()
    if action == "start":
        draft(e)
        if demo.active_batch():
            fail("Remove demo content before starting the competition; organizers can preview it while in draft.", 409)
        if QuestStep.query.first() is None:
            fail("Configure at least one room challenge before starting the event", 409)
        if e.start_at and e.start_at > at:
            fail("The configured start is still in the future", 409)
        if e.end_at and e.end_at <= at:
            fail("The configured end has already passed", 409)
        e.start_at = e.start_at or at
        e.status = "live"
        native_config("start", int(e.start_at.replace(tzinfo=timezone.utc).timestamp()))
        native_config("end", math.ceil(e.end_at.replace(tzinfo=timezone.utc).timestamp()) if e.end_at else None)
        native_config("paused", False)
    elif action == "pause":
        if e.status != "live":
            fail("Only a live event can pause", 409)
        e.status, e.paused_at = "paused", at
        db.session.add(QuestPause(started_at=at))
        native_config("paused", True)
    elif action == "resume":
        if e.status != "paused":
            fail("Only a paused event can resume", 409)
        if e.end_at and at >= e.end_at:
            fail("The configured cutoff has passed; close the event", 409)
        for pause in QuestPause.query.filter_by(ended_at=None).all():
            pause.ended_at = at
        e.status, e.paused_at = "live", None
        native_config("paused", False)
    elif action == "close":
        if e.status not in ("live", "paused"):
            fail("Only live or paused events can close", 409)
        cutoff = min(at, e.end_at) if e.end_at else at
        for pause in QuestPause.query.filter_by(ended_at=None).all():
            pause.ended_at = cutoff
        e.status, e.end_at, e.paused_at = "closed", cutoff, None
        native_config("end", int(cutoff.replace(tzinfo=timezone.utc).timestamp()))
        native_config("paused", True)
    elif action == "publish":
        if e.status != "closed":
            fail("Close the event before publishing", 409)
        e.snapshot = standings(e)
        e.status = "published"
    elif action == "unpublish":
        if e.status != "published":
            fail("Results are not published", 409)
        reason(data)
        e.status, e.snapshot = "closed", None
    elif action == "reopen":
        if e.status != "closed":
            fail("Unpublish results and close before reopening", 409)
        reason(data)
        # The closed interval is excluded when organizers resume play.
        db.session.add(QuestPause(started_at=e.end_at))
        e.status, e.paused_at, e.end_at = "paused", e.end_at, None
        native_config("end", None)
        native_config("paused", True)
    else:
        fail("Unknown event action")
    audit("event." + action, {"reason": data.get("reason"), "at": iso(at)})
    db.session.commit()
    clear_native_config()
    return success(event_data(e))


def asset_url(value):
    if value is None or value == "":
        return None
    value = text(value, "Asset URL", 2048)
    if any(ord(c) < 33 for c in value) or "\\" in value:
        fail("Asset URLs may not contain whitespace or backslashes")
    # Local curated static assets only: no remote tracking, script schemes or
    # access-controlled challenge files rendered as presentation assets.
    parsed = urlsplit(value)
    if parsed.scheme or parsed.netloc or parsed.query or parsed.fragment:
        fail("Use a local static asset URL")
    if not value.startswith("/plugins/open_tech_quest/assets/") or any(part in ("..", ".") for part in value.split("/")) or "%" in value:
        fail("Use an asset under /plugins/open_tech_quest/assets/")
    return value


@api.route("/admin/rooms/<slug>", methods=["PATCH"])
@admin
def configure_room(slug):
    data, e = body(), event(lock=True)
    room = room_by_slug(slug)
    if set(data) - {"name", "subtitle", "description", "theme", "challenge_ids", "position"}:
        fail("Unknown room setting")
    for field, maximum in (("name", 80), ("subtitle", 160), ("description", 10000)):
        if field in data:
            setattr(room, field, text(data[field], field, maximum, empty=field != "name"))
    if "position" in data:
        draft(e)
        room.position = integer(data["position"], "Position", 0, 100)
    if "theme" in data:
        theme = data["theme"]
        if not isinstance(theme, dict) or set(theme) - {"accent", "logo_url", "hero_url", "layout"}:
            fail("Invalid room theme")
        result = dict(room.theme)
        for key, value in theme.items():
            if key.endswith("_url"):
                result[key] = asset_url(value)
            elif key == "accent":
                if not isinstance(value, str) or re.fullmatch(r"#[0-9a-fA-F]{6}", value) is None:
                    fail("Accent must be a six-digit hex color")
                result[key] = value
            else:
                if value not in ("openshift", "ansible", "rhel", "security", "ai"):
                    fail("Unknown room layout")
                result[key] = value
        room.theme = result
    if "challenge_ids" in data:
        draft(e)
        ids = data["challenge_ids"]
        if not isinstance(ids, list) or any(type(x) is not int or x < 1 for x in ids) or len(ids) != len(set(ids)):
            fail("challenge_ids must be a list of unique challenge IDs")
        challenges = {c.id: c for c in Challenges.query.filter(Challenges.id.in_(ids)).all()}
        if set(challenges) != set(ids):
            fail("One or more challenges do not exist")
        if QuestStep.query.filter(QuestStep.room_id != room.id, QuestStep.challenge_id.in_(ids)).first():
            fail("A challenge belongs to another room", 409)
        previous = room_steps(room)
        for step in previous:
            challenge = Challenges.query.get(step.challenge_id)
            if challenge:
                challenge.requirements, challenge.next_id = None, None
            db.session.delete(step)
        db.session.flush()
        for position, challenge_id in enumerate(ids):
            challenge = challenges[challenge_id]
            challenge.requirements = {"prerequisites": ids[:position], "anonymize": False}
            challenge.next_id = ids[position + 1] if position + 1 < len(ids) else None
            challenge.position = position
            db.session.add(QuestStep(room_id=room.id, challenge_id=challenge_id, position=position))
    audit("room.configure", {"room_slug": slug, "changes": data})
    db.session.commit()
    clear_challenges()
    return success(room_data(room, admin=True))


def eligible_users():
    return Users.query.filter_by(type="user", banned=False, team_id=None).order_by(Users.id).all()


def unique_name(name, excluding=None):
    name = text(name, "Team name", 128)
    if any(t.id != excluding and t.name.casefold() == name.casefold() for t in Teams.query.all()):
        fail("Team names must be unique", 409)
    return name


def user_ids(data):
    ids = data.get("user_ids")
    if not isinstance(ids, list) or any(type(i) is not int or i < 1 for i in ids) or len(ids) != len(set(ids)):
        fail("user_ids must contain unique user IDs")
    return ids


@api.route("/admin/teams/allocate", methods=["POST"])
@admin
def allocate():
    data, e = body(), event(lock=True)
    draft(e)
    preview = boolean(data.get("preview", True), "preview")
    users = eligible_users()
    if preview:
        size = integer(data.get("team_size", 4), "Team size", 1, 50)
        if not users:
            return success({"groups": []})
        secrets.SystemRandom().shuffle(users)
        count = (len(users) + size - 1) // size
        groups, names = [], {t.name.casefold() for t in Teams.query.all()}
        next_number = 1
        for index in range(count):
            while f"Team {next_number:02}".casefold() in names:
                next_number += 1
            name = f"Team {next_number:02}"
            names.add(name.casefold())
            groups.append({"name": name, "user_ids": [u.id for u in users[index::count]]})
        return success({"groups": groups})
    groups = data.get("groups")
    if not isinstance(groups, list) or not groups:
        fail("Preview allocation and supply its groups")
    ids, names, validated = [], set(), []
    for group in groups:
        if not isinstance(group, dict):
            fail("Each group must contain name and user_ids")
        name, members = unique_name(group.get("name")), user_ids(group)
        if not members or len(members) > 50 or name.casefold() in names:
            fail("Groups require unique names and between 1 and 50 members")
        names.add(name.casefold())
        ids.extend(members)
        validated.append((name, members))
    if len(ids) != len(set(ids)) or set(ids) != {u.id for u in users}:
        fail("Eligible participants changed. Preview a complete allocation again.", 409)
    users_by_id = {u.id: u for u in users}
    for name, members in validated:
        team = Teams(name=name, captain_id=members[0])
        db.session.add(team)
        db.session.flush()
        for uid in members:
            users_by_id[uid].team_id = team.id
    audit("teams.allocate", {"groups": groups})
    db.session.commit()
    for uid in ids:
        clear_user_session(uid)
    clear_standings()
    return success({"groups": groups})


@api.route("/admin/teams/<int:team_id>", methods=["PATCH"])
@admin
def configure_team(team_id):
    data, e = body(), event(lock=True)
    team = Teams.query.get(team_id)
    if team is None:
        fail("Team not found", 404)
    if set(data) - {"name", "excluded", "reason", "user_ids"}:
        fail("Unknown team setting")
    if e.status == "published":
        fail("Unpublish results before changing teams", 409)
    if "name" in data:
        name = text(data["name"], "Team name", 128)
        if name != team.name:
            draft(e)
            team.name = unique_name(name, team.id)
    changed_users = set()
    if "user_ids" in data:
        draft(e)
        ids = user_ids(data)
        users = Users.query.filter(Users.id.in_(ids)).all()
        if len(users) != len(ids) or any(u.type != "user" or u.banned or (u.team_id and u.team_id != team_id) for u in users):
            fail("Members must be eligible unassigned participants or current team members")
        for user in team.members:
            changed_users.add(user.id)
            user.team_id = None
        for user in users:
            changed_users.add(user.id)
            user.team_id = team.id
        team.captain_id = ids[0] if ids else None
    if "excluded" in data:
        excluded = boolean(data["excluded"], "excluded")
        row = QuestExclusion.query.get(team.id)
        if excluded != (row is not None):
            explanation = reason(data)
            if excluded:
                db.session.add(QuestExclusion(team_id=team.id, reason=explanation))
            else:
                db.session.delete(row)
    audit("team.configure", {"team_id": team.id, "changes": data})
    db.session.commit()
    for uid in changed_users:
        clear_user_session(uid)
    clear_standings()
    clear_team_session(team_id)
    db.session.expire_all()
    return success(team_data(Teams.query.get(team_id)))


@api.route("/admin/projector", methods=["PATCH"])
@admin
def configure_projector():
    data, e = body(), event(lock=True)
    if data.get("view") not in ("overview", "room", "overall", "awards"):
        fail("Unknown projector view")
    slug = data.get("room_slug")
    if data["view"] == "room":
        room_by_slug(slug)
    elif slug is not None:
        room_by_slug(slug)
    e.projector = {"view": data["view"], "room_slug": slug}
    audit("projector.configure", e.projector)
    db.session.commit()
    return success(e.projector)


@api.route("/admin/corrections", methods=["POST"])
@admin
def correction():
    data, e = body(), event(lock=True)
    if e.status not in ("live", "paused", "closed"):
        fail("Corrections require a started, unpublished event", 409)
    team_id = integer(data.get("team_id"), "Team ID")
    if Teams.query.get(team_id) is None:
        fail("Team not found", 404)
    room = room_by_slug(data.get("room_slug"))
    adjustment = integer(data.get("adjustment_ms"), "Adjustment", -86400000, 86400000)
    explanation = reason(data)
    cumulative = sum(c.adjustment_ms for c in QuestCorrection.query.filter_by(team_id=team_id, room_id=room.id).all()) + adjustment
    if abs(cumulative) > 86400000:
        fail("Cumulative room adjustment cannot exceed 24 hours")
    db.session.add(QuestCorrection(team_id=team_id, room_id=room.id, adjustment_ms=adjustment, reason=explanation))
    audit("ranking.correct", {"team_id": team_id, "room_slug": room.slug, "adjustment_ms": adjustment, "reason": explanation})
    db.session.commit()
    return success({"standings": standings()})


@api.route("/admin/export")
@admin
def export():
    data = standings()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(("competition", "team_id", "team_name", "rank", "solved", "total", "active_elapsed_ms"))
    def safe_name(name):
        return "'" + name if name.startswith(("=", "+", "-", "@", "\t", "\r")) else name
    for team in data["teams"]:
        writer.writerow(("overall", team["id"], safe_name(team["name"]), team["rank"], team["total"], sum(r["total"] for r in data["rooms"]), team["overall_elapsed_ms"]))
        for p in team["room_progress"]:
            room = next(r for r in data["rooms"] if r["id"] == p["room_id"])
            writer.writerow((room["slug"], team["id"], safe_name(team["name"]), p["rank"], p["solved"], p["total"], p["milestone_elapsed_ms"]))
    return Response(output.getvalue(), mimetype="text/csv", headers={"Content-Disposition": "attachment; filename=quest-standings.csv"})


@api.route("/admin/demo", methods=["POST"])
@admin
def manage_demo():
    data, e = body(), event(lock=True)
    action = data.get("action")
    if action not in ("load", "unload"):
        fail("Choose demo action load or unload")
    try:
        batch = demo.load(e) if action == "load" else demo.unload(e)
    except demo.DemoConflict as exc:
        fail(str(exc), 409)
    audit("demo." + action, {"batch_id": batch.id, "challenge_ids": batch.challenge_ids})
    db.session.commit()
    clear_challenges()
    clear_standings()
    return success(demo.status(e))
