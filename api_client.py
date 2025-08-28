# Version: 1.0.1
"""API client for LSR integration.

This module provides functions to handle API requests to https://mp.lsr.ru/api/rpc.
"""

import aiohttp
import logging
import hashlib
from typing import Dict, List
from .const import NAMESPACE

_LOGGER = logging.getLogger(__name__)

async def authenticate(
    session: aiohttp.ClientSession,
    username: str,
    password: str,
    app_instance_id: str
) -> Dict[str, Any]:
    """authenticate with the LSR API and retrieve access and refresh tokens.

    Args:
        session (aiohttp.ClientSession): The HTTP session to use for the request.
        username (str): The username for authentication.
        password (str): The password for authentication.
        app_instance_id (str): The unique app instance ID.

    Returns:
        Dict[str, Any]: Response data containing access_token and refresh_token.

    Raises:
        aiohttp.ClientError: If the API request fails.
    """
    login_sha256 = hashlib.sha256(username.encode()).hexdigest()
    password_sha256 = hashlib.sha256(password.encode()).hexdigest()
    payload = {
        "data": {
            "credentials": {
                "loginSha256": login_sha256,
                "password": password_sha256,
            },
            "device": {
                "appInstanceId": app_instance_id,
                "platform": "ANDROID",
                "timeOffset": 10800,
                "appType": "CLIENT",
                "model": "sdk_gphone64_arm64",
            },
            "userType": "CLIENT",
        },
        "method": "Authorize",
        "namespace": NAMESPACE,
        "operation": "REQUEST",
        "parameters": {},
    }
    headers = {
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36",
        "Content-Type": "application/json",
    }
    try:
        async with session.post("https://mp.lsr.ru/api/rpc", json=payload, headers=headers, timeout=30) as resp:
            if resp.status != 200:
                _LOGGER.error("Authentication failed: HTTP %s", resp.status)
                raise aiohttp.ClientError(f"Authentication failed: HTTP {resp.status}")
            data = await resp.json()
            if data.get("statusCode") != 200:
                _LOGGER.error("Authentication failed: Status code %s, message: %s", data.get("statusCode"), data.get("message", "Unknown error"))
                raise aiohttp.ClientError(f"Authentication failed: Status code {data.get('statusCode')}")
            _LOGGER.debug("Authentication successful, response: %s", data)
            return data["data"]
    except aiohttp.ClientError as err:
        _LOGGER.error("Authentication error: %s", str(err))
        raise

async def get_accounts(session: aiohttp.ClientSession, access_token: str) -> List[Dict]:
    """get a list of communal accounts.

    Args:
        session (aiohttp.ClientSession): The HTTP session to use for the request.
        access_token (str): The access token for authentication.

    Returns:
        List[Dict]: List of account data.

    Raises:
        aiohttp.ClientError: If the API request fails.
    """
    headers = {
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36",
        "Content-Type": "application/json",
    }
    payload = {
        "data": {
            "type": "CommunalAccount",
            "query": {
                "conditions": [],
                "sort": [],
                "lastEditedPropertyType": None,
            },
            "pageQuery": None,
        },
        "method": "GetObjectList",
        "namespace": NAMESPACE,
        "operation": "REQUEST",
        "parameters": {"Authorization": f"Bearer {access_token}"},
    }
    try:
        async with session.post("https://mp.lsr.ru/api/rpc", json=payload, headers=headers, timeout=30) as resp:
            if resp.status != 200:
                _LOGGER.error("Failed to get accounts: HTTP %s", resp.status)
                raise aiohttp.ClientError(f"Failed to get accounts: HTTP {resp.status}")
            data = await resp.json()
            if data.get("statusCode") != 200:
                _LOGGER.error("Failed to get accounts: Status code %s, message: %s", data.get("statusCode"), data.get("message", "Unknown error"))
                raise aiohttp.ClientError(f"Failed to get accounts: Status code {data.get('statusCode')}")
            return data["data"]["items"]
    except aiohttp.ClientError as err:
        _LOGGER.error("Error fetching accounts: %s", err)
        raise

