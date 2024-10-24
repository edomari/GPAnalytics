from flask import Flask, render_template,request
import PyPDF2
import requests
from io import BytesIO
import re

app = Flask(__name__)
def fix_lap_times(text):
    """
    Corregge i tempi dei giri nel formato x'xx.xxx o gestisce il caso 'unfinished'.
    """
    # Regex per trovare i tempi sul giro, es. 1'31.117 o la stringa "unfinished"
    lap_time_pattern = re.compile(r"(\d'\d{2}\.\d{3}|unfinished)")
    
    # Aggiungi una nuova riga prima di ogni tempo che appare dopo il primo nella stessa riga
    fixed_text = lap_time_pattern.sub(lambda x: '\n' + x.group(0), text)
    
    # Rimuovi le righe vuote
    fixed_text = "\n".join([line for line in fixed_text.splitlines() if line.strip() != ""])
    
    return fixed_text

def convert_lap_times_seconds(text):
    """
    Estrae tutti i tempi validi (nel formato x'xx.xxx) e li converte in secondi.
    Ignora i giri contrassegnati come 'unfinished'.
    """
    # Regex per trovare tutti i tempi nel formato x'xx.xxx
    lap_time_pattern = re.compile(r"(\d)'(\d{2})\.(\d{3})")
    
    lap_times_in_seconds = []
    
    # Trova tutti i tempi nel testo
    for match in lap_time_pattern.finditer(text):
        minutes = int(match.group(1))
        seconds = int(match.group(2))
        milliseconds = int(match.group(3))
        
        # Converti il tempo in secondi
        total_seconds = minutes * 60 + seconds + milliseconds / 1000.0
        lap_times_in_seconds.append(total_seconds)
    
    return lap_times_in_seconds

def calculate_average_lap_time(lap_times):
    """
    Calcola la media dei tempi sul giro dati in secondi.
    """
    if len(lap_times) == 0:
        return None  # Nessun tempo valido disponibile
    return sum(lap_times) / len(lap_times)

