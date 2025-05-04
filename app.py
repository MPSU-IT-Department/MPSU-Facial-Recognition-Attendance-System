import os
import logging
from flask import Flask, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from sqlalchemy.orm import DeclarativeBase
from werkzeug.middleware.proxy_fix import ProxyFix

# Set up logging
logging.basicConfig(level=logging.DEBUG)

# Create base class for SQLAlchemy models
class Base(DeclarativeBase):
    pass

# Initialize SQLAlchemy with the Base class
db = SQLAlchemy(model_class=Base)

# Create the Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev-key-for-testing")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Configure the PostgreSQL database
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/classpass")
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["UPLOAD_FOLDER"] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static/uploads')
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16MB max upload size

# Initialize the app with SQLAlchemy
db.init_app(app)

# Configure LoginManager for authentication
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login'
login_manager.login_message_category = 'info'

# Import and register blueprints
from routes.auth import auth_bp
from routes.students import students_bp
from routes.classes import classes_bp
from routes.attendance import attendance_bp
from routes.instructors import instructors_bp
from routes.courses import courses_bp

app.register_blueprint(auth_bp)
app.register_blueprint(students_bp)
app.register_blueprint(classes_bp)
app.register_blueprint(attendance_bp)
app.register_blueprint(instructors_bp)
app.register_blueprint(courses_bp)

# Root route to redirect to login page
@app.route('/')
def index():
    return redirect(url_for('auth.login'))

# Import models and create all tables
with app.app_context():
    import models
    db.create_all()

# Load the user from the database when needed
@login_manager.user_loader
def load_user(user_id):
    from models import User
    return User.query.get(int(user_id))
