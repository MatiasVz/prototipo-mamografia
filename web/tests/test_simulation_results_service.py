import tempfile
import unittest
from pathlib import Path

from web.app.services.simulation_results_service import (
    _read_autocorrelation_rows,
    build_mpc_results_view,
    get_result_image_path,
)


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


class MpcConcentrationResultTests(unittest.TestCase):
    def test_builds_distinct_representative_mean_and_threshold_maps(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            results_dir = Path(temporary_directory)
            (results_dir / "mpc_concentration_summary.txt").write_text(
                "captured_output_times=0,100\n",
                encoding="utf-8",
            )
            for time_value in (0, 100):
                for filename in (
                    f"mpc_concentration_representative_t_{time_value}.pgm",
                    f"mpc_concentration_mean_t_{time_value}.pgm",
                    f"mpc_high_concentration_mean_t_{time_value}.pgm",
                ):
                    (results_dir / filename).write_text("P2\n1 1\n255\n0\n", encoding="utf-8")

            view = build_mpc_results_view(results_dir)
            keys = {result_map["key"] for result_map in view["concentration_maps"]}

            self.assertTrue(view["available"])
            self.assertEqual(len(keys), 6)
            self.assertIn("mpc_concentration_representative_t_100", keys)
            self.assertIn("mpc_concentration_mean_t_100", keys)
            self.assertIn("mpc_high_concentration_mean_t_100", keys)

    def test_does_not_present_legacy_random_walk_density_map(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            results_dir = Path(temporary_directory)
            (results_dir / "density_map.pgm").write_text(
                "P2\n1 1\n255\n255\n",
                encoding="utf-8",
            )

            view = build_mpc_results_view(results_dir)

            self.assertFalse(view["available"])
            self.assertEqual(view["domain_maps"], ())
            self.assertIsNone(get_result_image_path(results_dir, "density_map"))


def _read_rows(content):
    with tempfile.TemporaryDirectory() as temporary_directory:
        path = Path(temporary_directory) / "velocity_autocorrelation.tsv"
        path.write_text(content, encoding="utf-8")
        return _read_autocorrelation_rows(path)


if __name__ == "__main__":
    unittest.main()
