import os
import sys
import logging

# Configure Logging for Vercel
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

logger.info("Starting Application Init...")

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, Blueprint
from flask_login import LoginManager, login_required, current_user
from werkzeug.utils import secure_filename
from config import Config

# Verify Imports
try:
    from database import db, User, Document
    logger.info("Database module imported.")
except ImportError as e:
    logger.error(f"Database import failed: {e}")
    raise e

try:
    import PyPDF2
    logger.info("PyPDF2 imported.")
except ImportError as e:
    logger.error(f"PyPDF2 import failed: {e}")
    # Don't raise, just log (non-critical start)

# AI Engine Import (Safe)
try:
    from ai_engine import ai_engine
    logger.info("AI Engine imported.")
except Exception as e:
    logger.error(f"AI Engine import failed: {e}")
    ai_engine = None

app = Flask(__name__)
app.config.from_object(Config)

# Initialize Extensions
try:
    db.init_app(app)
    logger.info("SQLAlchemy initialized.")
except Exception as e:
    logger.error(f"SQLAlchemy init failed: {e}")

login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Health Check (Enhanced)
@app.route('/health')
def health_check():
    db_status = "UNKNOWN"
    ai_status = "OK" if ai_engine else "DISABLED"
    
    try:
        # Check DB Connection
        db.session.execute(db.text("SELECT 1"))
        db_status = "CONNECTED"
    except Exception as e:
        db_status = f"ERROR: {e}"

    return jsonify({
        "status": "RUNNING",
        "database": db_status,
        "ai_engine": ai_status,
        "env_vars": {
            "DATABASE_URL": "SET" if os.environ.get("DATABASE_URL") else "MISSING",
            "GOOGLE_API_KEY": "SET" if os.environ.get("GOOGLE_API_KEY") else "MISSING"
        }
    })

# Blueprints
main_bp = Blueprint('main', __name__)

@main_bp.route('/admin')
@login_required
def admin_dashboard():
    if current_user.role != 'admin':
        return redirect(url_for('main.chat'))
    try:
        users = User.query.filter_by(role='student').all()
        documents = Document.query.all()
    except Exception as e:
        flash(f"Database Error: {e}")
        users = []
        documents = []
    return render_template('admin_dashboard.html', users=users, documents=documents)

@main_bp.route('/admin/add_user', methods=['POST'])
@login_required
def add_user():
    if current_user.role != 'admin':
        return redirect(url_for('main.chat'))
    
    username = request.form.get('username')
    password = request.form.get('password')
    
    if User.query.filter_by(username=username).first():
        flash('Username already exists')
    else:
        new_user = User(username=username, role='student')
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        flash('User added successfully')
    
    return redirect(url_for('main.admin_dashboard'))

@main_bp.route('/admin/upload', methods=['POST'])
@login_required
def upload_file():
    if current_user.role != 'admin' and current_user.role != 'student': # Allow students? Logic says admin/student 
         pass 

    if 'file' not in request.files:
        flash('No file part')
        return redirect(request.referrer)
    
    file = request.files['file']
    if file.filename == '':
        flash('No selected file')
        return redirect(request.referrer)
    
    if file:
        filename = secure_filename(file.filename)
        
        try:
            text = ""
            if filename.endswith('.pdf'):
                reader = PyPDF2.PdfReader(file.stream)
                for page in reader.pages:
                    extracted = page.extract_text()
                    if extracted:
                        text += extracted
            elif filename.endswith('.txt'):
                text = file.stream.read().decode('utf-8')
            elif filename.endswith('.docx'):
                flash('DOCX parsing not yet enabled, please save as PDF or TXT')
                return redirect(request.referrer)
            
            doc = Document(
                filename=filename, 
                file_path="CLOUD_STORED",
                uploaded_by=current_user.id, 
                doc_type='file',
                content=text,
                processed=True
            )
            db.session.add(doc)
            db.session.commit()

            metadata = {"source": filename, "uploaded_by": current_user.role}
            if ai_engine:
                 ai_engine.add_document(text, metadata)
            else:
                 flash("Warning: AI Engine unavailable. Document saved but not indexed.")

            flash('File processed and saved to database successfully')
        except Exception as e:
            flash(f'Error processing file: {e}')

        return redirect(request.referrer)

@main_bp.route('/admin/delete_file/<int:file_id>', methods=['POST'])
@login_required
def delete_file(file_id):
    if current_user.role != 'admin':
        return redirect(url_for('main.chat'))
    
    doc = Document.query.get_or_404(file_id)
    # File usage is cloud/db only now, no local file delete needed usually
    # But code had os.remove, which will fail on Vercel if path doesn't exist
    # We skip fs delete for now or wrap it
    
    db.session.delete(doc)
    db.session.commit()
    return redirect(url_for('main.admin_dashboard'))

@main_bp.route('/chat')
@login_required
def chat():
    return render_template('chat.html')

@main_bp.route('/api/chat', methods=['POST'])
@login_required
def chat_api():
    data = request.json
    user_message = data.get('message')
    if ai_engine:
        response = ai_engine.get_answer(user_message)
    else:
        response = "AI System is currently initializing or unavailable."
    return jsonify({'response': response})

@app.route('/setup')
def setup_db():
    try:
        db_uri = app.config.get('SQLALCHEMY_DATABASE_URI')
        with app.app_context():
            db.create_all()
            if not User.query.filter_by(username='admin').first():
                admin = User(username='admin', role='admin')
                admin.set_password('admin123')
                db.session.add(admin)
                db.session.commit()
                return f"Init Success. DB: {db_uri} <a href='/'>Go Home</a>"
            return f"Already Initialized. DB: {db_uri} <a href='/'>Go Home</a>"
    except Exception as e:
        import traceback
        return f"Setup Failed: {e}<br><pre>{traceback.format_exc()}</pre>"

# Register Blueprints Safe
try:
    from auth import auth_bp
    app.register_blueprint(auth_bp)
except ImportError:
    pass

app.register_blueprint(main_bp)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
