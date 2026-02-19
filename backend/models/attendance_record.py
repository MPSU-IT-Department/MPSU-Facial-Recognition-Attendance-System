import datetime
from sqlalchemy import event, select
from extensions import db
from .attendance_status import AttendanceStatus
from utils.timezone import pst_now_naive

class AttendanceRecord(db.Model):
    __tablename__ = 'StudentAttendance'
    
    id = db.Column('StudentAttendanceID', db.Integer, primary_key=True)
    student_id = db.Column('StudentID', db.String(20), db.ForeignKey('Student.StudentID'), nullable=False)
    class_id = db.Column('ClassID', db.Integer, db.ForeignKey('Class.ClassID'), nullable=True)
    class_session_id = db.Column('ClassSessionID', db.Integer, db.ForeignKey('class_sessions.id'), nullable=True)  # Made nullable for facial recognition
    date = db.Column('Date', db.DateTime, nullable=False)
    attendance_time = db.Column('Time', db.Time, nullable=True)
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
    marked_by = db.Column(db.Integer, db.ForeignKey('Instructor.InstructorID'), nullable=True)
    
    # Relationships
    student = db.relationship('Student', back_populates='attendance_records')
    class_ref = db.relationship('Class', backref='student_attendance_records')
    class_session = db.relationship('ClassSession', backref='attendance_records')
    marker = db.relationship('User', backref='marked_attendance')
    
    def __repr__(self):
        return f'<AttendanceRecord {self.id}: {self.student_id} - {self.status.value if self.status else "No Status"}>'

    @property
    def student_attendance_id(self):
        return self.id


@event.listens_for(AttendanceRecord, 'before_insert')
@event.listens_for(AttendanceRecord, 'before_update')
def sync_attendance_record_fields(mapper, connection, target):
    if target.class_id is None and target.class_session_id is not None:
        class_sessions = db.metadata.tables.get('class_sessions')
        if class_sessions is not None:
            class_id = connection.execute(
                select(class_sessions.c.class_id).where(class_sessions.c.id == target.class_session_id)
            ).scalar()
            if class_id is not None:
                target.class_id = int(class_id)
    if target.attendance_time is None:
        for candidate in (target.time_in, target.date, target.marked_at):
            if isinstance(candidate, datetime.datetime):
                target.attendance_time = candidate.time()
                break
