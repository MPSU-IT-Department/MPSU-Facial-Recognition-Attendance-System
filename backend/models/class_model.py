from extensions import db
from sqlalchemy import Column, Integer, String, DateTime, Date, Time, ForeignKey, Enum, event
from datetime import datetime
from utils.timezone import pst_now_naive

class Class(db.Model):
    __tablename__ = 'Class'

    id = Column('ClassID', Integer, primary_key=True)
    class_code = Column('ClassCode', String(20), unique=True, nullable=False)
    class_name = Column('ClassName', String(200), nullable=True)
    description = Column('ClassDescription', String(200))
    class_date = Column('Date', Date, nullable=True)
    class_time = Column('Time', Time, nullable=True)
    instructor_id = Column('InstructorID', Integer, ForeignKey('Instructor.InstructorID'))
    substitute_instructor_id = Column('SubstituteInstructorID', Integer, ForeignKey('Instructor.InstructorID'), nullable=True)
    course_id = Column('CourseID', Integer, ForeignKey('Course.CourseID'), nullable=False)
    schedule = Column('Schedule', String(100))  # Format: "M 9:00-10:30,T 13:00-14:30"
    room_number = Column('RoomNumber', String(20))
    created_at = Column(DateTime, default=pst_now_naive)
    term = Column('Term', Enum('1st semester', '2nd semester', 'summer', name='term_enum'), nullable=True)
    school_year = Column('SchoolYear', String(9), nullable=True)  # Example: '2025-2026'

    # Relationships
    instructor = db.relationship('User', foreign_keys=[instructor_id], backref='classes')
    substitute_instructor = db.relationship('User', foreign_keys=[substitute_instructor_id], backref='substitute_classes')
    course = db.relationship('Course', backref='classes')

    def get_schedule(self, date):
        """Get schedule for a specific date"""
        # TODO: Implement schedule parsing and matching
        return None

    @property
    def date(self):
        return self.class_date

    @date.setter
    def date(self, value):
        self.class_date = value

    @property
    def time(self):
        return self.class_time

    @time.setter
    def time(self, value):
        self.class_time = value

    @property
    def class_id(self):
        return self.id


@event.listens_for(Class, 'before_insert')
@event.listens_for(Class, 'before_update')
def sync_class_name(mapper, connection, target):
    if not target.class_name:
        target.class_name = target.description or target.class_code
