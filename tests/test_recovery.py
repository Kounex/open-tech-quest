"""Preserve native history while eligible teammates replace banned solve credit."""
import json
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

import test_integration as integration
from CTFd.cache import cache
from CTFd.models import Fails, Solves, Submissions, Users, db
from CTFd.plugins.challenges import CHALLENGE_CLASSES
from CTFd.plugins.open_tech_quest import recovery
from CTFd.plugins.open_tech_quest.models import QuestAudit, QuestEvent, QuestStart
from CTFd.plugins.open_tech_quest.recovery_models import QuestRecoverySolve
from CTFd.plugins.open_tech_quest.service import Projection
from CTFd.utils import set_config

PREFIX = integration.PREFIX


class RecoveryIntegration(unittest.TestCase):
    setUpClass = classmethod(integration.QuestIntegration.setUpClass.__func__)
    tearDownClass = classmethod(integration.QuestIntegration.tearDownClass.__func__)
    client = integration.QuestIntegration.client
    post = integration.QuestIntegration.post
    configure = integration.QuestIntegration.configure
    action = integration.QuestIntegration.action
    start = integration.QuestIntegration.start
    solve = integration.QuestIntegration.solve

    def setUp(self):
        integration.QuestIntegration.setUp(self)
        self.action("start")
        self.start()
        self.assertEqual(self.solve(self.alice, 1).json["data"]["status"], "correct")
        with self.app.app_context():
            original = Solves.query.filter_by(challenge_id=1, team_id=self.team_id).one()
            self.original = (original.id, original.user_id, original.team_id,
                             original.challenge_id, original.date, original.provided)

    def access(self, uid, active, expected=200):
        rows = self.admin.get(PREFIX + "/admin/users").json["data"]["users"]
        identity = next(u["identity"] for u in rows if u["id"] == uid)
        response = self.post(self.admin, PREFIX + f"/admin/users/{uid}/access",
                             {"active": active, "confirm": True, "identity": identity}, "PATCH")
        self.assertEqual(response.status_code, expected, response.get_data(as_text=True))
        return response

    def room(self):
        return self.bob.get(PREFIX + "/rooms/openshift").json["data"]

    def assert_original_preserved(self):
        with self.app.app_context():
            original = Solves.query.get(self.original[0])
            self.assertEqual((original.id, original.user_id, original.team_id,
                              original.challenge_id, original.date, original.provided), self.original)

    def test_ban_reopens_only_affected_credit_and_correct_recovery_uses_native_grade(self):
        self.assertEqual(self.solve(self.bob, 2).json["data"]["status"], "correct")
        with self.app.app_context():
            starts_before = [(s.id, s.started_at) for s in QuestStart.query.all()]
        self.access(2, False)
        self.assertEqual(self.room()["progress"]["solved"], 0)
        self.assertEqual(self.room()["steps"][0]["state"], "available")
        detail = self.bob.get("/api/v1/challenges/1")
        self.assertFalse(detail.json["data"]["solved_by_me"])
        self.assertEqual(detail.json["data"]["solves"], 0)
        for path in ("/api/v1/challenges/2", "/api/v1/hints/1", "/files/known-hash/private.txt"):
            self.assertEqual(self.bob.get(path).status_code, 403)
        native = CHALLENGE_CLASSES["standard"]
        with patch.object(native, "attempt", wraps=native.attempt) as grader:
            response = self.solve(self.bob, 1)
            self.assertEqual(response.json["data"]["status"], "correct", response.get_data(as_text=True))
            self.assertEqual(grader.call_count, 1)
        self.assertEqual(self.room()["progress"]["solved"], 2)
        self.assertEqual(self.bob.get("/api/v1/challenges/2").status_code, 200)
        self.assertEqual(self.bob.get("/api/v1/hints/1").status_code, 200)
        self.assertTrue(self.bob.get("/api/v1/challenges/1").json["data"]["solved_by_me"])
        self.assertEqual(len(self.bob.get("/api/v1/challenges/1/solves").json["data"]), 1)
        with self.app.app_context():
            row = QuestRecoverySolve.query.one()
            self.assertEqual((row.user_id, row.team_id, row.challenge_id, row.original_solve_id),
                             (3, self.team_id, 1, self.original[0]))
            self.assertEqual(row.provided, "fixture-answer-1")
            self.assertEqual(Submissions.query.filter_by(type="quest_recovery").count(), 1)
            self.assertEqual(Solves.query.count(), 2)
            self.assertEqual([(s.id, s.started_at) for s in QuestStart.query.all()], starts_before)
            self.assertNotIn("fixture-answer", json.dumps([a.detail for a in QuestAudit.query.all()]))
        self.assert_original_preserved()

    def test_wrong_recovery_and_max_attempt_limit_use_native_fail_history(self):
        self.access(2, False)
        with self.app.app_context():
            recovery.Challenges.query.get(1).max_attempts = 1
            db.session.commit()
            cache.clear()
        self.bob = self.client(3)
        wrong = self.post(self.bob, "/api/v1/challenges/attempt", {"challenge_id": 1, "submission": "fixture-wrong"})
        self.assertEqual(wrong.json["data"]["status"], "incorrect")
        blocked = self.solve(self.bob, 1)
        self.assertEqual(blocked.json["data"]["status"], "ratelimited")
        self.assertEqual(blocked.status_code, 403)
        with self.app.app_context():
            self.assertEqual(QuestRecoverySolve.query.count(), 0)
            self.assertEqual(Fails.query.filter_by(user_id=3, challenge_id=1).count(), 1)
            self.assertEqual(Solves.query.count(), 1)
        self.assert_original_preserved()

    def test_native_incorrect_submission_rate_limit_still_applies(self):
        self.access(2, False)
        with self.app.app_context():
            set_config("incorrect_submissions_per_min", 1)
            cache.clear()
        self.bob = self.client(3)
        wrong = self.post(self.bob, "/api/v1/challenges/attempt", {"challenge_id": 1, "submission": "fixture-wrong"})
        self.assertEqual(wrong.json["data"]["status"], "incorrect")
        blocked = self.solve(self.bob, 1)
        self.assertEqual(blocked.status_code, 429)
        self.assertEqual(blocked.json["data"]["status"], "ratelimited")
        with self.app.app_context():
            self.assertEqual(QuestRecoverySolve.query.count(), 0)
        self.assert_original_preserved()

    def test_duplicate_concurrent_retries_create_one_credit(self):
        self.access(2, False)
        def retry(_):
            return self.solve(self.client(3), 1)
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(retry, range(2)))
        self.assertEqual(sorted(r.json["data"]["status"] for r in responses), ["already_solved", "correct"])
        with self.app.app_context():
            self.assertEqual(QuestRecoverySolve.query.count(), 1)
            self.assertEqual(Solves.query.count(), 1)
        self.assert_original_preserved()

    def test_repeated_contributor_bans_allow_another_teammate_and_unban_deduplicates(self):
        with self.app.app_context():
            db.session.add(Users(id=5, name="Third teammate", email="third@example.test", password="test-only",
                                 verified=True, team_id=self.team_id))
            db.session.commit()
        third = self.client(5)
        self.access(2, False)
        self.assertEqual(self.solve(self.bob, 1).json["data"]["status"], "correct")
        self.access(3, False)
        with self.app.app_context():
            self.assertNotIn(1, Projection().solves.get(self.team_id, {}))
        self.assertEqual(self.solve(third, 1).json["data"]["status"], "correct")
        with self.app.app_context():
            self.assertEqual(QuestRecoverySolve.query.count(), 2)
            self.assertEqual(len(Projection().solves[self.team_id]), 1)
        self.access(2, True)
        self.access(3, True)
        with self.app.app_context():
            self.assertEqual(Projection().solves[self.team_id][1], self.original[4])
            self.assertEqual(len(Projection().solves[self.team_id]), 1)
        self.assertEqual(self.solve(self.bob, 1).json["data"]["status"], "already_solved")
        self.assert_original_preserved()

    def test_paused_closed_cutoff_and_admin_preview_never_create_recovery(self):
        self.access(2, False)
        response = self.post(self.admin, "/api/v1/challenges/attempt?preview=true",
                             {"challenge_id": 1, "submission": "fixture-answer-1"})
        self.assertEqual(response.json["data"]["status"], "correct")
        self.action("pause")
        self.assertEqual(self.solve(self.bob, 1).status_code, 409)
        self.action("resume")
        self.action("close")
        self.assertEqual(self.solve(self.bob, 1).status_code, 409)
        with self.app.app_context():
            self.assertEqual(QuestRecoverySolve.query.count(), 0)
            self.assertEqual(Solves.query.count(), 1)
        self.assert_original_preserved()

    def test_recovery_rechecks_ban_and_event_after_native_grading(self):
        self.access(2, False)
        original_event = recovery.event
        def ban_while_waiting(lock=False):
            db.session.rollback()
            Users.query.get(3).banned = True
            db.session.commit()
            return original_event(lock=lock)
        with patch.object(recovery, "event", side_effect=ban_while_waiting):
            response = self.solve(self.bob, 1)
        self.assertEqual(response.status_code, 403)
        with self.app.app_context():
            self.assertEqual(QuestRecoverySolve.query.count(), 0)
        self.access(3, True)
        def pause_while_waiting(lock=False):
            db.session.rollback()
            QuestEvent.query.get(1).status = "paused"
            db.session.commit()
            return original_event(lock=lock)
        with patch.object(recovery, "event", side_effect=pause_while_waiting):
            response = self.solve(self.bob, 1)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json["data"]["status"], "paused")
        with self.app.app_context():
            self.assertEqual(QuestRecoverySolve.query.count(), 0)
            self.assertEqual(Fails.query.count(), 0)
        self.assert_original_preserved()

    def test_cross_team_cannot_replace_other_teams_credit(self):
        self.access(2, False)
        self.start(self.carol)
        self.assertEqual(self.solve(self.carol, 1).json["data"]["status"], "correct")
        with self.app.app_context():
            self.assertEqual(QuestRecoverySolve.query.count(), 0)
            self.assertEqual(Solves.query.count(), 2)
            self.assertNotIn(1, Projection().solves.get(self.team_id, {}))
        self.assertEqual(self.room()["progress"]["solved"], 0)
        self.assert_original_preserved()

    def test_published_contributor_access_changes_require_unpublish(self):
        self.access(2, False)
        self.assertEqual(self.solve(self.bob, 1).json["data"]["status"], "correct")
        self.action("close")
        self.action("publish")
        self.access(3, False, expected=409)
        self.access(2, True, expected=409)
        self.access(2, False)
        with self.app.app_context():
            self.assertFalse(Users.query.get(3).banned)
            self.assertTrue(Users.query.get(2).banned)
            self.assertEqual(QuestRecoverySolve.query.count(), 1)
        self.assert_original_preserved()
