import tempfile
import unittest
from pathlib import Path

from deploy.validate_env import load_environment, validate_environment


class DeploymentEnvironmentTests(unittest.TestCase):
    def test_accepts_expected_production_configuration(self):
        values = self._valid_values()

        self.assertEqual(validate_environment(values), [])

    def test_rejects_plain_redis_and_incorrect_worker_parameters(self):
        values = self._valid_values()
        values["REDIS_URL"] = "redis://queue.example:6379"
        values["SIMULATION_CPU_THREADS"] = "6"

        errors = validate_environment(values)

        self.assertTrue(any("REDIS_URL" in error for error in errors))
        self.assertTrue(any("SIMULATION_CPU_THREADS" in error for error in errors))

    def test_loader_keeps_urls_without_exposing_or_rewriting_values(self):
        content = "DATABASE_URL='postgresql://user:secret@db.example/db?sslmode=require'\n"
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / ".env.production"
            path.write_text(content, encoding="utf-8")

            values = load_environment(path)

        self.assertEqual(
            values["DATABASE_URL"],
            "postgresql://user:secret@db.example/db?sslmode=require",
        )

    @staticmethod
    def _valid_values():
        return {
            "PUBLIC_BASE_URL": "https://app.example",
            "SECRET_KEY": "secret",
            "DATABASE_URL": "postgresql://user:password@db.example/database",
            "REDIS_URL": "rediss://default:password@queue.example:6379",
            "STORAGE_BACKEND": "r2",
            "R2_BUCKET_NAME": "private-bucket",
            "R2_ENDPOINT_URL": "https://account.r2.cloudflarestorage.com",
            "R2_ACCESS_KEY_ID": "access-key",
            "R2_SECRET_ACCESS_KEY": "secret-key",
            "MAIL_BACKEND": "brevo",
            "BREVO_API_KEY": "api-key",
            "BREVO_SENDER_NAME": "Sender",
            "BREVO_SENDER_EMAIL": "sender@example.com",
            "SIMULATION_DEFAULT_STEPS": "200",
            "SIMULATION_DEFAULT_REALIZATIONS": "3",
            "SIMULATION_DEFAULT_LABELED_PARTICLES": "500",
            "SIMULATION_DEFAULT_OUTPUT_TIMES": "0,200",
            "SIMULATION_TIMEOUT_SECONDS": "0",
            "SIMULATION_CPU_THREADS": "30",
            "WORKER_CPU_LIMIT": "30",
        }


if __name__ == "__main__":
    unittest.main()
