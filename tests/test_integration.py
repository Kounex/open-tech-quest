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
    QuestStart, QuestPause, QuestAudit, QuestOnboarding, QuestReadiness, QuestTeamName)
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
            assert QuestOnboarding.query.get(1).phase == "check_in"
            assert QuestOnboarding.query.get(1).team_size == 5
            assert QuestReadiness.query.count() == 0

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
            db.session.add(QuestOnboarding(id=1, phase="finalized", team_size=5, grandfathered=True))
            for pos, slug in enumerate(("openshift", "ansible", "rhel", "security", "ai")):
                db.session.add(QuestRoom(slug=slug, name=slug.title(), position=pos, theme={"layout": slug}))
            self.team = Teams(name="Red team")
            self.other_team = Teams(name="Blue team")
            db.session.add_all([self.team, self.other_team])
            db.session.flush()
            db.session.add_all([Users(id=1, name="Organizer", email="admin@example.test", type="admin", password="test-only", verified=True), Users(id=2, name="Alice", email="alice@example.test", password="test-only", team_id=self.team.id, verified=True), Users(id=3, name="Bob", email="bob@example.test", password="test-only", team_id=self.team.id, verified=True), Users(id=4, name="Carol", email="carol@example.test", password="test-only", team_id=self.other_team.id, verified=True)])
            self.team_id, self.other_id = self.team.id, self.other_team.id
            db.session.add_all([QuestTeamName(team_id=self.team_id, name_locked=True), QuestTeamName(team_id=self.other_id, name_locked=True)])
            for uid in (2, 3, 4):
                db.session.add(QuestReadiness(user_id=uid))
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
            QuestOnboarding.query.get(1).phase = "check_in"
            QuestOnboarding.query.get(1).team_size = 3
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
        with self.app.app_context():
            QuestOnboarding.query.get(1).phase = "check_in"
            db.session.commit()
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
        with self.app.app_context():
            QuestOnboarding.query.get(1).phase = "check_in"
            QuestTeamName.query.delete()
            db.session.commit()
        endpoint = PREFIX + f"/admin/teams/{self.team_id}"
        result = self.post(self.admin, endpoint, {"name": "Renamed team", "excluded": False, "reason": "", "user_ids": [2, 3]}, "PATCH")
        self.assertEqual(result.status_code, 200, result.get_data(as_text=True))
        with self.app.app_context():
            QuestOnboarding.query.get(1).phase = "finalized"
            db.session.add_all([QuestTeamName(team_id=self.team_id,name_locked=True),QuestTeamName(team_id=self.other_id,name_locked=True)])
            db.session.commit()
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
        with self.app.app_context():
            QuestOnboarding.query.get(1).phase = "check_in"
            db.session.commit()
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
                self.assertEqual(membership.result().status_code, 409)
                self.assertEqual(opening.result().status_code, 200)
        with self.app.app_context():
            self.assertIsNone(Users.query.get(5).team_id)
            self.assertEqual(QuestEvent.query.get(1).status, "live")

    def test_allocation_rechecks_population_after_waiting_for_mariadb_lock(self):
        if self.app.config["SQLALCHEMY_DATABASE_URI"].startswith("sqlite"):
            self.skipTest("Production repeatable-read snapshots are exercised on MariaDB")
        from CTFd.plugins.open_tech_quest.service import event as locked_event
        with self.app.app_context():
            QuestOnboarding.query.get(1).phase = "check_in"
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

    def load_demo(self):
        self.configure([])
        result = self.post(self.admin, PREFIX + "/admin/demo", {"action": "load"})
        self.assertEqual(result.status_code, 200, result.get_data(as_text=True))
        return result.json["data"]

    def test_demo_admin_csrf_mappings_and_phase_guards(self):
        endpoint = PREFIX + "/admin/demo"
        with self.guest.session_transaction() as session:
            session["nonce"] = "quest-test-csrf"
        self.assertEqual(self.post(self.guest, endpoint, {"action": "load"}).status_code, 401)
        self.assertEqual(self.post(self.alice, endpoint, {"action": "load"}).status_code, 403)
        self.assertEqual(self.admin.post(endpoint, json={"action": "load"}).status_code, 403)
        self.assertEqual(self.post(self.admin, endpoint, {"action": "unknown"}).status_code, 400)
        state = self.admin.get(PREFIX + "/admin/state").json["data"]["demo"]
        self.assertFalse(state["can_load"])
        self.assertIn("mapped challenges", state["reason"])
        self.assertEqual(self.post(self.admin, endpoint, {"action": "load"}).status_code, 409)
        self.action("start")
        result = self.post(self.admin, endpoint, {"action": "load"})
        self.assertEqual(result.status_code, 409)
        self.assertIn("draft", result.json["error"])

    def test_demo_load_native_chains_preview_flags_and_no_participants(self):
        from CTFd.plugins.open_tech_quest.models import QuestDemoBatch, QuestDemoChallenge
        state = self.load_demo()
        self.assertEqual(state, {"active": True, "challenge_count": 25, "can_load": False, "can_unload": True, "reason": None})
        with self.app.app_context():
            self.assertEqual(Users.query.count(), 4)
            self.assertEqual(Teams.query.count(), 2)
            self.assertEqual(QuestStart.query.count(), 0)
            self.assertEqual(Solves.query.count(), 0)
            self.assertEqual(Challenges.query.count(), 28)
            self.assertEqual(QuestDemoBatch.query.count(), 1)
            self.assertEqual(QuestDemoChallenge.query.count(), 25)
            self.assertIsNotNone(Challenges.query.get(3))
            previews = []
            for room in QuestRoom.query.all():
                self.assertIn("### Your objectives", room.description)
                self.assertIn("demo{", room.description)
                steps = QuestStep.query.filter_by(room_id=room.id).order_by(QuestStep.position).all()
                self.assertEqual(len(steps), 5)
                ids = [step.challenge_id for step in steps]
                for position, challenge_id in enumerate(ids):
                    challenge = Challenges.query.get(challenge_id)
                    self.assertEqual(challenge.requirements["prerequisites"], ids[:position])
                    self.assertEqual(challenge.next_id, ids[position + 1] if position < 4 else None)
                    self.assertIn("### Example artifact", challenge.description)
                    self.assertEqual(challenge.type, "standard")
                    hint = Hints.query.filter_by(challenge_id=challenge_id).one()
                    self.assertEqual(hint.cost, 0)
                    flag = Flags.query.filter_by(challenge_id=challenge_id).one().content
                    self.assertTrue(flag.startswith("demo{"))
                    self.assertIn(flag, hint.content)
                    previews.append((challenge_id, flag, hint.id))
        for challenge_id, flag, hint_id in previews:
            response = self.post(self.admin, "/api/v1/challenges/attempt?preview=true", {"challenge_id": challenge_id, "submission": flag})
            self.assertEqual(response.json["data"]["status"], "correct")
            self.assertIn(flag, self.admin.get(f"/api/v1/hints/{hint_id}?preview=true").json["data"]["content"])
        self.assertEqual(self.post(self.admin, PREFIX + "/admin/demo", {"action": "load"}).status_code, 409)
        with self.app.app_context():
            self.assertEqual(Challenges.query.count(), 28)
            self.assertEqual(Solves.query.count(), 0)
            self.assertEqual(QuestAudit.query.filter_by(action="demo.load").count(), 1)

    def test_demo_unload_restores_original_copy_retains_edits_and_people(self):
        for slug in ("openshift", "ansible", "rhel", "security", "ai"):
            self.assertEqual(self.post(self.admin, PREFIX + f"/admin/rooms/{slug}", {"subtitle": f"Original {slug}", "description": f"## Original {slug} introduction"}, "PATCH").status_code, 200)
        self.load_demo()
        self.assertEqual(self.post(self.admin, PREFIX + "/admin/rooms/ansible", {"description": "## Organizer edit\n\nKeep this scenario."}, "PATCH").status_code, 200)
        self.assertEqual(self.post(self.admin, PREFIX + "/admin/rooms/rhel", {"subtitle": "Organizer topic update"}, "PATCH").status_code, 200)
        result = self.post(self.admin, PREFIX + "/admin/demo", {"action": "unload"})
        self.assertEqual(result.status_code, 200, result.get_data(as_text=True))
        self.assertFalse(result.json["data"]["active"])
        self.assertTrue(result.json["data"]["can_load"])
        with self.app.app_context():
            self.assertEqual(Challenges.query.count(), 3)
            self.assertEqual(Flags.query.count(), 3)
            self.assertEqual(Hints.query.count(), 1)
            self.assertEqual(Users.query.count(), 4)
            self.assertEqual(Teams.query.count(), 2)
            self.assertEqual(QuestStep.query.count(), 0)
            for room in QuestRoom.query.all():
                expected = "## Organizer edit\n\nKeep this scenario." if room.slug == "ansible" else f"## Original {room.slug} introduction"
                self.assertEqual(room.description, expected)
                self.assertEqual(room.subtitle, "Organizer topic update" if room.slug == "rhel" else f"Original {room.slug}")
        self.assertEqual(self.post(self.admin, PREFIX + "/admin/demo", {"action": "unload"}).status_code, 409)

    def test_demo_unload_repairs_later_real_steps_and_preserves_unmapped_content(self):
        self.load_demo()
        room = self.admin.get(PREFIX + "/rooms/openshift").json["data"]
        demo_ids = [step["id"] for step in room["steps"]]
        self.configure([demo_ids[0], 1, demo_ids[1], 2])
        result = self.post(self.admin, PREFIX + "/admin/demo", {"action": "unload"})
        self.assertEqual(result.status_code, 200, result.get_data(as_text=True))
        self.assertFalse(result.json["data"]["can_load"])
        self.assertIn("mapped challenges", result.json["data"]["reason"])
        with self.app.app_context():
            self.assertEqual(Challenges.query.count(), 3)
            self.assertEqual(Challenges.query.get(1).description, "Private instructions 1")
            self.assertEqual(Challenges.query.get(1).requirements["prerequisites"], [])
            self.assertEqual(Challenges.query.get(1).next_id, 2)
            self.assertEqual(Challenges.query.get(2).requirements["prerequisites"], [1])
            self.assertIsNone(Challenges.query.get(2).next_id)
            self.assertEqual([step.challenge_id for step in QuestStep.query.order_by(QuestStep.position).all()], [1, 2])
            self.assertEqual(Flags.query.filter_by(challenge_id=3).one().content, "fixture-answer-3")

    def test_demo_unload_refuses_submissions_and_reports_disabled_reason(self):
        from CTFd.models import Fails
        self.load_demo()
        with self.app.app_context():
            demo_id = QuestStep.query.first().challenge_id
            db.session.add(Fails(challenge_id=demo_id, user_id=2, team_id=self.team_id, provided="public demo attempt"))
            db.session.add(Solves(challenge_id=demo_id, user_id=2, team_id=self.team_id, provided="public dummy answer"))
            db.session.commit()
        state = self.admin.get(PREFIX + "/admin/state").json["data"]["demo"]
        self.assertFalse(state["can_unload"])
        self.assertIn("submissions", state["reason"])
        self.assertEqual(self.post(self.admin, PREFIX + "/admin/demo", {"action": "unload"}).status_code, 409)
        with self.app.app_context():
            self.assertEqual(Challenges.query.count(), 28)
            self.assertEqual(Fails.query.count(), 1)
            self.assertEqual(Solves.query.count(), 1)

    def test_demo_unload_refuses_room_starts_and_competition_start(self):
        self.load_demo()
        response = self.post(self.admin, PREFIX + "/admin/event/action", {"action": "start"})
        self.assertEqual(response.status_code, 409)
        self.assertIn("Remove demo content", response.json["error"])
        with self.app.app_context():
            self.assertEqual(QuestEvent.query.get(1).status, "draft")
            db.session.add(QuestStart(team_id=self.team_id, room_id=QuestRoom.query.first().id))
            db.session.commit()
        state = self.admin.get(PREFIX + "/admin/state").json["data"]["demo"]
        self.assertFalse(state["can_unload"])
        self.assertIn("starts", state["reason"])
        self.assertEqual(self.post(self.admin, PREFIX + "/admin/demo", {"action": "unload"}).status_code, 409)

    def test_demo_unload_refuses_unrelated_native_dependencies(self):
        self.load_demo()
        with self.app.app_context():
            demo_id = QuestStep.query.first().challenge_id
            Challenges.query.get(3).requirements = {"prerequisites": [demo_id]}
            db.session.commit()
        state = self.admin.get(PREFIX + "/admin/state").json["data"]["demo"]
        self.assertFalse(state["can_unload"])
        self.assertIn("depends on demo", state["reason"])
        self.assertEqual(self.post(self.admin, PREFIX + "/admin/demo", {"action": "unload"}).status_code, 409)
        with self.app.app_context():
            self.assertEqual(Challenges.query.get(3).requirements["prerequisites"], [demo_id])
            self.assertEqual(Challenges.query.count(), 28)

    def test_demo_does_not_claim_real_challenge_reusing_deleted_id(self):
        self.load_demo()
        with self.app.app_context():
            room = QuestRoom.query.filter_by(slug="openshift").one()
            ids = [step.challenge_id for step in QuestStep.query.filter_by(room_id=room.id).order_by(QuestStep.position).all()]
        self.configure(ids[:-1])
        self.assertEqual(self.post(self.admin, f"/api/v1/challenges/{ids[-1]}", {}, "DELETE").status_code, 200)
        with self.app.app_context():
            db.session.add(Challenges(id=ids[-1], name="Real replacement", description="Real organizer content", type="standard", state="visible", value=100))
            db.session.commit()
        result = self.post(self.admin, PREFIX + "/admin/demo", {"action": "unload"})
        self.assertEqual(result.status_code, 200, result.get_data(as_text=True))
        with self.app.app_context():
            self.assertEqual(Challenges.query.get(ids[-1]).description, "Real organizer content")
            self.assertEqual(Challenges.query.count(), 4)

    def test_demo_load_failure_rolls_back_every_created_row_and_room_copy(self):
        from CTFd.plugins.open_tech_quest.demo import DemoConflict, challenge_content
        from CTFd.plugins.open_tech_quest.models import QuestDemoBatch, QuestDemoChallenge
        self.configure([])
        count = 0
        def fail_midway(slug, item):
            nonlocal count
            count += 1
            if count == 7:
                raise DemoConflict("Unable to complete demo setup; no content was saved")
            return challenge_content(slug, item)
        with patch("CTFd.plugins.open_tech_quest.demo.challenge_content", side_effect=fail_midway):
            response = self.post(self.admin, PREFIX + "/admin/demo", {"action": "load"})
        self.assertEqual(response.status_code, 409)
        with self.app.app_context():
            self.assertEqual(Challenges.query.count(), 3)
            self.assertEqual(Flags.query.count(), 3)
            self.assertEqual(Hints.query.count(), 1)
            self.assertEqual(QuestStep.query.count(), 0)
            self.assertEqual(QuestDemoBatch.query.count(), 0)
            self.assertEqual(QuestDemoChallenge.query.count(), 0)
            self.assertTrue(all(room.description == "" and room.subtitle == "" for room in QuestRoom.query.all()))

    def test_demo_can_reload_after_unload_without_claiming_old_ids(self):
        from CTFd.plugins.open_tech_quest.models import QuestDemoBatch
        self.load_demo()
        for action in ("unload", "load", "unload"):
            response = self.post(self.admin, PREFIX + "/admin/demo", {"action": action})
            self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        with self.app.app_context():
            self.assertEqual(Challenges.query.count(), 3)
            self.assertEqual(QuestDemoBatch.query.count(), 2)
            self.assertEqual(QuestDemoBatch.query.filter_by(active=True).count(), 0)

    def test_demo_concurrent_load_creates_only_one_batch(self):
        from CTFd.plugins.open_tech_quest.models import QuestDemoBatch
        self.configure([])
        def load_once(_):
            return self.post(self.client(1), PREFIX + "/admin/demo", {"action": "load"})
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(load_once, range(2)))
        self.assertEqual(sorted(response.status_code for response in responses), [200, 409])
        with self.app.app_context():
            self.assertEqual(QuestDemoBatch.query.filter_by(active=True).count(), 1)
            self.assertEqual(Challenges.query.count(), 28)
            self.assertEqual(QuestStep.query.count(), 25)

    def test_demo_unload_serializes_native_delete_and_id_reuse_on_sqlite(self):
        if not self.app.config["SQLALCHEMY_DATABASE_URI"].startswith("sqlite"):
            self.skipTest("SQLite native ID reuse and writer serialization")
        self.load_demo()
        with self.app.app_context():
            room = QuestRoom.query.filter_by(slug="ai").one()
            ids = [step.challenge_id for step in QuestStep.query.filter_by(room_id=room.id).order_by(QuestStep.position).all()]
        response = self.post(self.admin, PREFIX + "/admin/rooms/ai", {"challenge_ids": ids[:-1]}, "PATCH")
        self.assertEqual(response.status_code, 200)
        from CTFd.plugins.open_tech_quest.demo import owned_ids as original_owned_ids
        entered, release = threading.Event(), threading.Event()
        local = threading.local()
        def gate(batch):
            result = original_owned_ids(batch)
            if getattr(local, "unloading", False):
                local.calls = getattr(local, "calls", 0) + 1
                if local.calls == 2:
                    entered.set()
                    if not release.wait(3):
                        raise RuntimeError("Unload test gate was not released")
            return result
        def unload():
            local.unloading = True
            return self.post(self.client(1), PREFIX + "/admin/demo", {"action": "unload"})
        def native_replace():
            client = self.client(1)
            deleted = self.post(client, f"/api/v1/challenges/{ids[-1]}", {}, "DELETE")
            created = self.post(client, "/api/v1/challenges", {"name": "Real concurrent challenge", "description": "Real organizer content", "category": "Real", "value": 100, "state": "visible", "type": "standard"})
            return deleted, created
        with patch("CTFd.plugins.open_tech_quest.demo.owned_ids", side_effect=gate):
            with ThreadPoolExecutor(max_workers=2) as pool:
                pending_unload = pool.submit(unload)
                self.assertTrue(entered.wait(3))
                pending_native = pool.submit(native_replace)
                time.sleep(0.1)
                try:
                    self.assertFalse(pending_native.done(), "Native writes must wait for the SQLite demo transaction")
                finally:
                    release.set()
                result = pending_unload.result()
                deleted, created = pending_native.result()
        self.assertEqual(result.status_code, 200, result.get_data(as_text=True))
        self.assertIn(deleted.status_code, (200, 404))
        self.assertEqual(created.status_code, 200, created.get_data(as_text=True))
        with self.app.app_context():
            self.assertEqual(Challenges.query.get(created.json["data"]["id"]).description, "Real organizer content")

    def test_demo_load_cannot_interleave_with_competition_start(self):
        if not self.app.config["SQLALCHEMY_DATABASE_URI"].startswith("sqlite"):
            self.skipTest("SQLite lifecycle writer serialization")
        from CTFd.plugins.open_tech_quest.demo import active_batch as original_active_batch
        self.configure([])
        entered, release = threading.Event(), threading.Event()
        local = threading.local()
        def gate():
            result = original_active_batch()
            if getattr(local, "opening", False):
                entered.set()
                if not release.wait(3):
                    raise RuntimeError("Event start gate was not released")
            return result
        def start_event():
            local.opening = True
            return self.post(self.client(1), PREFIX + "/admin/event/action", {"action": "start"})
        def load_demo():
            return self.post(self.client(1), PREFIX + "/admin/demo", {"action": "load"})
        with patch("CTFd.plugins.open_tech_quest.demo.active_batch", side_effect=gate):
            with ThreadPoolExecutor(max_workers=2) as pool:
                pending_start = pool.submit(start_event)
                self.assertTrue(entered.wait(3))
                pending_load = pool.submit(load_demo)
                time.sleep(0.1)
                try:
                    self.assertFalse(pending_load.done(), "Demo load must wait for the event lifecycle decision")
                finally:
                    release.set()
                started, loaded = pending_start.result(), pending_load.result()
        self.assertEqual(started.status_code, 409)
        self.assertEqual(loaded.status_code, 200, loaded.get_data(as_text=True))
        with self.app.app_context():
            self.assertEqual(QuestEvent.query.get(1).status, "draft")
            self.assertIsNotNone(original_active_batch())

    def open_onboarding(self, capacity=5):
        with self.app.app_context():
            state = QuestOnboarding.query.get(1)
            state.phase, state.team_size, state.grandfathered = "check_in", capacity, False
            state.applied_at, state.finalized_at = None, None
            QuestReadiness.query.delete()
            QuestTeamName.query.delete()
            db.session.commit()

    def ready_user(self, client):
        response = self.post(client, PREFIX + "/onboarding/ready", {})
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        return response.json["data"]

    def onboarding_action(self, action, **values):
        return self.post(self.admin, PREFIX + "/admin/onboarding/action", dict(action=action, **values))

    def attendance_plan(self):
        response = self.post(self.admin, PREFIX + "/admin/onboarding/optimize", {"preview": True})
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        return response.json["data"]

    def apply_attendance(self, plan):
        response = self.post(self.admin, PREFIX + "/admin/onboarding/optimize", {"preview": False, "fingerprint": plan["fingerprint"]})
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        return response.json["data"]

    def test_onboarding_personal_ready_is_idempotent_and_has_no_clock_side_effects(self):
        self.open_onboarding()
        self.assertEqual(self.guest.get(PREFIX + "/onboarding").status_code, 401)
        self.assertEqual(self.post(self.admin, PREFIX + "/onboarding/ready", {}).status_code, 403)
        self.assertEqual(self.alice.post(PREFIX + "/onboarding/ready", json={}).status_code, 403)
        self.assertEqual(self.post(self.alice, PREFIX + "/onboarding/ready", {"ready_at": "2000-01-01T00:00:00Z"}).status_code, 400)
        first, second = self.ready_user(self.alice), self.ready_user(self.alice)
        self.assertEqual(first["ready_at"], second["ready_at"])
        self.assertFalse(first["late"])
        self.assertNotIn("email", str(first))
        with self.app.app_context():
            self.assertEqual(QuestReadiness.query.count(), 1)
            self.assertEqual(QuestStart.query.count(), 0)
            self.assertEqual(Solves.query.count(), 0)
            self.assertIsNone(QuestEvent.query.get(1).start_at)
        self.assertEqual(self.onboarding_action("close_checkin").status_code, 200)
        late = self.ready_user(self.bob)
        self.assertTrue(late["late"])
        self.assertEqual(self.onboarding_action("reopen_checkin").status_code, 200)
        self.assertTrue(self.bob.get(PREFIX + "/onboarding").json["data"]["late"])

    def test_onboarding_full_workflow_preserves_readiness_names_and_empty_team_history(self):
        self.open_onboarding()
        for client in (self.alice, self.bob, self.carol):
            self.ready_user(client)
        self.assertEqual(self.post(self.admin, PREFIX + "/admin/event/action", {"action": "start"}).status_code, 409)
        self.assertEqual(self.onboarding_action("close_checkin").status_code, 200)
        plan = self.attendance_plan()
        self.assertEqual(len(plan["groups"]), 1)
        self.assertEqual(self.apply_attendance(plan)["phase"], "naming")
        self.assertEqual(self.post(self.admin, PREFIX + "/admin/onboarding/optimize", {"preview": False, "fingerprint": plan["fingerprint"]}).status_code, 409)
        self.assertEqual(self.onboarding_action("reopen_checkin").status_code, 409)
        self.assertEqual(self.onboarding_action("finalize").status_code, 409)
        response = self.post(self.alice, PREFIX + "/onboarding/name", {"name": "Workshop Foxes", "confirm": True})
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        self.assertTrue(response.json["data"]["team"]["name_locked"])
        self.assertEqual(self.post(self.bob, PREFIX + "/onboarding/name", {"name": "Other name", "confirm": True}).status_code, 409)
        self.assertEqual(self.onboarding_action("finalize").status_code, 200)
        self.assertTrue(self.admin.get(PREFIX + "/admin/state").json["data"]["onboarding"]["can_start"])
        public = self.guest.get(PREFIX + "/standings").json["data"]["teams"]
        self.assertEqual([team["name"] for team in public], ["Workshop Foxes"])
        with self.app.app_context():
            self.assertEqual(Teams.query.count(), 2)
            self.assertEqual(QuestReadiness.query.count(), 3)
            self.assertIsNotNone(Teams.query.get(self.other_id))
        self.action("start")

    def test_onboarding_preview_rejects_changed_attendance_capacity_identity_membership(self):
        self.open_onboarding()
        self.ready_user(self.alice)
        self.ready_user(self.bob)
        self.assertEqual(self.onboarding_action("close_checkin").status_code, 200)
        def reject(plan):
            result = self.post(self.admin, PREFIX + "/admin/onboarding/optimize", {"preview": False, "fingerprint": plan["fingerprint"]})
            self.assertEqual(result.status_code, 409, result.get_data(as_text=True))
            self.assertEqual(self.admin.get(PREFIX + "/admin/state").json["data"]["onboarding"]["phase"], "closed")
        plan = self.attendance_plan()
        self.ready_user(self.carol)
        reject(plan)
        plan = self.attendance_plan()
        self.assertEqual(self.post(self.admin, PREFIX + "/admin/onboarding", {"team_size": 4}, "PATCH").status_code, 200)
        reject(plan)
        plan = self.attendance_plan()
        self.assertEqual(self.post(self.admin, PREFIX + f"/admin/teams/{self.team_id}", {"name": "Provisional rename"}, "PATCH").status_code, 200)
        reject(plan)
        plan = self.attendance_plan()
        self.assertEqual(self.post(self.admin, PREFIX + f"/admin/teams/{self.team_id}", {"user_ids": [2]}, "PATCH").status_code, 200)
        reject(plan)
        plan = self.attendance_plan()
        self.assertEqual(self.post(self.admin, PREFIX + "/admin/onboarding/optimize", {"preview": False, "fingerprint": plan["fingerprint"], "groups": []}).status_code, 400)
        self.apply_attendance(plan)

    def test_onboarding_concurrent_once_name_claims_and_casefold_uniqueness(self):
        self.open_onboarding(capacity=2)
        for client in (self.alice, self.bob, self.carol):
            self.ready_user(client)
        self.assertEqual(self.onboarding_action("close_checkin").status_code, 200)
        self.apply_attendance(self.attendance_plan())
        def claim(item):
            uid, name = item
            return self.post(self.client(uid), PREFIX + "/onboarding/name", {"name": name, "confirm": True})
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(claim, [(2,"Orbit Foxes"),(3,"Orbit Ravens")]))
        self.assertEqual(sorted(response.status_code for response in results), [200,409])
        name = next(r.json["data"]["team"]["name"] for r in results if r.status_code == 200)
        self.assertEqual(self.post(self.carol, PREFIX + "/onboarding/name", {"name": name.swapcase(), "confirm": True}).status_code, 409)
        self.assertEqual(self.post(self.carol, PREFIX + "/onboarding/name", {"name": "Other cohort"}).status_code, 400)
        self.assertEqual(self.post(self.carol, PREFIX + "/onboarding/name", {"name": "Other cohort", "confirm": True}).status_code, 200)
        self.assertEqual(self.post(self.admin, PREFIX + f"/admin/teams/{self.team_id}", {"name": "Corrected name"}, "PATCH").status_code, 400)
        self.assertEqual(self.post(self.admin, PREFIX + f"/admin/teams/{self.team_id}", {"name": "Corrected name", "reason": "Organizer verified preferred spelling"}, "PATCH").status_code, 200)

    def test_onboarding_late_arrivals_can_form_reasoned_capacity_bound_team(self):
        self.open_onboarding(capacity=1)
        for client in (self.alice,self.bob,self.carol):
            self.ready_user(client)
        self.assertEqual(self.onboarding_action("close_checkin").status_code, 200)
        self.apply_attendance(self.attendance_plan())
        with self.app.app_context():
            db.session.add(Users(id=5, name="Late participant", email="late@example.test", password="test-only"))
            db.session.commit()
        late = self.client(5)
        self.assertTrue(self.ready_user(late)["late"])
        self.assertEqual(self.onboarding_action("finalize").status_code, 409)
        self.assertEqual(self.onboarding_action("create_late_team", user_ids=[5]).status_code, 400)
        self.assertEqual(self.onboarding_action("create_late_team", user_ids=[5], reason="Late arrival after attendance plan").status_code, 200)
        self.assertTrue(late.get(PREFIX + "/onboarding").json["data"]["can_name"])
        for uid in (2,3,4,5):
            response = self.post(self.client(uid), PREFIX + "/onboarding/name", {"name": f"Final team {uid}", "confirm": True})
            self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        self.assertEqual(self.onboarding_action("finalize").status_code, 200)
        self.assertEqual(self.onboarding_action("create_late_team", user_ids=[5], reason="Cannot move final member").status_code, 409)
        self.assertEqual(self.post(self.admin, PREFIX + f"/admin/teams/{self.team_id}", {"user_ids": []}, "PATCH").status_code, 409)
        self.assertEqual(self.post(self.admin, PREFIX + "/admin/onboarding", {"team_size": 10}, "PATCH").status_code, 409)

    def test_onboarding_roster_privacy_and_native_frozen_name_bypasses(self):
        self.open_onboarding(capacity=2)
        for client in (self.alice,self.bob,self.carol):
            self.ready_user(client)
        self.assertEqual(self.onboarding_action("close_checkin").status_code, 200)
        self.apply_attendance(self.attendance_plan())
        own = self.alice.get(PREFIX + "/onboarding").json["data"]
        self.assertEqual({member["id"] for member in own["team"]["members"]}, {2,3})
        self.assertNotIn("email", str(own))
        self.assertNotIn("@", str(own))
        for uid,name in ((2,"Native Guard Foxes"),(4,"Native Guard Ravens")):
            self.assertEqual(self.post(self.client(uid), PREFIX + "/onboarding/name", {"name": name, "confirm": True}).status_code, 200)
        self.assertEqual(self.onboarding_action("finalize").status_code, 200)
        for path,payload,method in ((f"/api/v1/teams/{self.team_id}",{"name":"Bypass"},"PATCH"),(f"/api/v1/teams/{self.team_id}/members",{"user_id":4},"POST"),("/api/v1/users/2",{},"DELETE")):
            self.assertEqual(self.post(self.admin,path,payload,method).status_code,409)
        self.assertEqual(self.post(self.alice,"/api/v1/teams/me",{"name":"Bypass"},"PATCH").status_code,403)
        self.assertEqual(self.admin.get("/teams/new").status_code,403)
        self.assertEqual(self.post(self.alice,"/api/v1/users/me",{"name":"Alice Updated"},"PATCH").status_code,200)
        self.assertEqual(self.alice.get(PREFIX + "/onboarding").json["data"]["team"]["name"],"Native Guard Foxes")
        release = (datetime.utcnow()+timedelta(hours=1)).isoformat()+"Z"
        self.assertEqual(self.post(self.admin,PREFIX+"/admin/event",{"rosters_release_at":release},"PATCH").status_code,200)
        hidden = self.alice.get(PREFIX+"/onboarding").json["data"]
        self.assertIsNone(hidden["team"])
        self.assertFalse(hidden["can_name"])
        self.assertIsNotNone(hidden["ready_at"])

    def test_onboarding_optimizer_keeps_full_groups_minimal_moves_and_no_show_accounts(self):
        self.open_onboarding()
        with self.app.app_context():
            password = Users.query.get(2).password
            for uid in range(5,24):
                db.session.execute(Users.__table__.insert(), {"id":uid,"name":f"Attendee {uid}","email":f"attendee{uid}@example.test","password":password,"type":"user"})
            teams = Teams.query.order_by(Teams.id).all()
            for index in range(3):
                team = Teams(name=f"Provisional {index+3}")
                db.session.add(team)
                db.session.flush()
                teams.append(team)
            for index,uid in enumerate(range(2,23)):
                Users.query.get(uid).team_id = teams[index//5].id
                db.session.add(QuestReadiness(user_id=uid))
            Users.query.get(23).team_id = teams[-1].id
            db.session.commit()
        self.assertEqual(self.onboarding_action("close_checkin").status_code,200)
        plan = self.attendance_plan()
        self.assertEqual(sorted(len(group["user_ids"]) for group in plan["groups"]),[4,4,4,4,5])
        self.assertEqual(len(plan["moves"]),3)
        self.assertEqual(plan["unassigned_user_ids"],[23])
        self.assertEqual(self.attendance_plan(),plan)
        self.apply_attendance(plan)
        with self.app.app_context():
            self.assertIsNone(Users.query.get(23).team_id)
            self.assertEqual(Users.query.count(),23)
            self.assertEqual(Teams.query.count(),5)
            self.assertEqual(QuestReadiness.query.count(),21)

    def test_onboarding_optimizer_preserves_activity_or_refuses_absent_members(self):
        self.open_onboarding()
        self.ready_user(self.alice)
        self.assertEqual(self.onboarding_action("close_checkin").status_code,200)
        with self.app.app_context():
            at = datetime.utcnow()-timedelta(minutes=1)
            db.session.add(Solves(challenge_id=1,user_id=2,team_id=self.team_id,date=at))
            db.session.add(QuestStart(team_id=self.team_id,room_id=QuestRoom.query.first().id,started_at=at))
            db.session.commit()
        refused = self.post(self.admin,PREFIX+"/admin/onboarding/optimize",{"preview":True})
        self.assertEqual(refused.status_code,409)
        self.assertIn("activity",refused.json["error"])
        self.ready_user(self.bob)
        plan = self.attendance_plan()
        self.assertEqual(plan["groups"][0]["team_id"],self.team_id)
        self.apply_attendance(plan)
        with self.app.app_context():
            self.assertEqual(Solves.query.one().date,at)
            self.assertEqual(QuestStart.query.one().started_at,at)
            self.assertEqual(Users.query.get(2).team_id,self.team_id)
            self.assertEqual(Users.query.get(3).team_id,self.team_id)
            self.assertIsNone(Users.query.get(4).team_id)

    def test_onboarding_additive_upgrade_grandfathers_live_without_changing_history(self):
        import importlib.util
        from alembic.migration import MigrationContext
        from alembic.operations import Operations
        path = Path("/opt/CTFd/CTFd/plugins/open_tech_quest/migrations/0004_onboarding.py")
        spec = importlib.util.spec_from_file_location("quest_onboarding_upgrade",path)
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        with self.app.app_context():
            at = datetime.utcnow()-timedelta(minutes=3)
            e = QuestEvent.query.get(1)
            e.status,e.start_at = "live",at
            db.session.add(Solves(challenge_id=1,user_id=2,team_id=self.team_id,date=at+timedelta(seconds=20)))
            db.session.commit()
            expected = [(u.id,u.team_id,u.name) for u in Users.query.order_by(Users.id).all()]
            db.session.remove()
            with db.engine.connect() as connection:
                transaction = connection.begin()
                for model in (QuestReadiness,QuestTeamName,QuestOnboarding):
                    model.__table__.drop(bind=connection)
                migration.upgrade(Operations(MigrationContext.configure(connection)))
                transaction.commit()
            db.session.expire_all()
            state = QuestOnboarding.query.get(1)
            self.assertEqual(state.phase,"finalized")
            self.assertTrue(state.grandfathered)
            self.assertEqual(state.team_size,5)
            self.assertEqual([(u.id,u.team_id,u.name) for u in Users.query.order_by(Users.id).all()],expected)
            self.assertEqual(QuestReadiness.query.count(),0)
            self.assertTrue(all(row.name_locked for row in QuestTeamName.query.all()))
            self.assertEqual(QuestEvent.query.get(1).start_at,at)
            self.assertEqual(Solves.query.one().date,at+timedelta(seconds=20))

    def test_onboarding_empty_history_team_remains_in_standings(self):
        from CTFd.models import Awards
        with self.app.app_context():
            archived = Teams(name="Historical empty team")
            empty = Teams(name="Unused empty team")
            db.session.add_all([archived,empty])
            db.session.flush()
            archived_id,empty_id = archived.id,empty.id
            db.session.add(Awards(team_id=archived.id,name="Historical note",value=0))
            db.session.commit()
            ids = {team["id"] for team in standings()["teams"]}
            self.assertIn(archived_id,ids)
            self.assertNotIn(empty_id,ids)

    def test_onboarding_ban_after_finalization_does_not_deadlock_start_or_move_roster(self):
        self.open_onboarding(capacity=2)
        for client in (self.alice,self.bob,self.carol):
            self.ready_user(client)
        self.assertEqual(self.onboarding_action("close_checkin").status_code,200)
        self.apply_attendance(self.attendance_plan())
        for uid,name in ((2,"Moderation Foxes"),(4,"Moderation Ravens")):
            self.assertEqual(self.post(self.client(uid),PREFIX+"/onboarding/name",{"name":name,"confirm":True}).status_code,200)
        self.assertEqual(self.onboarding_action("finalize").status_code,200)
        self.assertEqual(self.post(self.admin,"/api/v1/users/3",{"banned":True},"PATCH").status_code,200)
        self.assertEqual(self.post(self.admin,"/api/v1/users/2",{"type":"admin"},"PATCH").status_code,409)
        self.assertTrue(self.admin.get(PREFIX+"/admin/state").json["data"]["onboarding"]["can_start"])
        self.action("start")
        self.assertEqual(self.bob.get(PREFIX+"/onboarding").status_code,403)
        with self.app.app_context():
            self.assertEqual(Users.query.get(3).team_id,self.team_id)
            self.assertTrue(Users.query.get(3).banned)

    def test_onboarding_reasoned_ineligible_removal_before_finalization(self):
        self.open_onboarding()
        for client in (self.alice,self.bob,self.carol):
            self.ready_user(client)
        self.assertEqual(self.onboarding_action("close_checkin").status_code,200)
        self.apply_attendance(self.attendance_plan())
        self.assertEqual(self.post(self.admin,"/api/v1/users/3",{"banned":True},"PATCH").status_code,200)
        endpoint = PREFIX+f"/admin/teams/{self.team_id}"
        self.assertEqual(self.post(self.admin,endpoint,{"user_ids":[2,4]},"PATCH").status_code,400)
        result = self.post(self.admin,endpoint,{"user_ids":[2,4],"reason":"Banned account removed before final roster"},"PATCH")
        self.assertEqual(result.status_code,200,result.get_data(as_text=True))
        self.assertEqual(self.post(self.admin,endpoint,{"user_ids":[2],"reason":"Arbitrary eligible move"},"PATCH").status_code,409)
        with self.app.app_context():
            self.assertIsNone(Users.query.get(3).team_id)

    def test_onboarding_generated_placeholder_must_change_but_meaningful_name_can_confirm(self):
        self.open_onboarding(capacity=1)
        for client in (self.alice,self.bob,self.carol):
            self.ready_user(client)
        self.assertEqual(self.onboarding_action("close_checkin").status_code,200)
        self.apply_attendance(self.attendance_plan())
        own = self.bob.get(PREFIX+"/onboarding").json["data"]
        self.assertTrue(own["team"]["name"].startswith("Team "))
        response = self.post(self.bob,PREFIX+"/onboarding/name",{"name":own["team"]["name"].swapcase()+" ","confirm":True})
        self.assertEqual(response.status_code,400)
        self.assertIn("placeholder",response.json["error"])
        alice = self.alice.get(PREFIX+"/onboarding").json["data"]
        self.assertEqual(self.post(self.alice,PREFIX+"/onboarding/name",{"name":alice["team"]["name"],"confirm":True}).status_code,200)

    def test_onboarding_hidden_team_names_remain_reserved_when_creating_replacement(self):
        self.open_onboarding()
        with self.app.app_context():
            password = Users.query.get(2).password
            for uid in range(5,23):
                db.session.execute(Users.__table__.insert(), {"id":uid,"name":f"Attendee {uid}","email":f"attendee{uid}@example.test","password":password,"type":"user"})
            teams = Teams.query.order_by(Teams.id).all()
            for index in range(3):
                team = Teams(name=f"Team {index+3:02}")
                db.session.add(team)
                db.session.flush()
                teams.append(team)
            for index,team in enumerate(teams,1):
                team.name = f"Team {index:02}"
            hidden_id = teams[0].id
            for index,uid in enumerate(range(2,23)):
                Users.query.get(uid).team_id = teams[index//5].id
                db.session.add(QuestReadiness(user_id=uid))
            db.session.commit()
        self.assertEqual(self.post(self.admin,f"/api/v1/teams/{hidden_id}",{"hidden":True},"PATCH").status_code,200)
        self.assertEqual(self.onboarding_action("close_checkin").status_code,200)
        plan = self.attendance_plan()
        fresh = [group for group in plan["groups"] if group["team_id"] is None]
        self.assertEqual(len(fresh),1)
        self.assertEqual(fresh[0]["name"],"Team 06")
        self.apply_attendance(plan)
        with self.app.app_context():
            self.assertTrue(Teams.query.get(hidden_id).hidden)
            self.assertEqual(Teams.query.get(hidden_id).name,"Team 01")
            self.assertEqual(Teams.query.count(),6)
            self.assertEqual(Users.query.filter(Users.type=="user",Users.team_id.isnot(None)).count(),21)
            self.assertEqual(Teams.query.filter_by(name="Team 06").count(),1)
            self.assertEqual(QuestReadiness.query.count(),21)
