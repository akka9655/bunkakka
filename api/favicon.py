from flask import send_from_directory, Flask
import os

app = Flask(__name__)

@app.route('/favicon.ico')
def favicon():
    """Serve favicon from static directory"""
    static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static')
    return send_from_directory(static_dir, 'favicon.ico', mimetype='image/vnd.microsoft.icon')

if __name__ == '__main__':
    app.run()
