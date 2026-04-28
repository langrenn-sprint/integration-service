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
    ServiceInstanceAdapter,
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
service_info = {
    "mode": "",
    "name": "",
    "id": "",
    "status_type": "",
    "storage_mode": "",
}

if os.getenv("K_REVISION"):
    service_info["name"] = str(os.getenv("K_REVISION"))
else:
    service_info["name"] = f"{socket.gethostname()}"


async def create_service_instance_dict(
    event: dict,
) -> dict:
    """Create a service instance dictionary for the video service.

    Args:
        event: The event dictionary

    Returns:
        A dictionary representing the service instance

    """
    time_now = EventsAdapter().get_local_time(event, "log")
    return {
        "service_type": "INTEGRATION_SERVICE",
        "instance_name": service_info["name"],
        "status": "ready",
        "host_name": socket.gethostname(),
        "action": "",
        "event_id": event["id"],
        "started_at": time_now,
        "last_heartbeat": time_now,
        "metadata": {}
    }


async def run_the_service(token: str, event: dict, service_info: dict) -> None:
    """Run one iteration of the integration service loop."""
    try:
        service_config = await get_config(token, service_info["id"])
        if service_config["start"]:
            await ServiceInstanceAdapter().update_service_instance_status(
                token, event, service_info["id"], "running"
            )
            if service_info["storage_mode"] in ["cloud_storage", "local_storage"]:
                await SyncService().process_captured_raw_videos(token, event, service_info["storage_mode"])
                await SyncService().process_captured_srt_videos(token, event)
            elif service_info["storage_mode"] == "pull_detections":
                await SyncService().pull_photos_from_pubsub(token, event)
            else:
                raise_invalid_storage_mode(service_info["storage_mode"])
    except Exception as e:
        err_string = str(e)
        logging.exception(err_string)
        # try new login if token expired
        if str(HTTPStatus.UNAUTHORIZED.value) in err_string or str(
            HTTPStatus.FORBIDDEN.value
        ) in err_string:
            token = await do_login()
        else:
            await StatusAdapter().create_status(
                token,
                event,
                service_info["status_type"],
                f"Error in {service_info['name']}. Stopping.",
                {"error": err_string},
            )


async def main() -> None:
    """CLI for analysing integration stream."""
    token = ""
    event = {}
    i = STATUS_INTERVAL + 1
    try:
        try:
            # login to data-source
            token = await do_login()
            event = await get_event(token)

            service_info["status_type"] = await ConfigAdapter().get_config(
                token, event["id"], "INTEGRATION_SERVICE_STATUS_TYPE"
            )
            service_instance = await create_service_instance_dict(event)
            service_info["id"] = await ServiceInstanceAdapter().create_service_instance(token, service_instance)
            service_info["storage_mode"] = await ConfigAdapter().get_config(
                token, event["id"], "VIDEO_STORAGE_MODE"
            )
            await StatusAdapter().create_status(
                token, event, service_info["status_type"], f"{service_info['name']} is ready!", {}
            )

            while True:
                try:
                    await run_the_service(token, event, service_info)
                    if i > STATUS_INTERVAL:
                        await ServiceInstanceAdapter().send_heartbeat(token, event, service_info["id"])
                        i = 0
                    else:
                        i += 1
                    await ServiceInstanceAdapter().update_service_instance_status(token, event, service_info["id"], "ready")
                except Exception as e:
                    err_string = str(e)
                    logging.exception(err_string)
                    # try new login if token expired
                    if str(HTTPStatus.UNAUTHORIZED.value) in err_string or str(
                        HTTPStatus.FORBIDDEN.value
                    ) in err_string:
                        token = await do_login()
                    else:
                        raise Exception(err_string) from e
                await asyncio.sleep(5)

        except Exception as e:
            err_string = str(e)
            logging.exception(err_string)
            await StatusAdapter().create_status(
                token, event, status_type, "Critical Error - exiting program", {"error": err_string}
            )
    except asyncio.CancelledError:
        await StatusAdapter().create_status(
            token, event, service_info["status_type"], f"{service_info['name']} was cancelled (ctrl-c pressed).", {}
        )
    if service_info["id"]:
        await ServiceInstanceAdapter().delete_service_instance(token, service_info["id"])
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

async def get_config(token: str, instance_id: str) -> dict:
    """Get config details - use info from db."""
    instance_info = await ServiceInstanceAdapter().get_service_instance_by_id(token, instance_id)
    instance_config = {
        "start": False,
    }

    if instance_info["action"] == "start":
        instance_config["start"] = True
    elif instance_info["action"] == "stop":
        instance_config["start"] = False

    return instance_config

if __name__ == "__main__":
    asyncio.run(main())
