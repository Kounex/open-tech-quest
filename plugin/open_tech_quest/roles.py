"""Fresh database-backed staff authorization; native CTFd admins stay native."""
from functools import wraps
from flask import jsonify
from CTFd.models import Awards, Ratings, Submissions, Unlocks, Users
from CTFd.utils.user import get_current_user
from .models import QuestMaintainer, QuestStart


def is_maintainer(user=None):
    user = user if user is not None else get_current_user()
    return bool(user and QuestMaintainer.query.filter_by(user_id=user.id).first())


def role(user):
    if user is None:
        return "guest"
    if user.type == "admin":
        return "administrator"
    return "maintainer" if is_maintainer(user) else "participant"


def can_manage_rooms(user=None):
    user = user if user is not None else get_current_user()
    return bool(user and not user.banned and (user.type == "admin" or is_maintainer(user)))


def room_manager(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = get_current_user()
        if user is None:
            return jsonify(success=False, error="Sign in to manage rooms"), 401
        if not can_manage_rooms(user):
            return jsonify(success=False, error="Room management access required"), 403
        return fn(*args, **kwargs)
    return wrapper


def promotion_reason(user, e):
    if user.type != "user":
        return "Native administrators are managed through CTFd."
    if is_maintainer(user):
        return None
    if any(model.query.filter_by(user_id=user.id).first() for model in (Submissions, Awards, Unlocks, Ratings)):
        return "This account has competition activity and cannot become a maintainer."
    if user.team_id:
        if (QuestStart.query.filter_by(team_id=user.team_id).first()
                or any(model.query.filter_by(team_id=user.team_id).first() for model in (Submissions, Awards, Unlocks))
                or Ratings.query.join(Users, Ratings.user_id == Users.id).filter(Users.team_id == user.team_id).first()):
            return "This account's team has competition activity and cannot become staff."
        from .onboarding import settings
        if e.status != "draft" or settings().phase not in ("check_in", "closed"):
            return "Unassign this account before roster optimization to grant maintainer access."
    return None
