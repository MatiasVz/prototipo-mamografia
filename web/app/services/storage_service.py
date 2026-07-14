import json
import mimetypes
import shutil
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from urllib.parse import urlparse

from flask import current_app, has_app_context
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename


R2_SCHEME = "r2"
CLOUD_CACHE_DIRECTORY = ".cloud-cache"


class StorageConfigurationError(OSError):
    """Raised when the selected storage backend is not fully configured."""


class StorageOperationError(OSError):
    """Raised when a configured storage backend cannot complete an operation."""


@dataclass
class StoredFile:
    original_filename: str
    stored_filename: str
    absolute_path: Path
    relative_path: str
    size_bytes: int


class LocalStorageBackend:
    name = "local"

    def publish_file(self, local_path: Path, object_key: str) -> str:
        del object_key
        return _to_relative_storage_path(local_path)

    def publish_directory(self, local_directory: Path, object_prefix: str) -> str:
        del object_prefix
        return _to_relative_storage_path(local_directory)

    def materialize_file(self, reference: str, upload_folder: str) -> Path:
        return _resolve_local_storage_path(reference, upload_folder)

    def materialize_directory(self, reference: str, upload_folder: str) -> Path:
        return _resolve_local_storage_path(reference, upload_folder)

    def delete_prefix(self, object_prefix: str) -> bool:
        del object_prefix
        return False

    def delete_reference(self, reference: str) -> bool:
        path = Path(reference)
        if not path.exists() or not path.is_file():
            return False
        path.unlink()
        return True

    def create_presigned_download_url(self, reference: str, expires_seconds: int):
        del reference, expires_seconds
        return None


