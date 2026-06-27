import logging
from io import BytesIO

from pypdf import PdfReader
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
    """if year < 2008:
        return regex.compile(
            r'^(\d+)\s+'  # 1. Numero pilota
            r'([A-Z0-9]+)\s*'  # 2. Costruttore
            r'(.*?)\s*'  # 3. TEAM (Cattura tutto fino al cognome)
            # Nella regex per anni < 2008, cambia la parte del nome/cognome così:
            r'([A-Z]+(?:\s+[A-Z]+)*)\s+'  # 4. Cognome (Tutto maiuscolo)
            r'((?:\p{Lu}\p{Ll}+)(?:\s+\p{Lu}\p{Ll}+)*)\s+'  # 5. Nome (Gestisce spazi tra Jose e Luis)
            r'([A-Z]{3})'  # 6. Nazionalità
        )"""
    if year <= 2010:
        return regex.compile(
            r'^(\d+)\s+'  # 1. Numero
            r'(HONDA|YAMAHA|SUZUKI|DUCATI|KAWASAKI|APRILIA|KTM|[A-Z0-9&]+)\s*'  # 2. Costruttore
            r'('  # 3. TEAM
            r'.*?(?:MotoGP|LCR|HRC|SRT)'  # Opzione A: suffissi maiuscoli noti
            r'|'
            r'.*?[a-z0-9]'  # Opzione B: finisce in minuscola o numero
            r')\s*'
            r'([A-Z]+(?:\s+[A-Z]+)*)\s+'  # 4. Cognome (Tutto maiuscolo)
            r'((?:\p{Lu}\p{Ll}+)(?:\s+\p{Lu}\p{Ll}+)*)\s+'  # 5. Nome (Gestisce spazi tra Jose e Luis)
            r'([A-Z]{3})'
            # 6. Nazionalità
        )
    if year <= 2012:
        # Regex calibrata per l'era CRT (2012 e precedenti)
        # Costruttore, Team e Cognome fusi, costruttori con trattini (BQR-FTR), e sporcizia a fine riga
        return regex.compile(
            r'^(\d+)\s+'  # 1. Numero pilota
            # 2. Costruttori (Aggiunti i telai CRT come BQR-FTR)
            r'(BQR-FTR|HONDA|YAMAHA|SUTER|DUCATI|IODA|ART|FTR|[A-Z0-9-]+)\s*'
            r'('  # 3. TEAM (Inizio gruppo)
            r'.*?(?:MotoGP)'  # Opzione A: Il team finisce in Maiuscolo (es. LCR Honda MotoGP)
            r'|'  # OPPURE
            r'.*?[a-z0-9]'  # Opzione B: Il team finisce con minuscola o numero (es. Blusens, Racing)
            r')\s*'  # (Fine gruppo TEAM) + spazi opzionali
            r'(\p{Lu}{2,}(?:\s+\p{Lu}{2,})?)\s+'  # 4. Cognome (Tutto maiuscolo)
            r'(\p{Lu}\p{Ll}+(?:\s+\p{Lu}\p{Ll}+)*)\s+'  # 5. Nome (Inizia con Maiuscola)
            r'([A-Z]{3})'  # 6. Nazionalità
            # Non mettiamo vincoli stringenti dopo la nazionalità per ignorare le lettere extra (es. "r i")
        )
    if year == 2013:
        return regex.compile(
            r'^(\d+)\s+'  # 1. Numero pilota
            # 2. Costruttori (IMPORTANTE: I nomi composti più lunghi vanno per primi!)
            r'(FTR KAWASAKI|FTR HONDA|IODA-SUTER|DUCATI|HONDA|YAMAHA|ART|FTR|PBM|[A-Z0-9-]+)\s*'
            r'('  # 3. TEAM (Inizio gruppo)
            r'.*?(?:MotoGP)'  # Opzione A: Il team finisce in Maiuscolo (LCR Honda MotoGP)
            r'|'  # OPPURE
            r'.*?[a-z0-9]'  # Opzione B: Il team finisce con minuscola o numero (Team, Racing, Tech 3)
            r')\s*'  # (Fine gruppo TEAM) + spazi opzionali
            r'(\p{Lu}{2,}(?:\s+\p{Lu}{2,})?)\s+'  # 4. Cognome (Tutto maiuscolo)
            r'(\p{Lu}\p{Ll}+(?:\s+\p{Lu}\p{Ll}+)*)\s+'  # 5. Nome (Inizia con Maiuscola)
            r'([A-Z]{3})'  # 6. Nazionalità
        )
    if year <= 2015:
        # Regex calibrata per PDF <= 2015 (Senza Nickname, Costruttore/Team/Cognome incollati)
        return regex.compile(
            r'^(\d+)\s+'  # 1. Numero pilota
            # 2. Costruttore (Cattura i noti di quell'epoca, incluso Yamaha Forward che ha lo spazio)
            r'(ART|Aprilia|Ducati|Honda|Suzuki|Yamaha(?: Forward)?|[A-Za-z0-9]+)\s*'
            r'('  # 3. TEAM (Inizio gruppo)
            r'.*?(?:MotoGP|VDS|LCR|HRC)'  # Opzione A: suffissi del Team che finiscono in Maiuscolo
            r'|'  # OPPURE
            r'.*?[a-z0-9]'  # Opzione B: suffissi del Team che finiscono con lettera minuscola o numero (es. "Racing", "Team", "Tech 3")
            r')\s*'  # (Fine gruppo TEAM) + spazi opzionali
            r'(\p{Lu}{2,}(?:\s+\p{Lu}{2,})?)\s+'  # 4. Cognome (Tutto maiuscolo, richiede spazio dopo per staccarsi dal Nome)
            r'(\p{Lu}\p{Ll}+(?:\s+\p{Lu}\p{Ll}+)*)\s+'  # 5. Nome (Inizia con Maiuscola, richiede spazio dopo)
            r'([A-Z]{3})'  # 6. Nazionalità (3 lettere)
        )
    if year <= 2019:
        # Regex calibrata per gestire Team e Cognome incollati (es. "SRTQUARTARARO" o "RacingBAGNAIA")
        return regex.compile(
            r'^(\d+)\s+'  # 1. Numero pilota
            r'(APRILIA|DUCATI|HONDA|KTM|SUZUKI|YAMAHA|[A-Z0-9&]+)\s*'  # 2. Costruttore
            r'('  # 3. TEAM (Inizio gruppo)
            r'.*?(?:MotoGP|SRT|IDEMITSU|CASTROL|ECSTAR|HRC|VDS|IODA|PRAMAC|ASPAR|GRESINI)'  # Opzione A: suffissi noti tutti maiuscoli
            r'|'  # OPPURE
            r'.*?[a-z0-9]'  # Opzione B: finisce con lettera minuscola o numero (es. "Racing", "Tech 3")
            r')\s*'  # (Fine gruppo TEAM) + spazi opzionali
            r'(\p{Lu}{2,}(?:\s+\p{Lu}{2,})?)\s*'  # 4. Cognome (Tutto maiuscolo)
            r'(\p{Lu}\p{Ll}+(?:\s+\p{Lu}\p{Ll}+)*)\s*'  # 5. Nome
            r'\([A-Za-zÀ-ÿ]{3,}\)\s*'  # Nickname tra parentesi (es. (Dov)) - Non catturato
            r'([A-Z]{3})'  # 6. Nazionalità
        )

    # Regex per anni > 2019 (Include fix per costruttore e cognome uniti)
    return regex.compile(
        r'^(\d+)\s+'  # numero pilota
        # Costruttore (cerca prima quelli noti, poi fallback generico) con spazio opzionale \s*
        r'(APRILIA|DUCATI|HONDA|KTM|SUZUKI|YAMAHA|GASGAS|KALEX|BOSCOSCURO|HUSQVARNA|CFMOTO|[A-Z0-9&]+)\s*'
        r'(\p{Lu}{2,}(?:\s+\p{Lu}{2,})?)\s+'  # cognome
        r'(\p{Lu}\p{Ll}+(?:\s+\p{Lu}\p{Ll}+)*)\s+'  # nome
        r'\([A-Za-zÀ-ÿ]+\)\s+'  # nickname
        r'([A-Z]{3})\s+'  # nazionalità
        r'(.+)$'  # team
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

    text = PdfReader(pdf_data).pages[0].extract_text()
    print(text)
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

        # 1. Pulisci il prefisso 'GP' dal cognome
        if surname.startswith('GP'):
            surname = surname[2:]

        # 2. Recupera prefissi come 'Mc' o 'De' se finiti nel team (es. 'X3Ilmor SRTMc')
        # Questa regex controlla se il team finisce con un prefisso noto
        match_prefix = re.search(r'(Mc)$', team, re.IGNORECASE)
        if match_prefix:
            prefix = match_prefix.group(1)
            team = team[:-len(prefix)].strip()
            surname = prefix + surname

        # 3. Separazione automatica nomi/cognomi incollati (JoseLuis -> Jose Luis)
        # La '?' dopo il gruppo di cattura rende la regex più flessibile
        name = re.sub(r'([a-z])([A-Z])', r'\1 \2', name)
        surname = re.sub(r'([a-z])([A-Z])', r'\1 \2', surname)

        # 4. Normalizzazione finale
        surname = surname.strip()
        name = name.strip()

        team = team.replace('* ', '').replace('W     ', '')
        all_riders.append([number, constructor, team, surname, name, nationality])

    return all_riders