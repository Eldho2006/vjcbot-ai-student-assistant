import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    print("Error: GOOGLE_API_KEY not found in .env")
else:
    genai.configure(api_key=api_key)
    try:
        with open('available_models.txt', 'w') as f:
            f.write("Available models:\n")
            for m in genai.list_models():
                if 'generateContent' in m.supported_generation_methods:
                    f.write(f"{m.name}\n")
        print("Models written to available_models.txt")
    except Exception as e:
        print(f"Error listing models: {e}")
