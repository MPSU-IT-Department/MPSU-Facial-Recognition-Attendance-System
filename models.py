import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app import db

# Define the User model for authentication
class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    first_name = db.Column(db.String(64), nullable=False)
    last_name = db.Column(db.String(64), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='instructor')  # 'admin' or 'instructor'
    profile_picture = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    
    # Relationship with classes
    classes = db.relationship('Class', backref='instructor', lazy=True)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def __repr__(self):
        return f'<User {self.username}>'

# Student model
class Student(db.Model):
    __tablename__ = 'students'
    
    id = db.Column(db.String(20), primary_key=True)  # Format YY-XXXXX
    first_name = db.Column(db.String(64), nullable=False)
    last_name = db.Column(db.String(64), nullable=False)
    year_level = db.Column(db.String(20), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    email = db.Column(db.String(120), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    
    # Relationships
    enrollments = db.relationship('Enrollment', backref='student', lazy=True, cascade="all, delete-orphan")
    face_encodings = db.relationship('FaceEncoding', backref='student', lazy=True, cascade="all, delete-orphan")
    
    def __repr__(self):
        return f'<Student {self.id}: {self.first_name} {self.last_name}>'

# Class model
class Class(db.Model):
    __tablename__ = 'classes'
    
    id = db.Column(db.Integer, primary_key=True)
    class_code = db.Column(db.String(20), unique=True, nullable=False)
    description = db.Column(db.String(255), nullable=False)
    room_number = db.Column(db.String(20), nullable=False)
    schedule = db.Column(db.String(100), nullable=False)
    instructor_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    
    # Relationships
    enrollments = db.relationship('Enrollment', backref='class_ref', lazy=True, cascade="all, delete-orphan")
    attendance_records = db.relationship('AttendanceRecord', backref='class_ref', lazy=True, cascade="all, delete-orphan")
    
    def __repr__(self):
        return f'<Class {self.class_code}: {self.description}>'

# Enrollment model - Join table for students and classes
class Enrollment(db.Model):
    __tablename__ = 'enrollments'
    
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.String(20), db.ForeignKey('students.id'), nullable=False)
    class_id = db.Column(db.Integer, db.ForeignKey('classes.id'), nullable=False)
    enrolled_date = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    
    __table_args__ = (
        db.UniqueConstraint('student_id', 'class_id', name='unique_student_class'),
    )
    
    def __repr__(self):
        return f'<Enrollment {self.student_id} in class {self.class_id}>'

# Attendance Record model
class AttendanceRecord(db.Model):
    __tablename__ = 'attendance_records'
    
    id = db.Column(db.Integer, primary_key=True)
    class_id = db.Column(db.Integer, db.ForeignKey('classes.id'), nullable=False)
    student_id = db.Column(db.String(20), db.ForeignKey('students.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), nullable=False)  # 'Present', 'Absent', 'Late'
    marked_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)  # NULL if marked by facial recognition
    marked_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    
    # Define a relationship with the user who marked attendance
    marker = db.relationship('User', backref='marked_attendances')
    # Relationship with student
    student = db.relationship('Student', backref='attendance_records')
    
    __table_args__ = (
        db.UniqueConstraint('class_id', 'student_id', 'date', name='unique_attendance_record'),
    )
    
    def __repr__(self):
        return f'<Attendance {self.student_id} in class {self.class_id} on {self.date}: {self.status}>'

# Face Encoding model - For facial recognition
class FaceEncoding(db.Model):
    __tablename__ = 'face_encodings'
    
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.String(20), db.ForeignKey('students.id'), nullable=False)
    encoding_data = db.Column(db.LargeBinary, nullable=False)  # Store face encoding data
    image_path = db.Column(db.String(255), nullable=True)  # Reference to image file path
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    
    def __repr__(self):
        return f'<FaceEncoding for student {self.student_id}>'
