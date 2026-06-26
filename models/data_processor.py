import re

import PyPDF2

from utils.http_client import download_first_available_pdf
from utils.riders import get_riders_info

# Frammento regex riusato per riconoscere un tempo giro nel formato x'xx.xxx (es. 1'34.186),
# centralizzato qui invece di essere ridichiarato in più pattern.
LAP_TIME = r"\d{1,2}'\d{2}\.\d{3}"
SECTOR_TIME = rf"(?:{LAP_TIME}|\d+\.\d{{3}})"

class Analyzer:
    @staticmethod
    def fix_lap_times(text):
        """
        Corrects lap times in the format x'xx.xxx or handles the 'unfinished' case.
        Separates concatenated lap times in the same line.
        :param text: Text extracted from the PDF containing lap times.
        :return: Testo con un tempo giro per riga.
        """
        # Regex per trovare i tempi dei giri (es. 1'34.1862 o 1'33.8893)
        lap_time_pattern = re.compile(rf"({LAP_TIME})(?:\s+\d+(?:\.\d{{3}}){{5}}\s+\d+\.\d{{1}}\s+\d+\.\d{{3}})")

        fixed_lines = []

        for line in text.splitlines():
            stripped_line = line.strip()
            if lap_time_pattern.search(stripped_line):
                fixed_line = lap_time_pattern.sub(lambda x: '\n' + x.group(0), stripped_line)
                fixed_lines.append(fixed_line.strip())
            else:
                fixed_lines.append(stripped_line)
        return "\n".join(line for line in "\n".join(fixed_lines).splitlines() if line.strip())

    @staticmethod
    def extract_lap_times_strings(text):
        """
        Estrae i tempi giro dal formato PDF, salvandoli direttamente come stringhe
        nel formato 'Minuti:Secondi.Millisecondi' senza convertirli in secondi totali.
        """
        pattern = re.compile(
            r"(\d{1,2})'(\d{2}\.\d{3})"  # Gruppo 1: minuti, Gruppo 2: secondi.millisecondi
            r"\s+\d+"  # Posizione
            rf"\s+({SECTOR_TIME})"  # Settore 1
            rf"\s+({SECTOR_TIME})"  # Settore 2
            rf"\s+({SECTOR_TIME})"  # Settore 3
            r"\s+\d+\.\d{1,3}"  # Velocità max
            rf"\s+({SECTOR_TIME})",  # Settore 4
            re.MULTILINE
        )

        lap_times = []
        for match in pattern.finditer(text):
            try:
                # Creiamo direttamente la stringa (es. "1:32.456")
                lap_time_str = f"{match.group(1)}:{match.group(2)}"
                lap_times.append(lap_time_str)
            except IndexError as e:
                print(f"Errore processamento dati: {e}")
                continue
        return lap_times

    @staticmethod
    def get_pilot_name(pilot_data, pilots_names):
        """
        Extracts the pilot's name from the given pilot data by matching it against the list of
        pilots iscritti all'evento, ottenuta dinamicamente tramite get_riders_info (entry list PDF).

        :param pilot_data: Text containing pilot information (e.g., team, nationality, name, position).
        :param pilots_names: Lista di nomi piloti (es. "Augusto FERNANDEZ") relativa all'anno/GP/categoria correnti.
        :return: The name of the pilot if found, otherwise "Name not found".
        """
        normalized_data = "".join(pilot_data.partition('\n')[0].split())

        for name in pilots_names:
            normalized_name = name.replace(" ", "")
            if normalized_name in normalized_data:
                return name

        return "Name not found"

    @staticmethod
    def process_page_text(page_text, is_first_page=False):
        """
        Rimuove le righe di intestazione/piè di pagina non utili dal testo di una pagina del PDF
        e corregge i tempi giro. Unifica quelli che prima erano due metodi quasi identici
        (process_first_page_text / process_other_pages_text), che differivano solo per
        il numero di righe da tagliare in testa.

        :param page_text: Testo estratto dalla pagina del PDF.
        :param is_first_page: True se è la prima pagina del documento (ha un'intestazione più lunga).
        :return: Testo ripulito e con i tempi giro corretti.
        """
        lines = page_text.splitlines()
        head, min_lines = (8, 19) if is_first_page else (2, 11)
        if len(lines) > min_lines:
            lines = lines[head:-7]

        return Analyzer.fix_lap_times("\n".join(lines))

    @staticmethod
    def process_pilots_data(year, granprix):
        """
        Processa il testo estratto dal PDF e immagazzina i dati di ogni pilota in un vettore.

        :param text: Testo (analysis PDF) già processato dal data_reader.
        :param pilots_names: Lista di nomi piloti per l'evento corrente, ottenuta da get_riders_info.
        :return: Lista di tuple (nome_pilota, lista_tempi_giro_in_secondi).
        """
        # Regex per trovare l'inizio dei blocchi di ogni pilota (es. "37Red Bull GASGAS Tech3SPA Augusto FERNANDEZ14th")
        pilot_delimiter_pattern = re.compile(
            r"(\d{1,3})\s*"  # Numero del pilota (1-3 cifre)
            r"([A-Za-z\s&\.'-]+)\s*"  # Nome del team
            r"([A-Z]{2,4})\s*"  # Nazionalità del team
            r"([A-Za-z\s&\.'-Ññ]+)\s*"  # Nome del pilota (inclusi caratteri speciali come Ñ)
            r"(\d{1,2}(?:st|nd|rd|th))",  # Posizione
            re.MULTILINE
        )
        # Regex per delimitare la fine di un pilota, cercando "unfinished"
        end_delimiter_pattern = re.compile(r"unfinished", re.MULTILINE)

        pilots_data = []
        text = Analyzer.trash_eraser(year, granprix)
        #print(text)
        matches = list(pilot_delimiter_pattern.finditer(text))
        unfinished_matches = list(end_delimiter_pattern.finditer(text))

        for i, match in enumerate(matches):
            start = match.start()
            next_pilot_start = matches[i + 1].start() if i + 1 < len(matches) else len(text)

            # Se troviamo "unfinished" prima del prossimo pilota, usalo come fine del blocco
            next_unfinished = [
                u.start() for u in unfinished_matches
                if start < u.start() < next_pilot_start
            ]
            end = next_unfinished[0] if next_unfinished else next_pilot_start

            pilot_block = text[start:end]

            riders = get_riders_info(year, granprix, "MotoGP")
            pilots_names = [f"{rider[4]} {rider[3]}" for rider in riders]  # "Nome COGNOME"

            fixed_pilot_data = Analyzer.fix_lap_times(pilot_block.strip())
            lap_times = Analyzer.extract_lap_times_strings(fixed_pilot_data)
            pilot_name = Analyzer.get_pilot_name(fixed_pilot_data, pilots_names)

            pilots_data.append((pilot_name, lap_times))

        #print(pilots_data)
        return pilots_data

    @staticmethod
    def get_pdf_data(year, gp_name):
        """
        Selects data from a gran prix and year.

        :param year: Season's year.
        :param gp_name: Name of the Gran Prix.
        :return: BytesIO contains PDF's text, oppure None se il download fallisce.
        """
        base_url = "https://resources.motogp.com/files/results"
        urls = [
            f"{base_url}/{year}/{gp_name}/MotoGP/RAC/Analysis.pdf",
            f"{base_url}/{year}/MotoGP/{gp_name}/RAC/analysis.pdf",
        ]
        return download_first_available_pdf(urls)

    @staticmethod
    def trash_eraser(year, granprix):
        """
        Extracts and filters data from PDF.

        :param year: Season's year.
        :param granprix: Gran Prix.
        :return: Extacted and filtered text.
        """
        reader = PyPDF2.PdfReader(Analyzer.get_pdf_data(year, granprix))
        text = ""
        for page_num, page in enumerate(reader.pages):
            page_text = page.extract_text()
            print(page_text)
            filtered_text = Analyzer.process_page_text(page_text, is_first_page=(page_num == 0))
            text += filtered_text + "\n"

        lines = text.split('\n')
        #print('\n'.join(lines))
        formatted_lines = []

        for line in lines:
            match = re.match(r"(\d{1,2}'\d{2}\.\d{3}.*?\d{1,2}\.\d{3})(\d{1,2}[A-Za-z].*)", line)
            if match:
                formatted_lines.append(match.group(1).strip())
                formatted_lines.append(match.group(2).strip())
            else:
                formatted_lines.append(line)

        #print('\n'.join(formatted_lines))
        return '\n'.join(formatted_lines)