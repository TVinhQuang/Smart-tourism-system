from flask import Flask, send_from_directory

app = Flask(
    __name__,
    static_folder='../frontend',     # Thư mục chứa HTML/CSS/JS
    static_url_path=''              # Cho phép truy cập trực tiếp
)

# Route mặc định trả về index.html
@app.route('/')
def root():
    return send_from_directory(app.static_folder, 'index.html')

# Route trả về mọi file trong frontend
@app.route('/<path:path>')
def serve_file(path):
    return send_from_directory(app.static_folder, path)

if __name__ == '__main__':
    app.run(debug=True)
