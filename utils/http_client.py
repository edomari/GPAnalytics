import logging
from io import BytesIO

import requests

logger = logging.getLogger(__name__)


def download_first_available_pdf(urls):
    """
    Prova in ordine una lista di URL candidati e restituisce il contenuto del primo
    che risponde con HTTP 200. Centralizza la logica di download/log che prima era
    duplicata in più punti (data_reader.get_pdf_data, riders.get_riders_info, ecc).

    :param urls: Iterabile di URL da provare in ordine.
    :return: BytesIO con il contenuto del PDF, oppure None se nessun URL ha funzionato.
    """
    for url in urls:
        response = requests.get(url)
        if response.status_code == 200:
            logger.info(f"PDF downloaded from: {url}")
            return BytesIO(response.content)
        logger.warning(f"Impossible to download PDF from: {url}")
    return None