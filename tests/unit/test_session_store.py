import tempfile
import unittest
from pathlib import Path

from simulateinput.core.session import SessionStore


class SessionStoreTest(unittest.TestCase):
    def test_start_and_get_session(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            store = SessionStore(root=Path(temp_dir) / "sessions")
            started = store.start(profile_name="lab_default", operator="tester")

            loaded = store.get(started.session_id)

            self.assertEqual(loaded.session_id, started.session_id)
            self.assertEqual(loaded.profile, "lab_default")
            self.assertEqual(loaded.operator, "tester")
