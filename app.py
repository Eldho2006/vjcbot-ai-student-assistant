import os
import sys
import logging
from flask import Flask, jsonify, Blueprint

# --- Global App ---
app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("vjcbot")

# Global State
INITIALIZED = False
INIT_ERROR = None
db = None
ai_engine = None

# --- Init Logic (NOT CALLED AUTOMATICALLY) ---
def trigger_init():
    global INITIALIZED, INIT_ERROR, db, ai_engine
    if INITIALIZED: return
    
    try:
        from config import Config
        app.config.from_object(Config)
        
        from database import db as _db, User, Document
        import PyPDF2
        from flask_login import LoginManager
        
        db = _db
        db.init_app(app)
        
        lm = LoginManager()
        lm.login_view = 'auth.login'
        lm.init_app(app)
        
        try:
            from ai_engine import ai_engine as _ai
            ai_engine = _ai
        except: pass
        
        from auth import auth_bp
        app.register_blueprint(auth_bp)
        
        # Register Main Blueprint Inline
        main_bp = Blueprint('main', __name__)
        @main_bp.route('/chat')
        def chat(): return "Chat Placeholder"
        app.register_blueprint(main_bp)

        INITIALIZED = True
        INIT_ERROR = None
    except Exception as e:
        INIT_ERROR = str(e)
        raise e

@app.route('/health')
def health():
    return jsonify({
        "status": "RUNNING",
        "initialized": INITIALIZED,
        "init_error": INIT_ERROR,
        "python": sys.version
    })

@app.route('/start')
def start_app():
    try:
        trigger_init()
        return jsonify({"status": "INIT_SUCCESS"})
    except Exception as e:
        return jsonify({"status": "INIT_CRASH", "error": str(e)})

if __name__ == '__main__':
    app.run(debug=True)
