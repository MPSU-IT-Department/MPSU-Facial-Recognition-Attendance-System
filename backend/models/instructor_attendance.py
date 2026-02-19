from extensions import db
from sqlalchemy import Column, Integer, String, Date, DateTime, Time, ForeignKey, event, select
from datetime import datetime
from utils.timezone import pst_now_naive

class InstructorAttendance(db.Model):
    __tablename__ = 'InstructorAttendance'
    
    id = Column('InstructorAttendanceID', Integer, primary_key=True)
    instructor_id = Column('InstructorID', Integer, ForeignKey('Instructor.InstructorID'), nullable=False)
    class_session_id = Column('ClassSessionID', Integer, ForeignKey('class_sessions.id'), nullable=True)
    class_id = Column('ClassID', Integer, ForeignKey('Class.ClassID'), nullable=True)
    date = Column('Date', Date, nullable=False)
    attendance_time = Column('Time', Time, nullable=True)
    status = Column(String(20), nullable=False)  # 'Present', 'Absent'
    notes = Column(String(500))
    time_in = Column(DateTime)
    time_out = Column(DateTime)
    created_at = Column(DateTime, default=pst_now_naive)
    updated_at = Column(DateTime, default=pst_now_naive, onupdate=pst_now_naive)
    
    # Relationships
    instructor = db.relationship('User', backref='instructor_attendance')
    class_ref = db.relationship('Class', backref='instructor_attendance')
    class_session = db.relationship('ClassSession', backref='instructor_attendance_records')

    @property
    def instructor_attendance_id(self):
        return self.id


@event.listens_for(InstructorAttendance, 'before_insert')
@event.listens_for(InstructorAttendance, 'before_update')
def sync_instructor_attendance_fields(mapper, connection, target):
    if target.class_id is None and target.class_session_id is not None:
        class_sessions = db.metadata.tables.get('class_sessions')
        if class_sessions is not None:
            class_id = connection.execute(
                select(class_sessions.c.class_id).where(class_sessions.c.id == target.class_session_id)
            ).scalar()
            if class_id is not None:
                target.class_id = int(class_id)
    if target.attendance_time is None and target.time_in is not None:
        target.attendance_time = target.time_in.time()
