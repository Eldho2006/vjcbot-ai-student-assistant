import os
import sys
import logging
import traceback
from flask import Flask, jsonify, render_template, Blueprint, request, redirect, url_for, flash

# --- Global App Object ---
app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("vjcbot")

# --- Global State ---
INIT_ERROR = None
db = None
ai_engine = None

# --- Initialization Logic ---
def initialize_app(app):
    global db, ai_engine
    try:
        # 1. Config
        from config import Config
        app.config.from_object(Config)
        
        # DEBUG: Force set URI if specifically missing (Safety Net)
        if not app.config.get('SQLALCHEMY_DATABASE_URI'):
             uri = os.environ.get('DATABASE_URL')
             if uri and uri.startswith("postgres://"):
                 uri = uri.replace("postgres://", "postgresql://", 1)
             app.config['SQLALCHEMY_DATABASE_URI'] = uri or 'sqlite:///vjcbot.db'
        
        # 2. Database
        from database import db as _db, User, Document
        db = _db
        db.init_app(app)
        
        # 3. Extensions
        from flask_login import LoginManager, login_required, current_user
        login_manager = LoginManager()
        login_manager.login_view = 'auth.login'
        login_manager.init_app(app)

        @login_manager.user_loader
        def load_user(user_id):
            if INIT_ERROR: return None # Safety
            return User.query.get(int(user_id))
            
        # 4. AI Engine (Soft Fail)
        try:
            from ai_engine import ai_engine as _ai
            ai_engine = _ai
        except Exception as e:
            logger.warning(f"AI Engine skipped: {e}")

        # 5. Blueprints
        from auth import auth_bp
        app.register_blueprint(auth_bp)
        
        # Main Routes (Inline to avoid circular deps if any)
        register_main_routes(app, User, Document, login_required, current_user)
        
        logger.info("App Initialized Successfully")
        return None
        
    except Exception as e:
        logger.error(f"Init Failed: {e}")
        return f"{e}\n{traceback.format_exc()}"

def register_main_routes(app, User, Document, login_required, current_user):
    main_bp = Blueprint('main', __name__)
    
    # Helper to check DB health in routes
    def db_safe():
        return not INIT_ERROR

    @main_bp.route('/chat')
    @login_required
    def chat():
        return render_template('chat.html')

    @main_bp.route('/admin')
    @login_required
    def admin_dashboard():
        if not db_safe(): return "System Error", 500
        if current_user.role != 'admin':
            return redirect(url_for('main.chat'))
        try:
            users = User.query.filter_by(role='student').all()
            docs = Document.query.all()
            return render_template('admin_dashboard.html', users=users, documents=docs)
        except Exception as e:
            return f"Dashboard Error: {e}"

    @main_bp.route('/admin/add_user', methods=['POST'])
    @login_required
    def add_user():
        if current_user.role != 'admin': return redirect(url_for('main.chat'))
        try:
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
        except Exception as e:
            flash(f"Error: {e}")
        return redirect(url_for('main.admin_dashboard'))

    @main_bp.route('/admin/upload', methods=['POST'])
    @login_required
    def upload_file():
        from werkzeug.utils import secure_filename
        import PyPDF2
        try:
            if 'file' in request.files:
                f = request.files['file']
                if f and f.filename:
                    # Logic
                    filename = secure_filename(f.filename)
                    text = ""
                    if filename.lower().endswith('.pdf'):
                         reader = PyPDF2.PdfReader(f.stream)
                         for page in reader.pages: text += page.extract_text() or ""
                    else: text = "Non-PDF"
                    
                    doc = Document(filename=filename, file_path="CLOUD", uploaded_by=current_user.id, content=text[:100000], processed=True)
                    db.session.add(doc)
                    db.session.commit()
                    
                    if ai_engine: ai_engine.add_document(text, {})
                    flash('Uploaded')
        except Exception as e:
            flash(f"Upload Error: {e}")
        return redirect(request.referrer)

    @main_bp.route('/admin/delete_file/<int:file_id>', methods=['POST'])
    @login_required
    def delete_file(file_id):
        if current_user.role != 'admin': return redirect(url_for('main.chat'))
        try:
            doc = Document.query.get_or_404(file_id)
            db.session.delete(doc)
            db.session.commit()
            flash('File deleted')
        except Exception as e:
            flash(f"Delete Error: {e}")
        return redirect(url_for('main.admin_dashboard'))

    @main_bp.route('/api/chat', methods=['POST'])
    @login_required
    def chat_api():
        msg = request.json.get('message')
        if ai_engine:
             resp = ai_engine.get_answer(msg)
        else:
             resp = "AI Unavailable"
        return jsonify({'response': resp})

    app.register_blueprint(main_bp)


# --- EXECUTE INIT (Auto-Start) ---
INIT_ERROR = initialize_app(app)

# --- Routes ---
@app.route('/')
def index():
    if INIT_ERROR:
        return f"<h1>Startup Error (Safe Mode)</h1><pre>{INIT_ERROR}</pre>"
    return redirect(url_for('auth.login'))

@app.route('/health')
def health():
    return jsonify({
        "status": "RUNNING",
        "init_error": INIT_ERROR,
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
