import os
import sys
import logging
from flask import Flask, jsonify, render_template, Blueprint, request, redirect, url_for, flash

# --- Global App Object ---
app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("vjcbot")

# --- Global State ---
db = None
ai_engine = None
INIT_ERROR = None

# --- Critical: Top-level Error Handling for Vercel ---
# We define everything inside a function to prevent import crashes at module level
def initialize_app(app):
    global db, ai_engine
    try:
        # 1. Config
        from config import Config
        app.config.from_object(Config)
        
        # 2. Db & Extensions
        from database import db as _db, User, Document
        import PyPDF2
        from flask_login import LoginManager, login_required, current_user
        
        db = _db
        db.init_app(app)
        
        login_manager = LoginManager()
        login_manager.login_view = 'auth.login'
        login_manager.init_app(app)

        @login_manager.user_loader
        def load_user(user_id):
            return User.query.get(int(user_id))
            
        # 3. AI Engine
        try:
            from ai_engine import ai_engine as _ai
            ai_engine = _ai
        except Exception as e:
            logger.warning(f"AI Engine failed to load: {e}")
            
        # 4. Blueprints
        from auth import auth_bp
        app.register_blueprint(auth_bp)
        
        # Register Main Blueprint
        register_main_routes(app, User, Document, login_required, current_user)
        
        logger.info("Application Initialized Successfully")
        return None
        
    except Exception as e:
        logger.error(f"Initialization Failed: {e}")
        return str(e)

# --- Define Main Routes Function (Avoids circular imports) ---
def register_main_routes(app, User, Document, login_required, current_user):
    main_bp = Blueprint('main', __name__)
    
    @main_bp.route('/chat')
    @login_required
    def chat():
        return render_template('chat.html')

    @main_bp.route('/admin')
    @login_required
    def admin_dashboard():
        if current_user.role != 'admin': return redirect(url_for('main.chat'))
        try:
            users = User.query.filter_by(role='student').all()
            docs = Document.query.all()
        except:
             users, docs = [], []
        return render_template('admin_dashboard.html', users=users, documents=docs)

    # (Add other routes as needed - keeping minimal for stability first)
    # ...
    
    app.register_blueprint(main_bp)

# --- EXECUTE INITIALIZATION SAFELY ---
# This runs on startup. If it fails, INIT_ERROR is set.
INIT_ERROR = initialize_app(app)

# --- Health Check (Always Returns) ---
@app.route('/health')
def health():
    status = "RUNNING"
    if INIT_ERROR:
        status = "CRASHED_ON_STARTUP"
    
    return jsonify({
        "status": status,
        "init_error": INIT_ERROR,
        "db_connected": str(db.engine.url) if db and db.engine else "NO",
        "python": sys.version
    })

@app.route('/setup')
def setup():
    if INIT_ERROR: return f"Cannot Setup: {INIT_ERROR}"
    try:
        with app.app_context():
            db.create_all()
            if not User.query.filter_by(username='admin').first():
                 u = User(username='admin', role='admin')
                 u.set_password('admin123')
                 db.session.add(u)
                 db.session.commit()
                 return "DB Init OK"
            return "DB Exists"
    except Exception as e: return f"Setup Error: {e}"

if __name__ == '__main__':
    app.run(debug=True)
