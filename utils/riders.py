import logging
from io import BytesIO

import PyPDF2
import re
import regex

from utils.http_client import download_first_available_pdf

logger = logging.getLogger(__name__)

def _pattern_for_year(year):
    """
    Restituisce la regex compilata adatta a parsare l'entry list per un dato anno:
    il formato del PDF MotoGP è cambiato più volte nel tempo, quindi servono pattern diversi.

    :param year: Anno della stagione.
    :return: Pattern compilato (re o regex) con i gruppi (numero, costruttore, ..., nazionalità[, team]).
    """
    if year < 2008:
        return re.compile(r'^(\d+)\s+([A-Z0-9]+)\s+(.+)\s+([A-Za-z]*[A-Z][A-Za-z]*)\s+([A-Z][a-z]+)\s+([A-Z]{3})\b')
    if year <= 2010:
        return re.compile(r'^(\d+)\s+([A-Z0-9]+)\s+(.+?)\s+([A-Z]{2,}(?:\s+[A-Z]{2,})*)\s+([A-Z][A-Za-z]*(?:\s+[A-Za-z]+)*)\s+([A-Z]{3})\b')
    if year <= 2012:
        return re.compile(r'^(\d+)\s+([A-Z0-9]+)\s+(.+)\s+([A-Za-z]*[A-Z][A-Za-z]*)\s+([A-Z][a-z]+)\s+([A-Z]{3})\b')
    if year == 2013:
        return re.compile(r'^(\d+)\s+([A-Z0-9-]+(?:\s+[A-Z0-9-]+)*)\s+(.+?)\s+([A-Z]{2,}(?:\s+[A-Z]{2,})*)\s+([A-Z][A-Za-z]*(?:\s+[A-Za-z]+)*)\s+([A-Z]{3})\b')
    if year <= 2015:
        return regex.compile(
            r'^(\d+)\s+'                                                # numero pilota
            r'([A-Za-z0-9&]+)\s+'                                       # costruttore
            r'(.+?(?:\s+(?:VDS|ECSTAR|IODA|PRAMAC|ASPAR|GRESINI))?)\s+'  # team
            r'(\p{Lu}{2,}(?:\s+\p{Lu}{2,})?)\s+'                        # cognome (Unicode maiuscole)
            r'(\p{Lu}\p{Ll}+(?:\s+\p{Lu}\p{Ll}+)*)\s+'                  # nome (Unicode maiuscole+minuscole)
            r'([A-Z]{3})(?=\s|$)'                                       # nazionalità
        )
    if year <= 2019:
        return regex.compile(
            r'^(\d+)\s+'                                                                              # numero pilota
            r'([A-Z0-9&]+)\s+'                                                                        # costruttore
            r'(.+?(?:\s+(?:VDS|ECSTAR|IODA|PRAMAC|ASPAR|GRESINI|OCTO|CASTROL|IDEMITSU|HRC|SRT))?)\s+'  # team
            r'(\p{Lu}{2,}(?:\s+\p{Lu}{2,})?)\s+'                                                       # cognome
            r'(\p{Lu}\p{Ll}+(?:\s+\p{Lu}\p{Ll}+)*)\s+'                                                 # nome
            r'\([A-Za-zÀ-ÿ]{3}\)\s+'                                                                   # nickname tra parentesi (3 lettere)
            r'([A-Z]{3})'                                                                              # nazionalità
        )
    return regex.compile(
        r'^(\d+)\s+'                                # numero pilota
        r'([A-Z0-9&]+)\s+'                          # costruttore
        r'(\p{Lu}{2,}(?:\s+\p{Lu}{2,})?)\s+'        # cognome
        r'(\p{Lu}\p{Ll}+(?:\s+\p{Lu}\p{Ll}+)*)\s+'  # nome
        r'\([A-Za-zÀ-ÿ]+\)\s+'                      # nickname
        r'([A-Z]{3})\s+'                            # nazionalità
        r'(.+)$'                                    # team
    )

def get_riders_info(year, gp_name, category):
    """
    Scarica l'entry list (entry.pdf) di un GP/anno/categoria e ne estrae i piloti iscritti.

    :param year: Anno della stagione.
    :param gp_name: Nome del Gran Prix.
    :param category: Categoria (es. "MotoGP").
    :return: Lista di [numero, costruttore, team, cognome, nome, nazionalità] per ogni pilota,
             oppure [] se l'entry list non è scaricabile.
    """
    base_url = "https://resources.motogp.com/files/results"
    pattern = _pattern_for_year(year)

    urls = [
        f"{base_url}/{year}/{gp_name}/{category}/entry.pdf",
        f"{base_url}/{year}/{category}/{gp_name}/entry.pdf",
        f"{base_url}/{year}/{gp_name}/{category}/Entry.pdf",
        f"{base_url}/{year}/{category}/{gp_name}/Entry.pdf",
    ]

    pdf_data = download_first_available_pdf(urls)
    if pdf_data is None:
        return []

    text = PyPDF2.PdfReader(pdf_data).pages[0].extract_text()

    all_riders = []
    for line in text.split('\n'):
        rider = pattern.match(line)
        if not rider:
            continue

        if year <= 2019:
            number, constructor, team, surname, name, nationality = rider.groups()
        else:
            number, constructor, surname, name, nationality, team = rider.groups()
            team = regex.sub(r'^\s*[*r]*\s*R\(\d+\)\s*', '', team)
            team = regex.sub(r'^\s*[*r]+\s*', '', team)
            team = team.strip()

        team = team.replace('* ', '').replace('W     ', '')
        all_riders.append([number, constructor, team, surname, name.replace(' ', ''), nationality])

    return all_riders