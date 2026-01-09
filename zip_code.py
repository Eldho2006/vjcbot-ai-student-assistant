import os
import zipfile

SOURCE_DIR = r"c:\Users\ELDHO BASIL\Documents\VJCBOT-AI Chatbot"
OUTPUT_ZIP = r"c:\Users\ELDHO BASIL\Desktop\VJCBOT_Source_Code.zip"

EXCLUDE_DIRS = {'.venv', 'venv', '__pycache__', '.git', '.gemini', 'db', 'instance'}
EXCLUDE_EXT = {'.pyc', '.db', '.sqlite3'}

def zip_project():
    print(f"Zipping {SOURCE_DIR} to {OUTPUT_ZIP}...")
    
    # Explicitly verify existence of critical files
    CRITICAL_FILES = ['app.py', 'config.py', 'database.py', 'auth.py', 'ai_engine.py', 'requirements.txt']
    for cf in CRITICAL_FILES:
        if not os.path.exists(os.path.join(SOURCE_DIR, cf)):
            print(f"CRITICAL ERROR: {cf} MISSING from source!")
            
    with zipfile.ZipFile(OUTPUT_ZIP, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(SOURCE_DIR):
            # Filtering directories
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
            
            for file in files:
                # Exclude specific extensions
                if any(file.endswith(ext) for ext in EXCLUDE_EXT):
                    continue
                
                # Exclude the zip file itself if it's in the dir
                if file == "VJCBOT_Source_Code.zip" or file == "zip_code.py":
                    continue

                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, SOURCE_DIR)
                print(f"Adding: {arcname}")
                zipf.write(file_path, arcname)
    
    print("\nZip created successfully.")

if __name__ == "__main__":
    zip_project()
