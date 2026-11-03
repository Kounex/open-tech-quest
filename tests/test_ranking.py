"""Fast pure-rule tests; runnable without CTFd dependencies."""
import importlib.util
from pathlib import Path
import unittest
from datetime import datetime, timedelta

path = Path(__file__).resolve().parents[1] / "plugin/open_tech_quest/ranking.py"
if not path.exists():
    path = Path("/opt/CTFd/CTFd/plugins/open_tech_quest/ranking.py")
spec = importlib.util.spec_from_file_location("quest_ranking", path)
rules = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rules)


class RankingRules(unittest.TestCase):
    def test_only_consecutive_prefix_earns_room_progress(self):
        at = datetime(2026, 11, 3)
        self.assertEqual(rules.prefix([1, 2, 3], {1: at, 3: at}), [at])
        self.assertEqual(rules.prefix([1, 2], {2: at}), [])

    def test_pause_clipped_to_clock_interval_and_open_pause(self):
        at = datetime(2026, 11, 3)
        self.assertEqual(rules.active_ms(at, at + timedelta(seconds=100), [(at - timedelta(seconds=10), at + timedelta(seconds=20)), (at + timedelta(seconds=90), None)]), 70000)
        self.assertIsNone(rules.active_ms(at, None, []))

    def test_competition_ties_and_zero_solve_ineligibility(self):
        rows = [{"id": i, "count": count, "time": duration} for i, count, duration in ((1, 2, 100), (2, 2, 100), (3, 1, 10), (4, 0, None))]
        self.assertEqual([r["rank"] for r in rules.assign_ranks(rows, "count", "time")], [1, 1, 3, None])
