from flask import Flask

app = Flask(__name__)

@app.route('/')
def home():
    return "Hello from Vercel! <a href='/health'>Check Health</a>"

@app.route('/health')
def health():
    return "OK"

# Commenting out everything else to isolate crash
# -----------------------------------------------
# ... original code ...
if __name__ == '__main__':
    app.run(debug=True)
