import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from modules.shared.auth.models import UserRole
from modules.shared.auth.service import AuthService


class AuthServiceTest(unittest.TestCase):
    @patch.dict('os.environ', {'BOOTSTRAP_ADMIN_EMAIL': 'admin@platform.internal', 'BOOTSTRAP_ADMIN_PASSWORD': 'admin123'})
    def test_jwt_session_is_persisted_and_revocable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database = root / "auth.db"
            service = AuthService(
                users_file=root / "users.json",
                auth_db_file=database,
            )

            login = service.authenticate(
                "admin@platform.internal",
                "admin123",
                UserRole.ADMIN,
            )
            status = service.token_status(login.access_token)

            self.assertEqual(login.access_token.count("."), 2)
            self.assertIs(status["stored"], True)

            connection = sqlite3.connect(database)
            try:
                stored_hash, revoked_at = connection.execute(
                    "SELECT token_hash, revoked_at FROM auth_tokens WHERE jti = ?",
                    (status["jti"],),
                ).fetchone()
            finally:
                connection.close()
            self.assertNotEqual(stored_hash, login.access_token)
            self.assertIsNone(revoked_at)

            service.revoke_token(login.access_token)
            with self.assertRaisesRegex(ValueError, "missing, expired, or revoked"):
                service.decode_token(login.access_token)


if __name__ == "__main__":
    unittest.main()
