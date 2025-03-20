from flask import Flask, render_template,request
import PyPDF2
import requests
from io import BytesIO
import re
import sys
from pilots import motogp_pilots
app = Flask(__name__)

def fix_lap_times(text):
    """
    Corregge i tempi dei giri nel formato x'xx.xxx o gestisce il caso 'unfinished'.
    Separa i tempi concatenati nella stessa riga.
    """
    # Regex per trovare i tempi dei giri (es. 1'34.1862 o 1'33.8893)
    lap_time_pattern = re.compile(r"(\d{1,2})'(\d{2}\.\d{3})\s+(\d+)\s+(\d+\.\d{3})\s+(\d+\.\d{3})\s+(\d+\.\d{3})\s+(\d+\.\d{1})\s+(\d+\.\d{3})")

    # Trova tutte le occorrenze di tempi concatenati

    # Lista per memorizzare le righe corrette
    fixed_lines = []

    # Itera attraverso le righe del testo
    for line in text.splitlines():
        # Se la riga contiene un tempo concatenato, separiamolo
        if lap_time_pattern.search(line):
            # Sostituisci ogni tempo concatenato con una nuova riga
            fixed_line = lap_time_pattern.sub(lambda x: '\n' + x.group(0), line)
            fixed_lines.append(fixed_line.strip())
        else:
            fixed_lines.append(line.strip())

    # Unisci le righe corrette in un unico testo
    fixed_text = "\n".join(fixed_lines)

    # Rimuovi righe vuote
    fixed_text = "\n".join([line for line in fixed_text.splitlines() if line.strip() != ""])

    return fixed_text

def convert_lap_times_seconds(text):
    """
    Estrae tutti i tempi sul giro validi (nel formato x'xx.xxx all'inizio della riga) e li converte in secondi.
    Ignora i giri contrassegnati come 'unfinished'.
    """
    # Regex per trovare tempi sul giro validi all'inizio della riga (x'xx.xxx)
    lap_time_pattern = re.compile(r"^(\d+)'(\d{2})\.(\d{3})", re.MULTILINE)
    
    lap_times_in_seconds = []
    
    # Trova e converte i tempi sul giro
    for match in lap_time_pattern.finditer(text):
        # Estrai minuti, secondi e millisecondi dal tempo sul giro
        minutes = int(match.group(1))
        seconds = int(match.group(2))
        milliseconds = int(match.group(3))
        
        # Converti il tempo sul giro in secondi
        total_seconds = minutes * 60 + seconds + milliseconds / 1000.0
        lap_times_in_seconds.append(total_seconds)
    
    return lap_times_in_seconds

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
        fixed_pilot_data = fix_lap_times(pilot_block.strip())
        
        #print(fixed_pilot_data, file=sys.stderr)
        #print("\n")
        # Estrai i tempi validi e calcola la media
        lap_times = convert_lap_times_seconds(fixed_pilot_data)
        pilot_name = get_pilot_name(fixed_pilot_data)

        # Salva i dati del pilota e la sua media dei tempi
        pilots_data.append((pilot_name, lap_times))
    
    print(pilots_data)

    return pilots_data  

def get_pilot_name(pilot_data):
    pilot_name = None
    for name in motogp_pilots:
        if name.replace(" ", "") in "".join(pilot_data.partition('\n')[0].split()):
            pilot_name = name
            break
        else:
            continue
        
    # "".join(pilot_data.partition('\n')[0].split())
    if not pilot_name:
        pilot_name = "Nome non trovato"

    return pilot_name

def process_first_page_text(page_text):
    # Dividi il testo della prima pagina in righe
    lines = page_text.splitlines()
    
    # Rimuovi le prime 10 righe e le ultime 9 righe dalla prima pagina
    if len(lines) > 19:
        lines = lines[8:-7]
    
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