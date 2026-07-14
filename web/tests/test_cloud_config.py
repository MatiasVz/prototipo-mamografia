import unittest

from web.app.config import normalize_database_url


class CloudConfigTests(unittest.TestCase):
    def test_normalizes_neon_postgresql_url_without_dropping_tls_query(self):
        url = (
            "postgresql://owner:secret@db.example/neondb"
            "?sslmode=require&channel_binding=require"
        )

        normalized = normalize_database_url(url)

        self.assertEqual(
            normalized,
            (
                "postgresql+psycopg://owner:secret@db.example/neondb"
                "?sslmode=require&channel_binding=require"
            ),
        )

    def test_keeps_explicit_sqlalchemy_driver(self):
        url = "postgresql+psycopg://owner:secret@db.example/neondb"

        self.assertEqual(normalize_database_url(url), url)


if __name__ == "__main__":
    unittest.main()
