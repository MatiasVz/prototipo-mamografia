import unittest
from unittest.mock import patch

from web.app import create_app
from web.app.services.health_service import RuntimeHealth


class HealthTestConfig:
    TESTING = True
    SECRET_KEY = "test-secret"
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {}
    REDIS_URL = "redis://localhost:6379/0"
    STORAGE_BACKEND = "local"
    APP_VERSION = "test-version"


class HealthRouteTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(HealthTestConfig)
        self.client = self.app.test_client()

    def test_liveness_does_not_depend_on_external_services(self):
        response = self.client.get("/health/live")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_json(),
            {"status": "ok", "version": "test-version"},
        )

    def test_readiness_reports_available_dependencies(self):
        health = RuntimeHealth(database=True, queue=True, storage=True)

        with patch(
            "web.app.routes.health.check_runtime_dependencies",
            return_value=health,
        ):
            response = self.client.get("/health/ready")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["status"], "ready")
        self.assertEqual(response.get_json()["version"], "test-version")
        self.assertEqual(
            response.get_json()["checks"],
            {"database": "ok", "queue": "ok", "storage": "ok"},
        )

    def test_readiness_returns_503_without_leaking_connection_details(self):
        health = RuntimeHealth(database=True, queue=False, storage=True)

        with patch(
            "web.app.routes.health.check_runtime_dependencies",
            return_value=health,
        ):
            response = self.client.get("/health/ready")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.get_json()["status"], "unavailable")
        self.assertNotIn("redis://", response.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
