import unittest
from pathlib import Path

from deploy.check_repository_secrets import (
    is_forbidden_environment_file,
    scan_text,
)


class RepositorySecretScanTests(unittest.TestCase):
    def test_detects_provider_token_without_printing_its_value(self):
        findings = scan_text(Path("sample.txt"), "BREVO_API_KEY=xkeysib-" + "a" * 40)

        self.assertTrue(findings)
        self.assertTrue(all("xkeysib" not in reason for _, reason in findings))

    def test_allows_documented_placeholders(self):
        text = "\n".join(
            (
                "SECRET_KEY=replace-with-a-long-random-value",
                "DATABASE_URL=postgresql://user:password@example.invalid/database",
            )
        )

        self.assertEqual(scan_text(Path("production.env.example"), text), [])

    def test_rejects_real_environment_files(self):
        self.assertTrue(is_forbidden_environment_file(Path(".env.production")))
        self.assertFalse(is_forbidden_environment_file(Path(".env.example")))
        self.assertFalse(
            is_forbidden_environment_file(Path("production.env.example"))
        )


if __name__ == "__main__":
    unittest.main()
