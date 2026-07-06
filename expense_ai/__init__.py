import os

from flask import Flask

from .database import init_tables
from .ai import load_model
from .routes import register_routes


def create_app(test_config=None):
    templates_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'templates'))
    app = Flask(__name__, template_folder=templates_path)
    app.secret_key = 'replace_with_a_secure_random_key'

    if test_config:
        app.config.update(test_config)

    app.model, app.vectorizer = load_model()
    init_tables()
    register_routes(app)

    return app
