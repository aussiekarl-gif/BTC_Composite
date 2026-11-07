"""Offline local-git race simulations; never touch real GitHub or market data."""
from __future__ import annotations

import pathlib
import subprocess
import tempfile
import unittest

from engines.research.cycle_forward_publish_guard import PublicationBlocked, publish


def git(repo, *args):
    return subprocess.run(["git", *args], cwd=repo, check=True,
                          capture_output=True, text=True).stdout.strip()


class PublicationGuardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = pathlib.Path(self.temp.name)
        self.remote = root / "remote.git"
        git(root, "init", "--bare", "--initial-branch=main", str(self.remote))
        seed = root / "seed"
        git(root, "clone", str(self.remote), str(seed))
        git(seed, "config", "user.email", "test@example.test")
        git(seed, "config", "user.name", "Test")
        p = seed / "data/research_forward_validation/cycle_market_signals.csv"
        p.parent.mkdir(parents=True)
        p.write_text("seed\n")
        git(seed, "add", ".")
        git(seed, "commit", "-m", "seed")
        git(seed, "push", "origin", "HEAD:main")
        self.worker = root / "worker"
        self.other = root / "other"
        for clone in (self.worker, self.other):
            git(root, "clone", str(self.remote), str(clone))
            git(clone, "config", "user.email", "test@example.test")
            git(clone, "config", "user.name", "Test")
        self.data_path = "data/research_forward_validation/cycle_market_signals.csv"

    def commit(self, repo, path, text):
        target = repo / path
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("a") as f:
            f.write(text)
        git(repo, "add", path)
        git(repo, "commit", "-m", "prospective paper data")

    def test_unrelated_remote_advance_is_rebased_then_verified(self):
        self.commit(self.worker, self.data_path, "new paper record\n")
        self.commit(self.other, "docs/unrelated.txt", "other independent update\n")
        git(self.other, "push", "origin", "HEAD:main")
        verified = []
        result = publish(repo=self.worker, verify=lambda: verified.append(True), retry_delay=0)
        self.assertEqual(result, "PUBLISHED_VERIFIED_PAPER_DATA")
        self.assertEqual(len(verified), 1)
        git(self.other, "pull", "--ff-only")
        self.assertIn("new paper record", (self.other / self.data_path).read_text())
        self.assertTrue((self.other / "docs/unrelated.txt").exists())

    def test_same_tape_conflict_fails_closed_without_force(self):
        self.commit(self.worker, self.data_path, "worker record\n")
        self.commit(self.other, self.data_path, "other record\n")
        git(self.other, "push", "origin", "HEAD:main")
        with self.assertRaisesRegex(PublicationBlocked, "Concurrent source conflict"):
            publish(repo=self.worker, verify=lambda: None, retry_delay=0)
        self.assertIn("other record", git(self.other, "show", "HEAD:" + self.data_path))
        self.assertNotIn("worker record", git(self.other, "show", "HEAD:" + self.data_path))

    def test_validation_failure_never_pushes(self):
        self.commit(self.worker, self.data_path, "invalid row\n")
        original = git(self.worker, "rev-parse", "origin/main")
        def reject():
            raise ValueError("bad SHA chain")
        with self.assertRaisesRegex(PublicationBlocked, "validation failed"):
            publish(repo=self.worker, verify=reject, retry_delay=0)
        self.assertEqual(original, git(self.worker, "ls-remote", "origin", "refs/heads/main").split()[0])

    def test_non_research_path_never_pushed(self):
        self.commit(self.worker, "cycle_trading_daily_ntfy.py", "not allowed\n")
        with self.assertRaisesRegex(PublicationBlocked, "Unexpected publication paths"):
            publish(repo=self.worker, verify=lambda: None, retry_delay=0)

    def test_extra_staged_research_file_is_not_published(self):
        self.commit(self.worker, self.data_path, "new paper record\\n")
        self.commit(self.worker, "data/research_forward_validation/unexpected.csv",
                    "unexpected\\n")
        with self.assertRaisesRegex(PublicationBlocked, "Unexpected publication paths"):
            publish(repo=self.worker, verify=lambda: None, retry_delay=0)
        remote = git(self.worker, "ls-remote", "origin", "refs/heads/main").split()[0]
        self.assertEqual(remote, git(self.worker, "rev-parse", "origin/main"))

    def test_already_published_is_idempotent(self):
        self.commit(self.worker, self.data_path, "new record\n")
        self.assertEqual(publish(repo=self.worker, verify=lambda: None, retry_delay=0),
                         "PUBLISHED_VERIFIED_PAPER_DATA")
        self.assertEqual(publish(repo=self.worker, verify=lambda: None, retry_delay=0),
                         "ALREADY_PUBLISHED")


if __name__ == "__main__":
    unittest.main()
