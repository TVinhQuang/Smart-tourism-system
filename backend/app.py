from flask import Flask, send_from_directory
from flask_cors import CORS

app = Flask(__name__, static_folder="../frontend", static_url_path="/")
CORS(app)

@app.route('/frontend/<path:filename>')
def serve_frontend(filename):
    return send_from_directory('../frontend', filename)

@app.route('/')
def index():
    return send_from_directory('../frontend/page', 'homepage.html')

# import APIs
from routing import *

if __name__ == '__main__':
    app.run(debug=True, port=5000)
