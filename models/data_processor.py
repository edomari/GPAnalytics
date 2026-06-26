import re
from io import BytesIO

import logger
import requests
from pypdf import PdfReader
import logging

from utils.http_client import download_first_available_pdf
from utils.riders import get_riders_info

# Frammento regex per riconoscere un tempo giro (es. 1'34.186) o un tempo parziale
LAP_TIME = r"\d{1,2}'\d{2}\.\d{3}"
SECTOR_TIME = rf"(?:{LAP_TIME}|\d+\.\d{{3}})"
BASE_URL = "https://resources.motogp.com/files/results"

logger = logging.getLogger(__name__)

class Analyzer:
    @staticmethod
    def get_pdf_data(year, gp_name):
        """
        Scarica il PDF di analisi della gara in formato BytesIO.
        """
        urls = [
            f"{BASE_URL}/{year}/{gp_name}/MotoGP/RAC/Analysis.pdf",
            f"{BASE_URL}/{year}/MotoGP/{gp_name}/RAC/analysis.pdf",
        ]
        return download_first_available_pdf(urls)

    @staticmethod
    def extract_all_text(year, granprix):
        """
        Estrae tutto il testo grezzo dal PDF unendo tutte le pagine senza filtri.
        Grazie a pypdf, il testo è già sufficientemente pulito.
        """
        pdf_data = Analyzer.get_pdf_data(year, granprix)
        if not pdf_data:
            return ""

        reader = PdfReader(pdf_data)
        return "\n".join(page.extract_text() for page in reader.pages)

    @staticmethod
    def extract_lap_times_strings(text):
        """
        Estrae i tempi giro validi dal blocco di testo di un pilota.
        Ignora i giri rientrati ai box o incompleti poiché non fanno match con i 4 settori e la velocità.
        """
        # Il pattern cerca: TempoGiro + LapNumber + Settore1 + Settore2 + Settore3 + Velocità + Settore4
        pattern = re.compile(
            r"(\d{1,2})'(\d{2}\.\d{3})\*?"  # Gruppo 1: min, Gruppo 2: sec.ms (con opzionale * di cancellazione)
            r"\s+\d+\*?"  # Numero del giro
            rf"\s+({SECTOR_TIME})\*?"  # Settore 1
            rf"\s+({SECTOR_TIME})\*?"  # Settore 2
            rf"\s+({SECTOR_TIME})\*?"  # Settore 3
            r"\s+\d+\.\d{1,3}"  # Velocità max
            rf"\s+({SECTOR_TIME})\*?",  # Settore 4
            re.MULTILINE
        )

        lap_times = []
        for match in pattern.finditer(text):
            try:
                # Creiamo direttamente la stringa formattata: "1:32.456"
                lap_time_str = f"{match.group(1)}:{match.group(2)}"
                lap_times.append(lap_time_str)
            except IndexError as e:
                print(f"Errore processamento dati: {e}")
                continue
        return lap_times

    @staticmethod
    def process_pilots_data(year, granprix):
        """
        Trova i blocchi di testo per ogni pilota usando i nomi estratti dall'entry list
        come delimitatori, ed estrae i relativi tempi sul giro.
        """
        text = Analyzer.extract_all_text(year, granprix)
        if not text:
            return []

        # Otteniamo i piloti iscritti per quell'evento
        riders = get_riders_info(year, granprix, "MotoGP")

        # Formattiamo i nomi nel modo in cui compaiono nel PDF di pypdf (es. "Alex MARQUEZ")
        # riders: [numero, costruttore, team, cognome, nome, nazionalità]
        pilots_names = [f"{rider[4]} {rider[3]}" for rider in riders]

        # Cerchiamo l'indice (la posizione) di inizio di ogni pilota nel testo unico
        pilot_positions = []
        for name in pilots_names:
            idx = text.find(name)
            if idx != -1:
                pilot_positions.append((idx, name))

        # Ordiniamo l'elenco in base a come appaiono nel documento
        pilot_positions.sort(key=lambda x: x[0])

        pilots_data = []

        # Usiamo le posizioni scoperte per affettare (slice) il testo
        for i, (start_idx, name) in enumerate(pilot_positions):
            # La fine del blocco è l'inizio del pilota successivo (o la fine del documento)
            end_idx = pilot_positions[i + 1][0] if i + 1 < len(pilot_positions) else len(text)
            pilot_block = text[start_idx:end_idx]

            # Estraiamo i tempi giro da questo specifico blocco
            lap_times = Analyzer.extract_lap_times_strings(pilot_block)

            # Se ci sono tempi, aggiungiamo il pilota alla lista finale
            if lap_times:
                pilots_data.append((name, lap_times))

        return pilots_data

    @staticmethod
    def get_all_tracks_per_year(year):
        url = f"{BASE_URL}/{year}/SPA/MotoGP/RAC/worldstanding.pdf"

        response = requests.get(url)
        if response.status_code != 200:
            logger.warning(f"Impossible to download PDF from: {url}")
            return []

        logger.info(f"PDF downloaded from: {url}")

        text = PdfReader(BytesIO(response.content)).pages[0].extract_text()

        blocks = re.findall(
            r"(?:\b[A-Z][A-Z0-9]{2}\b(?:\s+|$)){2,}",
            text
        )

        return max(blocks, key=len).split()