"""Module for application looking at video and detecting line crossings."""

import asyncio
import logging
import os
import socket
from http import HTTPStatus
from logging.handlers import RotatingFileHandler

from integration_service.adapters import (
    ConfigAdapter,
    EventsAdapter,
    StatusAdapter,
    SyncService,
    UserAdapter,
)

# get base settings
CONTEXT_SETTINGS = {"help_option_names": ["-h", "--help"]}
event = {"id": ""}
status_type = ""
STATUS_INTERVAL = 250

# set up logging
LOGGING_LEVEL = os.getenv("LOGGING_LEVEL", "INFO")
logging.basicConfig(
    level=LOGGING_LEVEL,
    format="%(asctime)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
# Separate logging for errors
file_handler = RotatingFileHandler("error.log", maxBytes=1024 * 1024, backupCount=5)
file_handler.setLevel(logging.ERROR)

# Create a formatter with the desired format
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
file_handler.setFormatter(formatter)
logging.getLogger().addHandler(file_handler)

# Generate from hostname and PID
instance_name = ""
if os.getenv("K_REVISION"):
    instance_name = str(os.getenv("K_REVISION"))
else:
    instance_name = f"{socket.gethostname()}"


async def main() -> None:
    """CLI for analysing integration stream."""
    token = ""
    event = {}
    status_type = ""
    i = 0
    try:
        try:
            # login to data-source
            token = await do_login()
            event = await get_event(token)
            information = (f"{instance_name} er klar.")
            status_type = await ConfigAdapter().get_config(
                token, event["id"], "INTEGRATION_SERVICE_STATUS_TYPE"
            )
            await StatusAdapter().create_status(
                token, event, status_type, information, event
            )

            while True:
                try:
                    service_config = await get_service_status(token, event)
                    if service_config["service_start"]:
                        # run service
                        await ConfigAdapter().update_config(token, event["id"], "INTEGRATION_SERVICE_RUNNING", "True")
                        if service_config["storage_mode"] in ["cloud_storage", "local_storage"]:
                            await SyncService().process_captured_raw_videos(token, event, service_config["storage_mode"])
                        elif service_config["storage_mode"] in ["pull_detections"]:
                            await SyncService().pull_photos_from_pubsub(token, event)
                        else:
                            raise_invalid_storage_mode(service_config["storage_mode"])
                        await ConfigAdapter().update_config(token, event["id"], "INTEGRATION_SERVICE_RUNNING", "False")
                    if i > STATUS_INTERVAL:
                        information = (f"{instance_name} er klar.")
                        await StatusAdapter().create_status(
                            token, event, status_type, information, event
                        )
                        i = 0
                    else:
                        i += 1
                    # service ready!
                    await ConfigAdapter().update_config(
                        token, event["id"], "INTEGRATION_SERVICE_RUNNING", "False"
                    )
                    await ConfigAdapter().update_config(
                        token, event["id"], "INTEGRATION_SERVICE_AVAILABLE", "True"
                    )
                    await asyncio.sleep(5)
                except Exception as e:
                    err_string = str(e)
                    logging.exception(err_string)
                    # try new login if token expired (401 error)
                    if str(HTTPStatus.UNAUTHORIZED.value) in err_string:
                        token = await do_login()
                    else:
                        await StatusAdapter().create_status(
                            token,
                            event,
                            status_type,
                            f"Error in {instance_name}. Stopping.",
                            {"error": err_string},
                        )
                        await ConfigAdapter().update_config(
                            token, event["id"], "INTEGRATION_SERVICE_START", "False"
                        )
        except Exception as e:
            err_string = str(e)
            logging.exception(err_string)
            await StatusAdapter().create_status(
                token, event, status_type, "Critical Error - exiting program", {"error": err_string}
            )
    except asyncio.CancelledError:
        await ConfigAdapter().update_config(
            token, event["id"], "INTEGRATION_SERVICE_RUNNING", "False"
        )
        await StatusAdapter().create_status(
            token, event, status_type, f"{instance_name} was cancelled (ctrl-c pressed).", {}
        )
    await ConfigAdapter().update_config(
        token, event["id"], "INTEGRATION_SERVICE_AVAILABLE", "False"
    )
    logging.info("Goodbye!")


def raise_invalid_storage_mode(storage_mode: str) -> None:
    """Raise exception for invalid storage mode."""
    err_string = f"Invalid storage mode: {storage_mode}."
    raise Exception(err_string)


async def do_login() -> str:
    """Login to data-source."""
    uid = os.getenv("ADMIN_USERNAME", "a")
    pw = os.getenv("ADMIN_PASSWORD", ".")
    while True:
        try:
            token = await UserAdapter().login(uid, pw)
            if token:
                return token
        except Exception as e:
            err_string = str(e)
            logging.info(err_string)
        logging.info("Integration service is waiting for db connection")
        await asyncio.sleep(5)



async def get_event(token: str) -> dict:
    """Get event_details - use info from config and db."""
    def raise_multiple_events_error(events_db: list) -> None:
        """Raise an exception for multiple events found."""
        information = (
            f"Multiple events found. Please specify an EVENT_ID in .env: {events_db}"
        )
        raise Exception(information)

    event = {}
    while True:
        try:
            events_db = await EventsAdapter().get_all_events(token)
            event_id_config = os.getenv("EVENT_ID")
            if len(events_db) == 1:
                event = events_db[0]
            elif len(events_db) > 1:
                for _event in events_db:
                    if _event["id"] == event_id_config:
                        event = _event
                        break
                else:
                    raise_multiple_events_error(events_db)
            if event:
                break
        except Exception as e:
            err_string = str(e)
            logging.info(err_string)
        logging.info("integration-service is waiting for an event to work on.")
        await asyncio.sleep(5)

    return event


async def get_service_status(token: str, event: dict) -> dict:
    """Get config details - use info from db."""
    service_available = await ConfigAdapter().get_config_bool(
        token, event["id"], "INTEGRATION_SERVICE_AVAILABLE"
    )
    service_running = await ConfigAdapter().get_config_bool(
        token, event["id"], "INTEGRATION_SERVICE_RUNNING"
    )
    service_start = await ConfigAdapter().get_config_bool(
        token, event["id"], "INTEGRATION_SERVICE_START"
    )
    storage_mode = await ConfigAdapter().get_config(
        token, event["id"], "VIDEO_STORAGE_MODE"
    )
    return {
        "service_available": service_available,
        "service_running": service_running,
        "service_start": service_start,
        "storage_mode": storage_mode
    }


if __name__ == "__main__":
    asyncio.run(main())
