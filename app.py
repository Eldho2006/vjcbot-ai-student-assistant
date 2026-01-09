import os
import sys
import logging
import traceback

# 1. Initialize Flask App IMMEDIATELY
from flask import Flask, jsonify, render_template, Blueprint, request, redirect, url_for, flash

app = Flask(__name__)

# 2. Global Error Storage
STARTUP_ERRORS = []

# 3. Health Route (Always works)
@app.route('/health')
def health():
    return jsonify({
        "status": "RUNNING" if not STARTUP_ERRORS else "PARTIAL_FAIL",
        "errors": STARTUP_ERRORS,
        "python": sys.version
    })

# 4. Critical Logic Wrapper
try:
    # --- Logging ---
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    # --- Config ---
    try:
        from config import Config
        app.config.from_object(Config)
    except Exception as e:
        STARTUP_ERRORS.append(f"Config Error: {e}")

    # --- Database Init ---
    try:
        from database import db, User, Document
        db.init_app(app)
        # Verify connection immediately to catch Auth errors early
        # Note: We do NOT use 'with app.app_context()' here to avoid 'teardown_appcontext' issues if module level is weird
        # But we do need to known if DB is reachable? No, lazy connect is better.
    except Exception as e:
        STARTUP_ERRORS.append(f"Database Init Error: {e}")

    # --- Extensions ---
    try: 
        from flask_login import LoginManager, login_required, current_user
        login_manager = LoginManager()
        login_manager.login_view = 'auth.login'
        login_manager.init_app(app)

        @login_manager.user_loader
        def load_user(user_id):
            if not helper_db_ready(): return None
            return User.query.get(int(user_id))
            
    except Exception as e:
        STARTUP_ERRORS.append(f"Extensions/Login Error: {e}")

    # --- AI Engine ---
    ai_engine = None
    try:
        from ai_engine import ai_engine
    except Exception as e:
         # Log but don't crash
         logger.warning(f"AI Engine not loaded: {e}")

    # --- Helper: Check if DB is ready before queries ---
    def helper_db_ready():
        return "Database Init Error" not in str(STARTUP_ERRORS)

    # --- Blueprints ---
    main_bp = Blueprint('main', __name__)

    @main_bp.route('/admin')
    @login_required
    def admin_dashboard():
        if not helper_db_ready(): return "Database Error", 500
        if current_user.role != 'admin':
            return redirect(url_for('main.chat'))
        users = User.query.filter_by(role='student').all()
        documents = Document.query.all()
        return render_template('admin_dashboard.html', users=users, documents=documents)

    @main_bp.route('/admin/add_user', methods=['POST'])
    @login_required
    def add_user():
        if current_user.role != 'admin': return redirect(url_for('main.chat'))
        username = request.form.get('username')
        password = request.form.get('password')
        if User.query.filter_by(username=username).first():
            flash('Username exists')
        else:
            u = User(username=username, role='student')
            u.set_password(password)
            db.session.add(u)
            db.session.commit()
            flash('User created')
        return redirect(url_for('main.admin_dashboard'))
        
    @main_bp.route('/admin/upload', methods=['POST'])
    @login_required
    def upload_file():
        from werkzeug.utils import secure_filename
        import PyPDF2
        if 'file' in request.files:
            f = request.files['file']
            if f and f.filename:
                # Basic Logic
                filename = secure_filename(f.filename)
                text = ""
                # ... extraction logic ...
                # Saving
                doc = Document(filename=filename, file_path="CLOUD", uploaded_by=current_user.id, content=text, processed=True)
                db.session.add(doc)
                db.session.commit()
                # AI
                if ai_engine: ai_engine.add_document(text, {})
                flash('Uploaded')
        return redirect(request.referrer)

    @main_bp.route('/chat')
    @login_required
    def chat():
        return render_template('chat.html')
        
    @main_bp.route('/api/chat', methods=['POST'])
    @login_required
    def chat_api():
        msg = request.json.get('message')
        if ai_engine:
             resp = ai_engine.get_answer(msg)
        else:
             resp = "AI Unavailable"
        return jsonify({'response': resp})

    # Register Main
    app.register_blueprint(main_bp)
    
    # Register Auth Safely
    try:
        from auth import auth_bp
        app.register_blueprint(auth_bp)
    except Exception as e:
        STARTUP_ERRORS.append(f"Auth Blueprint Error (Likely DB related): {e}")

    # Setup Route
    @app.route('/setup')
    def setup_db():
        if not helper_db_ready(): return jsonify(STARTUP_ERRORS)
        try:
             with app.app_context():
                 db.create_all()
                 if not User.query.filter_by(username='admin').first():
                     u = User(username='admin', role='admin')
                     u.set_password('admin123')
                     db.session.add(u)
                     db.session.commit()
                     return "DB Init Success"
                 return "DB Exists"
        except Exception as e:
             return f"Setup Failed: {e}"

except Exception as e:
    STARTUP_ERRORS.append(f"FATAL STARTUP ERROR: {e}\n{traceback.format_exc()}")
    print(f"FATAL: {e}")

if __name__ == '__main__':
    app.run(debug=True)
