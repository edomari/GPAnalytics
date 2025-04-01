import re
import PyPDF2
import requests
from io import BytesIO
from models.data_processor import Analyzer
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Converting:

    @staticmethod
    def get_pdf_data(year, gp_name):
        """
        Selects data from a gran prix and year.

        :param year: Season's year.
        :param gp_name: Name of the Gran Prix.
        :return: BytesIO contains PDF's text.
        """
        base_url = "https://resources.motogp.com/files/results"
        urls = [
            f"{base_url}/{year}/{gp_name}/MotoGP/RAC/Analysis.pdf",
            f"{base_url}/{year}/MotoGP/{gp_name}/RAC/analysis.pdf",
        ]
        for url in urls:
            response = requests.get(url)
            if response.status_code == 200:
                logger.info(f"PDF downloaded from: {url}")
                return BytesIO(response.content)
            logger.warning(f"Impossible to download PDF from: {url}")
    
    @staticmethod
    def trash_eraser(pdf_data):
        """
        Extracts and filters data from PDF.

        :param pdf_data: BytesIO contains PDF.
        :return: Extacted and filtered text.
        """
        reader = PyPDF2.PdfReader(pdf_data)
        text = ""
        for page_num in range(len(reader.pages)):
            page = reader.pages[page_num]
            page_text = page.extract_text()
  
            if page_num == 0:
                filtered_text = Analyzer.process_first_page_text(page_text)
            else:
                filtered_text = Analyzer.process_other_pages_text(page_text)
            text += filtered_text + "\n"
        
        lines = text.split('\n')
        formatted_lines = []

        for line in lines:
            match = re.match(r"(\d{1,2}'\d{2}\.\d{3}.*?\d{1,2}\.\d{3})(\d{1,2}[A-Za-z].*)", line)
            if match:
                formatted_lines.append(match.group(1).strip())
                formatted_lines.append(match.group(2).strip())
            else:
                formatted_lines.append(line)

        return '\n'.join(formatted_lines)