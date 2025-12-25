from flask import Flask
app = Flask(__name__)

@app.route("/")
def home():
    return "ATS Analyzer is LIVE 🚀"

if __name__ == "__main__":
    app.run()