def format_time(seconds):
    """
    Converte un tempo dato in secondi nel formato minuti:secondi.millisecondi.
    """
    minutes = int(seconds // 60)
    remaining_seconds = seconds % 60
    return f"{minutes}:{remaining_seconds:06.3f}"

def process_pilots_data(text):
    """
    Processa il testo estratto dal PDF e immagazzina i dati di ogni pilota in un vettore.
    Ogni pilota ha 5 righe di informazioni seguite da 27 giri.
    """
    # Regex per trovare l'inizio dei blocchi di ogni pilota (es. "37Red Bull GASGAS Tech3SPA Augusto FERNANDEZ14th")
    pilot_delimiter_pattern = re.compile(r"\d{1,3}[A-Za-z\s&\-\']+[A-Z]{2,4}\s+[A-Za-z\s\-\u00C0-\u017F]+(?=\d{1,2}(st|nd|rd|th))", re.MULTILINE)
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
        fixed_pilot_data = fix_lap_times(pilot_block.strip())
        
        # Estrai i tempi validi e calcola la media
        lap_times = convert_lap_times_seconds(fixed_pilot_data)
        pilot_name = get_pilot_name(fixed_pilot_data)

        # Salva i dati del pilota e la sua media dei tempi
        pilots_data.append((pilot_name, lap_times))

    return pilots_data  

def get_pilot_name(pilot_data):
    pilot_name = None
    for name in motogp_pilots:
        if name[:6] in pilot_data:
            pilot_name = name
            break
        if name[-3:] in pilot_data:
            pilot_name = name

    if not pilot_name:
        pilot_name = "Nome non trovato"

    return pilot_name

# Lista dei nomi dei piloti della MotoGP 2024
motogp_pilots = [
    "Valentino ROSSI", "Nicky HAYDEN", "Dani PEDROSA", "Casey STONER", "Loris CAPIROSSI", 
    "Marco MELANDRI", "John HOPKINS", "Chris VERMEULEN", "Toni ELIAS", "Randy DE PUNIET", 
    "Shinya NAKANO", "Makoto TAMADA", "Alex HOFMANN", "Kenny ROBERTS Jr.", "James ELLISON",
    "Sylvain GUINTOLI", "Kurtis ROBERTS", "Anthony WEST", "Andrea DOVIZIOSO", "Jorge LORENZO", 
    "James TOSELAND", "Mika KALLIO", "Niccolo CANEPA", "Gabor TALMACSI", "Aleix ESPARGARO", 
    "Hiroshi AOYAMA", "Ben SPIES", "Marco SIMONCELLI", "Karel ABRAHAM", "Cal CRUTCHLOW", 
    "Stefan BRADL", "Colin EDWARDS", "Toni ELIAS", "Randy DE PUNIET", "Hector BARBERA",
    "Bradley SMITH", "Danilo PETRUCCI", "Scott REDDING", "Pol ESPARGARO", "Yonny HERNANDEZ",
    "Marc MARQUEZ", "Michele PIRRO", "Maverick VIÑALES", "Jack MILLER", "Tito RABAT", 
    "Franco MORBIDELLI", "Johann ZARCO", "Takaaki NAKAGAMI", "Alex RINS", "Fabio QUARTARARO", 
    "Miguel OLIVEIRA", "Pecco BAGNAIA", "Joan MIR", "Iker LECUONA", "Luca MARINI", 
    "Brad BINDER", "Fabio DI GIANNANTONIO", "Remy GARDNER", "Augusto FERNANDEZ", "Jorge MARTIN", 
    "Raul FERNANDEZ", "Pedro ACOSTA", "Marco BEZZECCHI", "Enea BASTIANINI", "Lorenzo SAVADORI", "Alex MARQUEZ", 
    "Andrea IANNONE", "Alvaro BAUTISTA", "Alex DE ANGELIS", "Loris BAZ", "Eugene LAVERTY", 
    "Claudio CORTI", "Troy BAYLISS"
]

def process_first_page_text(page_text):
    # Dividi il testo della prima pagina in righe
    lines = page_text.splitlines()
    
    # Rimuovi le prime 10 righe e le ultime 9 righe dalla prima pagina
    if len(lines) > 19:
        lines = lines[9:-7]
    
    # Unisci le linee e correggi i tempi
    return fix_lap_times("\n".join(lines))

def process_other_pages_text(page_text):
    # Dividi il testo delle altre pagine in righe
    lines = page_text.splitlines()
    
    # Rimuovi le prime 2 righe e le ultime 9 righe dalle altre pagine
    if len(lines) > 11:
        lines = lines[2:-7]
    
    # Unisci le linee e correggi i tempi
    return fix_lap_times("\n".join(lines))

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/results', methods=['GET'])
def result():
    # Verifica che anno e granPremio siano stati passati correttamente
    anno = request.args.get('anno')
    gran_premio = request.args.get('granPremio').upper()

    if not anno or not gran_premio:
        return "Parametri mancanti", 400  # Restituisce un errore se mancano parametri
    
    # Resto del codice per il download e l'elaborazione del PDF
    pdf_url = f'https://resources.motogp.com/files/results/{anno}/{gran_premio}/MotoGP/RAC/Analysis.pdf'

    # Scarica il PDF
    response = requests.get(pdf_url)
    if response.status_code != 200:
        new_url = f'https://resources.motogp.com/files/results/{anno}/MotoGP/{gran_premio}/RAC/analysis.pdf'
        response = requests.get(new_url)
        if response.status_code != 200:
            return f"Errore: non è possibile scaricare il PDF dal seguente URL: {new_url}", 404
        else:
            pdf_url = new_url
    
    # Scarica il PDF

    pdf_data = BytesIO(response.content)

    # Usa PyPDF2 per estrarre il testo
    reader = PyPDF2.PdfReader(pdf_data)
    text = ""
    for page_num in range(len(reader.pages)):
        page = reader.pages[page_num]
        page_text = page.extract_text()
            
        # Applica la rimozione delle righe solo alla prima pagina
        if page_num == 0:
            filtered_text = process_first_page_text(page_text)
        else:
            # Rimuovi le prime 2 righe e le ultime 9 righe per tutte le altre pagine
            filtered_text = process_other_pages_text(page_text)
                
        text += filtered_text + "\n"  # Aggiungi il testo (modificato o no)
    
    # Processa i dati dei piloti
    pilots_data = process_pilots_data(text)

    # Stampa i dati dei piloti
    # Rendi la pagina con il testo estratto e i dati dei piloti
    return render_template('result.html', pilots_data = pilots_data, format_time = format_time, anno = anno)

if __name__ == '__main__':
    app.run()