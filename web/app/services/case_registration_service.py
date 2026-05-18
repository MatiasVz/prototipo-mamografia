from dataclasses import dataclass

from sqlalchemy.exc import SQLAlchemyError
from werkzeug.datastructures import FileStorage

from ..extensions import db
from ..models import Case, CaseStatus, InputMode
from .file_validation import FileValidationResult
from .storage_service import StoredFile, store_original_file


@dataclass
class CaseRegistrationResult:
    case: Case
    stored_file: StoredFile


def register_mammogram_upload(
    file_storage: FileStorage,
    validation_result: FileValidationResult,
    upload_folder: str,
):
    stored_file = None

    try:
        case = Case(
            input_mode=InputMode.MAMMOGRAM,
            original_filename=file_storage.filename or "",
            original_file_path="",
            file_type=validation_result.file_type or "",
            file_size_bytes=0,
            status=CaseStatus.REGISTERED,
        )
        db.session.add(case)
        db.session.flush()

        stored_file = store_original_file(
            file_storage,
            case.id,
            validation_result.extension or "",
            upload_folder,
        )

        case.original_filename = stored_file.original_filename
        case.original_file_path = stored_file.relative_path
        case.file_type = validation_result.file_type or ""
        case.file_size_bytes = stored_file.size_bytes
        case.status = CaseStatus.REGISTERED
        db.session.commit()
    except (OSError, SQLAlchemyError):
        db.session.rollback()
        if stored_file is not None:
            _remove_stored_file(stored_file)
        raise

    return CaseRegistrationResult(case=case, stored_file=stored_file)


def _remove_stored_file(stored_file: StoredFile):
    try:
        stored_file.absolute_path.unlink(missing_ok=True)
        case_directory = stored_file.absolute_path.parent
        if case_directory.exists() and not any(case_directory.iterdir()):
            case_directory.rmdir()
    except OSError:
        pass
