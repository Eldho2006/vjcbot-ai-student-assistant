import os
from dotenv import load_dotenv
load_dotenv()

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, Blueprint
from flask_login import LoginManager, login_required, current_user
from werkzeug.utils import secure_filename
from config import Config
from database import db, User, Document
# from ai_engine import ai_engine
import PyPDF2

app = Flask(__name__)
app.config.from_object(Config)

@app.route('/health')
def health_check():
    return "OK: Server is running. Python Version: " + os.sys.version

# Try initializing DB, but don't crash the *entire* app if it fails (so we can see /health)
try:
    db.init_app(app)
except Exception as e:
    print(f"DB Init Failed: {e}")

login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Blueprint for main routes
main_bp = Blueprint('main', __name__)

@main_bp.route('/admin')
@login_required
def admin_dashboard():
    if current_user.role != 'admin':
        return redirect(url_for('main.chat'))
    users = User.query.filter_by(role='student').all()
    documents = Document.query.all()
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
    if current_user.role != 'admin' and current_user.role != 'student':
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
        
        # Process File for RAG (Simplified Text Extraction)
        # Note: In a real app, this should be a background task
        try:
            text = ""
            if filename.endswith('.pdf'):
                # Read directly from memory stream
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
            
            # Save to DB (Content ONLY)
            # We do NOT save the file path anymore
            doc = Document(
                filename=filename, 
                file_path="CLOUD_STORED", # Placeholder
                uploaded_by=current_user.id, 
                doc_type='file',
                content=text, # Save text content
                processed=True
            )
            db.session.add(doc)
            db.session.commit()

            # Construct metadata
            metadata = {"source": filename, "uploaded_by": current_user.role}
            # Add to AI Engine (Uses DB now)
            ai_engine.add_document(text, metadata)
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
    
    # Delete from filesystem
    try:
        if os.path.exists(doc.file_path):
            os.remove(doc.file_path)
            flash(f'File {doc.filename} deleted from server.')
        else:
            flash(f'File {doc.filename} not found on server, removing from DB.')
    except Exception as e:
        flash(f'Error deleting file: {e}')
        
    # Delete from DB
    db.session.delete(doc)
    db.session.commit()
    
    # Re-index to update knowledge_base.txt
    try:
        from reindex import reindex_knowledge_base
        # Pass the upload folder explicitly to avoid circular imports in reindex.py
        reindex_knowledge_base(current_app.config['UPLOAD_FOLDER'])
        flash(f'File {doc.filename} deleted and knowledge base updated.')
    except ImportError:
         flash(f'File {doc.filename} deleted. (Warning: Run reindex.py manually)')
    except Exception as e:
         flash(f'File deleted but reindex failed: {e}')

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
    # Use AI Engine
    # response = ai_engine.get_answer(user_message)
    # return jsonify({'response': response})
    return jsonify({'response': "AI Temporarily Disabled for Debugging"})

@app.route('/setup')
def setup_db():
    try:
        # Debugging: Print config to see if DB URL is picked up
        db_uri = app.config.get('SQLALCHEMY_DATABASE_URI')
        if not db_uri or 'sqlite' in db_uri:
             return f"Warning: Using SQLite or Missing DB URL. URI: {db_uri}"

        with app.app_context():
            db.create_all()
            # Create default admin if not exists
            if not User.query.filter_by(username='admin').first():
                admin = User(username='admin', role='admin')
                admin.set_password('admin123')
                db.session.add(admin)
                db.session.commit()
                return "Database initialized! Admin user created (admin/admin123). <a href='/'>Go Home</a>"
            return "Database already exists. <a href='/'>Go Home</a>"
    except Exception as e:
        import traceback
        return f"CRITICAL ERROR: {e} <br><pre>{traceback.format_exc()}</pre>"

# Register Blueprints
from auth import auth_bp
app.register_blueprint(auth_bp)
app.register_blueprint(main_bp)

# Create DB on startup
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        # Create default admin if not exists
        if not User.query.filter_by(username='admin').first():
            admin = User(username='admin', role='admin')
            admin.set_password('admin123')
            db.session.add(admin)
            db.session.commit()
            print("Default admin created: admin/admin123")
            
    app.run(debug=True)
