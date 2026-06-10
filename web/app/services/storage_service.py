from dataclasses import dataclass
from pathlib import Path

from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename


@dataclass
class StoredFile:
    original_filename: str
    stored_filename: str
    absolute_path: Path
    relative_path: str
    size_bytes: int


def store_original_file(file_storage: FileStorage, case_id: int, extension: str, upload_folder: str):
    case_directory = get_case_upload_directory(case_id, upload_folder)
    case_directory.mkdir(parents=True, exist_ok=True)
    get_case_roi_directory(case_id, upload_folder).mkdir(parents=True, exist_ok=True)

    normalized_extension = extension.lower().lstrip(".")
    stored_filename = f"original.{normalized_extension}"
    absolute_path = case_directory / stored_filename

    file_storage.stream.seek(0)
    file_storage.save(absolute_path)
    size_bytes = absolute_path.stat().st_size

    return StoredFile(
        original_filename=_clean_original_filename(file_storage.filename),
        stored_filename=stored_filename,
        absolute_path=absolute_path,
        relative_path=_to_relative_storage_path(absolute_path),
        size_bytes=size_bytes,
    )


def store_roi_file(file_storage: FileStorage, case_id: int, extension: str, upload_folder: str):
    roi_directory = get_case_roi_directory(case_id, upload_folder)
    roi_directory.mkdir(parents=True, exist_ok=True)

    normalized_extension = extension.lower().lstrip(".")
    stored_filename = f"roi.{normalized_extension}"
    absolute_path = roi_directory / stored_filename

    file_storage.stream.seek(0)
    file_storage.save(absolute_path)
    size_bytes = absolute_path.stat().st_size

    return StoredFile(
        original_filename=_clean_original_filename(file_storage.filename, "roi"),
        stored_filename=stored_filename,
        absolute_path=absolute_path,
        relative_path=_to_relative_storage_path(absolute_path),
        size_bytes=size_bytes,
    )


def store_generated_roi_image(image, case_id: int, upload_folder: str):
    roi_directory = get_case_roi_directory(case_id, upload_folder)
    roi_directory.mkdir(parents=True, exist_ok=True)

    stored_filename = "roi.png"
    absolute_path = roi_directory / stored_filename

    image.save(absolute_path, format="PNG")
    size_bytes = absolute_path.stat().st_size

    return StoredFile(
        original_filename="roi_recortada.png",
        stored_filename=stored_filename,
        absolute_path=absolute_path,
        relative_path=_to_relative_storage_path(absolute_path),
        size_bytes=size_bytes,
    )


def store_simulation_input_pgm(image, case_id: int, upload_folder: str):
    case_directory = get_case_upload_directory(case_id, upload_folder)
    case_directory.mkdir(parents=True, exist_ok=True)

    stored_filename = "simulation_input.pgm"
    absolute_path = case_directory / stored_filename

    image.save(absolute_path, format="PPM")
    size_bytes = absolute_path.stat().st_size

    return StoredFile(
        original_filename=stored_filename,
        stored_filename=stored_filename,
        absolute_path=absolute_path,
        relative_path=_to_relative_storage_path(absolute_path),
        size_bytes=size_bytes,
    )


def get_case_upload_directory(case_id: int, upload_folder: str):
    return Path(upload_folder) / f"case_{case_id}"


def get_case_roi_directory(case_id: int, upload_folder: str):
    return get_case_upload_directory(case_id, upload_folder) / "roi"


def get_case_simulation_results_directory(case_id: int, upload_folder: str):
    return get_case_upload_directory(case_id, upload_folder) / "results"


def to_relative_storage_path(path):
    return _to_relative_storage_path(Path(path))


def _clean_original_filename(filename, fallback="mamografia"):
    safe_filename = secure_filename(filename or "")
    return safe_filename or fallback


def _to_relative_storage_path(path):
    parts = path.resolve().parts

    if "storage" in parts:
        storage_index = parts.index("storage")
        return "/".join(parts[storage_index:])

    return path.as_posix()
