from dataclasses import dataclass

from sqlalchemy.exc import SQLAlchemyError
from werkzeug.datastructures import FileStorage

from ..extensions import db
from ..models import Case, CaseStatus, InputMode
from .file_validation import FileValidationResult
from .preview_service import ensure_preview_for_stored_file
from .storage_service import StoredFile, store_original_file, store_roi_file


@dataclass
class CaseRegistrationResult:
    case: Case
    stored_file: StoredFile
    stored_roi_file: StoredFile | None = None


def register_case_upload(
    file_storage: FileStorage,
    validation_result: FileValidationResult,
    upload_folder: str,
    input_mode: str = InputMode.MAMMOGRAM,
    user_id: int | None = None,
):
    stored_file = None
    stored_roi_file = None

    try:
        case = Case(
            input_mode=input_mode,
            original_filename=file_storage.filename or "",
            original_file_path="",
            file_type=validation_result.file_type or "",
            file_size_bytes=0,
            status=CaseStatus.REGISTERED,
            user_id=user_id,
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

        if input_mode == InputMode.ROI:
            stored_roi_file = store_roi_file(
                file_storage,
                case.id,
                validation_result.extension or "",
                upload_folder,
            )
            case.roi_filename = stored_roi_file.original_filename
            case.roi_file_path = stored_roi_file.relative_path
            case.roi_file_type = validation_result.file_type or ""
            case.roi_size_bytes = stored_roi_file.size_bytes

        case.status = CaseStatus.REGISTERED
        ensure_preview_for_stored_file(stored_file)
        db.session.commit()
    except (OSError, SQLAlchemyError):
        db.session.rollback()
        if stored_file is not None:
            _remove_stored_file(stored_file)
        raise

    return CaseRegistrationResult(
        case=case,
        stored_file=stored_file,
        stored_roi_file=stored_roi_file,
    )


def register_mammogram_upload(
    file_storage: FileStorage,
    validation_result: FileValidationResult,
    upload_folder: str,
):
    return register_case_upload(
        file_storage,
        validation_result,
        upload_folder,
        input_mode=InputMode.MAMMOGRAM,
    )


def _remove_stored_file(stored_file: StoredFile):
    try:
        case_directory = stored_file.absolute_path.parent
        for stored_path in case_directory.rglob("*"):
            if stored_path.is_file():
                stored_path.unlink()

        for stored_path in sorted(case_directory.rglob("*"), reverse=True):
            if stored_path.is_dir():
                stored_path.rmdir()

        if case_directory.exists() and not any(case_directory.iterdir()):
            case_directory.rmdir()
    except OSError:
        pass
