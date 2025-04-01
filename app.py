from flask import Flask, jsonify, render_template, request
from models.data_processor import Analyzer
from models.data_reader import Converting
app = Flask(__name__) 

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/results', methods=['POST'])
def result():
    data = request.form
    year = data.get('year')
    granPrix = data.get('granPrix').upper()

    if not year or not granPrix:
        return jsonify({"success": False, "message": "Parametro/i mancante/i"}), 400

    return render_template('result.html', pilots_data=Analyzer.process_pilots_data(Converting.trash_eraser(Converting.get_pdf_data(year, granPrix))), format_time=Analyzer.format_time, year=year, granPrix=granPrix)

if __name__ == '__main__':
    app.run()