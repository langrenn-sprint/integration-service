"""Module for foto service."""

import json
import logging
from pathlib import Path

import piexif

from .ai_image_service import AiImageService
from .config_adapter import ConfigAdapter
from .google_cloud_storage_adapter import GoogleCloudStorageAdapter
from .google_pub_sub_adapter import GooglePubSubAdapter
from .photos_file_adapter import PhotosFileAdapter
from .status_adapter import StatusAdapter


class FotoSyncService:
    """Class representing foto sync service."""

    async def push_new_photos_from_file(self, token: str, event: dict) -> str:
        """Push photos to cloud storage, analyze and publish."""
        i_photo_count = 0
        i_error_count = 0
        informasjon = ""
        service_name = "push_new_photos_from_file"
        status_type = await ConfigAdapter().get_config(
            token, event, "INTEGRATION_SERVICE_STATUS_TYPE"
        )

        # loop photos and group crops with main photo - only upload complete pairs
        new_photos = PhotosFileAdapter().get_all_photos()
        new_photos_grouped = group_photos(new_photos)
        logging.info(f"Starting to push {len(new_photos_grouped)} photos")
        for x in new_photos_grouped:
            group = {}
            try:
                group = new_photos_grouped[x]
                if group["main"] and group["crop"]:
                    # upload photo to cloud storage
                    try:
                        url_main = GoogleCloudStorageAdapter().upload_blob(
                            group["main"]
                        )
                        url_crop = GoogleCloudStorageAdapter().upload_blob(
                            group["crop"]
                        )
                    except Exception as e:
                        error_text = (
                            f"Error uploading to Google photos. Files {group} - {e}"
                        )
                        logging.exception(error_text)
                        raise Exception(error_text) from e

                    # analyze photo with Vision AI
                    try:
                        conf_limit = await ConfigAdapter().get_config(token, event, "CONFIDENCE_LIMIT")
                        ai_information = AiImageService().analyze_photo_g_langrenn_v2(
                            url_main, url_crop, conf_limit
                        )
                    except Exception as e:
                        error_text = f"AiImageService - Error analysing photos {url_main} and {url_crop} - {e}"
                        logging.exception(error_text)
                        raise Exception(error_text) from e

                    pub_message = {
                        "ai_information": ai_information,
                        "crop_url": url_crop,
                        "event_id": event["id"],
                        "photo_info": get_image_description(group["main"]),
                        "photo_url": url_main,
                    }

                    # publish info to pubsub
                    try:
                        result = await GooglePubSubAdapter().publish_message(
                            json.dumps(pub_message)
                        )
                    except Exception as e:
                        error_text = f"GooglePubSub - error publishing message {pub_message} - {e}"
                        raise Exception(error_text) from e

                    # archive photos - ignore errors
                    try:
                        PhotosFileAdapter().move_photo_to_archive(
                            Path(group["main"]).name
                        )
                        PhotosFileAdapter().move_photo_to_archive(
                            Path(group["crop"]).name
                        )
                    except Exception:
                        error_text = f"{service_name} - Error moving files {group} to archive."
                        logging.exception(error_text)

                    logging.debug(f"Published message {result} to pubsub.")
                    i_photo_count += 1

            except Exception:
                error_text = f"{service_name} - Error handling files {group}"
                i_error_count += 1
                logging.exception(error_text)
        informasjon = f"Pushed {i_photo_count} photos to pubsub, errors: {i_error_count}"
        await StatusAdapter().create_status(
            token,
            event,
            status_type,
            informasjon,
        )
        return informasjon


def group_photos(photo_list: list[str]) -> dict[str, dict[str, str]]:
    """Create a dictionary where the photos are grouped by main and crop."""
    photo_dict = {}
    for photo_name in photo_list:
        if "_crop" in photo_name:
            main_photo = photo_name.replace("_crop", "")
            if main_photo not in photo_dict:
                photo_dict[main_photo] = {"main": "", "crop": photo_name}
            else:
                photo_dict[main_photo] = {"main": main_photo, "crop": photo_name}
        elif photo_name not in photo_dict:
            photo_dict[photo_name] = {"main": photo_name, "crop": ""}
        else:
            photo_dict[photo_name] = {
                "main": photo_name,
                "crop": photo_dict[photo_name]["crop"],
            }
    return photo_dict


def get_image_description(file_path: str) -> dict:
    """Get image description from EXIF data."""
    try:
        # Load the EXIF data from the image
        exif_dict = piexif.load(file_path)

        # Get the ImageDescription from the '0th' IFD
        image_description = exif_dict["0th"].get(piexif.ImageIFD.ImageDescription)

        # The ImageDescription is a bytes object, so decode it to a string
        image_description = image_description.decode("utf-8")

        # The ImageDescription is a JSON string, so parse it to a dictionary
        image_info = json.loads(image_description)
    except Exception:
        logging.exception(f"Error reading image description - {file_path}")
        image_info = {}

    return image_info
