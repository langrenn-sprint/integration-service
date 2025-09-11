"""Module for application looking at video and detecting line crossings."""

import asyncio
import logging
import os
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
STATUS_INTERVAL = 60

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


async def main() -> None:
    """CLI for analysing video stream."""
    token = ""
    event = {}
    status_type = ""
    i = STATUS_INTERVAL
    try:
        # login to data-source
        token = await do_login()
        event = await get_event(token)
        information = (
            f"integration-service is ready! - {event['name']}, {event['date_of_event']}"
        )
        status_type = await ConfigAdapter().get_config(
            token, event["id"], "INTEGRATION_SERVICE_STATUS_TYPE"
        )
        await StatusAdapter().create_status(
            token, event, status_type, information
        )

        # service ready!
        await ConfigAdapter().update_config(
            token, event["id"], "INTEGRATION_SERVICE_AVAILABLE", "True"
        )
        while True:
            service_config = await get_service_status(token, event)
            try:
                # run simulation
                if service_config["service_start"]:
                    # run service
                    await ConfigAdapter().update_config(token, event["id"], "INTEGRATION_SERVICE_RUNNING", "True")
                    if service_config["service_mode"] in ["push_detections"]:
                        await SyncService().push_new_photos_from_file(token, event)
                    elif service_config["service_mode"] in ["pull_detections"]:
                        await SyncService().pull_photos_from_pubsub(token, event)
                    elif service_config["service_mode"] in ["push_captured_video"]:
                        await SyncService().push_captured_video(token, event)
                    else:
                        raise_invalid_service_mode(service_config["service_mode"])
                    await ConfigAdapter().update_config(token, event["id"], "INTEGRATION_SERVICE_RUNNING", "False")
                else:
                    # should be invalid (no muliti thread) - reset
                    await ConfigAdapter().update_config(
                        token, event["id"], "INTEGRATION_SERVICE_RUNNING", "False"
                    )
            except Exception as e:
                err_string = str(e)
                logging.exception(err_string)
                await StatusAdapter().create_status(
                    token,
                    event,
                    status_type,
                    f"Error in Integration Service. Stopping.: {err_string}",
                )
                await ConfigAdapter().update_config(
                    token, event["id"], "INTEGRATION_SERVICE_RUNNING", "False"
                )
                await ConfigAdapter().update_config(
                    token, event["id"], "INTEGRATION_SERVICE_START", "False"
                )
            if i > STATUS_INTERVAL:
                informasjon = f"Integration Service kjører i modus {service_config['service_mode']}."
                await StatusAdapter().create_status(
                    token, event, status_type, informasjon
                )
                i = 0
            else:
                i += 1
            await asyncio.sleep(2)
    except Exception as e:
        err_string = str(e)
        logging.exception(err_string)
        await StatusAdapter().create_status(
            token, event, status_type, f"Critical Error - exiting program: {err_string}"
        )
    await ConfigAdapter().update_config(
        token, event["id"], "INTEGRATION_SERVICE_AVAILABLE", "False"
    )
    logging.info("Goodbye!")


def raise_invalid_service_mode(service_mode: str) -> None:
    """Raise exception for invalid service mode."""
    err_string = f"Invalid service mode: {service_mode}. Use 'push' or 'pull'."
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
    service_mode = await ConfigAdapter().get_config(
        token, event["id"], "INTEGRATION_SERVICE_MODE"
    )
    return {
        "service_available": service_available,
        "service_running": service_running,
        "service_start": service_start,
        "service_mode": service_mode
    }


if __name__ == "__main__":
    asyncio.run(main())
