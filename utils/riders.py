"""
Extraction of the entry list (registered riders) via the MotoGP API (PulseLive).
"""
import functools
import logging
import requests
from dataclasses import dataclass
from typing import List
from config import config

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Rider:
    """
    Represents a rider entered in an event.
    """
    id: str
    number: str
    constructor: str
    team: str
    surname: str
    name: str
    nationality: str

    @property
    def full_name(self) -> str:
        """
        Gets the rider's full name.

        :return: The combined name and surname, stripped of extra spaces.
        :rtype: str
        """
        return f"{self.name} {self.surname}".strip()


def get_riders_info(event_id: str, category_id: str, session_id: str = "", year: int = 0) -> List[Rider]:
    """
    Retrieves the entry list for a specific event and category.

    Strategy:
    1. Tries the v2/entries endpoint (complete entry data).
    2. If no riders are found, falls back to the v1 classification endpoint
       (available for older sessions or when entries are not populated).

    :param event_id: The UUID of the event.
    :type event_id: str
    :param category_id: The UUID of the category.
    :type category_id: str
    :param session_id: The UUID of the session (required for fallback).
    :type session_id: str
    :param year: The season year (required for fallback).
    :type year: int
    :return: A list of Rider objects, or an empty list if both endpoints fail.
    :rtype: list
    """
    riders = _get_riders_from_entries(event_id, category_id)
    if riders:
        return riders

    logger.info(
        "Empty entries for event %s — trying classification fallback (session %s)",
        event_id, session_id,
    )
    return _get_riders_from_classification(session_id, year)


def _get_riders_from_entries(event_id: str, category_id: str) -> List[Rider]:
    """
    Attempts to fetch riders from the v2/entries endpoint.

    :param event_id: The UUID of the event.
    :type event_id: str
    :param category_id: The UUID of the category.
    :type category_id: str
    :return: A list of Rider objects found (empty list if the request fails).
    :rtype: list
    """
    url = f"{config.API_ENTRIES_URL}?categoryId={category_id}&eventId={event_id}"
    try:
        resp = requests.get(url, headers=config.HEADERS, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        logger.error("Error fetching v2 entry list: %s", e)
        return []

    riders: List[Rider] = []
    for entry in data.get("entry", []):
        rider_data = entry.get("rider", {})
        full_name = rider_data.get("full_name", "").strip()
        if not full_name:
            continue

        name_parts = full_name.split(" ", 1)
        name = name_parts[0]
        surname = name_parts[1] if len(name_parts) > 1 else ""

        riders.append(Rider(
            id=entry.get("rider", {}).get("riders_id", ""),
            number=str(entry.get("number", rider_data.get("number", ""))),
            constructor=entry.get("constructor", {}).get("name", ""),
            team=entry.get("team_name", ""),
            surname=surname,
            name=name,
            nationality=rider_data.get("country", {}).get("iso", ""),
        ))
    return riders


def _get_riders_from_classification(session_id: str, year: int) -> List[Rider]:
    """
    Fallback method: extracts rider names from the v1 classification endpoint.

    :param session_id: The UUID of the session.
    :type session_id: str
    :param year: The season year.
    :type year: int
    :return: A list of Rider objects extracted from the classification (empty list if it fails).
    :rtype: list
    """
    if not session_id:
        logger.warning("Missing session_id: unable to use classification fallback")
        return []

    url = (
        f"{config.API_BASE_URL}/results/session/{session_id}"
        f"/classification"
    )
    try:
        resp = requests.get(url, headers=config.HEADERS, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        logger.info("Found url: %s", url)
    except Exception as e:
        logger.error("Error in classification fallback (session %s): %s", session_id, e)
        return []

    riders: List[Rider] = []
    for entry in data.get("classification", []):
        rider_data = entry.get("rider", {})
        full_name = rider_data.get("full_name", "").strip()
        if not full_name:
            continue

        name_parts = full_name.split(" ", 1)
        name = name_parts[0]
        surname = name_parts[1] if len(name_parts) > 1 else ""

        riders.append(Rider(
            id=entry.get("rider", {}).get("riders_id", ""),
            number=str(rider_data.get("number") or ""),
            constructor=entry.get("constructor", {}).get("name", ""),
            team=(entry.get("team") or {}).get("name", ""),
            surname=surname,
            name=name,
            nationality=rider_data.get("country", {}).get("iso", ""),
        ))
    return riders


@functools.lru_cache(maxsize=256)
def get_rider_visuals(rider_uuid: str, year: int) -> dict:
    """
    Retrieves visual and team information for a specific rider and year.

    Fetches the rider's career profile and attempts to extract photos,
    team colors, and background images, prioritizing the specified year
    and falling back to other years if necessary.

    :param rider_uuid: The UUID of the rider.
    :type rider_uuid: str
    :param year: The target season year.
    :type year: int
    :return: A dictionary containing 'photo', 'team_color', 'team_text_color', 'team_bg', and 'team_name'.
    :rtype: dict
    """
    if not rider_uuid:
        return {}

    url = f"{config.API_BASE_URL}/riders/{rider_uuid}"
    try:
        resp = requests.get(url, headers=config.HEADERS, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        logger.warning("Unable to fetch visuals for rider %s: %s", rider_uuid, exc)
        return {}

    career = data.get("career", [])
    if not career:
        return {}

    career_sorted = sorted(career, key=lambda x: x.get("season", 0), reverse=True)
    target_entry = next((c for c in career if c.get("season") == year), None)

    # Helper function including 'portrait' logic
    def get_photo_path():
        # 1. First try the portrait field in the target year (specific to your request)
        if target_entry:
            val = (target_entry.get("pictures") or {}).get("portrait")
            if val: return val

            # 2. Then try the profile.main field in the target year
            val = (target_entry.get("pictures") or {}).get("profile", {}).get("main")
            if val: return val

        # 3. Fallback: search across the entire career
        for entry in career_sorted:
            pics = entry.get("pictures") or {}
            # Prioritize the portrait even in the fallback
            val = pics.get("portrait") or pics.get("profile", {}).get("main")
            if val: return val
        return ""

    def get_field(path_keys, default=""):
        if target_entry:
            val = target_entry
            for key in path_keys:
                val = (val or {}).get(key)
            if val: return val

        for entry in career_sorted:
            val = entry
            for key in path_keys:
                val = (val or {}).get(key)
            if val: return val
        return default

    return {
        "photo": get_photo_path(),  # Uses the custom logic that prefers the portrait
        "team_color": get_field(["team", "color"]),
        "team_text_color": get_field(["team", "text_color"]),
        "team_bg": get_field(["team", "background_picture"]),
        "team_name": get_field(["team", "name"]),
    }