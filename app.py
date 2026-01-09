import os
from flask import Flask, jsonify

app = Flask(__name__)

@app.route('/')
def home():
    return "Hello! <a href='/health'>Check Health</a>"

@app.route('/health')
def health():
    results = {}
    try:
        import flask_sqlalchemy
        results["flask_sqlalchemy"] = "OK"
    except ImportError as e: results["flask_sqlalchemy"] = str(e)

    try:
        import psycopg2
        results["psycopg2"] = "OK"
    except ImportError as e: results["psycopg2"] = str(e)

    try:
        import google.generativeai
        results["google.generativeai"] = "OK"
    except ImportError as e: results["google.generativeai"] = str(e)

    try:
        import PyPDF2
        results["PyPDF2"] = "OK"
    except ImportError as e: results["PyPDF2"] = str(e)

    try:
        import dotenv
        results["python-dotenv"] = "OK"
    except ImportError as e: results["python-dotenv"] = str(e)

    return jsonify(results)

if __name__ == '__main__':
    app.run(debug=True)
