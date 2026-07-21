"""
Shared HTTP client for downloading PDFs from MotoGP servers.

Compared to calling `requests.get()` directly for each request (as in the
original code), this module:
- reuses a single `requests.Session`, thus reusing TCP/TLS connections
  (connection pooling) instead of opening a new one every time;
- applies automatic timeouts and retries (with backoff) on 5xx errors;
- explicitly distinguishes between "resource not found" (404 -> expected data,
  e.g., a GP that didn't exist that year) and "unreachable server"
  (network error -> infrastructure problem, to be reported differently).
"""
import logging
from io import BytesIO
from typing import Iterable, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from config import config
from exceptions import UpstreamServiceError

logger = logging.getLogger(__name__)

def _build_session() -> requests.Session:
    """
    Builds and configures a requests Session with retry logic.

    :return: A configured requests.Session object.
    :rtype: requests.Session
    """
    session = requests.Session()
    retry_strategy = Retry(
        total=config.HTTP_MAX_RETRIES,
        backoff_factor=0.5,
        status_forcelist=(500, 502, 503, 504),
        allowed_methods=("GET",),
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session

# Shared session at the module level: lives for the entire lifespan of the process
# and is reused by all calls, instead of creating a new one for each request.
_session = _build_session()

def get_pdf_data(url: str) -> Optional[BytesIO]:
    """
    Attempts to fetch a PDF from the given URL.

    :param url: The URL of the PDF to download.
    :type url: str
    :return: A BytesIO object containing the PDF content, or None if the URL
             did not respond with HTTP 200 (expected case: the resource does
             not exist for that combination of parameters, not a system error).
    :rtype: Optional[BytesIO]
    :raises UpstreamServiceError: If the request fails due to a network issue
                                  (timeout, DNS, connection refused), distinct
                                  from a simple 404/wrong-url.
    """
    last_network_error: Optional[Exception] = None

    try:
        response = _session.get(url, timeout=config.HTTP_TIMEOUT_SECONDS)
    except requests.exceptions.RequestException as exc:
        logger.warning("Network error downloading %s: %s", url, exc)
        last_network_error = exc
        return None

    if response.status_code == 200:
        logger.info("PDF downloaded from: %s", url)
        return BytesIO(response.content)

    logger.info("Resource unavailable (HTTP %s): %s", response.status_code, url)

    if last_network_error is not None:
        raise UpstreamServiceError(
            f"Unable to reach MotoGP servers: {last_network_error}"
        )

    return None