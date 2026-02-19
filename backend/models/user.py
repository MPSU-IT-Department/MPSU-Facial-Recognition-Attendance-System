from extensions import db
from flask_login import UserMixin
from sqlalchemy import Column, Integer, String, DateTime, LargeBinary, event
from datetime import datetime
from utils.timezone import pst_now_naive

class User(UserMixin, db.Model):
    __tablename__ = 'Instructor'
    
    id = Column('InstructorID', Integer, primary_key=True) #must be unique numeric
    username = Column(String(80), unique=True, nullable=False)
    email = Column(String(120), unique=True, nullable=True)
    password_hash = Column(String(256))
    first_name = Column('FirstName', String(50))
    middle_name = Column('MiddleName', String(50), nullable=True)
    last_name = Column('LastName', String(50))
    role = Column(String(20), nullable=False)  # 'admin', 'instructor', 'student'
    department = Column('Department', String(50), nullable=True)  # Department for instructors (IT, CRIM, etc.)
    school_year = Column('SchoolYear', String(9), nullable=True)
    term = Column('Term', String(20), nullable=True)
    face_encoding = Column('FaceEncoding', LargeBinary, nullable=True)
    image_path = Column('ImagePath', String(255), nullable=True)
    profile_picture = Column(String(255), nullable=True)  # Path to profile picture
    created_at = Column(DateTime, default=pst_now_naive)
    
    def set_password(self, password):
        self.password_hash = password  # Store plaintext password
        
    def check_password(self, password):
        return self.password_hash == password  # Direct comparison for plaintext

    @property
    def instructor_id(self):
        return self.id


@event.listens_for(User, 'before_insert')
@event.listens_for(User, 'before_update')
def sync_user_image_fields(mapper, connection, target):
    if not target.image_path and target.profile_picture:
        target.image_path = target.profile_picture
    elif not target.profile_picture and target.image_path:
        target.profile_picture = target.image_path
