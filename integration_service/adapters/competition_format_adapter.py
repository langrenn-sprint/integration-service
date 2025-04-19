"""Module for competition format adapter."""

import json
import logging
import os
from http import HTTPStatus
from pathlib import Path

from aiohttp import ClientSession, hdrs, web
from multidict import MultiDict

COMPETITION_FORMAT_HOST_SERVER = os.getenv(
    "COMPETITION_FORMAT_HOST_SERVER", "localhost"
)
COMPETITION_FORMAT_HOST_PORT = os.getenv("COMPETITION_FORMAT_HOST_PORT", "8094")
COMPETITION_FORMAT_SERVICE_URL = (
    f"http://{COMPETITION_FORMAT_HOST_SERVER}:{COMPETITION_FORMAT_HOST_PORT}"
)


class CompetitionFormatAdapter:
    """Class representing competition format."""

    async def get_competition_formats(self, token: str) -> list:
        """Get competition_formats function."""
        competition_formats = []
        headers = MultiDict(
            [
                (hdrs.CONTENT_TYPE, "application/json"),
                (hdrs.AUTHORIZATION, f"Bearer {token}"),
            ]
        )

        async with ClientSession() as session, session.get(
            f"{COMPETITION_FORMAT_SERVICE_URL}/competition-formats", headers=headers
        ) as resp:
            logging.debug(f"get_competition_formats - got response {resp.status}")
            if resp.status == HTTPStatus.OK:
                competition_formats = await resp.json()
                logging.debug(
                    f"competition_formats - got response {competition_formats}"
                )
            elif resp.status == HTTPStatus.UNAUTHORIZED:
                err_msg = f"Login expired: {resp}"
                raise Exception(err_msg)
            else:
                servicename = "get_competition_formats"
                body = await resp.json()
                logging.error(f"{servicename} failed - {resp.status} - {body}")
                raise web.HTTPBadRequest(
                    reason=f"Error - {resp.status}: {body['detail']}."
                )
        return competition_formats
