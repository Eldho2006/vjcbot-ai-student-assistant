import os
from flask import Flask

app = Flask(__name__)

@app.route('/')
def home():
    return "Hello! <a href='/health'>Check Health</a>"

@app.route('/health')
def health():
    try:
        from flask_sqlalchemy import SQLAlchemy
        db = SQLAlchemy(app)
        return "OK: SQLAlchemy Loaded."
    except Exception as e:
        return f"CRITICAL ERROR: {e}"

if __name__ == '__main__':
    app.run(debug=True)
