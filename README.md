# VJCBOT - AI Chatbot Setup Instructions

## Prerequisites
1.  **Python** installed (3.10+ recommended).
2.  **API Keys**:
    - **Google Gemini API Key**: Get it from [AI Studio](https://aistudio.google.com/).
    - **Serper API Key** (for Google Search): Get it from [serper.dev](https://serper.dev/).

## Setup Steps

1.  **Install Dependencies**
    Open your terminal in this folder and run:
    ```bash
    pip install -r requirements.txt
    ```

2.  **Set Environment Variables**
    Create a file named `.env` in this directory and add your keys:
    ```env
    GOOGLE_API_KEY=your_gemini_api_key_here
    SERPER_API_KEY=your_serper_api_key_here
    SECRET_KEY=optional_random_string_for_security
    ```
    *Note: If you don't create a .env file, you might need to set them in your system environment.*

3.  **Run the Application**
    ```bash
    python app.py
    ```

4.  **Usage**
    - Open your browser to `http://127.0.0.1:5000`.
    - **Admin Login**:
        - Username: `admin`
        - Password: `admin123`
    - Go to `/admin` to add student users and upload knowledge base documents.
    - **Student Login**: Use the credentials created by the admin.

## Features
- **Admin Dashboard**: Add users, upload PDF/Images.
- **RAG System**: The bot answers based on uploaded documents.
- **Google Search**: If the answer isn't in the documents, it searches the web.
