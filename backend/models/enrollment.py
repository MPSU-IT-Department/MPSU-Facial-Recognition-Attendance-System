from extensions import db
from sqlalchemy import Column, Integer, DateTime, ForeignKey
from datetime import datetime
from utils.timezone import pst_now_naive

class Enrollment(db.Model):
    __tablename__ = 'Enrolled'
    
    id = Column('EnrollmentID', Integer, primary_key=True)
    student_id = Column('StudentID', db.String(20), ForeignKey('Student.StudentID'), nullable=False)
    class_id = Column('ClassID', Integer, ForeignKey('Class.ClassID'), nullable=False)
    school_year = Column('SchoolYear', db.String(9), nullable=True)
    term = Column('Term', db.String(20), nullable=True)
    created_at = Column(DateTime, default=pst_now_naive)
    
    # Relationships
    student = db.relationship('Student', back_populates='enrollments')
    class_record = db.relationship('Class', backref='enrollments')

    @property
    def enrolled_date(self):
        """Backward-compatible alias used throughout the codebase."""
        return self.created_at

    @enrolled_date.setter
    def enrolled_date(self, value):
        self.created_at = value

    @property
    def enrollment_id(self):
        return self.id
