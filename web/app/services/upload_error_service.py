from sqlalchemy.exc import SQLAlchemyError
from werkzeug.datastructures import FileStorage

from ..extensions import db
from ..models import Case, CaseStatus, InputMode
from .file_validation import ALLOWED_DICOM_EXTENSIONS, ALLOWED_IMAGE_EXTENSIONS


def register_upload_error(
    file_storage: FileStorage | None,
    validation_result,
    input_mode=InputMode.MAMMOGRAM,
):
    filename = _get_filename(file_storage)
    extension = _get_extension(filename)

    case = Case(
        input_mode=input_mode,
        original_filename=filename,
        original_file_path="",
        file_type=_get_error_file_type(extension, validation_result),
        file_size_bytes=validation_result.size_bytes or 0,
        status=CaseStatus.ERROR,
        error_message=validation_result.message,
    )

    db.session.add(case)
    db.session.commit()

    return case


def register_request_size_error(message: str):
    case = Case(
        input_mode=InputMode.MAMMOGRAM,
        original_filename="",
        original_file_path="",
        file_type="invalid",
        file_size_bytes=0,
        status=CaseStatus.ERROR,
        error_message=message,
    )

    db.session.add(case)
    db.session.commit()

    return case


def safe_register_upload_error(
    file_storage: FileStorage | None,
    validation_result,
    logger,
    input_mode=InputMode.MAMMOGRAM,
):
    try:
        return register_upload_error(file_storage, validation_result, input_mode)
    except SQLAlchemyError:
        db.session.rollback()
        logger.exception("No se pudo registrar el error de carga.")
        return None


def safe_register_request_size_error(message: str, logger):
    try:
        return register_request_size_error(message)
    except SQLAlchemyError:
        db.session.rollback()
        logger.exception("No se pudo registrar el error de tamano de carga.")
        return None


def _get_filename(file_storage):
    if file_storage is None or not file_storage.filename:
        return ""

    return file_storage.filename


def _get_extension(filename):
    if "." not in filename:
        return ""

    return filename.rsplit(".", 1)[-1].lower()


def _get_error_file_type(extension, validation_result):
    if validation_result.file_type:
        return validation_result.file_type

    if extension in ALLOWED_IMAGE_EXTENSIONS:
        return "image"

    if extension in ALLOWED_DICOM_EXTENSIONS:
        return "dicom"

    return "invalid"
