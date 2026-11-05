"""Additional native submission history when a banned contributor loses credit."""
from CTFd.models import Submissions, db
from .models import UTCDateTime


class QuestRecoverySolve(Submissions):
    __tablename__ = "quest_recovery_solves"
    id = db.Column(db.Integer, db.ForeignKey("submissions.id", ondelete="CASCADE"), primary_key=True)
    original_solve_id = db.Column(db.Integer, db.ForeignKey("solves.id", ondelete="RESTRICT"), nullable=False)
    # Explicit acceptance time for prize calculations. Native history and its
    # timestamps remain unchanged; both fields on a recovery record use at.
    credited_at = db.Column(UTCDateTime, nullable=False)
    credited_user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    __table_args__ = (db.UniqueConstraint("original_solve_id", "credited_user_id"),)
    __mapper_args__ = {"polymorphic_identity": "quest_recovery"}

