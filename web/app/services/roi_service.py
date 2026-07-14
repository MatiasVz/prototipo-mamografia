from dataclasses import dataclass

from PIL import Image

from ..models import CaseStatus
from .preview_service import ensure_preview_for_case
from .storage_service import StoredFile, store_generated_roi_image


@dataclass
class RoiCrop:
    x: int
    y: int
    width: int
    height: int


def crop_roi_for_case(case, upload_folder: str, crop: RoiCrop):
    preview = ensure_preview_for_case(case, upload_folder)

    if preview is None:
        raise ValueError("No existe imagen disponible para recortar.")

    with Image.open(preview.absolute_path) as image:
        image = image.convert("RGB")
        crop_box = _build_crop_box(crop, image.size)
        roi_image = image.crop(crop_box)
        stored_roi = store_generated_roi_image(
            roi_image,
            case.id,
            upload_folder,
            user_id=getattr(case, "user_id", None),
        )

    _update_case_roi(case, stored_roi)
    return stored_roi


def _build_crop_box(crop: RoiCrop, image_size):
    image_width, image_height = image_size

    x1 = _clamp(crop.x, 0, image_width - 1)
    y1 = _clamp(crop.y, 0, image_height - 1)
    x2 = _clamp(crop.x + crop.width, x1 + 1, image_width)
    y2 = _clamp(crop.y + crop.height, y1 + 1, image_height)

    if x2 - x1 < 2 or y2 - y1 < 2:
        raise ValueError("Selecciona una region de ROI mas amplia.")

    return (x1, y1, x2, y2)


def _clamp(value, minimum, maximum):
    return max(minimum, min(value, maximum))


def _update_case_roi(case, stored_roi: StoredFile):
    case.roi_filename = stored_roi.original_filename
    case.roi_file_path = stored_roi.relative_path
    case.roi_file_type = "image"
    case.roi_size_bytes = stored_roi.size_bytes
    case.status = CaseStatus.REGISTERED
