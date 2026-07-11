import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from web.app.services.simulation_comparison_service import build_case_comparison


class SimulationComparisonTests(unittest.TestCase):
    def test_compares_corrected_metrics_and_equivalent_mpc_maps(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            results_a = _write_case_results(root / "case_a", mdc=0.5, tau_c=0.4)
            results_b = _write_case_results(root / "case_b", mdc=0.6, tau_c=0.6)

            comparison = build_case_comparison(
                _case(1),
                _case(2),
                results_a,
                results_b,
            )

            self.assertTrue(comparison["available"])
            self.assertTrue(comparison["compatible"])
            self.assertEqual(len(comparison["metric_rows"]), 8)
            self.assertEqual(len(comparison["parameter_rows"]), 12)

            rows = {row["label"]: row for row in comparison["metric_rows"]}
            self.assertEqual(rows["Difusión calculada (MDC)"]["delta"], "+0.1")
            self.assertEqual(
                rows["Difusión calculada (MDC)"]["relative_delta"],
                "+20.00%",
            )
            self.assertEqual(rows["Tiempo característico (tauC)"]["delta"], "+0.2")

            map_keys = {map_pair["key"] for map_pair in comparison["map_pairs"]}
            self.assertEqual(
                map_keys,
                {
                    "simulation_box_3d",
                    "domain_mask",
                    "obstacle_radius_map",
                    "mpc_concentration_mean_t_100",
                },
            )

    def test_rejects_cases_with_different_simulation_configuration(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            results_a = _write_case_results(root / "case_a", mdc=0.5, tau_c=0.4)
            results_b = _write_case_results(
                root / "case_b",
                mdc=0.6,
                tau_c=0.6,
                steps=200,
            )

            comparison = build_case_comparison(
                _case(1),
                _case(2),
                results_a,
                results_b,
            )

            self.assertFalse(comparison["available"])
            self.assertFalse(comparison["compatible"])
            self.assertTrue(
                any("Pasos ejecutados" in error for error in comparison["errors"]),
            )


def _case(case_id):
    return SimpleNamespace(
        id=case_id,
        status="completado",
        created_at=datetime(2026, 7, case_id, tzinfo=timezone.utc),
        input_mode="roi_recortada",
        simulation_input_file_path=f"storage/uploads/case_{case_id}/simulation_input.pgm",
    )


def _write_case_results(directory, *, mdc, tau_c, steps=100):
    directory.mkdir(parents=True)
    config = {
        "steps": steps,
        "n0": 10.0,
        "tau": 1.0,
        "kbt": 1.0,
        "mass": 1.0,
        "realizations": 3,
        "velocity_autocorrelation_labeled_particle_count": 500,
        "correlation_initial_times": 50,
        "rotation_angle": 1.5707963267948966,
        "rotation_policy": "random_axis_xyz_and_random_sign_plus_minus_angle",
        "output_times": [0, 100],
        "grid_shift_enabled": False,
    }
    diffusion = {
        "mdc": mdc,
        "mdc0": 1.0,
        "mdc_star": mdc,
        "characteristic_time": tau_c,
        "mdc_standard_deviation": 0.03,
        "mdc_standard_error": 0.017320508,
        "mdc_star_standard_deviation": 0.03,
        "mdc_star_standard_error": 0.017320508,
    }
    (directory / "mpc_config.json").write_text(json.dumps(config), encoding="utf-8")
    (directory / "diffusion_metrics.json").write_text(
        json.dumps(diffusion),
        encoding="utf-8",
    )
    (directory / "mpc_concentration_summary.txt").write_text(
        "captured_output_times=0,100\n",
        encoding="utf-8",
    )
    for filename in (
        "simulation_box_3d.png",
        "domain_mask.pgm",
        "obstacle_radius_map.pgm",
        "mpc_concentration_mean_t_100.pgm",
    ):
        (directory / filename).write_bytes(b"result")

    return directory


if __name__ == "__main__":
    unittest.main()
