"""Module for user adapter."""

import logging
import os
from http import HTTPStatus

from aiohttp import ClientSession, hdrs
from dotenv import load_dotenv
from multidict import MultiDict

# Load environment variables from .env file
load_dotenv()

# Get environment variables with validation
USERS_HOST_SERVER = os.getenv("USERS_HOST_SERVER")
USERS_HOST_PORT = os.getenv("USERS_HOST_PORT")

if not USERS_HOST_SERVER or not USERS_HOST_PORT:
    err_msg = "USERS_HOST_SERVER or USERS_HOST_PORT is not set."
    raise OSError(err_msg)

USER_SERVICE_URL = f"http://{USERS_HOST_SERVER}:{USERS_HOST_PORT}"


class UserAdapter:
    """Class representing user."""

    async def login(self, username: str, password: str) -> str:
        """Perform login function, return token."""
        result = 0
        request_body = {
            "username": username,
            "password": password,
        }
        headers = MultiDict(
            [
                (hdrs.CONTENT_TYPE, "application/json"),
            ]
        )
        async with ClientSession() as session, session.post(
            f"{USER_SERVICE_URL}/login", headers=headers, json=request_body
        ) as resp:
            result = resp.status
            logging.info(f"do login - got response {result}")
            if result == HTTPStatus.OK:
                body = await resp.json()
                return body["token"]
        return ""