class R2StorageBackend:
    name = "r2"

    def __init__(
        self,
        *,
        bucket_name,
        endpoint_url,
        access_key_id,
        secret_access_key,
        region="auto",
        client=None,
    ):
        self.bucket_name = _required_value("R2_BUCKET_NAME", bucket_name)
        self.endpoint_url = _required_value("R2_ENDPOINT_URL", endpoint_url).rstrip("/")
        self.access_key_id = _required_value("R2_ACCESS_KEY_ID", access_key_id)
        self.secret_access_key = _required_value(
            "R2_SECRET_ACCESS_KEY",
            secret_access_key,
        )
        self.region = region or "auto"
        self._client = client

    @property
    def client(self):
        if self._client is None:
            try:
                import boto3
            except ImportError as exc:
                raise StorageConfigurationError(
                    "El backend R2 requiere instalar la dependencia boto3."
                ) from exc

            self._client = boto3.client(
                service_name="s3",
                endpoint_url=self.endpoint_url,
                aws_access_key_id=self.access_key_id,
                aws_secret_access_key=self.secret_access_key,
                region_name=self.region,
            )

        return self._client

    def publish_file(self, local_path: Path, object_key: str) -> str:
        local_path = Path(local_path)
        object_key = _normalize_object_key(object_key)
        content_type = mimetypes.guess_type(local_path.name)[0] or "application/octet-stream"
        try:
            self.client.upload_file(
                str(local_path),
                self.bucket_name,
                object_key,
                ExtraArgs={"ContentType": content_type},
            )
        except Exception as exc:
            raise StorageOperationError(
                f"No se pudo publicar el objeto {object_key!r} en R2."
            ) from exc
        return build_r2_reference(self.bucket_name, object_key)

    def publish_directory(self, local_directory: Path, object_prefix: str) -> str:
        local_directory = Path(local_directory)
        object_prefix = _normalize_object_key(object_prefix)

        if not local_directory.is_dir():
            raise StorageOperationError(
                f"No existe el directorio local que se intentaba publicar: {local_directory}"
            )

        for local_path in sorted(local_directory.rglob("*")):
            if not local_path.is_file():
                continue
            relative_name = local_path.relative_to(local_directory).as_posix()
            self.publish_file(local_path, f"{object_prefix}/{relative_name}")

        return build_r2_reference(self.bucket_name, object_prefix)

    def materialize_file(self, reference: str, upload_folder: str) -> Path:
        bucket, object_key = parse_r2_reference(reference)
        self._ensure_bucket(bucket)
        destination = _cloud_cache_path(upload_folder, object_key)
        destination.parent.mkdir(parents=True, exist_ok=True)

        if destination.exists():
            return destination

        try:
            self.client.download_file(self.bucket_name, object_key, str(destination))
        except Exception as exc:
            if _is_missing_object_error(exc):
                return destination
            raise StorageOperationError(
                f"No se pudo descargar el objeto {object_key!r} desde R2."
            ) from exc
        return destination

    def materialize_directory(self, reference: str, upload_folder: str) -> Path:
        bucket, object_prefix = parse_r2_reference(reference)
        self._ensure_bucket(bucket)
        destination = _cloud_cache_path(upload_folder, object_prefix)
        destination.mkdir(parents=True, exist_ok=True)
        prefix = f"{object_prefix.rstrip('/')}/"

        try:
            for object_key in self._iter_object_keys(prefix):
                relative_name = object_key[len(prefix) :]
                if not relative_name:
                    continue
                local_path = destination / Path(*PurePosixPath(relative_name).parts)
                local_path.parent.mkdir(parents=True, exist_ok=True)
                self.client.download_file(self.bucket_name, object_key, str(local_path))
        except Exception as exc:
            raise StorageOperationError(
                f"No se pudo materializar el prefijo {object_prefix!r} desde R2."
            ) from exc

        return destination

    def delete_prefix(self, object_prefix: str) -> bool:
        object_prefix = _normalize_object_key(object_prefix).rstrip("/") + "/"
        object_keys = list(self._iter_object_keys(object_prefix))

        try:
            for start in range(0, len(object_keys), 1000):
                batch = object_keys[start : start + 1000]
                self.client.delete_objects(
                    Bucket=self.bucket_name,
                    Delete={"Objects": [{"Key": key} for key in batch], "Quiet": True},
                )
        except Exception as exc:
            raise StorageOperationError(
                f"No se pudo eliminar el prefijo {object_prefix!r} de R2."
            ) from exc

        return bool(object_keys)

    def delete_reference(self, reference: str) -> bool:
        bucket, object_key = parse_r2_reference(reference)
        self._ensure_bucket(bucket)
        try:
            self.client.delete_object(Bucket=self.bucket_name, Key=object_key)
        except Exception as exc:
            raise StorageOperationError(
                f"No se pudo eliminar el objeto {object_key!r} de R2."
            ) from exc
        return True

    def create_presigned_download_url(self, reference: str, expires_seconds: int):
        bucket, object_key = parse_r2_reference(reference)
        self._ensure_bucket(bucket)
        try:
            return self.client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket_name, "Key": object_key},
                ExpiresIn=max(1, int(expires_seconds)),
            )
        except Exception as exc:
            raise StorageOperationError(
                f"No se pudo crear un acceso temporal para {object_key!r}."
            ) from exc

    def _iter_object_keys(self, prefix):
        continuation_token = None
        while True:
            request = {"Bucket": self.bucket_name, "Prefix": prefix}
            if continuation_token:
                request["ContinuationToken"] = continuation_token
            response = self.client.list_objects_v2(**request)
            for item in response.get("Contents", ()):
                object_key = item.get("Key")
                if object_key:
                    yield object_key
            if not response.get("IsTruncated"):
                break
            continuation_token = response.get("NextContinuationToken")

    def _ensure_bucket(self, bucket):
        if bucket != self.bucket_name:
            raise StorageOperationError(
                "La referencia solicitada pertenece a un bucket R2 no configurado."
            )


