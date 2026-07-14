import tempfile
import unittest
from pathlib import Path

from flask import Flask

from web.app.services.storage_service import (
    R2StorageBackend,
    build_case_object_key,
    build_r2_reference,
    parse_r2_reference,
    remove_case_temporary_files_if_cloud,
)


class FakeR2Client:
    def __init__(self):
        self.objects = {}
        self.deleted_keys = []

    def upload_file(self, filename, bucket, key, ExtraArgs=None):
        self.objects[(bucket, key)] = {
            "content": Path(filename).read_bytes(),
            "extra_args": ExtraArgs or {},
        }

    def download_file(self, bucket, key, filename):
        Path(filename).write_bytes(self.objects[(bucket, key)]["content"])

    def list_objects_v2(self, Bucket, Prefix, ContinuationToken=None):
        del ContinuationToken
        keys = sorted(
            key
            for bucket, key in self.objects
            if bucket == Bucket and key.startswith(Prefix)
        )
        return {
            "Contents": [{"Key": key} for key in keys],
            "IsTruncated": False,
        }

    def delete_objects(self, Bucket, Delete):
        for item in Delete["Objects"]:
            key = item["Key"]
            self.objects.pop((Bucket, key), None)
            self.deleted_keys.append(key)

    def delete_object(self, Bucket, Key):
        self.objects.pop((Bucket, Key), None)
        self.deleted_keys.append(Key)

    def generate_presigned_url(self, operation, Params, ExpiresIn):
        return (
            f"https://signed.example/{Params['Bucket']}/{Params['Key']}"
            f"?operation={operation}&expires={ExpiresIn}"
        )


class R2StorageBackendTests(unittest.TestCase):
    def setUp(self):
        self.client = FakeR2Client()
        self.backend = R2StorageBackend(
            bucket_name="private-cases",
            endpoint_url="https://r2.example",
            access_key_id="test-access",
            secret_access_key="test-secret",
            client=self.client,
        )

    def test_builds_user_and_case_scoped_object_keys(self):
        object_key = build_case_object_key(12, 34, "roi/roi.png")

        self.assertEqual(object_key, "users/12/cases/34/roi/roi.png")

    def test_publishes_and_materializes_private_object(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "source.png"
            source.write_bytes(b"image-content")
            reference = self.backend.publish_file(
                source,
                "users/12/cases/34/original.png",
            )

            materialized = self.backend.materialize_file(
                reference,
                str(Path(temporary_directory) / "cache"),
            )

            self.assertEqual(materialized.read_bytes(), b"image-content")
            self.assertEqual(
                self.client.objects[
                    ("private-cases", "users/12/cases/34/original.png")
                ]["extra_args"]["ContentType"],
                "image/png",
            )

    def test_deletes_only_requested_case_prefix(self):
        self.client.objects = {
            ("private-cases", "users/12/cases/34/original.png"): {"content": b"a"},
            ("private-cases", "users/12/cases/34/results/map.pgm"): {"content": b"b"},
            ("private-cases", "users/12/cases/35/original.png"): {"content": b"c"},
        }

        deleted = self.backend.delete_prefix("users/12/cases/34")

        self.assertTrue(deleted)
        self.assertEqual(
            set(self.client.deleted_keys),
            {
                "users/12/cases/34/original.png",
                "users/12/cases/34/results/map.pgm",
            },
        )
        self.assertIn(
            ("private-cases", "users/12/cases/35/original.png"),
            self.client.objects,
        )

    def test_generates_short_lived_download_url(self):
        reference = build_r2_reference(
            "private-cases",
            "users/12/cases/34/original.png",
        )

        url = self.backend.create_presigned_download_url(reference, 300)

        self.assertIn("expires=300", url)
        self.assertNotIn("test-secret", url)
        self.assertEqual(
            parse_r2_reference(reference),
            ("private-cases", "users/12/cases/34/original.png"),
        )

    def test_removes_local_case_and_materialized_cache_in_cloud_mode(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            upload_folder = Path(temporary_directory) / "uploads"
            local_case = upload_folder / "case_34"
            local_case.mkdir(parents=True)
            (local_case / "original.png").write_bytes(b"local-copy")

            object_key = "users/12/cases/34/original.png"
            self.client.objects[("private-cases", object_key)] = {
                "content": b"cloud-copy"
            }
            cached_file = self.backend.materialize_file(
                build_r2_reference("private-cases", object_key),
                str(upload_folder),
            )
            app = Flask(__name__)
            app.config["STORAGE_BACKEND"] = "r2"
            app.extensions["storage_backend"] = self.backend

            with app.app_context():
                removed = remove_case_temporary_files_if_cloud(
                    12,
                    34,
                    str(upload_folder),
                )

            self.assertTrue(removed)
            self.assertFalse(local_case.exists())
            self.assertFalse(cached_file.exists())


if __name__ == "__main__":
    unittest.main()
