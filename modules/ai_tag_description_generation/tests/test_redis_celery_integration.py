import unittest

from modules.ai_tag_description_generation.app.config import Settings


BASE_SETTINGS = {
    "DATABASE_URL": "postgresql+asyncpg://user:pass@localhost/test",
    "DATABASE_URL_SYNC": "postgresql+psycopg2://user:pass@localhost/test",
    "QDRANT_URL": "http://localhost:6333",
}


class RedisSettingsTests(unittest.TestCase):
    def test_legacy_redis_url_is_used_for_all_roles(self) -> None:
        settings = Settings(
            **BASE_SETTINGS,
            REDIS_URL="redis://legacy:6379/0",
            _env_file=None,
        )

        self.assertEqual(settings.CELERY_BROKER_URL, "redis://legacy:6379/0")
        self.assertEqual(settings.CELERY_RESULT_BACKEND, "redis://legacy:6379/0")
        self.assertEqual(settings.EVENT_REDIS_URL, "redis://legacy:6379/0")

    def test_role_specific_redis_urls_override_fallback(self) -> None:
        settings = Settings(
            **BASE_SETTINGS,
            REDIS_URL="redis://legacy:6379/0",
            CELERY_BROKER_URL="redis://broker:6379/0",
            CELERY_RESULT_BACKEND="redis://results:6379/1",
            EVENT_REDIS_URL="redis://events:6379/2",
            _env_file=None,
        )

        self.assertEqual(settings.CELERY_BROKER_URL, "redis://broker:6379/0")
        self.assertEqual(settings.CELERY_RESULT_BACKEND, "redis://results:6379/1")
        self.assertEqual(settings.EVENT_REDIS_URL, "redis://events:6379/2")


if __name__ == "__main__":
    unittest.main()
