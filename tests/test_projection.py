"""Bound participant history without changing native credit or prize rules."""
from datetime import datetime
import unittest

import test_integration as integration
from CTFd.models import Solves, Users, db
from CTFd.plugins.open_tech_quest.models import QuestCorrection
from CTFd.plugins.open_tech_quest.service import Projection, projection, solve_map


class ProjectionIntegration(unittest.TestCase):
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
        self.start(self.alice)
        self.start(self.carol)
        self.assertEqual(self.solve(self.alice, 1).json["data"]["status"], "correct")
        self.assertEqual(self.solve(self.carol, 1).json["data"]["status"], "correct")
        self.assertEqual(self.solve(self.carol, 2).json["data"]["status"], "correct")

    def test_team_scope_matches_global_progress_without_other_team_history(self):
        with self.app.app_context():
            full = Projection()
            room = full.rooms[0]
            db.session.add(QuestCorrection(team_id=self.other_id, room_id=room.id,
                                           adjustment_ms=123, reason="Other team fixture"))
            db.session.commit()
            full = Projection()
            own = Projection(team_id=self.team_id)
            own.at = full.at
            self.assertEqual(set(own.solves), {self.team_id})
            self.assertTrue(all(tid == self.team_id for tid, rid in own.starts))
            self.assertNotIn((self.other_id, room.id), own.corrections)
            self.assertEqual(own.room(room, self.team_id), full.room(room, self.team_id))
            anonymous = Projection(team_id=0)
            self.assertEqual(anonymous.solves, {})
            self.assertEqual(anonymous.starts, {})

    def test_native_challenge_counts_keep_other_teams_and_fresh_ban_filter(self):
        detail = self.bob.get("/api/v1/challenges/1")
        self.assertEqual(detail.status_code, 200)
        self.assertTrue(detail.json["data"]["solved_by_me"])
        self.assertEqual(detail.json["data"]["solves"], 2)
        with self.app.app_context():
            single = Projection(challenge_id=1)
            self.assertEqual(set(single.solves), {self.team_id, self.other_id})
            self.assertTrue(all(set(credit) == {1} for credit in single.solves.values()))
            Users.query.get(2).banned = True
            db.session.commit()
        # Bob remains active, but Alice's original credit must immediately stop
        # unlocking his path and counting toward the public native total.
        detail = self.bob.get("/api/v1/challenges/1")
        self.assertEqual(detail.status_code, 200)
        self.assertFalse(detail.json["data"]["solved_by_me"])
        self.assertEqual(detail.json["data"]["solves"], 1)
        self.assertEqual(self.bob.get("/api/v1/challenges/2").status_code, 403)

    def test_http_views_do_not_reuse_other_users_or_prior_request_progress(self):
        def solved(client):
            data = client.get(integration.PREFIX + "/bootstrap").json["data"]
            return data["rooms"][0]["progress"]["solved"]
        self.assertEqual(solved(self.alice), 1)
        self.assertEqual(solved(self.carol), 2)
        self.assertEqual(solved(self.guest), 0)
        self.assertEqual(self.solve(self.bob, 2).json["data"]["status"], "correct")
        self.assertEqual(solved(self.alice), 2)

    def test_request_reuse_is_scoped_and_never_used_across_write_commits(self):
        with self.app.test_request_context(method="GET"):
            red = projection(team_id=self.team_id)
            self.assertIs(red, projection(team_id=self.team_id))
            self.assertNotIn(self.other_id, projection(team_id=self.team_id).solves)
            self.assertIn(self.other_id, projection(team_id=self.other_id).solves)
            self.assertEqual(set(projection(challenge_id=1).solves[self.other_id]), {1})
        with self.app.test_request_context(method="POST"):
            self.assertNotIn(2, solve_map(team_id=self.team_id)[self.team_id])
            db.session.add(Solves(challenge_id=2, user_id=3, team_id=self.team_id,
                                  date=datetime.utcnow()))
            db.session.commit()
            self.assertIn(2, solve_map(team_id=self.team_id)[self.team_id])
