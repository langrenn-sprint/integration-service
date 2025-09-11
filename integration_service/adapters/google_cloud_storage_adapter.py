"""Module for google cloud storage adapter."""

import logging
import os
from pathlib import Path

from google.cloud import storage


class GoogleCloudStorageAdapter:
    """Class representing google cloud storage."""

    def upload_blob(self, destination_folder: str, source_file_name: str) -> str:
        """Upload a file to the bucket, return URL to uploaded file."""
        servicename = "GoogleCloudStorageAdapter.upload_blob"
        storage_bucket = os.getenv("GOOGLE_STORAGE_BUCKET", "")
        storage_server = os.getenv("GOOGLE_STORAGE_SERVER", "")
        if storage_bucket == "" or storage_server == "":
            err_msg = "GOOGLE_STORAGE_BUCKET or GOOGLE_STORAGE_SERVER not found in .env"
            raise Exception(err_msg)

        try:

            storage_client = storage.Client()
            bucket = storage_client.bucket(storage_bucket)
            destination_blob_name = f"{Path(source_file_name).name}"
            if destination_folder != "":
                destination_blob_name = f"{destination_folder}/{Path(source_file_name).name}"
            blob = bucket.blob(destination_blob_name)
            blob.upload_from_filename(source_file_name)
        except Exception as e:
            logging.exception(servicename)
            raise Exception(servicename) from e
        return (
            f"{storage_server}/{storage_bucket}/{destination_blob_name}"
        )
