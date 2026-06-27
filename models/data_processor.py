import re
from io import BytesIO

import logger
import requests
from pypdf import PdfReader
import logging
import pycountry

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
        Pulisce i piè di pagina per evitare conflitti con la ricerca dei piloti.
        """
        pdf_data = Analyzer.get_pdf_data(year, granprix)
        if not pdf_data:
            return ""

        reader = PdfReader(pdf_data)
        text = "\n".join(page.extract_text() for page in reader.pages)

        # FIX: Rimuove la riga del giro veloce a fondo pagina (che contiene nomi di piloti!)
        text = re.sub(r"^.*Fastest Lap:.*$\n?", "", text, flags=re.MULTILINE)

        # FIX (Opzionale ma consigliato): Rimuove il lunghissimo blocco di copyright
        # che si interpone tra i giri durante i cambi di pagina
        text = re.sub(r"These data/results cannot be reproduced.*?TISSOT\n?", "", text, flags=re.DOTALL)

        return text

    @staticmethod
    def extract_lap_times_strings(text):
        """
        Estrae i tempi giro validi dal blocco di testo di un pilota.
        Ignora i giri rientrati ai box o incompleti poiché non fanno match con i 4 settori e la velocità.
        """
        # Il pattern cerca: TempoGiro + LapNumber + Settore1 + Settore2 + Settore3 + Velocità + Settore4
        pattern = re.compile(
            r"(\d{1,2})'(\d{2}\.\d{3})\*?"  # Gruppo 1: min, Gruppo 2: sec.ms (con opzionale * di cancellazione)
            r"\s*\d+\*?"  # Numero del giro (spazio opzionale)
            rf"\s+({SECTOR_TIME})\*?"  # Settore 1
            rf"\s+({SECTOR_TIME})\*?"  # Settore 2
            rf"\s+({SECTOR_TIME})\*?"  # Settore 3
            r"\s+\d+\.\d"  # Velocità max (FISSATA A 1 DECIMALE per evitare sovrapposizioni)
            rf"\s*({SECTOR_TIME})\*?",  # Settore 4 (SPAZIO OPZIONALE tra velocità e settore 4)
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
        come delimitatori, ed estrae i relativi tempi sul giro tramite Regex tolleranti.
        """
        text = Analyzer.extract_all_text(year, granprix)
        #print(text)
        if not text:
            return []

        # Otteniamo i piloti iscritti per quell'evento
        riders = get_riders_info(year, granprix, "MotoGP")
        #print(riders)
        pilot_positions = []
        for rider in riders:
            # riders: [numero, costruttore, team, cognome, nome, nazionalità]
            name = rider[4]
            surname = rider[3]
            full_name_display = f"{name} {surname}"

            # Prendiamo solo i primi 8 caratteri del cognome per evitare problemi
            # di troncamento a fine riga da parte del PDF (es. DI GIANNANTONI7th)
            short_surname = surname[:8]

            # Rendiamo sicuri i nomi per la regex (evita errori con gli apostrofi)
            # e permettiamo spazi opzionali nel cognome (es. "DI GIANN" -> "DI\s*GIANN")
            safe_name = re.escape(name)
            safe_surname = re.escape(short_surname).replace(r"\ ", r"\s*")

            # Pattern: cerca il nome seguito da almeno uno spazio e dai primi caratteri del cognome
            pattern = re.compile(rf"{safe_name}\s+{safe_surname}", re.IGNORECASE)

            match = pattern.search(text)
            if match:
                # match.start() restituisce la posizione esatta in cui inizia il nome nel testo
                pilot_positions.append((match.start(), full_name_display))

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
        urls = [
            f"{BASE_URL}/{year}/SPA/MotoGP/RAC/worldstanding.pdf",
            f"{BASE_URL}/{year}/MotoGP/SPA/world%2bstanding.pdf",
        ]

        for url in urls:
            response = requests.get(url)
            if response.status_code != 200:
                logger.warning(f"Impossible to download PDF from: {url}")
                continue

            logger.info(f"PDF downloaded from: {url}")

            text = PdfReader(BytesIO(response.content)).pages[0].extract_text()

            blocks = re.findall(
                r"(?:\b[A-Z][A-Z0-9]{2}\b(?:\s+|$)){2,}",
                text
            )

        return max(blocks, key=len).split()