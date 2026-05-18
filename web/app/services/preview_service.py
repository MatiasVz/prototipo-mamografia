from dataclasses import dataclass
from pathlib import Path

from PIL import Image


DIRECT_PREVIEW_EXTENSIONS = {"png", "jpg", "jpeg"}
GENERATED_PREVIEW_EXTENSIONS = {"bmp", "tif", "tiff"}
PREVIEW_FILENAME = "preview.png"
MAX_PREVIEW_SIZE = (1200, 1200)


@dataclass
class PreviewFile:
    absolute_path: Path
    is_generated: bool
    mimetype: str


def ensure_preview_for_stored_file(stored_file):
    return ensure_preview_for_path(stored_file.absolute_path)


def ensure_preview_for_case(case, upload_folder: str):
    if case.file_type != "image":
        return None

    original_path = _case_original_path(case, upload_folder)
    return ensure_preview_for_path(original_path)


def ensure_preview_for_path(original_path: Path):
    extension = _get_extension(original_path)

    if extension in DIRECT_PREVIEW_EXTENSIONS:
        if not original_path.exists():
            return None

        return PreviewFile(
            absolute_path=original_path,
            is_generated=False,
            mimetype=_get_direct_mimetype(extension),
        )

    if extension in GENERATED_PREVIEW_EXTENSIONS:
        if not original_path.exists():
            return None

        preview_path = original_path.parent / PREVIEW_FILENAME
        _generate_png_preview(original_path, preview_path)
        return PreviewFile(
            absolute_path=preview_path,
            is_generated=True,
            mimetype="image/png",
        )

    return None


def _case_original_path(case, upload_folder: str):
    original_filename = Path(case.original_file_path).name
    return Path(upload_folder) / f"case_{case.id}" / original_filename


def _generate_png_preview(original_path: Path, preview_path: Path):
    with Image.open(original_path) as image:
        preview_image = image.copy()
        preview_image.thumbnail(MAX_PREVIEW_SIZE)

        if preview_image.mode not in ("RGB", "RGBA"):
            preview_image = preview_image.convert("RGB")

        preview_image.save(preview_path, format="PNG")


def _get_extension(path: Path):
    return path.suffix.lower().lstrip(".")


def _get_direct_mimetype(extension: str):
    if extension in {"jpg", "jpeg"}:
        return "image/jpeg"

    return "image/png"
