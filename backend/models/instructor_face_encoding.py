from extensions import db
from sqlalchemy import Column, Integer, String, LargeBinary, ForeignKey, DateTime
from datetime import datetime
from utils.timezone import pst_now_naive

class InstructorFaceEncoding(db.Model):
    __tablename__ = 'instructor_face_encodings'
    id = Column(Integer, primary_key=True)
    instructor_id = Column(Integer, ForeignKey('Instructor.InstructorID'), nullable=False)
    encoding = Column(LargeBinary, nullable=False)
    image_path = Column(String(255))
    created_at = Column(DateTime, default=pst_now_naive)

    def __init__(self, instructor_id, encoding=None, image_path=None, created_at=None):
        self.instructor_id = instructor_id
        self.encoding = encoding if encoding is not None else bytes([0] * 128)
        self.image_path = image_path
        self.created_at = created_at or pst_now_naive()

    def __repr__(self):
        return f'<InstructorFaceEncoding {self.id} for instructor {self.instructor_id}>' 
