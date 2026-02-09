import datetime
from extensions import db
from .attendance_status import AttendanceStatus
from utils.timezone import pst_now_naive

class AttendanceRecord(db.Model):
    __tablename__ = 'attendance_records'
    
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.String(20), db.ForeignKey('students.id'), nullable=False)
    class_session_id = db.Column(db.Integer, db.ForeignKey('class_sessions.id'), nullable=True)  # Made nullable for facial recognition
    date = db.Column(db.DateTime, nullable=False)
    status = db.Column(
        db.Enum(
            AttendanceStatus,
            name='attendancestatus',
            values_callable=lambda enum: [status.value for status in enum],
        ),
        nullable=True,
    )  # Store lowercase enum values to match DB type
    time_in = db.Column(db.DateTime)
    time_out = db.Column(db.DateTime)
    notes = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=pst_now_naive)
    updated_at = db.Column(db.DateTime, default=pst_now_naive, onupdate=pst_now_naive)
    marked_at = db.Column(db.DateTime, default=pst_now_naive)
    marked_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    
    # Relationships
    student = db.relationship('Student', back_populates='attendance_records')
    class_session = db.relationship('ClassSession', backref='attendance_records')
    marker = db.relationship('User', backref='marked_attendance')
    
    def __repr__(self):
        return f'<AttendanceRecord {self.id}: {self.student_id} - {self.status.value if self.status else "No Status"}>' 