import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from PIL import Image

from web.app.models import CaseStatus
from web.app.services.preview_service import (
    _scale_16_bit_monochrome_to_l,
    load_processing_image_for_path,
)
from web.app.services.simulation_preparation_service import (
    _normalize_simulation_image,
    prepare_simulation_input_for_case,
)


class SimulationImageNormalizationTests(unittest.TestCase):
    def test_preserves_original_grayscale_range_without_autocontrast(self):
        source = Image.new("L", (2, 1))
        source.putdata([40, 80])

        normalized = _normalize_simulation_image(source)

        self.assertEqual(list(normalized.getdata()), [40, 80])

    def test_converts_colored_pixels_with_stable_luminance(self):
        source = Image.new("RGB", (2, 1))
        source.putdata([(0, 0, 255), (255, 255, 255)])

        normalized = _normalize_simulation_image(source)

        self.assertEqual(list(normalized.getdata()), [29, 255])

    def test_composites_transparent_pixels_over_black(self):
        source = Image.new("RGBA", (2, 1))
        source.putdata([(255, 255, 255, 0), (255, 255, 255, 255)])

        normalized = _normalize_simulation_image(source)

        self.assertEqual(list(normalized.getdata()), [0, 255])

    def test_scales_high_depth_pgm_with_fixed_16_bit_range(self):
        source = Image.new("I", (3, 1))
        source.putdata([0, 32768, 65535])

        normalized = _normalize_simulation_image(source)

        self.assertEqual(list(normalized.getdata()), [0, 128, 255])

    def test_scales_dicom_with_bits_stored_range_instead_of_observed_extrema(self):
        dataset = SimpleNamespace(
            PixelRepresentation=0,
            BitsStored=12,
            file_meta=None,
        )
        pixel_data = b"".join(value.to_bytes(2, "little") for value in [0, 2048, 4095])

        normalized = _scale_16_bit_monochrome_to_l(
            dataset,
            pixel_data,
            1,
            3,
            use_stored_range=True,
        )

        self.assertEqual(list(normalized.getdata()), [0, 128, 255])


class SimulationPreparationTests(unittest.TestCase):
    def test_uses_full_source_resolution_and_writes_reproducible_evidence(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            upload_folder = Path(temporary_directory) / "storage" / "uploads"
            roi_directory = upload_folder / "case_7" / "roi"
            roi_directory.mkdir(parents=True)
            roi_path = roi_directory / "roi.pgm"

            source = Image.new("L", (1301, 2), color=40)
            source.putpixel((1300, 1), 80)
            source.save(roi_path, format="PPM")

            case = SimpleNamespace(
                id=7,
                status=CaseStatus.ROI_CONFIRMED,
                roi_file_path="storage/uploads/case_7/roi/roi.pgm",
                simulation_input_filename=None,
                simulation_input_file_path=None,
                simulation_input_file_type=None,
                simulation_input_size_bytes=None,
            )

            first_result = prepare_simulation_input_for_case(case, str(upload_folder))
            first_digest = _file_digest(first_result.absolute_path)
            second_result = prepare_simulation_input_for_case(case, str(upload_folder))
            second_digest = _file_digest(second_result.absolute_path)

            prepared_image = load_processing_image_for_path(second_result.absolute_path)
            try:
                self.assertEqual(prepared_image.size, (1301, 2))
                self.assertEqual(list(prepared_image.getdata())[-1], 80)
            finally:
                prepared_image.close()

            metadata_path = upload_folder / "case_7" / "simulation_preparation.json"
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))

            self.assertEqual(first_digest, second_digest)
            self.assertEqual(metadata["contrast_normalization"], "none")
            self.assertEqual(metadata["resolution_policy"], "full_source_resolution")
            self.assertEqual(metadata["output_width"], 1301)
            self.assertEqual(metadata["simulation_input_sha256"], second_digest)
            self.assertTrue(
                (upload_folder / "case_7" / "simulation_grayscale.png").exists()
            )

    def test_processing_loader_does_not_apply_preview_thumbnail(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            image_path = Path(temporary_directory) / "large.tiff"
            Image.new("L", (1400, 3), color=60).save(image_path)

            loaded_image = load_processing_image_for_path(image_path)
            try:
                self.assertIsNotNone(loaded_image)
                self.assertEqual(loaded_image.size, (1400, 3))
            finally:
                if loaded_image is not None:
                    loaded_image.close()

    def test_prepares_high_depth_pgm_without_saturating_intermediate_tones(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            image_path = Path(temporary_directory) / "high_depth.pgm"
            pixel_values = [0, 2048, 4095]
            pixel_bytes = b"".join(value.to_bytes(2, "big") for value in pixel_values)
            image_path.write_bytes(b"P5\n3 1\n4095\n" + pixel_bytes)

            loaded_image = load_processing_image_for_path(image_path)
            try:
                normalized = _normalize_simulation_image(loaded_image)
                self.assertEqual(list(normalized.getdata()), [0, 128, 255])
            finally:
                loaded_image.close()


def _file_digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


if __name__ == "__main__":
    unittest.main()
