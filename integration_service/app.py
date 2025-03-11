"""Module for application looking at video and detecting line crossings."""

import asyncio
import logging
import os
from logging.handlers import RotatingFileHandler

from dotenv import load_dotenv

from integration_service.adapters import (
    ConfigAdapter,
    EventsAdapter,
    StatusAdapter,
    SyncService,
    UserAdapter,
)

# get base settings
load_dotenv()
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

        # service ready!
        await ConfigAdapter().update_config(
            token, event, "INTEGRATION_SERVICE_AVAILABLE", "True"
        )
        while True:
            service_config = await get_service_status(token, event)
            try:
                # run simulation
                if service_config["service_start"]:
                    # run service
                    await ConfigAdapter().update_config(token, event, "INTEGRATION_SERVICE_RUNNING", "True")
                    if service_config["service_mode"] in ["PUSH", "push", "Push"]:
                        await SyncService().push_new_photos_from_file(token, event)
                    elif service_config["service_mode"] in ["PULL", "pull", "Pull"]:
                        await SyncService().pull_photos_from_pubsub(token, event)
                    else:
                        raise_invalid_service_mode(service_config["service_mode"])
                    await ConfigAdapter().update_config(token, event, "INTEGRATION_SERVICE_RUNNING", "False")
                else:
                    # should be invalid (no muliti thread) - reset
                    await ConfigAdapter().update_config(
                        token, event, "INTEGRATION_SERVICE_RUNNING", "False"
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
                    token, event, "INTEGRATION_SERVICE_RUNNING", "False"
                )
                await ConfigAdapter().update_config(
                    token, event, "INTEGRATION_SERVICE_START", "False"
                )
            if i >= STATUS_INTERVAL:
                informasjon = f"Integration Service er kjører - status: {service_config}."
                logging.info(informasjon)
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
        token, event, "INTEGRATION_SERVICE_AVAILABLE", "False"
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
    event = {}
    event_found = False
    while not event_found:
        try:
            events_db = await EventsAdapter().get_all_events(token)
            event_id_config = os.getenv("EVENT_ID")
            if len(events_db) == 1:
                event = events_db[0]
            elif len(events_db) == 0:
                event["id"] = event_id_config
            else:
                for _event in events_db:
                    if _event["id"] == event_id_config:
                        event = _event
                        break
                else:
                    if event_id_config:
                        event["id"] = event_id_config
                    else:
                        event["id"] = events_db[0]["id"]
            status_type = await ConfigAdapter().get_config(
                token, event, "INTEGRATION_SERVICE_STATUS_TYPE"
            )
            if event:
                event_found = True
                information = (
                    f"integration-service is ready! - {event['name']}, {event['date']}"
                )
                await StatusAdapter().create_status(
                    token, event, status_type, information
                )
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
        token, event, "INTEGRATION_SERVICE_AVAILABLE"
    )
    service_running = await ConfigAdapter().get_config_bool(
        token, event, "INTEGRATION_SERVICE_RUNNING"
    )
    service_start = await ConfigAdapter().get_config_bool(
        token, event, "INTEGRATION_SERVICE_START"
    )
    service_mode = await ConfigAdapter().get_config(
        token, event, "INTEGRATION_SERVICE_MODE"
    )
    return {
        "service_available": service_available,
        "service_running": service_running,
        "service_start": service_start,
        "service_mode": service_mode
    }


if __name__ == "__main__":
    asyncio.run(main())
