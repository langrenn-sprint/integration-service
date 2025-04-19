"""Module adapter for photos on file storage."""

import logging
import os
from pathlib import Path

from .config_adapter import ConfigAdapter

PHOTOS_FILE_PATH = f"{Path.cwd()}/integration_service/files"
PHOTOS_ARCHIVE_PATH = f"{PHOTOS_FILE_PATH}/archive"
PHOTOS_URL_PATH = "files"


class PhotosFileAdapter:
    """Class representing photos."""

    def get_all_photos(self) -> list:
        """Get all path/filename to all photos on file directory."""
        photos = []
        try:
            # loop files in directory
            for f in Path(PHOTOS_FILE_PATH).iterdir():
                if f.suffix in [".jpg", ".png"] and "_config" not in f.name:
                        photos.append(f"{PHOTOS_FILE_PATH}/{f}")
        except Exception:
            logging.exception("Error getting photos")
        return photos

    def get_all_photo_urls(self) -> list:
        """Get all url to all photos on file directory."""
        photos = []
        try:
            # loop files in directory and find all photos
            for file in Path(PHOTOS_FILE_PATH).iterdir():
                if file.suffix in [".jpg", ".png"] and "_config" not in file.name and "_crop" not in file.name:
                    photos.append(f"{PHOTOS_URL_PATH}/{file.name}")
        except Exception:
            logging.exception("Error getting photos")
        return photos

    async def get_trigger_line_file_url(self, token: str, event: dict) -> str:
        """Get url to latest trigger line photo."""
        key = "TRIGGER_LINE_CONFIG_FILE"
        file_identifier = await ConfigAdapter().get_config(token, event["id"], key)
        trigger_line_file_name = ""
        try:
            # Lists files in a directory sorted by creation date, newest first."""
            files = Path(PHOTOS_FILE_PATH).iterdir()
            files_with_ctime = [
                (f, (Path(PHOTOS_FILE_PATH) / f).stat().st_ctime) for f in files
            ]
            sorted_files = [
                f[0] for f in sorted(files_with_ctime, key=lambda x: x[1], reverse=True)
            ]
            trigger_line_files = [
                f for f in sorted_files if file_identifier in f.name
            ]

            # Return url to newest file, archive
            if len(trigger_line_files) == 0:
                return ""
            trigger_line_file_name = trigger_line_files[0]
            if len(trigger_line_files) > 1:
                for f in trigger_line_files[1:]:
                    move_to_archive(f.name)

        except Exception:
            logging.exception("Error getting photos")
        return f"{PHOTOS_URL_PATH}/{trigger_line_file_name}"

    def move_photo_to_archive(self, filename: str) -> None:
        """Move photo to archive."""
        source_file = Path(PHOTOS_FILE_PATH) / filename
        destination_file = Path(PHOTOS_ARCHIVE_PATH) / source_file.name

        try:
            source_file.rename(destination_file)
        except FileNotFoundError:
            logging.info("Destination folder not found. Creating...")
            Path(PHOTOS_ARCHIVE_PATH).mkdir(parents=True, exist_ok=True)
            source_file.rename(destination_file)
        except Exception:
            logging.exception("Error moving photo to archive.")


def move_to_archive(filename: str) -> None:
    """Move photo to archive."""
    source_file = Path(PHOTOS_FILE_PATH) / filename
    destination_file = Path(PHOTOS_ARCHIVE_PATH) / source_file.name

    try:
        source_file.rename(destination_file)
    except FileNotFoundError:
        logging.info("Destination folder not found. Creating...")
        Path(PHOTOS_ARCHIVE_PATH).mkdir(parents=True, exist_ok=True)
        source_file.rename(destination_file)
    except Exception:
        logging.exception("Error moving photo to archive.")
