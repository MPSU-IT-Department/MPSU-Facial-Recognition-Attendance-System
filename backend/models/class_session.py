from extensions import db
from sqlalchemy import Column, Integer, Date, DateTime, ForeignKey, Boolean, String
from datetime import datetime


class ClassSession(db.Model):
    __tablename__ = 'class_sessions'

    id = Column(Integer, primary_key=True)
    class_id = Column(Integer, ForeignKey('Class.ClassID'), nullable=False)
    instructor_id = Column(Integer, ForeignKey('Instructor.InstructorID'), nullable=True)
    date = Column(Date, nullable=False)
    start_time = Column(DateTime)
    scheduled_start_time = Column(DateTime)
    scheduled_end_time = Column(DateTime)
    is_attendance_processed = Column(Boolean, default=False)

    # Room number used for this specific session (e.g., entered in scanner client)
    session_room_number = Column(String(50), nullable=True)

    # Track which kiosk currently holds the view/console lock for this session
    view_lock_owner = Column(String(128), nullable=True)
    view_lock_acquired_at = Column(DateTime, nullable=True)

    # Relationships can be added as needed 
