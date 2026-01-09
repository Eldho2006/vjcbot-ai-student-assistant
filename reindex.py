import os
import PyPDF2
from database import db, Document
from ai_engine import ai_engine

def reindex_knowledge_base(upload_folder):
    """
    Clears and rebuilds the knowledge_base.txt from the uploads directory.
    """
    if os.path.exists("knowledge_base.txt"):
        try:
            os.remove("knowledge_base.txt")
            print("Cleared existing knowledge base.")
        except Exception as e:
            print(f"Error clearing knowledge base: {e}")

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
                    skipped_pages = 0
                    for ids, page in enumerate(reader.pages):
                        extracted = page.extract_text()
                        if extracted:
                            # --- SMART FILTER: Skip Syllabus Pages ---
                            # If the page header (first 500 chars) explicitly mentions "SYLLABUS" or "COURSE OBJECTIVES"
                            header_text = extracted[:500].upper()
                            if "SYLLABUS" in header_text or "COURSE OBJECTIVES" in header_text or "COURSE OUTLINE" in header_text:
                                skipped_pages += 1
                                continue # Skip this page
                            
                            text += extracted
                    
                    if skipped_pages > 0:
                        print(f"  [Filter] Skipped {skipped_pages} syllabus/intro pages from {filename}")
            elif filename.endswith('.txt'):
                print(f"Processing Text: {filename}")
                with open(filepath, 'r', encoding='utf-8') as f:
                    text = f.read()
            else:
                print(f"Skipping unsupported file: {filename}")
                continue
                
            if text:
                print(f"Adding {len(text)} characters to knowledge base...")
                # We use metadata to ensure the 'filename' is recorded for Source Filtering
                ai_engine.add_document(text, {"source": filename, "uploaded_by": "system_recovery"})
                print("Done.")
            else:
                print(f"Warning: No text extracted from {filename}")
                
        except Exception as e:
            print(f"Error processing {filename}: {e}")

if __name__ == "__main__":
    from app import app
    with app.app_context():
        reindex_knowledge_base(app.config['UPLOAD_FOLDER'])
