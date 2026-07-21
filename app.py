"""
Main Flask application for MotoGP Stats.

Handles routing, coordinates data fetching from external APIs,
serves frontend templates, and acts as an internal proxy to
manage caching and prevent CORS issues.
"""

import functools
import logging
import requests

from flask import Flask, jsonify, render_template, request
from werkzeug.exceptions import HTTPException

from exceptions import (
    DataNotFoundError,
    InvalidParameterError,
    MotoGPStatsError,
    UpstreamServiceError,
)

from models.data_processor import SessionAnalyzer
from config import config

logging.basicConfig(level=config.LOG_LEVEL)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# ---------------------------------------------------------------------------
# External API Configuration (Proxy)
# ---------------------------------------------------------------------------

@functools.lru_cache(maxsize=1)
def get_all_season_years() -> list:
    """
    Fetches all available seasons (years) from the MotoGP API.

    :return: A list of dictionaries, where each dictionary contains 'id' and 'year'.
    :rtype: list
    :raises UpstreamServiceError: If the external API is unreachable or returns an error.
    """
    try:
        resp = requests.get(config.API_BASE_URL + "/results/seasons", headers=config.HEADERS, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return [{"id": item['id'], "year": item['year']} for item in data]
    except Exception as e:
        logger.error("Error fetching championship years: %s", e)
        raise UpstreamServiceError("Unable to fetch seasons from external API")

@functools.lru_cache(maxsize=32)
def get_every_race_name(season_uuid: str) -> list:
    """
    Fetches all events (circuits) for a given season UUID.

    :param season_uuid: The unique identifier for the championship season.
    :type season_uuid: str
    :return: A list of tuples containing the event ID and its sponsored name.
    :rtype: list
    :raises UpstreamServiceError: If the external API is unreachable or returns an error.
    """
    try:
        resp = requests.get(config.API_BASE_URL + f"/results/events?seasonUuid={season_uuid}&isFinished=True", headers=config.HEADERS, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return [(item['id'], item['sponsored_name']) for item in data if item['test'] == False]
    except Exception as e:
        logger.error("Error fetching circuits for season %s: %s", season_uuid, e)
        raise UpstreamServiceError("Unable to fetch circuits")

@functools.lru_cache(maxsize=64)
def get_categoryId_by_eventId(event_id: str) -> list:
    """
    Fetches all racing categories (MotoGP, Moto2, Moto3) for a given event ID.

    :param event_id: The unique identifier of the specific racing event.
    :type event_id: str
    :return: A list of tuples containing the category ID and its name.
    :rtype: list
    :raises UpstreamServiceError: If the external API is unreachable or returns an error.
    """
    try:
        resp = requests.get(config.API_BASE_URL + f"/results/categories?eventUuid={event_id}", headers=config.HEADERS, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return [(item['id'], item['name']) for item in data]
    except Exception as e:
        logger.error("Error fetching categories for event %s: %s", event_id, e)
        raise UpstreamServiceError(f"Unable to fetch categories for event {event_id}")

@functools.lru_cache(maxsize=128)
def get_sessions_by_eventId(event_id: str, category_id: str) -> list:
    """
    Fetches all sessions and their associated files for a specific event and category.

    :param event_id: The unique identifier of the racing event.
    :type event_id: str
    :param category_id: The unique identifier of the racing category.
    :type category_id: str
    :return: A list of tuples containing session ID, formatted session type/number, and session files.
    :rtype: list
    """
    resp = requests.get(
        config.API_BASE_URL + f"/results/sessions?eventUuid={event_id}&categoryUuid={category_id}"
    ).json()
    return [
        (
            resp[i]["id"],   # Session UUID — used for classification fallback
            f"{resp[i]['type']}{resp[i]['number'] if resp[i]['number'] is not None else ''}",
            resp[i]["session_files"],
        )
        for i in range(len(resp))
    ]

# ---------------------------------------------------------------------------
# Centralized Error Handlers
# ---------------------------------------------------------------------------

@app.errorhandler(InvalidParameterError)
def handle_invalid_parameter(error: InvalidParameterError):
    """
    Handles HTTP 400 errors for invalid client inputs.

    :param error: The exception instance raised.
    :type error: InvalidParameterError
    :return: A JSON response containing the error message and a 400 status code.
    :rtype: tuple
    """
    return jsonify({"error": str(error)}), 400

@app.errorhandler(DataNotFoundError)
def handle_data_not_found(error: DataNotFoundError):
    """
    Handles HTTP 404 errors for missing data.

    :param error: The exception instance raised.
    :type error: DataNotFoundError
    :return: A JSON response containing the error message and a 404 status code.
    :rtype: tuple
    """
    return jsonify({"error": str(error)}), 404

@app.errorhandler(UpstreamServiceError)
def handle_upstream_error(error: UpstreamServiceError):
    """
    Handles HTTP 502 errors when external MotoGP APIs fail.

    :param error: The exception instance raised.
    :type error: UpstreamServiceError
    :return: A JSON response containing a generic error message and a 502 status code.
    :rtype: tuple
    """
    logger.error("Upstream error: %s", error)
    return jsonify({"error": "MotoGP service temporarily unavailable"}), 502

@app.errorhandler(MotoGPStatsError)
def handle_generic_app_error(error: MotoGPStatsError):
    """
    Fallback handler for any unmapped custom MotoGPStatsError.

    :param error: The exception instance raised.
    :type error: MotoGPStatsError
    :return: A JSON response containing the error message and a 400 status code.
    :rtype: tuple
    """
    logger.warning("Unmapped application error: %s", error)
    return jsonify({"error": str(error)}), 400

@app.errorhandler(Exception)
def handle_unexpected_error(error: Exception):
    """
    Global catch-all for unexpected server errors (HTTP 500).

    :param error: The generic exception instance raised.
    :type error: Exception
    :return: A JSON response containing a generic error message and a 500 status code.
    :rtype: tuple
    """
    if isinstance(error, HTTPException):
        return error
    logger.exception("Unhandled error")
    return jsonify({"error": "Internal server error"}), 500

# ---------------------------------------------------------------------------
# Internal APIs for the Frontend (Proxy)
# ---------------------------------------------------------------------------

@app.route('/api/seasons')
def api_seasons():
    """
    API endpoint to retrieve all available seasons.

    :return: JSON list of seasons.
    :rtype: flask.Response
    """
    years = get_all_season_years()
    return jsonify(years)

@app.route('/api/tracks/<season_uuid>')
def api_tracks(season_uuid: str):
    """
    API endpoint to retrieve all tracks for a specific season.

    :param season_uuid: The UUID of the chosen season.
    :type season_uuid: str
    :return: JSON list of tracks or an error message.
    :rtype: tuple or flask.Response
    """
    try:
        tracks_data = get_every_race_name(season_uuid)
        tracks = [{"id": t[0], "name": t[1]} for t in tracks_data]
        return jsonify(tracks)
    except Exception as e:
        logger.error("Error fetching tracks: %s", e)
        return jsonify({"error": "Error fetching tracks"}), 502

@app.route('/api/categories/<event_id>')
def api_categories(event_id: str):
    """
    API endpoint to retrieve all categories for a specific event.

    :param event_id: The UUID of the chosen event.
    :type event_id: str
    :return: JSON list of categories.
    :rtype: flask.Response
    """
    categories_data = get_categoryId_by_eventId(event_id)
    categories = [{"id": cat[0], "name": cat[1]} for cat in categories_data]
    return jsonify(categories)

@app.route('/api/sessions/<event_id>/<category_id>')
def api_sessions(event_id: str, category_id: str):
    """
    API endpoint to retrieve all sessions and their relevant files.

    :param event_id: The UUID of the chosen event.
    :type event_id: str
    :param category_id: The UUID of the chosen category.
    :type category_id: str
    :return: JSON list of formatted sessions containing sorted PDF files.
    :rtype: flask.Response
    :raises UpstreamServiceError: If the external API request fails.
    """
    try:
        raw_sessions = get_sessions_by_eventId(event_id, category_id)
    except requests.exceptions.RequestException as exc:
        raise UpstreamServiceError(f"Error fetching sessions: {exc}") from exc

    sessions = []
    for session_id, session_type, session_files in raw_sessions:
        files = []
        for file_key, file_data in session_files.items():
            url = file_data.get("url", "")
            if not url:
                continue
            display_name = url.rsplit("/", 1)[-1].replace(".pdf", "").replace(".PDF", "").replace("_", " ")
            files.append({
                "name": display_name,
                "url": url,
                "order": file_data.get("menu_position", 99),
            })

        files.sort(key=lambda f: f["order"])
        if files:
            sessions.append({"id": session_id, "type": session_type, "files": files})

    return jsonify(sessions)

# ---------------------------------------------------------------------------
# Web Routes
# ---------------------------------------------------------------------------

@app.route('/')
def home():
    """
    Renders the main application homepage.

    :return: The rendered HTML string for the homepage.
    :rtype: str
    """
    return render_template('home.html')

@app.route('/results', methods=['POST'])
def result():
    """
    Processes form submission to analyze the requested session.

    Validates user input, instantiates the SessionAnalyzer, processes
    the data, and returns the result page.

    :return: The rendered HTML string displaying the analysis results.
    :rtype: str
    :raises InvalidParameterError: If required form fields are missing or invalid.
    """
    pdf_url          = request.form.get('pdfUrl',      '').strip()
    event_id         = request.form.get('granPrix',    '').strip()
    category_id      = request.form.get('category',    '').strip()
    session_type_form = request.form.get('sessionType', '').strip()
    session_id       = request.form.get('sessionId',   '').strip()

    if not pdf_url:
        raise InvalidParameterError("The 'pdfUrl' parameter is required")
    if not pdf_url.startswith("https://resources.motogp.com/"):
        raise InvalidParameterError("Invalid PDF URL")
    if not event_id or not category_id:
        raise InvalidParameterError("The 'granPrix' and 'category' parameters are required")

    analyzer = SessionAnalyzer(
        pdf_url=pdf_url,
        event_id=event_id,
        category_id=category_id,
        session_type=session_type_form,
        session_id=session_id,
    )

    analysis_result = analyzer.process_data()

    return render_template('result.html', result=analysis_result)

if __name__ == '__main__':
    app.run()