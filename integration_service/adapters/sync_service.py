"""Module for sync service."""

import datetime
import json
import logging
import os
from http import HTTPStatus
from pathlib import Path

import piexif

from .ai_image_service import AiImageService
from .config_adapter import ConfigAdapter
from .contestants_adapter import ContestantsAdapter
from .events_adapter import EventsAdapter
from .google_cloud_storage_adapter import GoogleCloudStorageAdapter
from .google_pub_sub_adapter import GooglePubSubAdapter
from .photos_adapter import PhotosAdapter
from .photos_file_adapter import PhotosFileAdapter
from .raceclasses_adapter import RaceclassesAdapter
from .raceplans_adapter import RaceplansAdapter
from .start_adapter import StartAdapter
from .status_adapter import StatusAdapter

BIG_DIFF = 99999


class SyncService:
    """Class representing sync service."""

    async def pull_photos_from_pubsub(
        self,
        token: str,
        event: dict,
    ) -> str:
        """Get events from pubsub and sync with local database."""
        informasjon = ""
        status_type = await ConfigAdapter().get_config(
            token, event["id"], "INTEGRATION_SERVICE_STATUS_TYPE"
        )
        i_c = 0
        i_u = 0
        i_other = 0
        # get all messages from pubsub

        pull_messages = GooglePubSubAdapter().pull_messages()
        if len(pull_messages) == 0:
            informasjon = "Ingen bilder funnet."
        else:
            raceclasses = await RaceclassesAdapter().get_raceclasses(
                token, event["id"]
            )
            for message in pull_messages:
                # use message data to identify contestant/bib and race
                # then create photo
                # check if message event_id is same as event_id
                if message["event_id"] == event["id"]:
                    try:
                        creation_time = message["photo_info"]["passeringstid"]
                    except Exception:
                        creation_time = ""
                    # update or create record in db
                    try:
                        photo = await PhotosAdapter().get_photo_by_g_base_url(
                            token, message["photo_url"]
                        )
                    except Exception:
                        photo = {}
                    if photo:
                        # update existing photo
                        photo["name"] = Path(message["photo_url"]).name
                        photo["g_crop_url"] = ""
                        photo["g_base_url"] = message["photo_url"]
                        if message["photo_info"]["passeringspunkt"] in [
                            "Finish",
                            "Mål",
                        ]:
                            photo["is_photo_finish"] = True
                        if message["photo_info"]["passeringspunkt"] == "Start":
                            photo["is_start_registration"] = True
                        result = await PhotosAdapter().update_photo(
                            token, photo["id"], photo
                        )
                        logging.debug(
                            f"Updated photo with id {photo['id']}, result {result}"
                        )
                        i_u += 1
                    else:
                        # create new photo
                        photo_info = {
                            "confidence": 0,
                            "name": Path(message["photo_url"]).name,
                            "is_photo_finish": False,
                            "is_start_registration": False,
                            "starred": False,
                            "event_id": event["id"],
                            "creation_time": await format_time(token, event, creation_time),
                            "ai_information": message["ai_information"],
                            "information": message["photo_info"],
                            "race_id": "",
                            "raceclass": "",
                            "biblist": [],
                            "clublist": [],
                            "g_crop_url": message["crop_url"],
                            "g_base_url": message["photo_url"],
                        }
                        # new photo - try to link with event activities
                        if message["photo_info"]["passeringspunkt"] in [
                            "Finish",
                            "Mål",
                        ]:
                            photo_info["is_photo_finish"] = True
                        if message["photo_info"]["passeringspunkt"] == "Start":
                            photo_info["is_start_registration"] = True
                        if message["ai_information"]:
                            result = await link_ai_info_to_photo(
                                token,
                                photo_info,
                                message["ai_information"],
                                event,
                                raceclasses,
                            )

                        photo_id = await PhotosAdapter().create_photo(
                            token, photo_info
                        )
                        await ConfigAdapter().update_config(
                            token, event["id"], "GOOGLE_LATEST_PHOTO", message["photo_url"]
                        )
                        logging.debug(f"Created photo with id {photo_id}")
                        i_c += 1
                else:
                    i_other += 1
            informasjon = (
                f"Synkronisert bilder fra PubSub. {i_u} oppdatert og {i_c} opprettet."
            )
            if i_other > 0:
                informasjon += f" Forkastet {i_other} meldinger som ikke tilhører dette arrangementet."
            await StatusAdapter().create_status(token, event, status_type, informasjon)
        return informasjon

    async def push_new_photos_from_file(self, token: str, event: dict) -> str:
        """Push photos to cloud storage, analyze and publish."""
        i_photo_count = 0
        i_error_count = 0
        informasjon = ""
        service_name = "push_new_photos_from_file"
        status_type = await ConfigAdapter().get_config(
            token, event["id"], "INTEGRATION_SERVICE_STATUS_TYPE"
        )

        # loop photos and group crops with main photo - only upload complete pairs
        new_photos = PhotosFileAdapter().get_all_photos()
        new_photos_grouped = group_photos(new_photos)
        for x in new_photos_grouped:
            group = {}
            try:
                group = new_photos_grouped[x]
                if group["main"] and group["crop"]:
                    # upload photo to cloud storage
                    url_main = GoogleCloudStorageAdapter().upload_blob(
                        "photos", group["main"]
                    )
                    url_crop = GoogleCloudStorageAdapter().upload_blob(
                        "photos", group["crop"]
                    )

                    # analyze photo with Vision AI
                    try:
                        conf_limit = await ConfigAdapter().get_config(token, event["id"], "CONFIDENCE_LIMIT")
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
                        result = GooglePubSubAdapter().publish_message(
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

            except Exception as e:
                error_text = f"{service_name} - {e}"
                i_error_count += 1
                await StatusAdapter().create_status(
                    token,
                    event,
                    status_type,
                    error_text,
                )
                logging.exception(error_text)
        informasjon = f"Pushed {i_photo_count} photos to pubsub, errors: {i_error_count}"
        if (i_error_count > 0) or (i_photo_count > 0):
            await StatusAdapter().create_status(
                token,
                event,
                status_type,
                informasjon,
            )
        return informasjon


    async def push_captured_video(self, token: str, event: dict) -> str:
        """Push captured video to cloud storage, analyze and publish."""
        i_video_count = 0
        i_error_count = 0
        informasjon = ""
        service_name = "push_captured_video"
        status_type = await ConfigAdapter().get_config(
            token, event["id"], "INTEGRATION_SERVICE_STATUS_TYPE"
        )

        # loop videos
        url_video = ""
        new_videos = PhotosFileAdapter().get_all_capture_files()
        for video in new_videos:
            try:
                # upload video to cloud storage
                url_video = GoogleCloudStorageAdapter().upload_blob("CAPTURE", video)

                # archive video - ignore errors
                try:
                    PhotosFileAdapter().move_to_captured_archive(
                        Path(video).name
                    )
                except Exception:
                    error_text = f"{service_name} - Error moving file {video} to archive."
                    logging.exception(error_text)

                i_video_count += 1

            except Exception as e:
                error_text = f"{service_name} - {e}"
                i_error_count += 1
                await StatusAdapter().create_status(
                    token,
                    event,
                    status_type,
                    error_text,
                )
                logging.exception(error_text)
        informasjon = f"Pushed {i_video_count} videos (<a href='{url_video}'>link</a>) to cloud bucket, errors: {i_error_count}"
        if (i_error_count > 0) or (i_video_count > 0):
            await StatusAdapter().create_status(
                token,
                event,
                status_type,
                informasjon,
            )
        return informasjon

async def link_ai_info_to_photo(
    token: str, photo_info: dict, ai_information: dict, event: dict, raceclasses: list
) -> int:
    """Link ai information to photo."""
    # first check for bib on cropped image
    result = HTTPStatus.NO_CONTENT
    for nummer in ai_information["ai_crop_numbers"]:
        result = await find_race_info_by_bib(
            token, nummer, photo_info, event, raceclasses, 100
        )
    # use time only if by bib was not successful
    if result == HTTPStatus.NO_CONTENT:
        result = await find_race_info_by_time(token, photo_info, event, 50)
    return result


async def find_race_info_by_bib(
    token: str,
    bib: int,
    photo_info: dict,
    event: dict,
    raceclasses: list,
    confidence: int,
) -> int:
    """Analyse photo ai info and add race info to photo."""
    result = HTTPStatus.NO_CONTENT  # no content
    foundheat = ""
    raceduration = await ConfigAdapter().get_config_int(
        token, event["id"], "RACE_DURATION_ESTIMATE"
    )
    starter = await StartAdapter().get_start_entries_by_bib(token, event["id"], bib)
    if len(starter) > 0:
        for start in starter:
            # check heat (if not already found)
            if foundheat == "":
                foundheat = await verify_heat_time(
                    token,
                    event,
                    photo_info["creation_time"],
                    raceduration,
                    start["race_id"],
                )
                if foundheat != "":
                    photo_info["race_id"] = foundheat
                    result = HTTPStatus.OK  # OK, found a heat

                    # Get klubb and klasse
                    if bib not in photo_info["biblist"]:
                        try:
                            contestant = (
                                await ContestantsAdapter().get_contestant_by_bib(
                                    token, event["id"], bib
                                )
                            )
                            if contestant:
                                photo_info["biblist"].append(bib)
                                if contestant["club"] not in photo_info["clublist"]:
                                    photo_info["clublist"].append(contestant["club"])
                                photo_info["raceclass"] = find_raceclass(
                                    contestant["ageclass"], raceclasses
                                )
                                photo_info["confidence"] = (
                                    confidence  # identified by bib - high confidence!
                                )
                        except Exception as e:
                            logging.debug(f"Missing attribute - {e}")
                            result = HTTPStatus.PARTIAL_CONTENT  # Partial content
    return result


async def find_race_info_by_time(
    token: str, photo_info: dict, event: dict, confidence: int
) -> int:
    """Analyse photo time and identify race with best time-match."""
    result = HTTPStatus.NO_CONTENT  # no content
    raceduration = await ConfigAdapter().get_config_int(
        token, event["id"], "RACE_DURATION_ESTIMATE"
    )
    all_races = await RaceplansAdapter().get_all_races(token, event["id"])
    best_fit_race = {
        "race_id": "",
        "seconds_diff": BIG_DIFF,
        "raceclass": "",
    }
    for race in all_races:
        seconds_diff = abs(
            await get_seconds_diff(token, event, photo_info["creation_time"], race["start_time"])
            - raceduration
        )

        if seconds_diff < best_fit_race["seconds_diff"]:
            best_fit_race["seconds_diff"] = seconds_diff
            best_fit_race["race_id"] = race["id"]
            best_fit_race["raceclass"] = race["raceclass"]
            best_fit_race["name"] = f"{race['round']}{race['index']}{race['heat']}"

    if best_fit_race["seconds_diff"] < BIG_DIFF:
        photo_info["race_id"] = best_fit_race["race_id"]
        photo_info["raceclass"] = best_fit_race["raceclass"]
        result = HTTPStatus.OK  # OK, found a heat
        photo_info["confidence"] = confidence  # identified by time - medium confidence!
        logging.info(f"Diff - best match race {best_fit_race}")
    return result


def find_raceclass(ageclass: str, raceclasses: list) -> str:
    """Analyse photo tags and identify løpsklasse."""
    funnetklasse = ""
    for klasse in raceclasses:
        if ageclass in klasse["ageclasses"]:
            funnetklasse = klasse["name"]
            break

    return funnetklasse


async def format_time(token: str, event: dict, timez: str) -> str:
    """Convert to normalized time - string formats."""
    time = ""
    t1 = None
    date_patterns = await ConfigAdapter().get_config(token, event["id"], "DATE_PATTERNS")
    date_pattern_list = date_patterns.split(";")
    for pattern in date_pattern_list:
        try:
            t1 = datetime.datetime.strptime(timez, pattern).replace(tzinfo=datetime.UTC)
        except ValueError:
            logging.debug(f"Got error parsing time {ValueError}")
    if t1:
        time = f"{t1.strftime('%Y')}-{t1.strftime('%m')}-{t1.strftime('%d')}T{t1.strftime('%X')}"
    return time


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


async def get_seconds_diff(token: str, event: dict, time1: str, time2: str) -> int:
    """Compare time1 and time2, return time diff in min."""
    t1 = datetime.datetime.strptime("1", "%S").replace(tzinfo=datetime.UTC)  # Initialize time to zero
    t2 = datetime.datetime.strptime("1", "%S").replace(tzinfo=datetime.UTC)

    date_patterns = await ConfigAdapter().get_config(token, event["id"], "DATE_PATTERNS")
    date_pattern_list = date_patterns.split(";")
    for pattern in date_pattern_list:
        try:
            t1 = datetime.datetime.strptime(time1, pattern).replace(tzinfo=datetime.UTC)
        except ValueError:
            logging.debug(f"Got error parsing time {ValueError}")
        try:
            t2 = datetime.datetime.strptime(time2, pattern).replace(tzinfo=datetime.UTC)
        except ValueError:
            logging.debug(f"Got error parsing time {ValueError}")

    return int((t1 - t2).total_seconds())


async def verify_heat_time(
    token: str,
    event: dict,
    datetime_foto: str,
    raceduration: int,
    race_id: str,
) -> str:
    """Analyse photo tags and identify heat."""
    foundheat = ""
    if datetime_foto is not None:
        race = await RaceplansAdapter().get_race_by_id(token, race_id)
        if race is not None:
            max_time_dev = await ConfigAdapter().get_config_int(
                token, event["id"], "RACE_TIME_DEVIATION_ALLOWED"
            )
            seconds = await get_seconds_diff(token, event, datetime_foto, race["start_time"])
            if 0 < seconds < (max_time_dev + raceduration):
                foundheat = race["id"]
                race_name = (
                    f"{race['raceclass']}-{race['round']}{race['index']}{race['heat']}"
                )
                logging.info(
                    f"Diff - confirmed bib {seconds} seconds, for race {race_name}"
                )

    return foundheat