def get_storage_backend(config=None):
    if config is None:
        config = current_app.config if has_app_context() else {}

    backend_name = str(config.get("STORAGE_BACKEND", "local")).strip().lower()

    if backend_name == "local":
        return LocalStorageBackend()

    if backend_name != "r2":
        raise StorageConfigurationError(
            "STORAGE_BACKEND debe ser 'local' o 'r2'."
        )

    if has_app_context() and config is current_app.config:
        cached_backend = current_app.extensions.get("storage_backend")
        if cached_backend is not None:
            return cached_backend

    backend = R2StorageBackend(
        bucket_name=config.get("R2_BUCKET_NAME"),
        endpoint_url=config.get("R2_ENDPOINT_URL"),
        access_key_id=config.get("R2_ACCESS_KEY_ID"),
        secret_access_key=config.get("R2_SECRET_ACCESS_KEY"),
        region=config.get("R2_REGION", "auto"),
    )

    if has_app_context() and config is current_app.config:
        current_app.extensions["storage_backend"] = backend

    return backend


def store_original_file(
    file_storage: FileStorage,
    case_id: int,
    extension: str,
    upload_folder: str,
    *,
    user_id=None,
):
    case_directory = get_case_upload_directory(case_id, upload_folder)
    case_directory.mkdir(parents=True, exist_ok=True)
    get_case_roi_directory(case_id, upload_folder).mkdir(parents=True, exist_ok=True)
    normalized_extension = extension.lower().lstrip(".")
    stored_filename = f"original.{normalized_extension}"
    absolute_path = case_directory / stored_filename
    file_storage.stream.seek(0)
    file_storage.save(absolute_path)
    return _stored_file_from_path(
        absolute_path,
        original_filename=_clean_original_filename(file_storage.filename),
        stored_filename=stored_filename,
        object_key=build_case_object_key(user_id, case_id, stored_filename),
    )


def store_roi_file(
    file_storage: FileStorage,
    case_id: int,
    extension: str,
    upload_folder: str,
    *,
    user_id=None,
):
    roi_directory = get_case_roi_directory(case_id, upload_folder)
    roi_directory.mkdir(parents=True, exist_ok=True)
    normalized_extension = extension.lower().lstrip(".")
    stored_filename = f"roi.{normalized_extension}"
    absolute_path = roi_directory / stored_filename
    file_storage.stream.seek(0)
    file_storage.save(absolute_path)
    return _stored_file_from_path(
        absolute_path,
        original_filename=_clean_original_filename(file_storage.filename, "roi"),
        stored_filename=stored_filename,
        object_key=build_case_object_key(user_id, case_id, f"roi/{stored_filename}"),
    )


def store_generated_roi_image(image, case_id: int, upload_folder: str, *, user_id=None):
    roi_directory = get_case_roi_directory(case_id, upload_folder)
    roi_directory.mkdir(parents=True, exist_ok=True)
    stored_filename = "roi.png"
    absolute_path = roi_directory / stored_filename
    image.save(absolute_path, format="PNG")
    return _stored_file_from_path(
        absolute_path,
        original_filename="roi_recortada.png",
        stored_filename=stored_filename,
        object_key=build_case_object_key(user_id, case_id, f"roi/{stored_filename}"),
    )


def store_simulation_input_pgm(image, case_id: int, upload_folder: str, *, user_id=None):
    case_directory = get_case_upload_directory(case_id, upload_folder)
    case_directory.mkdir(parents=True, exist_ok=True)
    stored_filename = "simulation_input.pgm"
    absolute_path = case_directory / stored_filename
    image.save(absolute_path, format="PPM")
    return _stored_file_from_path(
        absolute_path,
        original_filename=stored_filename,
        stored_filename=stored_filename,
        object_key=build_case_object_key(user_id, case_id, stored_filename),
    )


def store_simulation_grayscale_png(image, case_id: int, upload_folder: str, *, user_id=None):
    case_directory = get_case_upload_directory(case_id, upload_folder)
    case_directory.mkdir(parents=True, exist_ok=True)
    stored_filename = "simulation_grayscale.png"
    absolute_path = case_directory / stored_filename
    image.save(absolute_path, format="PNG")
    return _stored_file_from_path(
        absolute_path,
        original_filename=stored_filename,
        stored_filename=stored_filename,
        object_key=build_case_object_key(user_id, case_id, stored_filename),
    )


