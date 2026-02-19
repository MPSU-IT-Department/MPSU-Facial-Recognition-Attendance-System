from dotenv import load_dotenv
import os

load_dotenv()


def _env_bool(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_csv(name, default_csv):
    value = os.environ.get(name, default_csv)
    return [item.strip() for item in value.split(",") if item.strip()]


class Config:
    LOCALHOST_ONLY = _env_bool("FRCAS_LOCALHOST_ONLY", True)

    # Flask-Limiter Storage
    # Default to in-memory for local/dev; override with REDIS_URL for production
    RATELIMIT_STORAGE_URL = os.environ.get('REDIS_URL', 'memory://')
    SECRET_KEY = os.environ.get('SESSION_SECRET', 'frcas-local-session-secret')
    
    # Database configuration
    DB_USER = os.environ.get('DB_USER', 'postgres')
    DB_PASSWORD = os.environ.get('DB_PASSWORD', 'password')
    DB_HOST = os.environ.get('DB_HOST', 'localhost')
    DB_PORT = os.environ.get('DB_PORT', '5432')
    DB_NAME = os.environ.get('DB_NAME', 'capstone_db')
    
    SQLALCHEMY_DATABASE_URI = f'postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # API Security
    API_KEY = os.environ.get('FRCAS_API_KEY', 'frcas-local-api-key')
    API_RATE_LIMIT = '100 per minute'  # Rate limiting for API endpoints
    API_TIMESTAMP_TOLERANCE = 300  # 5 minutes in seconds for client-server time sync
    API_MAX_RETRIES = 3  # Maximum number of retries for failed operations
    API_RETRY_DELAY = 0.1  # Delay between retries in seconds
    CORS_ALLOWED_ORIGINS = _env_csv(
        'FRCAS_CORS_ALLOWED_ORIGINS',
        'http://localhost:5000,http://127.0.0.1:5000,https://localhost:5000,https://127.0.0.1:5000'
    )
    
    # File upload configuration (store under frontend/static/uploads)
    _BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    _FRONTEND_STATIC = os.path.abspath(os.path.join(_BASE_DIR, '..', 'frontend', 'static'))
    UPLOAD_FOLDER = os.path.join(_FRONTEND_STATIC, 'uploads')
    FACE_ENCODINGS_CACHE = os.path.abspath(
        os.path.join(_BASE_DIR, '..', 'cache', 'face_encodings.pkl')
    )
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
    
    # Attendance Settings
    ATTENDANCE_GRACE_PERIOD = 15  # minutes after actual start time (when instructor clicked class) to mark as PRESENT
    ATTENDANCE_ABSENT_THRESHOLD = 45  # minutes after actual start time (when instructor clicked class) to mark as ABSENT
    ATTENDANCE_TIMEOUT_WINDOW = 10  # minutes before class end when timeout starts
    ATTENDANCE_SESSION_TIMEOUT = 240  # 4 hours in minutes
    ATTENDANCE_ABSENT_PROCESSING_DELAY = 15  # minutes after session end
    ATTENDANCE_EARLY_THRESHOLD = -5  # minutes (negative means before scheduled start)
    
    # Security Settings
    SESSION_COOKIE_SECURE = _env_bool('SESSION_COOKIE_SECURE', False)  # Keep False for localhost HTTP
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = 3600  # 1 hour
    SESSION_TYPE = 'filesystem'  # Use filesystem for session storage
    SESSION_FILE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'flask_session')
    SESSION_FILE_THRESHOLD = 500  # Maximum number of sessions to store
    
    # Application Settings
    VERSION = '1.0.0'
    DEBUG = _env_bool('FLASK_DEBUG', True)  # Enable debug by default for localhost
    TESTING = False
