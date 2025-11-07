# app.py
import os
from flask import Flask, jsonify
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)

# Read DB URL from environment (docker compose will provide this)
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
    "DATABASE_URL", "sqlite:///dev.db"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

@app.route("/")
def home():
    return "Hello from Flask inside Docker!"

@app.route("/health")
def health():
    return jsonify(status="ok")
