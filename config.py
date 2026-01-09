import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'you-will-never-guess-this-key-vjcbot'
    # Vercel/Render provide 'postgres://' but SQLAlchemy needs 'postgresql://'
    uri = os.environ.get('DATABASE_URL')
    if uri and uri.startswith("postgres://"):
        uri = uri.replace("postgres://", "postgresql://", 1)
    
    SQLALCHEMY_DATABASE_URI = uri or 'sqlite:///vjcbot.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # Upload folder is no longer used for storage, but Flask might want a temp dir
    UPLOAD_FOLDER = '/tmp' 
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max upload size
