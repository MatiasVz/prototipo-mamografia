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
    def test_builds_only_initial_and_final_scientific_maps(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            results_dir = Path(temporary_directory)
            (results_dir / "mpc_concentration_summary.txt").write_text(
                "captured_output_times=0,100\n"
                "realizations=3\n"
                "representative_realization_index=1\n"
                "representative_seed=1234\n"
                "high_concentration_threshold=20\n"
                "snapshot_t_0_high_concentration_cell_count=0\n"
                "snapshot_t_100_high_concentration_cell_count=2\n",
                encoding="utf-8",
            )
            (results_dir / "mpc_config.json").write_text(
                '{"domain_cell_count": 10}',
                encoding="utf-8",
            )
            for time_value in (0, 100):
                for filename in (
                    f"mpc_concentration_scientific_t_{time_value}.ppm",
                    f"mpc_concentration_representative_t_{time_value}.pgm",
                    f"mpc_concentration_mean_t_{time_value}.pgm",
                    f"mpc_high_concentration_mean_t_{time_value}.pgm",
                ):
                    (results_dir / filename).write_text("P2\n1 1\n255\n0\n", encoding="utf-8")

            view = build_mpc_results_view(results_dir)
            keys = {result_map["key"] for result_map in view["concentration_maps"]}

            self.assertTrue(view["available"])
            self.assertEqual(len(keys), 2)
            self.assertEqual(
                keys,
                {
                    "mpc_concentration_scientific_t_0",
                    "mpc_concentration_scientific_t_100",
                },
            )
            final_map = next(
                result_map
                for result_map in view["concentration_maps"]
                if result_map["key"] == "mpc_concentration_scientific_t_100"
            )
            self.assertIn("Rojo", final_map["legend"][-1])
            self.assertIn("semilla 1234", final_map["sampling_note"])

    def test_generates_normalized_cv_chart_with_characteristic_time(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            results_dir = Path(temporary_directory)
            (results_dir / "velocity_autocorrelation.tsv").write_text(
                "lag\ttime\tcv_raw\tcv_normalized\tsample_count\tmdc_cumulative\n"
                "0\t0\t2.0\t1.0\t1500\t0\n"
                "1\t1\t0.7\t0.35\t1500\t0.5\n"
                "2\t2\t0.2\t0.1\t1500\t0.7\n",
                encoding="utf-8",
            )
            (results_dir / "velocity_autocorrelation_summary.txt").write_text(
                "characteristic_time=0.75\n",
                encoding="utf-8",
            )

            view = build_mpc_results_view(results_dir)

            self.assertIsNotNone(view["autocorrelation_chart"])
            self.assertEqual(
                view["autocorrelation_chart"]["key"],
                "velocity_autocorrelation_chart",
            )
            self.assertIn("0.75", view["autocorrelation_chart"]["sampling_note"])
            self.assertTrue((results_dir / "velocity_autocorrelation_chart.png").exists())

    def test_includes_radius_top_view_with_visualization_metadata(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            results_dir = Path(temporary_directory)
            (results_dir / "simulation_radius_top_view.png").write_bytes(b"result")
            (results_dir / "simulation_box_visualization.txt").write_text(
                "section_columns=12\nsection_rows=8\nvisualized_cylinder_count=96\n",
                encoding="utf-8",
            )

            view = build_mpc_results_view(results_dir)
            top_view = next(
                result_map
                for result_map in view["domain_maps"]
                if result_map["key"] == "simulation_radius_top_view"
            )

            self.assertIn("12 x 8", top_view["sampling_note"])
            self.assertIn("96", top_view["sampling_note"])

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
