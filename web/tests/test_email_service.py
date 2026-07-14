import json
import unittest
from unittest.mock import patch

from flask import Flask

from web.app.services.email_service import EmailDeliveryError, send_email


class FakeResponse:
    status = 201

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False


class BrevoEmailServiceTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(
            MAIL_BACKEND="brevo",
            BREVO_API_URL="https://api.brevo.test/v3/smtp/email",
            BREVO_API_KEY="private-test-key",
            BREVO_SENDER_NAME="Prototipo Mamografico",
            BREVO_SENDER_EMAIL="sender@example.com",
        )

    def test_sends_transactional_email_with_verified_sender(self):
        captured_request = None

        def fake_urlopen(request, timeout):
            nonlocal captured_request
            captured_request = request
            self.assertEqual(timeout, 20)
            return FakeResponse()

        with self.app.app_context(), patch(
            "web.app.services.email_service.urlopen",
            side_effect=fake_urlopen,
        ):
            send_email("user@example.com", "Caso completado", "Resultados listos")

        payload = json.loads(captured_request.data.decode("utf-8"))
        self.assertEqual(payload["sender"]["email"], "sender@example.com")
        self.assertEqual(payload["to"], [{"email": "user@example.com"}])
        self.assertEqual(payload["textContent"], "Resultados listos")
        self.assertEqual(captured_request.headers["Api-key"], "private-test-key")

    def test_rejects_incomplete_configuration_without_exposing_key(self):
        self.app.config["BREVO_SENDER_EMAIL"] = ""

        with self.app.app_context(), self.assertRaises(EmailDeliveryError) as context:
            send_email("user@example.com", "Caso", "Contenido")

        self.assertNotIn("private-test-key", str(context.exception))


if __name__ == "__main__":
    unittest.main()
