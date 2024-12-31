import os
from flask import Flask
from flask_cors import CORS


def create_app():
    app = Flask(__name__, static_folder="static")
    CORS(
        app, resources={r"/*": {"origins": "*"}}
    )  # Allow all origins for development; restrict in production
    app.config["UPLOAD_FOLDER"] = "static/uploads"

    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    from .routes import api

    app.register_blueprint(api)

    return app
