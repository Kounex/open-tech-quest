"""Guard native content paths as well as the SPA; known URLs grant no access."""
import re
from flask import jsonify, redirect, request
from CTFd.models import Challenges, Files, Hints, Solutions, Submissions, Teams, Users
from CTFd.utils.dates import ctftime
from CTFd.utils.user import get_current_user, is_admin
from CTFd.utils.security.signing import unserialize, BadSignature, BadTimeSignature, SignatureExpired
from .models import QuestStep, QuestStart
from .service import event, now, released, solve_map


def denied(message, status=403):
    return jsonify(success=False, error=message), status


def install_guards(app):
    @app.before_request
    def quest_access():
        path = request.path.rstrip("/") or "/"
        write = request.method not in ("GET", "HEAD", "OPTIONS")
        administrator = is_admin()
        data = request.get_json(silent=True) if request.is_json else request.form
        data = data if isinstance(data, dict) or hasattr(data, "get") else {}
        if path == "/":
            return redirect("/quest")
        if path == "/team":
            user = get_current_user()
            if user and not user.team_id:
                return redirect("/quest")
        if path == "/setup" and request.method == "POST":
            # The plugin is team-based even when the upstream wizard defaults
            # its account-mode radio button to individual users.
            form = request.form.copy()
            form["user_mode"] = "teams"
            request.form = form
        # Topology remains managed in one place, even when native challenge
        # authoring is used for the actual descriptions, files and flags.
        match = re.fullmatch(r"/api/v1/challenges/(\d+)", path)
        if administrator:
            if write and path.startswith("/api/v1/configs"):
                controlled = {"user_mode", "start", "end", "paused"}
                key = path.rsplit("/", 1)[-1]
                if key in controlled or set(data).intersection(controlled) or data.get("key") in controlled:
                    return denied("Manage team mode and event clocks through Open Tech Quest", 409)
            if match and write:
                mapped = QuestStep.query.filter_by(challenge_id=int(match[1])).first()
                if mapped:
                    event(lock=True)
                    challenge = Challenges.query.get(int(match[1]))
                    changed = "requirements" in data and data["requirements"] != challenge.requirements
                    # Native edit forms serialize numeric values as strings and
                    # always send position, even when only description changed.
                    changed = changed or any(k in data and str(data[k]) != str(getattr(challenge, k)) for k in ("next_id", "position"))
                    if request.method == "DELETE" or changed:
                        return denied("Manage mapped challenge topology through Open Tech Quest room settings", 409)
            membership_write = path.startswith("/api/v1/teams") or (
                path.startswith("/api/v1/users/") and ("team_id" in data or request.method == "DELETE")
            )
            if write and membership_write and event(lock=True).status != "draft":
                return denied("Team membership and identity are locked after draft", 409)
            if write and path.startswith("/api/v1/submissions") and event(lock=True).status != "draft":
                submission_match = re.fullmatch(r"/api/v1/submissions/(\d+)", path)
                submission = Submissions.query.get(int(submission_match[1])) if submission_match else None
                challenge_id = submission.challenge_id if submission else data.get("challenge_id")
                if str(challenge_id).isdigit() and QuestStep.query.filter_by(challenge_id=int(challenge_id)).first():
                    return denied("Native event submissions are preserved. Use audited quest corrections.", 409)
            return
        if path in ("/", "/challenges", "/scoreboard"):
            return redirect("/quest/standings" if path == "/scoreboard" else "/quest")
        # Native self-service must never undo organizer allocation. Session
        # and password management still use CTFd's own supported routes.
        if path in ("/teams/new", "/teams/join", "/teams/invite") or (write and path.startswith("/api/v1/teams")):
            return denied("Team allocation is managed by the organizers")
        if path.startswith("/api/v1/scoreboard") or path.startswith("/api/v1/statistics"):
            return denied("Use the Open Tech Quest standings")
        if (path in ("/teams", "/team", "/users") or path.startswith(("/teams/", "/users/", "/api/v1/teams", "/api/v1/users"))) and not released():
            # Permit personal settings reads/updates, but keep allocation private.
            if path not in ("/api/v1/users/me",):
                return denied("Team rosters have not been released")
        if path == "/api/v1/challenges":
            return denied("Use the Open Tech Quest room board")
        challenge_id = None
        token_user = None
        attempt = path == "/api/v1/challenges/attempt"
        if attempt:
            challenge_id = data.get("challenge_id")
        elif path.startswith("/api/v1/challenges/"):
            match = re.match(r"/api/v1/challenges/(\d+)(?:/|$)", path)
            if match:
                challenge_id = int(match[1])
        elif path.startswith("/api/v1/hints/"):
            match = re.fullmatch(r"/api/v1/hints/(\d+)", path)
            hint = Hints.query.get(int(match[1])) if match else None
            challenge_id = hint.challenge_id if hint else None
        elif path.startswith("/api/v1/solutions/"):
            match = re.fullmatch(r"/api/v1/solutions/(\d+)", path)
            solution = Solutions.query.get(int(match[1])) if match else None
            challenge_id = solution.challenge_id if solution else None
        elif path == "/api/v1/unlocks" and write:
            model = {"hints": Hints, "solutions": Solutions}.get(data.get("type"))
            target = model.query.get(data.get("target")) if model and str(data.get("target", "")).isdigit() else None
            challenge_id = target.challenge_id if target else None
        elif path.startswith("/files/"):
            file = Files.query.filter_by(location=path[len("/files/"):]).first()
            challenge_id = getattr(file, "challenge_id", None)
            if file and file.type == "solution":
                solution = Solutions.query.get(file.solution_id)
                challenge_id = solution.challenge_id if solution else None
            if file and challenge_id and request.args.get("token"):
                try:
                    claims = unserialize(request.args["token"], max_age=3600)
                except (BadSignature, BadTimeSignature, SignatureExpired):
                    return denied("The download token is invalid or expired")
                if not isinstance(claims, dict):
                    return denied("Invalid download token")
                token_user = Users.query.get(claims.get("user_id")) if type(claims.get("user_id")) is int else None
                token_team = Teams.query.get(claims.get("team_id")) if type(claims.get("team_id")) is int else None
                if (not token_user or token_user.banned or not token_team or token_team.banned
                        or token_user.team_id != token_team.id or claims.get("file_id") != file.id):
                    return denied("The download token does not match this file and active team")
                current = get_current_user()
                if current and current.id != token_user.id:
                    return denied("The download token belongs to another account")
        if challenge_id is None:
            return
        try:
            challenge_id = int(challenge_id)
        except (ValueError, TypeError, OverflowError):
            return denied("Invalid challenge ID", 400)
        step = QuestStep.query.filter_by(challenge_id=challenge_id).first()
        if step is None:
            # Unmapped challenges stay in native authoring, never in the event.
            return denied("This challenge is not part of Open Tech Quest", 404)
        user = token_user or get_current_user()
        if user is None:
            return denied("Sign in to open a challenge", 401)
        if not user.team_id:
            return denied("An organizer must assign you to a team")
        e = event(lock=attempt)
        if e.status == "draft" or not e.start_at or now() < e.start_at or not released(e):
            return denied("The event has not opened")
        if attempt and e.status == "paused":
            message = "The event is paused. Your answer was not submitted; try again when organizers resume."
            return jsonify(success=False, error=message, data={"status": "paused", "message": message}), 409
        if attempt and (e.status != "live" or not ctftime() or (e.end_at and now() > e.end_at)):
            return denied("Submissions are accepted only while the event is live", 409)
        start = QuestStart.query.filter_by(team_id=user.team_id, room_id=step.room_id).first()
        if start is None:
            return denied("Start the room before opening challenge content")
        challenge = Challenges.query.get(challenge_id)
        if not challenge or challenge.state != "visible":
            return denied("This challenge is not available", 404)
        prerequisites = {s.challenge_id for s in QuestStep.query.filter(QuestStep.room_id == step.room_id, QuestStep.position < step.position).all()}
        solved = set(solve_map(e).get(user.team_id, {}))
        if not solved >= prerequisites:
            return denied("Solve the previous steps before opening this challenge")
