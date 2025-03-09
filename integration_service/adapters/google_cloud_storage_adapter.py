"""Module for google cloud storage adapter."""

import logging
import os
from pathlib import Path

from google.cloud import storage

GOOGLE_STORAGE_BUCKET = os.getenv("GOOGLE_STORAGE_BUCKET")
GOOGLE_STORAGE_SERVER = os.getenv("GOOGLE_STORAGE_SERVER")


class GoogleCloudStorageAdapter:
    """Class representing google cloud storage."""

    def upload_blob(self, source_file_name: str) -> str:
        """Upload a file to the bucket, return URL to uploaded file."""
        servicename = "GoogleCloudStorageAdapter.upload_blob"
        try:
            storage_client = storage.Client()
            bucket = storage_client.bucket(GOOGLE_STORAGE_BUCKET)
            destination_blob_name = f"{Path(source_file_name).name}"
            blob = bucket.blob(destination_blob_name)

            blob.upload_from_filename(source_file_name)
            logging.info(
                f"{servicename} File {source_file_name} uploaded to {destination_blob_name}."
            )
        except Exception as e:
            logging.exception(servicename)
            raise Exception(servicename) from e
        return (
            f"{GOOGLE_STORAGE_SERVER}/{GOOGLE_STORAGE_BUCKET}/{destination_blob_name}"
        )
