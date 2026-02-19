from extensions import db
from sqlalchemy import Column, Integer, String, DateTime
from datetime import datetime
from utils.timezone import pst_now_naive

class Course(db.Model):
    __tablename__ = 'Course'
    id = Column('CourseID', Integer, primary_key=True)
    code = Column('CourseCode', String(20), unique=True, nullable=False)
    description = Column('CourseDescription', String(500), nullable=False, default='No description')
    created_at = Column(DateTime, default=pst_now_naive)

    @property
    def course_id(self):
        return self.id

    @property
    def course_code(self):
        return self.code

    @course_code.setter
    def course_code(self, value):
        self.code = value

    @property
    def course_description(self):
        return self.description

    @course_description.setter
    def course_description(self, value):
        self.description = value
