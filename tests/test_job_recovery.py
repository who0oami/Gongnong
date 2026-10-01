from datetime import datetime
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from services.job_repository import fail_incomplete_jobs_created_before


class JobRecoveryTests(unittest.TestCase):
    def test_recovery_commits_and_returns_affected_count(self):
        db = Mock()
        db.execute.return_value.rowcount = 3

        count = fail_incomplete_jobs_created_before(db, datetime(2026, 1, 1))

        self.assertEqual(count, 3)
        db.execute.assert_called_once()
        db.commit.assert_called_once()


if __name__ == "__main__":
    unittest.main()
