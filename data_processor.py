import re
from pilots import motogp_pilots

class Analyzer:
    @staticmethod
    def fix_lap_times(text):
        """
        Corrects lap times in the format x'xx.xxx or handles the 'unfinished' case.
        Separates concatenated lap times in the same line.
        :param text: Text extracted from the PDF containing lap times.
        :return: Formatted lap time.
        """
        # Regex per trovare i tempi dei giri (es. 1'34.1862 o 1'33.8893)
        lap_time_pattern = re.compile(r"(\d{1,2}'\d{2}\.\d{3})(?:\s+\d+(?:\.\d{3}){5}\s+\d+\.\d{1}\s+\d+\.\d{3})")

        fixed_lines = []

        for line in text.splitlines():
            stripped_line = line.strip()
            if lap_time_pattern.search(stripped_line):
                fixed_line = lap_time_pattern.sub(lambda x: '\n' + x.group(0), stripped_line)
                fixed_lines.append(fixed_line.strip())
            else:
                fixed_lines.append(stripped_line)

        """with open('out.txt', 'w') as f:
            print("\n".join(line for line in "\n".join(fixed_lines).splitlines() if line.strip()), file=f)"""
        return "\n".join(line for line in "\n".join(fixed_lines).splitlines() if line.strip())
    
    @staticmethod
    def convert_lap_times_seconds(text):
        """
        Estrae e converte i tempi giro dal formato PDF, gestendo l'inversione tra quarto settore e velocità massima.
        
        :param text: Stringa contenente i dati formattati dal PDF
        :return: Dizionario con tempo giro, settori e velocità massima
        """
        pattern = re.compile(
            r"(\d{1,2})'(\d{2}\.\d{3})"  # Gruppo 1: minuti, Gruppo 2: secondi.millisecondi (tempo giro)
            r"\s+\d+"                    # Posizione (ignorata)
            r"\s+(\d{1,2}'(?:\d{2}\.\d{3})|\d+\.\d{3})"  # Settore 1 (minuti o secondi)
            r"\s+(\d{1,2}'(?:\d{2}\.\d{3})|\d+\.\d{3})"  # Settore 2 (minuti o secondi)
            r"\s+(\d{1,2}'(?:\d{2}\.\d{3})|\d+\.\d{3})"  # Settore 3 (minuti o secondi)
            r"\s+\d+\.\d{1,3}"           # Velocità max
            r"\s+(\d{1,2}'(?:\d{2}\.\d{3})|\d+\.\d{3})",  # Settore 4 (minuti o secondi)
            re.MULTILINE
        )

        lap_times = []
        for match in pattern.finditer(text):
            try:
                # Converti il tempo sul giro
                minutes = int(match.group(1))
                seconds = float(match.group(2))
                total = minutes * 60 + seconds
                lap_times.append(round(total, 3))

            except (ValueError, IndexError) as e:
                print(f"Errore processamento dati: {e}")
                continue
        return lap_times
    
    @staticmethod
    def format_time(seconds):
        """
        Converts a given time in seconds to the format minutes:seconds.milliseconds.

        :param seconds: Time in seconds (can be a float).
        :return: Time formatted as minutes:seconds.milliseconds.
        """
        minutes = int(seconds // 60)
        remaining_seconds = seconds % 60
        return f"{minutes}:{remaining_seconds:06.3f}"
    
    @staticmethod
    def get_pilot_name(pilot_data):
        """
        Extracts the pilot's name from the given pilot data by matching it against a list of known MotoGP pilots.

        :param pilot_data: Text containing pilot information (e.g., team, nationality, name, position).
        :return: The name of the pilot if found, otherwise "Name not found".
        """
        pilot_name = None
        # Normalize the first line of pilot_data by removing spaces and newlines
        normalized_data = "".join(pilot_data.partition('\n')[0].split())

        # Iterate through the list of known MotoGP pilots
        for name in motogp_pilots:
            # Normalize the pilot name by removing spaces
            normalized_name = name.replace(" ", "")
            if normalized_name in normalized_data:
                pilot_name = name
                break

        # Return the pilot's name or a default message if not found
        return pilot_name or "Name not found"
    
    def process_first_page_text(page_text):
        """
        Processes the text of the first page by removing unnecessary lines and correcting lap times.

        :param page_text: Text extracted from the first page of the PDF.
        :return: Text with unnecessary lines removed and lap times corrected.
        """
        # Split the page text into lines
        lines = page_text.splitlines()
    
        # Remove the first 10 lines and the last 9 lines from the first page
        if len(lines) > 19:
            lines = lines[8:-7]
    
        # Join the lines and correct lap times
        #print(Analyzer.fix_lap_times("\n".join(lines)))
        return Analyzer.fix_lap_times("\n".join(lines))
    
    def process_other_pages_text(page_text):
        """
        Processes the text of other pages by removing unnecessary lines and correcting lap times.

        :param page_text: Text extracted from other pages of the PDF.
        :return: Text with unnecessary lines removed and lap times corrected.
        """
        # Split the page text into lines
        lines = page_text.splitlines()

        # Remove the first 2 lines and the last 9 lines from other pages
        if len(lines) > 11:
            lines = lines[2:-7]

        # Join the lines and correct lap times
        #print(Analyzer.fix_lap_times("\n".join(lines)))
        return Analyzer.fix_lap_times("\n".join(lines))
    
    def process_pilots_data(text):
        """
        Processa il testo estratto dal PDF e immagazzina i dati di ogni pilota in un vettore.
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
        matches = list(pilot_delimiter_pattern.finditer(text))
        unfinished_matches = list(end_delimiter_pattern.finditer(text))

        for i, match in enumerate(matches):
            start = match.start()
            end = None

            # Trova il prossimo "unfinished" o la prossima occorrenza di un pilota
            if i + 1 < len(matches):
                next_pilot_start = matches[i + 1].start()
                next_unfinished = [u.start() for u in unfinished_matches if u.start() > start and u.start() < next_pilot_start]
            else:
                next_pilot_start = len(text)
                next_unfinished = [u.start() for u in unfinished_matches if u.start() > start]

            # Se troviamo "unfinished", usalo come fine del blocco
            if next_unfinished:
                end = next_unfinished[0]
            else:
                end = next_pilot_start

            # Estrai il blocco del pilota corrente
            pilot_block = text[start:end]

            # Correggi i tempi del pilota
            fixed_pilot_data = Analyzer.fix_lap_times(pilot_block.strip())

            # Estrai i tempi validi e calcola la media
            lap_times = Analyzer.convert_lap_times_seconds(fixed_pilot_data)
            pilot_name = Analyzer.get_pilot_name(fixed_pilot_data)

            # Salva i dati del pilota e la sua media dei tempi
            pilots_data.append((pilot_name, lap_times))
    
        return pilots_data 