def store_simulation_preparation_metadata(
    metadata,
    case_id: int,
    upload_folder: str,
    *,
    user_id=None,
):
    case_directory = get_case_upload_directory(case_id, upload_folder)
    case_directory.mkdir(parents=True, exist_ok=True)
    stored_filename = "simulation_preparation.json"
    absolute_path = case_directory / stored_filename
    with absolute_path.open("w", encoding="utf-8", newline="\n") as metadata_file:
        json.dump(metadata, metadata_file, ensure_ascii=True, indent=2, sort_keys=True)
        metadata_file.write("\n")
    return _stored_file_from_path(
        absolute_path,
        original_filename=stored_filename,
        stored_filename=stored_filename,
        object_key=build_case_object_key(user_id, case_id, stored_filename),
    )


def publish_case_results_directory(local_directory, *, case_id, user_id, upload_folder):
    backend = get_storage_backend()
    object_prefix = build_case_object_key(user_id, case_id, "results")
    return backend.publish_directory(Path(local_directory), object_prefix)


def build_case_storage_reference(user_id, case_id, relative_name, upload_folder=None):
    backend = get_storage_backend()
    if backend.name == "r2":
        return build_r2_reference(
            backend.bucket_name,
            build_case_object_key(user_id, case_id, relative_name),
        )
    if upload_folder is None:
        upload_folder = current_app.config["UPLOAD_FOLDER"]
    return _to_relative_storage_path(
        get_case_upload_directory(case_id, upload_folder) / Path(relative_name)
    )


def join_storage_reference(base_reference, relative_name):
    if is_r2_reference(base_reference):
        bucket, object_key = parse_r2_reference(base_reference)
        joined_key = f"{object_key.rstrip('/')}/{str(relative_name).lstrip('/')}"
        return build_r2_reference(bucket, joined_key)
    return str(Path(base_reference) / Path(relative_name)).replace("\\", "/")


def resolve_stored_path(stored_path, upload_folder: str):
    if not stored_path:
        return None
    return get_storage_backend().materialize_file(str(stored_path), upload_folder)


def resolve_stored_directory(stored_path, upload_folder: str):
    if not stored_path:
        return None
    return get_storage_backend().materialize_directory(str(stored_path), upload_folder)


def create_presigned_download_url(stored_path, expires_seconds=300):
    if not stored_path or not is_r2_reference(stored_path):
        return None
    return get_storage_backend().create_presigned_download_url(
        str(stored_path),
        expires_seconds,
    )


def delete_storage_reference(stored_path):
    if not stored_path:
        return False
    return get_storage_backend().delete_reference(str(stored_path))


def remove_case_storage_directory(case_id: int, upload_folder: str, *, user_id=None):
    local_removed = remove_local_case_storage_directory(case_id, upload_folder)
    backend = get_storage_backend()
    remote_removed = False
    if backend.name == "r2":
        remote_removed = backend.delete_prefix(
            build_case_object_key(user_id, case_id, "")
        )
        _remove_cloud_cache_prefix(user_id, case_id, upload_folder)
    return local_removed or remote_removed


def remove_local_case_storage_directory(case_id: int, upload_folder: str):
    case_directory = get_case_upload_directory(case_id, upload_folder)
    if not case_directory.exists():
        return False
    shutil.rmtree(case_directory)
    return True


def remove_case_materialized_cache(user_id, case_id, upload_folder):
    _remove_cloud_cache_prefix(user_id, case_id, upload_folder)


def remove_case_temporary_files_if_cloud(user_id, case_id, upload_folder):
    """Remove disk copies after R2 becomes the source of truth."""
    if get_storage_backend().name != "r2":
        return False

    local_removed = remove_local_case_storage_directory(case_id, upload_folder)
    remove_case_materialized_cache(user_id, case_id, upload_folder)
    return local_removed


