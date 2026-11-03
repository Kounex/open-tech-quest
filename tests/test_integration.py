"""Real Flask/SQLAlchemy/native CTFd integration; disposable DB only.

Run inside pinned CTFd image with plugin installed:
python -m unittest discover -s /opt/quest-tests -p 'test_*.py' -v
DATABASE_URL may select a dedicated MariaDB database ending in `_test`.
No pytest or other test dependencies are required.
"""
import os
import tempfile
import time
import threading
from pathlib import Path
from sqlalchemy import event as sqlalchemy_event
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from unittest.mock import patch

from CTFd import create_app
from CTFd.config import TestingConfig
from CTFd.cache import cache
from CTFd.models import ChallengeFiles, Challenges, Configs, Flags, Hints, Solves, Teams, Users, db
from CTFd.utils import get_config, set_config
from CTFd.plugins.open_tech_quest.models import (QuestEvent, QuestRoom, QuestStep,
    QuestStart, QuestPause, QuestAudit)
from CTFd.plugins.open_tech_quest.service import standings

PREFIX = "/api/v1/quest"


class QuestIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="quest-tests-")
        database = os.environ.get("DATABASE_URL", "sqlite:///" + cls.temp.name + "/test.db")
        if not database.startswith("sqlite:") and not database.rsplit("/", 1)[-1].split("?", 1)[0].endswith("_test"):
            raise RuntimeError("Integration tests require a disposable database ending in _test")
        class Config(TestingConfig):
            SAFE_MODE = False
            SQLALCHEMY_DATABASE_URI = database
            SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}
            UPLOAD_FOLDER = cls.temp.name + "/uploads"
            LOG_FOLDER = cls.temp.name + "/logs"
        cls.app = create_app(Config)
        # Validate real first-install behavior before test fixtures add data.
        with cls.app.app_context():
            assert get_config("user_mode") == "teams"
            assert QuestEvent.query.one().status == "draft"
            assert QuestRoom.query.count() == 5
            assert Challenges.query.count() == Solves.query.count() == 0

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            db.session.remove()
            with db.engine.connect() as connection:
                dialect = db.engine.dialect.name
                connection.execute("PRAGMA foreign_keys=OFF" if dialect == "sqlite" else "SET FOREIGN_KEY_CHECKS=0")
                revisions = [{"key": row.key, "value": row.value} for row in connection.execute(Configs.__table__.select()).fetchall() if row.key.endswith("_alembic_version")]
                transaction = connection.begin()
                for table in reversed(db.metadata.sorted_tables):
                    connection.execute(table.delete())
                if revisions:
                    connection.execute(Configs.__table__.insert(), revisions)
                transaction.commit()
                connection.execute("PRAGMA foreign_keys=ON" if dialect == "sqlite" else "SET FOREIGN_KEY_CHECKS=1")
            db.engine.dispose()
        cls.temp.cleanup()

    def setUp(self):
        with self.app.app_context():
            db.session.remove()
            with db.engine.connect() as connection:
                dialect = db.engine.dialect.name
                connection.execute("PRAGMA foreign_keys=OFF" if dialect == "sqlite" else "SET FOREIGN_KEY_CHECKS=0")
                revisions = [{"key": row.key, "value": row.value} for row in connection.execute(Configs.__table__.select()).fetchall() if row.key.endswith("_alembic_version")]
                transaction = connection.begin()
                for table in reversed(db.metadata.sorted_tables):
                    connection.execute(table.delete())
                if revisions:
                    connection.execute(Configs.__table__.insert(), revisions)
                transaction.commit()
                connection.execute("PRAGMA foreign_keys=ON" if dialect == "sqlite" else "SET FOREIGN_KEY_CHECKS=1")
            cache.clear()
            for key, value in (("setup", True), ("ctf_name", "Quest test"), ("user_mode", "teams"), ("challenge_visibility", "public"), ("account_visibility", "public"), ("verify_emails", False), ("paused", False), ("start", None), ("end", None)):
                set_config(key, value)
            db.session.add(QuestEvent(id=1))
            for pos, slug in enumerate(("openshift", "ansible", "rhel", "security", "ai")):
                db.session.add(QuestRoom(slug=slug, name=slug.title(), position=pos, theme={"layout": slug}))
            self.team = Teams(name="Red team")
            self.other_team = Teams(name="Blue team")
            db.session.add_all([self.team, self.other_team])
            db.session.flush()
            db.session.add_all([Users(id=1, name="Organizer", email="admin@example.test", type="admin", password="test-only", verified=True), Users(id=2, name="Alice", email="alice@example.test", password="test-only", team_id=self.team.id, verified=True), Users(id=3, name="Bob", email="bob@example.test", password="test-only", team_id=self.team.id, verified=True), Users(id=4, name="Carol", email="carol@example.test", password="test-only", team_id=self.other_team.id, verified=True)])
            self.team_id, self.other_id = self.team.id, self.other_team.id
            for i in range(1, 4):
                c = Challenges(id=i, name=f"Challenge {i}", description=f"Private instructions {i}", value=100, category="Quest", type="standard", state="visible")
                db.session.add(c)
                db.session.flush()
                db.session.add(Flags(challenge_id=i, type="static", content=f"fixture-answer-{i}", data=""))
            db.session.add(ChallengeFiles(challenge_id=2, location="known-hash/private.txt"))
            db.session.add(Hints(id=1, challenge_id=2, title="Help", content="Private hint", cost=0))
            db.session.commit()
        self.admin = self.client(1)
        self.alice, self.bob, self.carol = self.client(2), self.client(3), self.client(4)
        self.guest = self.app.test_client()
        self.configure([1, 2])

    def client(self, uid):
        client = self.app.test_client()
        with client.session_transaction() as session:
            session["id"] = uid
            session["nonce"] = "quest-test-csrf"
        return client

    def post(self, client, path, data, method="POST"):
        return client.open(path, method=method, json=data, headers={"CSRF-Token": "quest-test-csrf"})

    def configure(self, ids):
        response = self.post(self.admin, PREFIX + "/admin/rooms/openshift", {"challenge_ids": ids}, "PATCH")
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))

    def action(self, action, **kwargs):
        response = self.post(self.admin, PREFIX + "/admin/event/action", dict(action=action, **kwargs))
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        return response.json["data"]

    def start(self, client=None):
        response = self.post(client or self.alice, PREFIX + "/rooms/openshift/start", {})
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        return response.json["data"]

    def solve(self, client, challenge_id):
        return self.post(client, "/api/v1/challenges/attempt", {"challenge_id": challenge_id, "submission": f"fixture-answer-{challenge_id}"})

    def test_safe_guest_lobby_shell_and_admin_authorization(self):
        response = self.guest.get(PREFIX + "/bootstrap")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["data"]["event"]["status"], "draft")
        serialized = response.get_data(as_text=True)
        self.assertNotIn("Private instructions", serialized)
        self.assertNotIn("fixture-answer", serialized)
        self.assertEqual(self.guest.get(PREFIX + "/admin/state").status_code, 401)
        self.assertEqual(self.alice.get(PREFIX + "/admin/state").status_code, 403)
        self.assertEqual(self.guest.get("/").status_code, 302)
        self.assertEqual(self.admin.get("/").location, "/quest")
        shell = self.alice.get("/quest/rooms/openshift").get_data(as_text=True)
        self.assertIn("window.QUEST_INIT", shell)
        self.assertIn("app/quest.js", shell)
        self.assertNotIn("alice@example", shell)
        self.assertNotIn("test-only", shell)

    def test_early_content_and_known_file_and_hint_url_guards(self):
        for client in (self.alice, self.guest):
            for path in ("/api/v1/challenges/1", "/api/v1/challenges/2/files", "/api/v1/hints/1", "/files/known-hash/private.txt"):
                self.assertIn(client.get(path).status_code, (401, 403))
        self.action("start")
        self.assertEqual(self.alice.get("/api/v1/challenges/1").status_code, 403)
        self.start()
        self.assertEqual(self.alice.get("/api/v1/challenges/1").status_code, 200)
        for path in ("/api/v1/challenges/2", "/api/v1/hints/1", "/files/known-hash/private.txt"):
            self.assertEqual(self.alice.get(path).status_code, 403)
        self.assertEqual(self.post(self.alice, "/api/v1/unlocks", {"type": "hints", "target": 1}).status_code, 403)
        self.assertEqual(self.carol.get("/api/v1/challenges/1").status_code, 403)

    def test_native_requirements_sequence_shared_solve_and_duplicates(self):
        with self.app.app_context():
            self.assertEqual(Challenges.query.get(2).requirements["prerequisites"], [1])
            self.assertEqual(Challenges.query.get(1).next_id, 2)
        self.action("start")
        self.start()
        self.assertEqual(self.solve(self.alice, 2).status_code, 403)
        result = self.solve(self.alice, 1)
        self.assertEqual(result.status_code, 200, result.get_data(as_text=True))
        self.assertEqual(result.json["data"]["status"], "correct")
        duplicate = self.solve(self.bob, 1)
        self.assertEqual(duplicate.json["data"]["status"], "already_solved")
        self.assertEqual(self.bob.get("/api/v1/challenges/2").status_code, 200)
        self.assertEqual(self.bob.get("/api/v1/hints/1").status_code, 200)
        self.assertEqual(self.solve(self.bob, 2).json["data"]["status"], "correct")
        room = self.bob.get(PREFIX + "/rooms/openshift").json["data"]
        self.assertEqual(room["progress"]["status"], "complete")
        self.assertEqual(room["progress"]["solved"], 2)
        self.assertEqual(self.carol.get(PREFIX + "/rooms/openshift").json["data"]["progress"]["solved"], 0)
        with self.app.app_context():
            self.assertEqual(Solves.query.filter_by(team_id=self.team_id).count(), 2)

    def test_idempotent_concurrent_teammate_starts(self):
        self.action("start")
        def start_user(uid):
            client = self.client(uid)
            return self.post(client, PREFIX + "/rooms/openshift/start", {})
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(start_user, (2, 3)))
        self.assertEqual([r.status_code for r in responses], [200, 200])
        self.assertEqual(responses[0].json["data"]["progress"]["started_at"], responses[1].json["data"]["progress"]["started_at"])
        with self.app.app_context():
            self.assertEqual(QuestStart.query.count(), 1)

    def test_partial_room_distinct_total_ties_and_last_milestone_time(self):
        self.action("start")
        self.start(self.alice)
        self.start(self.carol)
        with self.app.app_context():
            at = datetime.utcnow() - timedelta(seconds=100)
            QuestEvent.query.get(1).start_at = at
            for start in QuestStart.query.all():
                start.started_at = at
            # Red has out-of-order step 2 only: total 1, room prefix 0.
            db.session.add(Solves(challenge_id=2, user_id=2, team_id=self.team_id, date=at + timedelta(seconds=20)))
            db.session.add(Solves(challenge_id=1, user_id=4, team_id=self.other_id, date=at + timedelta(seconds=20)))
            db.session.commit()
            result = standings()
            self.assertEqual([t["rank"] for t in result["teams"]], [1, 1])
            red = next(t for t in result["teams"] if t["id"] == self.team_id)
            blue = next(t for t in result["teams"] if t["id"] == self.other_id)
            self.assertIsNone(red["room_progress"][0]["rank"])
            self.assertEqual(blue["room_progress"][0]["milestone_elapsed_ms"], 20000)
            self.assertEqual(blue["overall_elapsed_ms"], 20000)
            self.assertEqual(blue["room_progress"][0]["rank"], 1)

    def test_pause_cutoff_snapshot_and_explicit_unpublish(self):
        self.action("start")
        self.start()
        self.action("pause")
        paused = self.solve(self.alice, 1)
        self.assertEqual(paused.status_code, 409)
        self.assertEqual(paused.json["data"]["status"], "paused")
        self.assertIn("not submitted", paused.json["error"])
        with self.app.app_context():
            self.assertEqual(QuestPause.query.filter_by(ended_at=None).count(), 1)
        self.action("resume")
        self.assertEqual(self.solve(self.alice, 1).json["data"]["status"], "correct")
        self.action("close")
        self.assertEqual(self.solve(self.alice, 2).status_code, 409)
        self.action("publish")
        before = self.guest.get(PREFIX + "/standings").json["data"]["teams"]
        with self.app.app_context():
            Teams.query.get(self.team_id).name = "Edited after publication"
            db.session.add(Solves(challenge_id=2, user_id=2, team_id=self.team_id, date=datetime.utcnow() + timedelta(seconds=60)))
            db.session.commit()
        after = self.guest.get(PREFIX + "/standings").json["data"]["teams"]
        self.assertEqual(before, after)
        self.assertEqual(self.post(self.admin, PREFIX + "/admin/corrections", {"team_id": self.team_id, "room_slug": "openshift", "adjustment_ms": 1, "reason": "Test"}).status_code, 409)
        self.assertEqual(self.post(self.admin, PREFIX + "/admin/event/action", {"action": "unpublish"}).status_code, 400)
        self.action("unpublish", reason="Correct display name")
        with self.app.app_context():
            self.assertEqual(standings()["teams"][0]["total"], 1)
            self.assertTrue(QuestAudit.query.filter_by(action="event.unpublish").first())

    def test_pause_time_excluded_from_room_and_overall(self):
        self.action("start")
        self.start()
        with self.app.app_context():
            at = datetime.utcnow() - timedelta(seconds=100)
            QuestEvent.query.get(1).start_at = at
            QuestStart.query.one().started_at = at
            db.session.add(QuestPause(started_at=at + timedelta(seconds=20), ended_at=at + timedelta(seconds=60)))
            db.session.add(Solves(challenge_id=1, user_id=2, team_id=self.team_id, date=at + timedelta(seconds=80)))
            db.session.commit()
            team = next(t for t in standings()["teams"] if t["id"] == self.team_id)
            self.assertEqual(team["overall_elapsed_ms"], 40000)
            self.assertEqual(team["room_progress"][0]["milestone_elapsed_ms"], 40000)

    def test_csrf_assets_topology_and_self_allocation_guards(self):
        self.assertEqual(self.admin.patch(PREFIX + "/admin/event", json={"name": "No CSRF"}).status_code, 403)
        for url in ("javascript:alert(1)", "https://example.com/tracker.svg", "//example.com/a", "/files/private.txt", "/plugins/open_tech_quest/assets/../private", "/plugins/open_tech_quest/assets/%2e%2e/a"):
            self.assertEqual(self.post(self.admin, PREFIX + "/admin/rooms/openshift", {"theme": {"logo_url": url}}, "PATCH").status_code, 400)
        self.assertEqual(self.post(self.admin, PREFIX + "/admin/rooms/openshift", {"theme": {"hero_url": "/plugins/open_tech_quest/assets/branding/openshift.png"}}, "PATCH").status_code, 200)
        self.assertEqual(self.alice.get("/teams/new").status_code, 403)
        self.assertEqual(self.post(self.alice, "/api/v1/teams/me", {}, "DELETE").status_code, 403)
        self.action("start")
        self.assertEqual(self.post(self.admin, PREFIX + "/admin/rooms/openshift", {"challenge_ids": [2, 1]}, "PATCH").status_code, 409)
        self.assertEqual(self.post(self.admin, "/api/v1/challenges/1", {"requirements": {}}, "PATCH").status_code, 409)
        self.assertEqual(self.post(self.admin, "/api/v1/teams/1/members", {"user_id": 4}).status_code, 409)

    def test_allocation_preview_commit_validation_and_private_rosters(self):
        with self.app.app_context():
            for i in range(5, 12):
                db.session.add(Users(id=i, name=f"Player {i}", email=f"p{i}@example.test", password="test-only"))
            db.session.commit()
        response = self.post(self.admin, PREFIX + "/admin/teams/allocate", {"team_size": 3, "preview": True})
        groups = response.json["data"]["groups"]
        self.assertEqual(sorted(len(g["user_ids"]) for g in groups), [2, 2, 3])
        self.assertEqual(self.post(self.admin, PREFIX + "/admin/teams/allocate", {"preview": False, "groups": groups[:-1]}).status_code, 409)
        result = self.post(self.admin, PREFIX + "/admin/teams/allocate", {"preview": False, "groups": groups})
        self.assertEqual(result.status_code, 200, result.get_data(as_text=True))
        with self.app.app_context():
            self.assertEqual(Users.query.filter_by(type="user", team_id=None).count(), 0)
            self.assertEqual(Teams.query.get(self.team_id).name, "Red team")
        release = (datetime.utcnow() + timedelta(hours=2)).isoformat() + "Z"
        self.assertEqual(self.post(self.admin, PREFIX + "/admin/event", {"rosters_release_at": release}, "PATCH").status_code, 200)
        self.assertIsNone(self.alice.get(PREFIX + "/session").json["data"]["team_name"])
        self.assertEqual(self.guest.get(PREFIX + "/standings").json["data"]["teams"], [])
        self.assertEqual(self.guest.get("/api/v1/teams").status_code, 403)
        self.assertIn("participants", self.admin.get(PREFIX + "/admin/state").json["data"])

    def test_corrections_exclusions_export_and_audit(self):
        self.action("start")
        self.start()
        self.assertEqual(self.solve(self.alice, 1).json["data"]["status"], "correct")
        payload = {"team_id": self.team_id, "room_slug": "openshift", "adjustment_ms": 1000, "reason": "Organizer verified workstation outage"}
        self.assertEqual(self.post(self.admin, PREFIX + "/admin/corrections", payload).status_code, 200)
        self.assertEqual(self.post(self.admin, PREFIX + "/admin/corrections", dict(payload, adjustment_ms=86400001)).status_code, 400)
        result = self.post(self.admin, PREFIX + f"/admin/teams/{self.team_id}", {"excluded": True, "reason": "Staff team"}, "PATCH")
        self.assertEqual(result.status_code, 200)
        teams = self.guest.get(PREFIX + "/standings").json["data"]["teams"]
        self.assertNotIn(self.team_id, [t["id"] for t in teams])
        exported = self.admin.get(PREFIX + "/admin/export")
        self.assertEqual(exported.status_code, 200)
        self.assertIn("active_elapsed_ms", exported.get_data(as_text=True))
        self.assertNotIn("alice@example", exported.get_data(as_text=True))
        public = self.guest.get(PREFIX + "/standings").get_data(as_text=True)
        self.assertNotIn("reason", public)
        self.assertNotIn("email", public)
        self.assertNotIn("provided", public)

    def test_manual_membership_and_cross_room_reuse(self):
        result = self.post(self.admin, PREFIX + "/admin/rooms/ansible", {"challenge_ids": [2]}, "PATCH")
        self.assertEqual(result.status_code, 409)
        result = self.post(self.admin, PREFIX + f"/admin/teams/{self.team_id}", {"user_ids": [2]}, "PATCH")
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json["data"]["user_ids"], [2])
        with self.app.app_context():
            self.assertIsNone(Users.query.get(3).team_id)

    def test_signed_attachment_downloads_respect_room_and_identity(self):
        from CTFd.utils.security.signing import serialize
        with self.app.app_context():
            file = ChallengeFiles.query.filter_by(challenge_id=2).first()
            claims = {"user_id": 2, "team_id": self.team_id, "file_id": file.id}
            valid = serialize(claims)
            wrong_team = serialize(dict(claims, team_id=self.other_id))
            wrong_file = serialize(dict(claims, file_id=file.id + 1))
            with patch("itsdangerous.timed.TimestampSigner.get_timestamp", return_value=int(time.time()) - 7200):
                expired = serialize(claims)
            path = Path(self.app.config["UPLOAD_FOLDER"]) / file.location
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("Authorized isolated test attachment")
        url = "/files/known-hash/private.txt?token="
        self.assertEqual(self.guest.get(url + valid).status_code, 403)
        self.action("start")
        self.start()
        self.assertEqual(self.guest.get(url + valid).status_code, 403)
        self.assertEqual(self.solve(self.alice, 1).json["data"]["status"], "correct")
        response = self.guest.get(url + valid)
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        self.assertIn("Authorized", response.get_data(as_text=True))
        response.close()
        for token in (wrong_team, wrong_file, expired, "invalid"):
            self.assertEqual(self.guest.get(url + token).status_code, 403)
        self.assertEqual(self.carol.get(url + valid).status_code, 403)

    def test_time_policies_offsets_and_legacy_ownership_guard(self):
        self.assertEqual(self.post(self.admin, PREFIX + "/admin/event", {"room_clock": "event", "overall_clock": "team", "start_at": "2026-01-01T10:00:00+02:00"}, "PATCH").status_code, 200)
        value = self.admin.get(PREFIX + "/bootstrap").json["data"]["event"]
        self.assertEqual(value["start_at"], "2026-01-01T08:00:00.000Z")
        for endpoint, payload in (("/api/v1/configs", {"paused": True}), ("/api/v1/configs/user_mode", {"value": "users"})):
            self.assertEqual(self.post(self.admin, endpoint, payload, "PATCH").status_code, 409)
        with self.app.app_context():
            from CTFd.plugins.open_tech_quest import load
            set_config("user_mode", "users")
            db.session.add(Solves(challenge_id=1, user_id=2, date=datetime.utcnow()))
            db.session.commit()
            with self.assertRaisesRegex(RuntimeError, "individual solves"):
                load(self.app)
            self.assertEqual(get_config("user_mode"), "users")

    def test_fifty_team_standings_bounded_queries_and_parallel_load(self):
        self.action("start")
        self.start()
        with self.app.app_context():
            at = datetime.utcnow() - timedelta(minutes=10)
            QuestEvent.query.get(1).start_at = at
            QuestStart.query.one().started_at = at
            password = Users.query.get(2).password
            room = QuestRoom.query.filter_by(slug="openshift").one()
            for index in range(48):
                team = Teams(name=f"Load team {index + 1:02}")
                db.session.add(team)
                db.session.flush()
                uid = index + 10
                db.session.execute(Users.__table__.insert(), {"id": uid, "name": f"Load player {index}", "email": f"load{index}@example.test", "password": password, "type": "user", "team_id": team.id})
                db.session.add(QuestStart(team_id=team.id, room_id=room.id, started_at=at))
                db.session.add(Solves(challenge_id=1, user_id=uid, team_id=team.id, date=at + timedelta(seconds=10 + index)))
            db.session.commit()
            statements = []
            def count(conn, cursor, statement, parameters, context, many):
                statements.append(statement)
            sqlalchemy_event.listen(db.engine, "before_cursor_execute", count)
            try:
                data = standings()
            finally:
                sqlalchemy_event.remove(db.engine, "before_cursor_execute", count)
            self.assertEqual(len(data["teams"]), 50)
            self.assertLessEqual(len(statements), 12)
        def fetch(_):
            client = self.app.test_client()
            started = time.perf_counter()
            response = client.get(PREFIX + "/standings")
            return response.status_code, time.perf_counter() - started, len(response.json["data"]["teams"])
        with ThreadPoolExecutor(max_workers=10) as pool:
            results = list(pool.map(fetch, range(50)))
        self.assertTrue(all(status == 200 and count == 50 for status, _, count in results))
        durations = sorted(duration for _, duration, _ in results)
        print(f"50-team isolated projection: 50 requests / concurrency 10; p95={durations[47]:.3f}s; max={durations[-1]:.3f}s")
        self.assertLess(durations[47], 5.0)

    def test_team_form_noop_fields_allow_draft_save_and_live_exclusion(self):
        endpoint = PREFIX + f"/admin/teams/{self.team_id}"
        result = self.post(self.admin, endpoint, {"name": "Renamed team", "excluded": False, "reason": "", "user_ids": [2, 3]}, "PATCH")
        self.assertEqual(result.status_code, 200, result.get_data(as_text=True))
        self.action("start")
        payload = {"name": "Renamed team", "excluded": True, "reason": "Staff team"}
        result = self.post(self.admin, endpoint, payload, "PATCH")
        self.assertEqual(result.status_code, 200, result.get_data(as_text=True))
        self.assertTrue(result.json["data"]["excluded"])
        self.assertEqual(self.post(self.admin, endpoint, dict(payload, reason=""), "PATCH").status_code, 200)
        self.assertEqual(self.post(self.admin, endpoint, dict(payload, excluded=False, reason=""), "PATCH").status_code, 400)
        self.assertEqual(self.post(self.admin, endpoint, dict(payload, name="Another name"), "PATCH").status_code, 409)

    def test_native_admin_cannot_destroy_membership_or_solve_history(self):
        self.action("start")
        self.start()
        self.assertEqual(self.solve(self.alice, 1).json["data"]["status"], "correct")
        with self.app.app_context():
            solve_id = Solves.query.one().id
        for path, payload, method in (
            ("/api/v1/users/2", {}, "DELETE"),
            (f"/api/v1/submissions/{solve_id}", {}, "DELETE"),
            (f"/api/v1/submissions/{solve_id}", {"type": "incorrect"}, "PATCH"),
            ("/api/v1/submissions", {"type": "correct", "challenge_id": 2, "team_id": self.team_id, "user_id": 2}, "POST"),
        ):
            response = self.post(self.admin, path, payload, method)
            self.assertEqual(response.status_code, 409, response.get_data(as_text=True))
        with self.app.app_context():
            self.assertEqual(Solves.query.count(), 1)
            self.assertIsNotNone(Users.query.get(2))
            self.assertEqual(next(t for t in standings()["teams"] if t["id"] == self.team_id)["total"], 1)

    def test_native_authoring_accepts_unchanged_position_without_topology_bypass(self):
        self.action("start")
        result = self.post(self.admin, "/api/v1/challenges/1", {"name": "Edited native challenge", "description": "Updated native instructions", "position": "0"}, "PATCH")
        self.assertEqual(result.status_code, 200, result.get_data(as_text=True))
        self.assertEqual(self.post(self.admin, "/api/v1/challenges/1", {"position": "9"}, "PATCH").status_code, 409)
        with self.app.app_context():
            challenge = Challenges.query.get(1)
            self.assertEqual(challenge.description, "Updated native instructions")
            self.assertEqual(challenge.position, 0)
            self.assertEqual(challenge.next_id, 2)

    def test_native_login_landing_for_unassigned_users_and_organizers(self):
        self.assertEqual(self.admin.get("/team?next=%2Fchallenges").location, "/quest")
        result = self.post(self.admin, PREFIX + f"/admin/teams/{self.team_id}", {"user_ids": [2]}, "PATCH")
        self.assertEqual(result.status_code, 200)
        self.assertEqual(self.bob.get("/team?next=%2Fchallenges").location, "/quest")
        self.assertNotEqual(self.alice.get("/team").location, "/quest")

    def test_native_membership_commit_serializes_with_event_start_on_mariadb(self):
        if self.app.config["SQLALCHEMY_DATABASE_URI"].startswith("sqlite"):
            self.skipTest("Production row-lock serialization is exercised on MariaDB")
        with self.app.app_context():
            db.session.add(Users(id=5, name="Waiting player", email="waiting@example.test", password="test-only"))
            db.session.commit()
        from CTFd.plugins.open_tech_quest.guards import event as original_event
        entered, release = threading.Event(), threading.Event()
        local = threading.local()
        def gate(lock=False):
            result = original_event(lock=lock)
            if getattr(local, "membership", False):
                entered.set()
                if not release.wait(3):
                    raise RuntimeError("Test failed to release native membership transaction")
            return result
        def native_membership():
            local.membership = True
            return self.post(self.client(1), f"/api/v1/teams/{self.team_id}/members", {"user_id": 5})
        def start_event():
            return self.post(self.client(1), PREFIX + "/admin/event/action", {"action": "start"})
        with patch("CTFd.plugins.open_tech_quest.guards.event", side_effect=gate):
            with ThreadPoolExecutor(max_workers=2) as pool:
                membership = pool.submit(native_membership)
                self.assertTrue(entered.wait(3))
                opening = pool.submit(start_event)
                time.sleep(0.1)
                try:
                    self.assertFalse(opening.done(), "Event start must wait for the accepted draft membership transaction")
                finally:
                    release.set()
                self.assertEqual(membership.result().status_code, 200)
                self.assertEqual(opening.result().status_code, 200)
        with self.app.app_context():
            self.assertEqual(Users.query.get(5).team_id, self.team_id)
            self.assertEqual(QuestEvent.query.get(1).status, "live")

    def test_allocation_rechecks_population_after_waiting_for_mariadb_lock(self):
        if self.app.config["SQLALCHEMY_DATABASE_URI"].startswith("sqlite"):
            self.skipTest("Production repeatable-read snapshots are exercised on MariaDB")
        from CTFd.plugins.open_tech_quest.service import event as locked_event
        with self.app.app_context():
            db.session.add(Users(id=5, name="Waiting player", email="waiting@example.test", password="test-only"))
            db.session.commit()
            locked_event(lock=True)
            Users.query.get(5).team_id = self.team_id
            db.session.flush()
            with ThreadPoolExecutor(max_workers=1) as pool:
                pending = pool.submit(lambda: self.post(self.client(1), PREFIX + "/admin/teams/allocate", {"preview": False, "groups": [{"name": "Stale proposal", "user_ids": [5]}]}))
                time.sleep(0.15)
                self.assertFalse(pending.done())
                db.session.commit()
                result = pending.result()
            self.assertEqual(result.status_code, 409, result.get_data(as_text=True))
            db.session.expire_all()
            self.assertEqual(Users.query.get(5).team_id, self.team_id)

    def test_empty_event_cannot_start_and_freeze_authoring(self):
        self.configure([])
        response = self.post(self.admin, PREFIX + "/admin/event/action", {"action": "start"})
        self.assertEqual(response.status_code, 409, response.get_data(as_text=True))
        self.assertIn("Configure at least one room challenge", response.json["error"])
        self.assertEqual(self.admin.get(PREFIX + "/admin/state").json["data"]["event"]["status"], "draft")
        self.configure([1])
        self.action("start")