async def get_account_data(session: aiohttp.ClientSession, access_token: str, account_id: str) -> Dict:
    """get detailed data for a specific account.

    Args:
        session (aiohttp.ClientSession): The HTTP session to use for the request.
        access_token (str): The access token for authentication.
        account_id (str): The ID of the account to retrieve data for.

    Returns:
        Dict: Account data.

    Raises:
        aiohttp.ClientError: If the API request fails.
    """
    headers = {
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36",
        "Content-Type": "application/json",
    }
    payload = {
        "data": {"communalAccountId": account_id},
        "method": "GetCommunalAccountData",
        "namespace": NAMESPACE,
        "operation": "REQUEST",
        "parameters": {"Authorization": f"Bearer {access_token}"},
    }
    try:
        async with session.post("https://mp.lsr.ru/api/rpc", json=payload, headers=headers, timeout=30) as resp:
            if resp.status != 200:
                _LOGGER.error("Failed to get account data for %s: HTTP %s", account_id, resp.status)
                raise aiohttp.ClientError(f"Failed to get account data: HTTP {resp.status}")
            data = await resp.json()
            if data.get("statusCode") != 200:
                _LOGGER.error("Failed to get account data for %s: Status code %s, message: %s", account_id, data.get("statusCode"), data.get("message", "Unknown error"))
                raise aiohttp.ClientError(f"Failed to get account data: Status code {data.get('statusCode')}")
            return data["data"]
    except aiohttp.ClientError as err:
        _LOGGER.error("Error fetching account data for %s: %s", account_id, err)
        raise

