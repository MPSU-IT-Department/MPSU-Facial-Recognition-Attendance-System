from extensions import db
from .user import User
from .student import Student
from .class_model import Class
from .enrollment import Enrollment
from .face_encoding import FaceEncoding
from .class_session import ClassSession
from .instructor_attendance import InstructorAttendance
from .attendance_record import AttendanceRecord
from .instructor_face_encoding import InstructorFaceEncoding
from .course import Course
from .attendance_log import AttendanceLog
from .attendance_status import AttendanceStatus
from .system_settings import SystemSettings
Instructor = User
Enrolled = Enrollment
StudentAttendance = AttendanceRecord

__all__ = [
    'db',
    'User',
    'Instructor',
    'Enrolled',
    'StudentAttendance',
    'Student',
    'Class',
    'Enrollment',
    'FaceEncoding',
    'ClassSession',
    'InstructorAttendance',
    'AttendanceRecord',
    'InstructorFaceEncoding',
    'Course',
    'AttendanceLog',
    'AttendanceStatus',
    'SystemSettings'
] 
