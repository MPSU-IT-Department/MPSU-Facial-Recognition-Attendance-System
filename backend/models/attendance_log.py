from extensions import db
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from datetime import datetime
from utils.timezone import pst_now_naive

class AttendanceLog(db.Model):
    __tablename__ = 'attendance_logs'
    
    id = Column(Integer, primary_key=True)
    student_id = Column(String(20), ForeignKey('Student.StudentID'), nullable=False)
    class_id = Column(Integer, ForeignKey('Class.ClassID'), nullable=False)
    check_in_time = Column(DateTime, nullable=False)
    status = Column(String(20), nullable=False)  # 'Present', 'Late', 'Absent'
    notes = Column(String(500))
    created_at = Column(DateTime, default=pst_now_naive)
    
    # Relationships
    student = db.relationship('Student', backref='attendance_logs')
    class_record = db.relationship('Class', backref='attendance_logs') 
