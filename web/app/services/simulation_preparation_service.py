import hashlib
from pathlib import Path

from PIL import Image, ImageOps

from ..models import CaseStatus
from .preview_service import load_processing_image_for_path
from .storage_service import (
    StoredFile,
    get_case_roi_directory,
    store_simulation_grayscale_png,
    store_simulation_input_pgm,
    store_simulation_preparation_metadata,
    to_relative_storage_path,
)


def prepare_simulation_input_for_case(case, upload_folder: str):
    _ensure_case_is_ready(case)
    roi_path = _get_case_roi_path(case, upload_folder)

    if not roi_path.exists():
        raise ValueError("No se encontro el archivo ROI asociado al caso.")

    source_image = load_processing_image_for_path(roi_path)

    if source_image is None:
        raise ValueError(
            "No se pudo preparar una imagen valida a partir de la ROI para la simulacion."
        )

    try:
        source_mode = source_image.mode
        source_size = source_image.size
        simulation_image = _normalize_simulation_image(source_image)
        try:
            output_mode = simulation_image.mode
            output_size = simulation_image.size
            grayscale_path = store_simulation_grayscale_png(
                simulation_image,
                case.id,
                upload_folder,
            )
            stored_input = store_simulation_input_pgm(
                simulation_image,
                case.id,
                upload_folder,
            )
        finally:
            simulation_image.close()
    finally:
        source_image.close()

    metadata = {
        "schema_version": 1,
        "case_id": case.id,
        "source_filename": roi_path.name,
        "source_extension": roi_path.suffix.lower().lstrip("."),
        "source_mode": source_mode,
        "source_width": source_size[0],
        "source_height": source_size[1],
        "output_mode": output_mode,
        "output_width": output_size[0],
        "output_height": output_size[1],
        "grayscale_conversion": "deterministic_luminance_or_fixed_bit_depth",
        "alpha_background": "black",
        "contrast_normalization": "none",
        "resolution_policy": "full_source_resolution",
        "grayscale_path": to_relative_storage_path(grayscale_path),
        "simulation_input_path": stored_input.relative_path,
        "simulation_input_sha256": _sha256(stored_input.absolute_path),
    }
    store_simulation_preparation_metadata(metadata, case.id, upload_folder)

    _update_case_simulation_input(case, stored_input)
    return stored_input


def _normalize_simulation_image(image):
    if _has_transparency(image):
        rgba_image = image.convert("RGBA")
        black_background = Image.new("RGBA", rgba_image.size, (0, 0, 0, 255))
        image = Image.alpha_composite(black_background, rgba_image).convert("RGB")

    if image.mode in {"I", "I;16", "I;16B", "I;16L", "I;16N"}:
        return _scale_unsigned_16_bit_image_to_l(image)

    return ImageOps.grayscale(image)


def _scale_unsigned_16_bit_image_to_l(image):
    scaled_values = bytearray(image.width * image.height)
    for index, value in enumerate(image.getdata()):
        if value < 0 or value > 65535:
            raise ValueError("La imagen entera excede el rango soportado de 16 bits.")
        scaled_values[index] = round(value * 255 / 65535)

    return Image.frombytes("L", image.size, bytes(scaled_values))


def _has_transparency(image):
    return image.mode in {"RGBA", "LA"} or "transparency" in image.info


def _sha256(path: Path):
    digest = hashlib.sha256()
    with path.open("rb") as stored_file:
        for chunk in iter(lambda: stored_file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _ensure_case_is_ready(case):
    if not case.roi_file_path:
        raise ValueError("No existe una ROI asociada para preparar la simulacion.")

    if case.status != CaseStatus.ROI_CONFIRMED:
        raise ValueError("Confirma la ROI antes de preparar la imagen para simulacion.")


def _get_case_roi_path(case, upload_folder: str):
    roi_filename = Path(case.roi_file_path).name
    return get_case_roi_directory(case.id, upload_folder) / roi_filename


def _update_case_simulation_input(case, stored_input: StoredFile):
    case.simulation_input_filename = stored_input.original_filename
    case.simulation_input_file_path = stored_input.relative_path
    case.simulation_input_file_type = "pgm"
    case.simulation_input_size_bytes = stored_input.size_bytes
