import os
import datetime
from flask import Flask
from models import db, User, Class, Student, Enrollment, AttendanceRecord, ClassSession, AttendanceStatus
from config import Config
from extensions import db as extensions_db

def reset_class_sessions():
    """Reset class sessions by deleting all existing ones and recreating based on class schedules."""
    app = Flask(__name__)
    app.config.from_object(Config)
    extensions_db.init_app(app)
    with app.app_context():
        AttendanceRecord.query.delete()
        db.session.commit()
        ClassSession.query.delete()
        db.session.commit()
if __name__ == '__main__':
    reset_class_sessions()
