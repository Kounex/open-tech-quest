"""Attendance optimizer acceptance rules, independent of CTFd dependencies."""
import importlib.util
from pathlib import Path
import unittest

path = Path(__file__).resolve().parents[1] / "plugin/open_tech_quest/onboarding_math.py"
if not path.exists():
    path = Path("/opt/CTFd/CTFd/plugins/open_tech_quest/onboarding_math.py")
spec = importlib.util.spec_from_file_location("quest_onboarding_math", path)
math = importlib.util.module_from_spec(spec)
spec.loader.exec_module(math)


class AttendanceMath(unittest.TestCase):
    def plan(self, sizes, total, capacity):
        teams = [{"id": i+1, "name": f"Team {i+1}"} for i in range(len(sizes))]
        memberships, uid = {}, 1
        for tid, count in enumerate(sizes, 1):
            for _ in range(count):
                memberships[uid] = tid
                uid += 1
        return math.optimize(range(1, total+1), memberships, teams, capacity), memberships

    def test_soft_minimum_and_small_tail(self):
        for count, expected in ((21, [5,4,4,4,4]), (22,[5,5,4,4,4]), (11,[4,4,3])):
            (groups, warnings), _ = self.plan([], count, 5)
            self.assertEqual(sorted((len(g["user_ids"]) for g in groups), reverse=True), expected)
            self.assertEqual(bool(warnings), count == 11)

    def test_keep_full_groups_and_do_not_move_valid_nines(self):
        (groups, _), _ = self.plan([10,10], 36, 10)
        self.assertEqual([len(g["user_ids"]) for g in groups], [10,10,8,8])
        (groups, _), memberships = self.plan([9,9,9,9], 36, 10)
        self.assertTrue(all(memberships[uid] == group["team_id"] for group in groups for uid in group["user_ids"]))
        (groups, _), memberships = self.plan([10,9,9,8], 36, 10)
        self.assertTrue(all(memberships[uid] == group["team_id"] for group in groups for uid in group["user_ids"]))

    def test_full_groups_only_move_the_three_necessary_people(self):
        (groups, _), memberships = self.plan([5,5,5,5,1], 21, 5)
        self.assertEqual(sorted(len(g["user_ids"]) for g in groups), [4,4,4,4,5])
        self.assertEqual(sum(memberships[uid] != group["team_id"] for group in groups for uid in group["user_ids"]), 3)
        self.assertEqual(self.plan([5,5,5,5,1],21,5)[0][0], groups)

    def test_capacity_and_attendance_preserved_at_boundaries(self):
        for capacity in (1,2,5,10,50):
            for total in (1, capacity, capacity+1, 21, 103):
                (groups, _), _ = self.plan([], total, capacity)
                ids = [uid for group in groups for uid in group["user_ids"]]
                self.assertEqual(sorted(ids), list(range(1,total+1)))
                self.assertEqual(len(set(ids)), total)
                self.assertTrue(all(0 < len(g["user_ids"]) <= capacity for g in groups))
