"""
Extraction and analysis of lap times from MotoGP analysis PDFs.
"""
import logging
import re
from typing import List, Tuple

from pypdf import PdfReader

from exceptions import DataNotFoundError
from utils import http_client
from utils.riders import get_riders_info, get_rider_visuals

logger = logging.getLogger(__name__)

class SessionAnalyzer:
    """
    Analyzer dedicated to a single MotoGP session.
    Maintains state (URL, ID) to avoid repeatedly passing parameters.
    """

    def __init__(self, pdf_url: str, event_id: str, category_id: str, session_type: str, session_id: str = ""):
        self.pdf_url = pdf_url
        self.event_id = event_id
        self.category_id = category_id
        self.session_type = session_type
        self.session_id = session_id

        # Immediately extract the year and GP, and save them as instance state
        self.year, self.gp_name = self._parse_url()

    def _parse_url(self) -> Tuple[int, str]:
        """
        Extracts the year and GP acronym from the PDF URL saved in self.pdf_url.

        :return: A tuple containing the year and the GP name.
        :rtype: Tuple[int, str]
        :raises DataNotFoundError: If the year or GP cannot be extracted from the URL.
        """
        parts = self.pdf_url.rstrip("/").split("/")
        try:
            idx = parts.index("results")
            year = int(parts[idx + 1])
            gp_name = parts[idx + 2]
            return year, gp_name
        except (ValueError, IndexError) as exc:
            raise DataNotFoundError(
                f"Unable to extract year/GP from URL: {self.pdf_url}"
            ) from exc

    def _extract_all_text(self) -> str:
        """
        Extracts and cleans all raw text from the PDF.

        :return: The cleaned extracted text.
        :rtype: str
        :raises DataNotFoundError: If no PDF is available at the provided URL.
        """
        pdf_data = http_client.get_pdf_data(self.pdf_url)
        if not pdf_data:
            raise DataNotFoundError(
                f"No PDF available at URL: {self.pdf_url}"
            )

        reader = PdfReader(pdf_data)
        text = "\n".join(page.extract_text() for page in reader.pages)

        # Removes rows containing 'Fastest Lap' and page indications
        text = re.sub(r"^.*Fastest Lap.*$", "", text, flags=re.MULTILINE)
        text = re.sub(r"Page \d+ of \d+.*$", "", text, flags=re.MULTILINE)

        return text

    def _extract_lap_times_strings(self, text_block: str) -> List[str]:
        """
        Extracts lap times from a rider's specific text block by processing it line by line.
        Looks only for the first occurrence of a time (e.g., 1'56.626) on each line.
        This automatically handles cases where sectors are missing or the lap number
        is concatenated to the milliseconds (e.g., 1'56.9737).

        :param text_block: The raw text block for a specific rider.
        :type text_block: str
        :return: A list of formatted lap time strings.
        :rtype: List[str]
        """
        lap_times = []
        # Pattern that searches exactly for the minute'seconds.milliseconds format
        pattern = re.compile(r"(\d{1,2})'(\d{2}\.\d{3})")

        for line in text_block.splitlines():
            # search() finds only the first occurrence in the string, ignoring everything else
            match = pattern.search(line)
            if match:
                lap_times.append(f"{match.group(1)}:{match.group(2)}")

        return lap_times

    def process_data(self) -> dict:
        """
        Main public method.
        Manages the data extraction flow and returns the results dictionary.

        :return: A dictionary containing the parsed session data and rider lap times.
        :rtype: dict
        :raises DataNotFoundError: If the entry list is unavailable for the event.
        """
        text = self._extract_all_text()
        print(text)

        riders = get_riders_info(self.event_id, self.category_id, self.session_id, self.year)
        print(riders)
        if not riders:
            raise DataNotFoundError(
                f"No entry list available for the event {self.gp_name} {self.year}"
            )

        # Map full_name → rider UUID to fetch visuals
        rider_uuid_by_name = {rider.full_name: rider.id for rider in riders}

        # 1. Find the riders' positions within the text
        pilot_positions: List[Tuple[int, str]] = []
        for rider in riders:
            first_two_name = rider.name[:2]

            surname_parts = rider.surname.split()
            surname_key = surname_parts[0] if surname_parts else rider.name

            pattern_str = rf"{re.escape(first_two_name)}.*{re.escape(surname_key)}"
            pattern = re.compile(pattern_str, re.IGNORECASE)

            match = pattern.search(text)
            if match:
                pilot_positions.append((match.start(), rider.full_name))
            else:
                logger.debug("Pattern not found for: %s...%s", first_two_name, surname_key)

        pilot_positions.sort(key=lambda item: item[0])

        # 2. Extract lap times and visuals for each rider
        pilots_data = []
        for i, (start_idx, name) in enumerate(pilot_positions):
            end_idx = (
                pilot_positions[i + 1][0]
                if i + 1 < len(pilot_positions)
                else len(text)
            )
            pilot_block = text[start_idx:end_idx]
            lap_times = self._extract_lap_times_strings(pilot_block)

            if lap_times:
                rider_uuid = rider_uuid_by_name.get(name, "")
                visuals = get_rider_visuals(rider_uuid, self.year)
                pilots_data.append({
                    "name":    name,
                    "times":   lap_times,
                    "visuals": visuals,
                })

        return {
            "year": self.year,
            "gp_name": self.gp_name,
            "session_type": self.session_type,
            "pilots": pilots_data
        }