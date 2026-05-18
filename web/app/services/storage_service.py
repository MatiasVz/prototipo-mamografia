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


def store_original_file(file_storage: FileStorage, case_id: int, extension: str, upload_folder: str):
    case_directory = get_case_upload_directory(case_id, upload_folder)
    case_directory.mkdir(parents=True, exist_ok=True)

    normalized_extension = extension.lower().lstrip(".")
    stored_filename = f"original.{normalized_extension}"
    absolute_path = case_directory / stored_filename

    file_storage.stream.seek(0)
    file_storage.save(absolute_path)

    return StoredFile(
        original_filename=_clean_original_filename(file_storage.filename),
        stored_filename=stored_filename,
        absolute_path=absolute_path,
        relative_path=_to_relative_storage_path(absolute_path),
    )


def get_case_upload_directory(case_id: int, upload_folder: str):
    return Path(upload_folder) / f"case_{case_id}"


def _clean_original_filename(filename):
    safe_filename = secure_filename(filename or "")
    return safe_filename or "mamografia"


def _to_relative_storage_path(path):
    parts = path.resolve().parts

    if "storage" in parts:
        storage_index = parts.index("storage")
        return "/".join(parts[storage_index:])

    return path.as_posix()
