from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageOps
from pydicom.errors import InvalidDicomError
from pydicom.filereader import dcmread
from pydicom.uid import ExplicitVRBigEndian


DIRECT_PREVIEW_EXTENSIONS = {"png", "jpg", "jpeg"}
GENERATED_PREVIEW_EXTENSIONS = {"bmp", "tif", "tiff"}
DICOM_PREVIEW_EXTENSIONS = {"dcm"}
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
    if case.file_type not in {"image", "dicom"}:
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
        if not _generate_image_png_preview(original_path, preview_path):
            return None

        return PreviewFile(
            absolute_path=preview_path,
            is_generated=True,
            mimetype="image/png",
        )

    if extension in DICOM_PREVIEW_EXTENSIONS:
        if not original_path.exists():
            return None

        preview_path = original_path.parent / PREVIEW_FILENAME
        if not _generate_dicom_png_preview(original_path, preview_path):
            return None

        return PreviewFile(
            absolute_path=preview_path,
            is_generated=True,
            mimetype="image/png",
        )

    return None


def _case_original_path(case, upload_folder: str):
    original_filename = Path(case.original_file_path).name
    return Path(upload_folder) / f"case_{case.id}" / original_filename


def _generate_image_png_preview(original_path: Path, preview_path: Path):
    try:
        with Image.open(original_path) as image:
            preview_image = image.copy()
            preview_image.thumbnail(MAX_PREVIEW_SIZE)

            if preview_image.mode not in ("RGB", "RGBA"):
                preview_image = preview_image.convert("RGB")

            preview_image.save(preview_path, format="PNG")
    except (OSError, ValueError):
        return False

    return True


def _generate_dicom_png_preview(original_path: Path, preview_path: Path):
    try:
        dataset = dcmread(original_path)
        preview_image = _dicom_dataset_to_image(dataset)
        preview_image.thumbnail(MAX_PREVIEW_SIZE)
        preview_image.save(preview_path, format="PNG")
    except (
        AttributeError,
        InvalidDicomError,
        NotImplementedError,
        OSError,
        TypeError,
        ValueError,
    ):
        return False

    return True


def _dicom_dataset_to_image(dataset):
    if _is_compressed_dicom(dataset):
        raise NotImplementedError("DICOM comprimido no soportado para vista previa basica.")

    rows = int(dataset.Rows)
    columns = int(dataset.Columns)
    bits_allocated = int(getattr(dataset, "BitsAllocated", 0))
    samples_per_pixel = int(getattr(dataset, "SamplesPerPixel", 1))
    photometric = str(getattr(dataset, "PhotometricInterpretation", "")).upper()

    if not getattr(dataset, "PixelData", None):
        raise ValueError("DICOM sin PixelData.")

    if samples_per_pixel == 1:
        return _monochrome_dicom_to_image(
            dataset,
            rows,
            columns,
            bits_allocated,
            photometric,
        )

    if samples_per_pixel == 3 and photometric == "RGB" and bits_allocated == 8:
        expected_bytes = rows * columns * samples_per_pixel
        pixel_data = dataset.PixelData[:expected_bytes]
        if len(pixel_data) < expected_bytes:
            raise ValueError("PixelData RGB incompleto.")

        return Image.frombytes("RGB", (columns, rows), pixel_data)

    raise NotImplementedError("Formato DICOM no soportado para vista previa basica.")


def _monochrome_dicom_to_image(dataset, rows, columns, bits_allocated, photometric):
    if bits_allocated == 8:
        expected_bytes = rows * columns
        pixel_data = dataset.PixelData[:expected_bytes]
        if len(pixel_data) < expected_bytes:
            raise ValueError("PixelData monocromatico incompleto.")

        image = Image.frombytes("L", (columns, rows), pixel_data)
    elif bits_allocated == 16:
        expected_bytes = rows * columns * 2
        pixel_data = dataset.PixelData[:expected_bytes]
        if len(pixel_data) < expected_bytes:
            raise ValueError("PixelData monocromatico incompleto.")

        image = _scale_16_bit_monochrome_to_l(dataset, pixel_data, rows, columns)
    else:
        raise NotImplementedError("Profundidad DICOM no soportada.")

    if photometric == "MONOCHROME1":
        image = ImageOps.invert(image.convert("L"))

    return image.convert("RGB")


def _scale_16_bit_monochrome_to_l(dataset, pixel_data, rows, columns):
    value_count = rows * columns
    signed = int(getattr(dataset, "PixelRepresentation", 0)) == 1
    byteorder = "big" if _is_big_endian(dataset) else "little"

    min_value = None
    max_value = None
    for index in range(0, value_count * 2, 2):
        value = int.from_bytes(
            pixel_data[index : index + 2],
            byteorder,
            signed=signed,
        )
        min_value = value if min_value is None else min(min_value, value)
        max_value = value if max_value is None else max(max_value, value)

    if min_value is None or max_value is None:
        raise ValueError("PixelData monocromatico vacio.")

    if min_value == max_value:
        scaled_pixels = bytes([0] * value_count)
    else:
        scale = 255 / (max_value - min_value)
        scaled_pixels = bytearray(value_count)
        output_index = 0
        for index in range(0, value_count * 2, 2):
            value = int.from_bytes(
                pixel_data[index : index + 2],
                byteorder,
                signed=signed,
            )
            scaled_pixels[output_index] = round((value - min_value) * scale)
            output_index += 1
        scaled_pixels = bytes(scaled_pixels)

    return Image.frombytes("L", (columns, rows), scaled_pixels)


def _is_compressed_dicom(dataset):
    transfer_syntax_uid = getattr(
        getattr(dataset, "file_meta", None),
        "TransferSyntaxUID",
        None,
    )
    return bool(getattr(transfer_syntax_uid, "is_compressed", False))


def _is_big_endian(dataset):
    transfer_syntax_uid = getattr(
        getattr(dataset, "file_meta", None),
        "TransferSyntaxUID",
        None,
    )

    if transfer_syntax_uid == ExplicitVRBigEndian:
        return True

    return False


def _get_extension(path: Path):
    return path.suffix.lower().lstrip(".")


def _get_direct_mimetype(extension: str):
    if extension in {"jpg", "jpeg"}:
        return "image/jpeg"

    return "image/png"