async def get_cameras(session: aiohttp.ClientSession, access_token: str, account_id: str) -> List[Dict]:
    """get a list of cameras for a specific account.

    Args:
        session (aiohttp.ClientSession): The HTTP session to use for the request.
        access_token (str): The access token for authentication.
        account_id (str): The ID of the account to retrieve cameras for.

    Returns:
        List[Dict]: List of camera data.

    Raises:
        aiohttp.ClientError: If the API request fails.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36",
        "Authorization": f"Bearer {access_token}",
    }
    # noinspection HttpUrlsUsage
    payload = {
        "data": {"communalAccountId": account_id},
        "method": "StreamCameraList",
        "namespace": "http://www.lsr.ru/estate/headlessCMS",
        "operation": "REQUEST",
        "parameters": {"Authorization": f"Bearer {access_token}"},
    }
    try:
        async with session.post("https://mp.lsr.ru/api/rpc", json=payload, headers=headers, timeout=30) as resp:
            if resp.status != 200:
                _LOGGER.error("Failed to get camera list for %s: HTTP %s", account_id, resp.status)
                raise aiohttp.ClientError(f"Failed to get camera list: HTTP {resp.status}")
            data = await resp.json()
            if data.get("statusCode") != 200:
                _LOGGER.error("Failed to get camera list for %s: Status code %s, message: %s", account_id, data.get("statusCode"), data.get("message", "Unknown error"))
                raise aiohttp.ClientError(f"Failed to get camera list: Status code {data.get('statusCode')}")
            cameras = data["data"].get("cameras", [])
            for camera in cameras:
                camera["preview"] = camera.get("preview", "").split("?")[0]
            return cameras
    except aiohttp.ClientError as err:
        _LOGGER.error("Error fetching camera list for %s: %s", account_id, err)
        raise

async def get_camera_stream_url(session: aiohttp.ClientSession, camera: Dict, headers: Dict) -> None:
    """getch the stream URL for a specific camera.

    Args:
        session (aiohttp.ClientSession): The HTTP session to use for the request.
        camera (Dict): The camera data dictionary to update with the stream URL.
        headers (Dict): The HTTP headers to use for the request.

    Raises:
        aiohttp.ClientError: If the API request fails.
    """
    video_url = camera.get("videoUrl", "")
    if not video_url:
        camera["stream_url"] = ""
        return

    curl_command = f"curl -v '{video_url}'"
    for header, value in headers.items():
        curl_command += f" -H \"{header}: {value}\""
    _LOGGER.debug("cURL command for camera %s: %s", camera["id"], curl_command)

    try:
        async with session.get(video_url, headers=headers, timeout=10) as video_resp:
            if video_resp.status == 200:
                try:
                    video_data = await video_resp.json()
                    camera["stream_url"] = video_data.get("url", "")
                except ValueError:
                    _LOGGER.error("Failed to parse JSON response for camera %s: Response: %s", camera["id"], await video_resp.text())
                    camera["stream_url"] = ""
            else:
                _LOGGER.error("Failed to get stream URL for camera %s: HTTP %s, Response: %s", camera["id"], video_resp.status, await video_resp.text())
                camera["stream_url"] = ""
    except (aiohttp.ClientError, asyncio.TimeoutError) as err:
        error_details = f"{str(err)} ({type(err).__name__})"
        try:
            response_text = await video_resp.text() if 'video_resp' in locals() else "No response received"
            _LOGGER.error("Failed to get stream URL for camera %s: %s, Response: %s, URL: %s", camera["id"], error_details, response_text, video_url)
        except Exception as text_err:
            _LOGGER.error("Failed to get stream URL for camera %s: %s, Response: unavailable (%s), URL: %s", camera["id"], error_details, str(text_err), video_url)
        camera["stream_url"] = ""

async def get_meters(session: aiohttp.ClientSession, access_token: str, account_id: str) -> List[Dict]:
    """get a list of meters for a specific account.

    Args:
        session (aiohttp.ClientSession): The HTTP session to use for the request.
        access_token (str): The access token for authentication.
        account_id (str): The ID of the account to retrieve meters for.

    Returns:
        List[Dict]: List of meter data.

    Raises:
        aiohttp.ClientError: If the API request fails.
    """
    headers = {
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36",
        "Content-Type": "application/json",
    }
    payload = {
        "data": {
            "type": "Meter",
            "query": {
                "conditions": [
                    {
                        "property": "communalAccountId",
                        "value": [account_id],
                        "comparisonOperator": "="
                    }
                ],
                "sort": [],
                "lastEditedPropertyType": None,
            },
            "pageQuery": None,
        },
        "method": "GetObjectList",
        "namespace": NAMESPACE,
        "operation": "REQUEST",
        "parameters": {"Authorization": f"Bearer {access_token}"},
    }
    try:
        async with session.post("https://mp.lsr.ru/api/rpc", json=payload, headers=headers, timeout=30) as resp:
            if resp.status != 200:
                _LOGGER.error("Failed to get meters for %s: HTTP %s", account_id, resp.status)
                raise aiohttp.ClientError(f"Failed to get meters: HTTP {resp.status}")
            data = await resp.json()
            if data.get("statusCode") != 200:
                _LOGGER.error("Failed to get meters for %s: Status code %s, message: %s", account_id, data.get("statusCode"), data.get("message", "Unknown error"))
                raise aiohttp.ClientError(f"Failed to get meters: Status code {data.get('statusCode')}")
            return data["data"]["items"]
    except aiohttp.ClientError as err:
        _LOGGER.error("Error fetching meters for %s: %s", account_id, err)
        raise

async def get_meter_history(session: aiohttp.ClientSession, access_token: str, meter_id: str) -> List[Dict]:
    """get history of readings for a specific meter.

    Args:
        session (aiohttp.ClientSession): The HTTP session to use for the request.
        access_token (str): The access token for authentication.
        meter_id (str): The ID of the meter to retrieve history for.

    Returns:
        List[Dict]: List of meter reading history data.

    Raises:
        aiohttp.ClientError: If the API request fails.
    """
    headers = {
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36",
        "Content-Type": "application/json",
    }
    payload = {
        "data": {
            "type": "MeterValue",
            "query": {
                "conditions": [
                    {
                        "property": "meterId",
                        "value": [meter_id],
                        "comparisonOperator": "="
                    }
                ],
                "sort": [],
                "lastEditedPropertyType": None,
            },
            "pageQuery": None,
        },
        "method": "GetObjectList",
        "namespace": NAMESPACE,
        "operation": "REQUEST",
        "parameters": {"Authorization": f"Bearer {access_token}"},
    }
    try:
        async with session.post("https://mp.lsr.ru/api/rpc", json=payload, headers=headers, timeout=30) as resp:
            if resp.status != 200:
                _LOGGER.error("Failed to get meter history for %s: HTTP %s", meter_id, resp.status)
                raise aiohttp.ClientError(f"Failed to get meter history: HTTP {resp.status}")
            data = await resp.json()
            if data.get("statusCode") != 200:
                _LOGGER.error("Failed to get meter history for %s: Status code %s, message: %s", meter_id, data.get("statusCode"), data.get("message", "Unknown error"))
                raise aiohttp.ClientError(f"Failed to get meter history: Status code {data.get('statusCode')}")
            return data["data"]["items"]
    except aiohttp.ClientError as err:
        _LOGGER.error("Error fetching meter history for %s: %s", meter_id, err)
        raise