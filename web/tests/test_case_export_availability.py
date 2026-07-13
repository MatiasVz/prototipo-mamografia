import unittest
from types import SimpleNamespace
from unittest.mock import patch

from flask import Flask

from web.app.models import CaseStatus
from web.app.routes import upload as upload_routes


class CaseExportAvailabilityTests(unittest.TestCase):
    def setUp(self):
        app = Flask(__name__)
        app.config.update(SECRET_KEY="test-secret", TESTING=True)
        app.register_blueprint(upload_routes.upload_bp)
        self.client = app.test_client()
        self.case = SimpleNamespace(id=7, status=CaseStatus.REGISTERED)

    def test_incomplete_case_cannot_download_exports(self):
        export_paths = (
            "/mamografias/casos/7/exportar/reporte",
            "/mamografias/casos/7/exportar/reporte-md",
            "/mamografias/casos/7/exportar/paquete",
        )

        with (
            patch.object(upload_routes, "require_authenticated_user", return_value=None),
            patch.object(upload_routes, "_get_owned_case", return_value=self.case),
            patch.object(upload_routes, "_has_completed_results", return_value=False),
            patch.object(upload_routes, "build_case_pdf_report") as build_pdf,
            patch.object(upload_routes, "build_case_export_bundle") as build_bundle,
        ):
            for path in export_paths:
                response = self.client.get(path)

                self.assertEqual(response.status_code, 302)
                self.assertTrue(response.headers["Location"].endswith("/mamografias/casos/7"))

        build_pdf.assert_not_called()
        build_bundle.assert_not_called()


if __name__ == "__main__":
    unittest.main()
