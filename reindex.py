import os
import PyPDF2
from app import app
from database import db, Document
from ai_engine import ai_engine

def reindex_all():
    upload_folder = app.config['UPLOAD_FOLDER']
    if not os.path.exists(upload_folder):
        print("No uploads folder found.")
        return

    print("Re-indexing files from:", upload_folder)
    
    for filename in os.listdir(upload_folder):
        filepath = os.path.join(upload_folder, filename)
        text = ""
        
        try:
            if filename.endswith('.pdf'):
                print(f"Processing PDF: {filename}")
                with open(filepath, 'rb') as f:
                    reader = PyPDF2.PdfReader(f)
                    for page in reader.pages:
                        extracted = page.extract_text()
                        if extracted:
                            text += extracted
            elif filename.endswith('.txt'):
                print(f"Processing Text: {filename}")
                with open(filepath, 'r', encoding='utf-8') as f:
                    text = f.read()
            else:
                print(f"Skipping unsupported file: {filename}")
                continue
                
            if text:
                print(f"Adding {len(text)} characters to knowledge base...")
                ai_engine.add_document(text, {"source": filename, "uploaded_by": "system_recovery"})
                print("Done.")
            else:
                print(f"Warning: No text extracted from {filename}")
                
        except Exception as e:
            print(f"Error processing {filename}: {e}")

if __name__ == "__main__":
    with app.app_context():
        reindex_all()
