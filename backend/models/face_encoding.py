from extensions import db
from sqlalchemy import Column, Integer, String, LargeBinary, ForeignKey, DateTime, event
from datetime import datetime
from utils.timezone import pst_now_naive

class FaceEncoding(db.Model):
    __tablename__ = 'face_encodings'
    id = Column(Integer, primary_key=True)
    student_id = Column(String(20), ForeignKey('Student.StudentID'), nullable=False)
    encoding_data = Column(LargeBinary, nullable=False, default=lambda: bytes([0] * 128))  # Store facial encoding as bytes with default
    image_path = Column(String(255))  # Optional: path to the reference image
    created_at = Column(DateTime, default=pst_now_naive)  # Add created_at column

    def __init__(self, student_id, encoding_data=None, image_path=None, created_at=None):
        self.student_id = student_id
        self.encoding_data = encoding_data if encoding_data is not None else bytes([0] * 128)
        self.image_path = image_path
        self.created_at = created_at or pst_now_naive()

    def __repr__(self):
        return f'<FaceEncoding {self.id} for student {self.student_id}>'

@event.listens_for(FaceEncoding, 'before_insert')
def ensure_encoding_data(mapper, connection, target):
    if target.encoding_data is None:
        target.encoding_data = bytes([0] * 128) 
