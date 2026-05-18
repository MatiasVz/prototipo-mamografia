from dataclasses import dataclass
from pathlib import Path

from PIL import Image, UnidentifiedImageError
from pydicom.errors import InvalidDicomError
from pydicom.filereader import dcmread


ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "bmp", "tif", "tiff"}
ALLOWED_DICOM_EXTENSIONS = {"dcm"}
ALLOWED_EXTENSIONS = ALLOWED_IMAGE_EXTENSIONS | ALLOWED_DICOM_EXTENSIONS
DICOM_METADATA_FIELDS = {
    "Modality": "modalidad",
    "StudyDate": "fecha_estudio",
    "Rows": "filas",
    "Columns": "columnas",
    "PhotometricInterpretation": "interpretacion_fotometrica",
}


@dataclass
class FileValidationResult:
    is_valid: bool
    message: str
    extension: str | None = None
    size_bytes: int | None = None
    file_type: str | None = None
    metadata: dict | None = None


def validate_mammogram_file(file_storage, max_size_bytes):
    if file_storage is None or not file_storage.filename:
        return FileValidationResult(
            is_valid=False,
            message="Selecciona un archivo de mamografia antes de enviar el formulario.",
    )

    extension = _get_extension(file_storage.filename)
    size_bytes = _get_size_bytes(file_storage)

    if size_bytes is not None and size_bytes > max_size_bytes:
        return FileValidationResult(
            is_valid=False,
            message=f"El archivo supera el tamano maximo permitido de {_format_bytes(max_size_bytes)}.",
            extension=extension,
            size_bytes=size_bytes,
        )

    if extension not in ALLOWED_IMAGE_EXTENSIONS:
        if extension in ALLOWED_DICOM_EXTENSIONS:
            return _validate_dicom_file(file_storage, extension, size_bytes)

        return FileValidationResult(
            is_valid=False,
            message=(
                "Formato no permitido. Usa PNG, JPG, JPEG, BMP, TIF, TIFF o DCM."
            ),
            extension=extension,
        )

    if not _is_readable_image(file_storage):
        return FileValidationResult(
            is_valid=False,
            message="El archivo no se pudo leer como imagen valida o esta corrupto.",
            extension=extension,
            size_bytes=size_bytes,
        )

    return FileValidationResult(
        is_valid=True,
        message="Imagen valida para continuar con el flujo de carga.",
        extension=extension,
        size_bytes=size_bytes,
        file_type="image",
    )


def validate_image_file(file_storage, max_size_bytes):
    return validate_mammogram_file(file_storage, max_size_bytes)


def _validate_dicom_file(file_storage, extension, size_bytes):
    stream = file_storage.stream

    try:
        stream.seek(0)
        dataset = dcmread(stream, stop_before_pixels=True)
        metadata = _extract_dicom_metadata(dataset)
    except (InvalidDicomError, OSError, AttributeError, ValueError):
        return FileValidationResult(
            is_valid=False,
            message="El archivo DICOM no se pudo leer o no es valido.",
            extension=extension,
            size_bytes=size_bytes,
            file_type="dicom",
        )
    finally:
        try:
            stream.seek(0)
        except (AttributeError, OSError):
            pass

    return FileValidationResult(
        is_valid=True,
        message="Archivo DICOM valido para continuar con el flujo de carga.",
        extension=extension,
        size_bytes=size_bytes,
        file_type="dicom",
        metadata=metadata,
    )


def _extract_dicom_metadata(dataset):
    metadata = {}

    for dicom_field, metadata_key in DICOM_METADATA_FIELDS.items():
        value = getattr(dataset, dicom_field, None)
        if value is not None:
            metadata[metadata_key] = str(value)

    return metadata


def _get_extension(filename):
    return Path(filename).suffix.lower().lstrip(".")


def _get_size_bytes(file_storage):
    stream = file_storage.stream

    try:
        current_position = stream.tell()
        stream.seek(0, 2)
        size_bytes = stream.tell()
        stream.seek(current_position)
        return size_bytes
    except (AttributeError, OSError):
        return None


def _is_readable_image(file_storage):
    stream = file_storage.stream

    try:
        stream.seek(0)
        with Image.open(stream) as image:
            image.verify()
        return True
    except (UnidentifiedImageError, OSError, ValueError):
        return False
    finally:
        try:
            stream.seek(0)
        except (AttributeError, OSError):
            pass


def _format_bytes(size_bytes):
    if size_bytes >= 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.0f} MB"
    if size_bytes >= 1024:
        return f"{size_bytes / 1024:.0f} KB"
    return f"{size_bytes} bytes"
