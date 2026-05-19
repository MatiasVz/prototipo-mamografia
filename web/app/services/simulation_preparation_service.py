from pathlib import Path

from PIL import Image

from ..models import CaseStatus
from .storage_service import (
    StoredFile,
    get_case_roi_directory,
    store_simulation_input_pgm,
)


def prepare_simulation_input_for_case(case, upload_folder: str):
    _ensure_case_is_ready(case)
    roi_path = _get_case_roi_path(case, upload_folder)

    if not roi_path.exists():
        raise ValueError("No se encontro el archivo ROI asociado al caso.")

    with Image.open(roi_path) as image:
        simulation_image = image.convert("L")
        stored_input = store_simulation_input_pgm(
            simulation_image,
            case.id,
            upload_folder,
        )

    _update_case_simulation_input(case, stored_input)
    return stored_input


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
