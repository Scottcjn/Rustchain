from flask import Flask
from src.api import init_api

app = Flask(__name__)

# Initialize API routes
init_api(app)

if __name__ == '__main__':
    app.run(debug=True)