def get_case_upload_directory(case_id: int, upload_folder: str):
    return Path(upload_folder) / f"case_{case_id}"


def get_case_roi_directory(case_id: int, upload_folder: str):
    return get_case_upload_directory(case_id, upload_folder) / "roi"


def get_case_simulation_results_directory(case_id: int, upload_folder: str):
    return get_case_upload_directory(case_id, upload_folder) / "results"


def build_case_object_key(user_id, case_id, relative_name):
    user_segment = str(user_id) if user_id is not None else "unassigned"
    prefix = f"users/{user_segment}/cases/{int(case_id)}"
    relative_name = str(relative_name or "").replace("\\", "/").strip("/")
    return f"{prefix}/{relative_name}" if relative_name else prefix


def build_r2_reference(bucket_name, object_key):
    return f"{R2_SCHEME}://{bucket_name}/{_normalize_object_key(object_key)}"


def parse_r2_reference(reference):
    parsed = urlparse(str(reference))
    if parsed.scheme != R2_SCHEME or not parsed.netloc:
        raise StorageOperationError("La referencia R2 almacenada no es valida.")
    return parsed.netloc, _normalize_object_key(parsed.path)


def is_r2_reference(reference):
    return str(reference or "").startswith(f"{R2_SCHEME}://")


def to_relative_storage_path(path):
    return _to_relative_storage_path(Path(path))


def _stored_file_from_path(
    absolute_path,
    *,
    original_filename,
    stored_filename,
    object_key,
):
    absolute_path = Path(absolute_path)
    storage_reference = get_storage_backend().publish_file(absolute_path, object_key)
    return StoredFile(
        original_filename=original_filename,
        stored_filename=stored_filename,
        absolute_path=absolute_path,
        relative_path=storage_reference,
        size_bytes=absolute_path.stat().st_size,
    )


def _resolve_local_storage_path(reference, upload_folder):
    path = Path(reference)
    if path.is_absolute():
        return path

    cwd_candidate = Path.cwd() / path
    if cwd_candidate.exists():
        return cwd_candidate

    repo_candidate = Path.cwd().parent / path
    if repo_candidate.exists():
        return repo_candidate

    parts = path.parts
    if "uploads" in parts:
        uploads_index = parts.index("uploads")
        return Path(upload_folder) / Path(*parts[uploads_index + 1 :])
    return Path(upload_folder) / path


def _cloud_cache_path(upload_folder, object_key):
    return Path(upload_folder) / CLOUD_CACHE_DIRECTORY / Path(
        *PurePosixPath(object_key).parts
    )


def _remove_cloud_cache_prefix(user_id, case_id, upload_folder):
    cache_path = _cloud_cache_path(
        upload_folder,
        build_case_object_key(user_id, case_id, ""),
    )
    if cache_path.exists():
        shutil.rmtree(cache_path)


def _clean_original_filename(filename, fallback="mamografia"):
    safe_filename = secure_filename(filename or "")
    return safe_filename or fallback


def _to_relative_storage_path(path):
    parts = path.resolve().parts
    if "storage" in parts:
        storage_index = parts.index("storage")
        return "/".join(parts[storage_index:])
    return path.as_posix()


def _required_value(name, value):
    normalized_value = str(value or "").strip()
    if not normalized_value:
        raise StorageConfigurationError(f"Falta configurar la variable {name}.")
    return normalized_value


def _normalize_object_key(value):
    object_key = str(value or "").replace("\\", "/").strip("/")
    if not object_key or ".." in PurePosixPath(object_key).parts:
        raise StorageOperationError("La clave de objeto solicitada no es valida.")
    return object_key


def _is_missing_object_error(error):
    response = getattr(error, "response", None)
    if not isinstance(response, dict):
        return False
    error_data = response.get("Error", {})
    status_code = response.get("ResponseMetadata", {}).get("HTTPStatusCode")
    return error_data.get("Code") in {"404", "NoSuchKey", "NotFound"} or status_code == 404
