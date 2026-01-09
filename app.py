import os
import sys
import traceback

# 1. Minimal Imports
from flask import Flask, jsonify, render_template

# 2. Create App immediately
app = Flask(__name__)

# 3. Global Status Log
DIAGNOSTICS = {
    "flask": "OK",
    "config": "PENDING",
    "extensions": "PENDING",
    "local_imports": "PENDING",
    "blueprints": "PENDING",
    "errors": []
}

@app.route('/health')
def health_check():
    status = "OK" if not DIAGNOSTICS["errors"] else "PARTIAL_ERROR"
    return jsonify({
        "status": status,
        "python_version": sys.version,
        "diagnostics": DIAGNOSTICS
    })

# 4. Safe Import & Init Block
try:
    # --- Config ---
    try:
        from dotenv import load_dotenv
        load_dotenv()
        from config import Config
        app.config.from_object(Config)
        DIAGNOSTICS["config"] = "OK"
    except Exception as e:
        DIAGNOSTICS["config"] = f"FAIL: {e}"
        raise e

    # --- Extensions ---
    try:
        from werkzeug.utils import secure_filename
        from flask import request, redirect, url_for, flash, Blueprint
        from flask_login import LoginManager, login_required, current_user
        import PyPDF2
        DIAGNOSTICS["extensions"] = "OK"
    except Exception as e:
        DIAGNOSTICS["extensions"] = f"FAIL: {e}"
        raise e

    # --- Local Imports (DB/AI) ---
    try:
        from database import db, User, Document
        # NOTE: AI Engine import is commented out for safety, uncomment if needed later
        # from ai_engine import ai_engine 
        DIAGNOSTICS["local_imports"] = "OK (AI Disabled)"
    except Exception as e:
        DIAGNOSTICS["local_imports"] = f"FAIL: {e}"
        raise e

    # --- Init DB ---
    try:
        db.init_app(app)
        login_manager = LoginManager()
        login_manager.login_view = 'auth.login'
        login_manager.init_app(app)

        @login_manager.user_loader
        def load_user(user_id):
            return User.query.get(int(user_id))
        
        DIAGNOSTICS["db_init"] = "OK"
    except Exception as e:
        DIAGNOSTICS["db_init"] = f"FAIL: {e}"
        raise e

    # --- Blueprints ---
    main_bp = Blueprint('main', __name__)
    
    try:
        from auth import auth_bp
        app.register_blueprint(auth_bp)
        DIAGNOSTICS["blueprints"] = "Auth OK"
    except Exception as e:
        DIAGNOSTICS["blueprints"] = f"Auth FAIL: {e}"
        # Trigger error but continue
        DIAGNOSTICS["errors"].append(f"Auth Blueprint Failed: {e}")

    app.register_blueprint(main_bp)

except Exception as e:
    err = f"CRITICAL STARTUP CRASH: {e}\n{traceback.format_exc()}"
    print(err)
    DIAGNOSTICS["errors"].append(err)


# --- ROUTES (Attached to main_bp) ---
# We define them here so they register correctly if main_bp exists
@main_bp.route('/chat')
@login_required
def chat():
    return render_template('chat.html')

@main_bp.route('/admin')
@login_required
def admin_dashboard():
    if current_user.role != 'admin':
        return redirect(url_for('main.chat'))
    # Safe query
    try:
        users = User.query.filter_by(role='student').all()
        documents = Document.query.all()
    except:
        users = []
        documents = []
    return render_template('admin_dashboard.html', users=users, documents=documents)

# ... (omitting other routes for brevity to keep deployment safe/small first) ...
# We can add them back once we confirm imports work.

@app.route('/setup')
def setup_db():
    if DIAGNOSTICS["errors"]:
        return jsonify(DIAGNOSTICS)
        
    try:
        with app.app_context():
            db.create_all()
            if not User.query.filter_by(username='admin').first():
                admin = User(username='admin', role='admin')
                admin.set_password('admin123')
                db.session.add(admin)
                db.session.commit()
                return "Database initialized! Admin created."
            return "Database already exists."
    except Exception as e:
        return f"Setup Error: {e}"

if __name__ == '__main__':
    app.run(debug=True)
