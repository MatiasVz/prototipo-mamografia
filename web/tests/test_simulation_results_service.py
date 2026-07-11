import tempfile
import unittest
from pathlib import Path

from web.app.services.simulation_results_service import _read_autocorrelation_rows


class VelocityAutocorrelationResultTests(unittest.TestCase):
    def test_reads_normalized_cv_from_current_output(self):
        rows = _read_rows(
            "lag\ttime\tcv_raw\tcv_normalized\tsample_count\tmdc_cumulative\n"
            "0\t0\t2.0\t1.0\t75000\t0\n"
            "1\t1\t0.4\t0.2\t75000\t0.6\n"
        )

        self.assertEqual(rows[0]["cv"], "1")
        self.assertEqual(rows[1]["cv"], "0.2")

    def test_keeps_compatibility_with_legacy_cv_column(self):
        rows = _read_rows(
            "lag\ttime\tcv\tsample_count\n"
            "0\t0\t1.0\t500\n"
        )

        self.assertEqual(rows[0]["cv"], "1")


def _read_rows(content):
    with tempfile.TemporaryDirectory() as temporary_directory:
        path = Path(temporary_directory) / "velocity_autocorrelation.tsv"
        path.write_text(content, encoding="utf-8")
        return _read_autocorrelation_rows(path)


if __name__ == "__main__":
    unittest.main()
