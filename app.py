from flask import Flask, jsonify, render_template, request
from models.data_processor import Analyzer

app = Flask(__name__)

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/results', methods=['POST'])
def result():
    data = request.form
    year = int(data.get('year'))
    granprix = data.get('granPrix').upper()

    if not year or not granprix:
        return jsonify({"success": False, "message": "Parametro/i mancante/i"}), 400

    return render_template(
        'result.html',
        pilots_data=Analyzer.process_pilots_data(year, granprix),
        year=year,
        granPrix=granprix
    )

if __name__ == '__main__':
    for i in range(2002, 2027):
        print(Analyzer.get_all_tracks_per_year(int(i)))
    app.run()