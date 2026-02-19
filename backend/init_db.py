import os
from flask import Flask
from flask_migrate import Migrate, upgrade
from models import db, User
from config import Config
from extensions import db as extensions_db

def init_app():
    """Initialize Flask application."""
    app = Flask(__name__)
    app.config.from_object(Config)
    extensions_db.init_app(app)
    return app

def init_database():
    """Initialize database and run migrations."""
    app = init_app()
    with app.app_context():
        try:
            migrate = Migrate(app, extensions_db, directory=os.path.join(os.path.dirname(__file__), 'migrations'))
            upgrade()
            return True
        except Exception as e:
            return False

def main():
    """Main function to initialize the database."""
    if init_database():
        pass
    else:
        return 1
    return 0
if __name__ == '__main__':
    exit(main())
