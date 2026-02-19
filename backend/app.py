import os
import sys
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'
from flask import Flask, redirect, url_for, session, request
from werkzeug.middleware.proxy_fix import ProxyFix
from dotenv import load_dotenv
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
from config import Config
from extensions import db
from flask_migrate import Migrate
from flask_session import Session
from flask_login import LoginManager
from routes.admin import admin_bp
from models import User, Student, Class, Enrollment, AttendanceRecord, FaceEncoding
load_dotenv()
login_manager = LoginManager()

def create_app():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    frontend_dir = os.path.abspath(os.path.join(base_dir, '..', 'frontend'))
    app = Flask(__name__, static_folder=os.path.join(frontend_dir, 'static'), template_folder=os.path.join(frontend_dir, 'templates'))
    app.config.from_object(Config)
    app.secret_key = app.config['SECRET_KEY']
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

    @app.after_request
    def after_request(response):
        allowed_origins = app.config.get('CORS_ALLOWED_ORIGINS', [])
        request_origin = request.headers.get('Origin')
        if request_origin and request_origin in allowed_origins:
            response.headers['Access-Control-Allow-Origin'] = request_origin
            response.headers['Vary'] = 'Origin'
        elif not app.config.get('LOCALHOST_ONLY', True):
            response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
        response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
        return response
    db.init_app(app)
    migrate = Migrate(app, db, directory=os.path.join(base_dir, 'migrations'))
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    Session(app)
    from routes.api import limiter
    limiter.init_app(app)
    limiter.default_limits = [app.config['API_RATE_LIMIT']]
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    from routes.auth import auth_bp
    from routes.instructors import instructors_bp
    from routes.students import students_bp
    from routes.classes import classes_bp
    from routes.attendance import attendance_bp
    from routes.admin import admin_bp
    from routes.courses import courses_bp
    from routes.api import api_bp
    app.register_blueprint(auth_bp)
    app.register_blueprint(instructors_bp)
    app.register_blueprint(students_bp)
    app.register_blueprint(classes_bp)
    app.register_blueprint(attendance_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(courses_bp)
    app.register_blueprint(api_bp)

    @app.route('/')
    def index():
        return redirect(url_for('auth.login'))

    @app.before_request
    def before_request():
        session.permanent = True
    return app

@login_manager.user_loader
def load_user(user_id):
    from models import User
    return User.query.get(int(user_id))
if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)
