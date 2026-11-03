"""Authoritative quest history; native CTFd remains owner of all solves."""
from datetime import datetime
from CTFd.models import db
from sqlalchemy.dialects.mysql import DATETIME

# Preserve identical microsecond clock origins on MariaDB and SQLite.
UTCDateTime = db.DateTime().with_variant(DATETIME(fsp=6), "mysql")


class QuestEvent(db.Model):
    __tablename__ = "quest_events"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False, default="Open Tech Quest")
    status = db.Column(db.String(16), nullable=False, default="draft")
    start_at = db.Column(UTCDateTime)
    end_at = db.Column(UTCDateTime)
    paused_at = db.Column(UTCDateTime)
    rosters_release_at = db.Column(UTCDateTime)
    room_clock = db.Column(db.String(16), nullable=False, default="explicit")
    overall_clock = db.Column(db.String(16), nullable=False, default="event")
    projector = db.Column(db.JSON, nullable=False, default=lambda: {"view": "overview", "room_slug": None})
    snapshot = db.Column(db.JSON)


class QuestRoom(db.Model):
    __tablename__ = "quest_rooms"
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(32), unique=True, nullable=False)
    name = db.Column(db.String(80), nullable=False)
    subtitle = db.Column(db.String(160), nullable=False, default="")
    description = db.Column(db.Text, nullable=False, default="")
    position = db.Column(db.Integer, nullable=False)
    theme = db.Column(db.JSON, nullable=False, default=dict)


class QuestStep(db.Model):
    __tablename__ = "quest_steps"
    id = db.Column(db.Integer, primary_key=True)
    room_id = db.Column(db.Integer, db.ForeignKey("quest_rooms.id", ondelete="CASCADE"), nullable=False)
    challenge_id = db.Column(db.Integer, db.ForeignKey("challenges.id", ondelete="RESTRICT"), unique=True, nullable=False)
    position = db.Column(db.Integer, nullable=False)
    __table_args__ = (db.UniqueConstraint("room_id", "position"),)


class QuestStart(db.Model):
    __tablename__ = "quest_starts"
    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey("teams.id", ondelete="CASCADE"), nullable=False)
    room_id = db.Column(db.Integer, db.ForeignKey("quest_rooms.id", ondelete="CASCADE"), nullable=False)
    started_at = db.Column(UTCDateTime, nullable=False, default=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint("team_id", "room_id"),)


class QuestPause(db.Model):
    __tablename__ = "quest_pauses"
    id = db.Column(db.Integer, primary_key=True)
    started_at = db.Column(UTCDateTime, nullable=False)
    ended_at = db.Column(UTCDateTime)


class QuestExclusion(db.Model):
    __tablename__ = "quest_exclusions"
    team_id = db.Column(db.Integer, db.ForeignKey("teams.id", ondelete="CASCADE"), primary_key=True)
    reason = db.Column(db.Text, nullable=False)


class QuestCorrection(db.Model):
    __tablename__ = "quest_corrections"
    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey("teams.id", ondelete="CASCADE"), nullable=False)
    room_id = db.Column(db.Integer, db.ForeignKey("quest_rooms.id", ondelete="CASCADE"), nullable=False)
    adjustment_ms = db.Column(db.Integer, nullable=False)
    reason = db.Column(db.Text, nullable=False)
    created_at = db.Column(UTCDateTime, nullable=False, default=datetime.utcnow)


class QuestAudit(db.Model):
    __tablename__ = "quest_audit"
    id = db.Column(db.Integer, primary_key=True)
    actor_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"))
    action = db.Column(db.String(64), nullable=False)
    detail = db.Column(db.JSON, nullable=False)
    created_at = db.Column(UTCDateTime, nullable=False, default=datetime.utcnow)
