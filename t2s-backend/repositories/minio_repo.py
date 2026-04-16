from __future__ import annotations

import io
from datetime import timedelta

from minio import Minio
from minio.error import S3Error

from core.config import settings


class MinioRepository:
    def __init__(self) -> None:
        self.client = Minio(
            endpoint=settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=bool(settings.MINIO_SECURE),
        )
        self.bucket_name = settings.MINIO_BUCKET_NAME

    def ensure_bucket(self) -> None:
        if not self.client.bucket_exists(self.bucket_name):
            self.client.make_bucket(self.bucket_name)

    def upload_file_bytes(
        self,
        object_name: str,
        file_data: bytes,
        content_type: str = "application/octet-stream",
    ) -> str:
        self.ensure_bucket()
        stream = io.BytesIO(file_data)
        self.client.put_object(
            bucket_name=self.bucket_name,
            object_name=object_name,
            data=stream,
            length=len(file_data),
            content_type=content_type,
        )
        return object_name

    def get_file_bytes(self, object_name: str) -> bytes:
        self.ensure_bucket()
        response = self.client.get_object(self.bucket_name, object_name)
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()

    def get_presigned_url(self, object_name: str, expires_hours: int = 2) -> str:
        self.ensure_bucket()
        return self.client.get_presigned_url(
            method="GET",
            bucket_name=self.bucket_name,
            object_name=object_name,
            expires=timedelta(hours=expires_hours),
        )

    def delete_file(self, object_name: str) -> None:
        self.ensure_bucket()
        try:
            self.client.remove_object(self.bucket_name, object_name)
        except S3Error as exc:
            if exc.code == "NoSuchKey":
                return
            raise


minio_repo = MinioRepository()
