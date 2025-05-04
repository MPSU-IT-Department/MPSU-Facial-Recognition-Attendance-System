from flask import Blueprint, render_template, redirect, url_for, request, jsonify, flash
from flask_login import login_required, current_user
import datetime
import json

from app import db
from models import Student, Class, Enrollment, FaceEncoding
from forms import StudentForm, EnrollmentForm

students_bp = Blueprint('students', __name__, url_prefix='/students')

@students_bp.route('/enroll', methods=['GET'])
@login_required
def enroll():
    form = StudentForm()
    return render_template('students/enroll.html', form=form)

@students_bp.route('/api/list', methods=['GET'])
@login_required
def get_students():
    students = Student.query.all()
    
    # Convert to dictionary
    student_list = []
    for student in students:
        # Get enrolled classes for each student
        enrolled_classes = [enrollment.class_id for enrollment in student.enrollments]
        
        student_list.append({
            'id': student.id,
            'firstName': student.first_name,
            'lastName': student.last_name,
            'yearLevel': student.year_level,
            'phone': student.phone,
            'email': student.email or '',
            'enrolledClasses': enrolled_classes
        })
    
    return jsonify(student_list)

@students_bp.route('/api/create', methods=['POST'])
@login_required
def create_student():
    data = request.get_json()
    
    # Validate data
    if not data or not all(key in data for key in ['firstName', 'lastName', 'id', 'yearLevel', 'phone']):
        return jsonify({'success': False, 'message': 'Missing required student data'}), 400
    
    # Check if student ID already exists
    existing_student = Student.query.get(data['id'])
    if existing_student:
        return jsonify({'success': False, 'message': 'Student ID already exists'}), 400
    
    # Create new student
    student = Student(
        id=data['id'],
        first_name=data['firstName'],
        last_name=data['lastName'],
        year_level=data['yearLevel'],
        phone=data['phone'],
        email=data.get('email', None)
    )
    
    try:
        db.session.add(student)
        db.session.commit()
        return jsonify({
            'success': True, 
            'message': 'Student created successfully',
            'student': {
                'id': student.id,
                'firstName': student.first_name,
                'lastName': student.last_name,
                'yearLevel': student.year_level,
                'phone': student.phone,
                'email': student.email or '',
                'enrolledClasses': []
            }
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

@students_bp.route('/api/update/<string:student_id>', methods=['PUT'])
@login_required
def update_student(student_id):
    student = Student.query.get(student_id)
    
    if not student:
        return jsonify({'success': False, 'message': 'Student not found'}), 404
    
    data = request.get_json()
    
    # Update student info
    student.first_name = data.get('firstName', student.first_name)
    student.last_name = data.get('lastName', student.last_name)
    student.year_level = data.get('yearLevel', student.year_level)
    student.phone = data.get('phone', student.phone)
    student.email = data.get('email', student.email)
    
    try:
        db.session.commit()
        return jsonify({'success': True, 'message': 'Student updated successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

@students_bp.route('/api/delete/<string:student_id>', methods=['DELETE'])
@login_required
def delete_student(student_id):
    student = Student.query.get(student_id)
    
    if not student:
        return jsonify({'success': False, 'message': 'Student not found'}), 404
    
    try:
        # This will cascade delete enrollments and face encodings
        db.session.delete(student)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Student deleted successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

@students_bp.route('/api/face-encodings/<string:student_id>', methods=['POST'])
@login_required
def save_face_encodings(student_id):
    student = Student.query.get(student_id)
    
    if not student:
        return jsonify({'success': False, 'message': 'Student not found'}), 404
    
    data = request.get_json()
    
    if not data or 'encodings' not in data:
        return jsonify({'success': False, 'message': 'No encoding data provided'}), 400
    
    try:
        # First, delete any existing encodings for this student
        FaceEncoding.query.filter_by(student_id=student_id).delete()
        
        # Save the new encodings
        for encoding_data in data['encodings']:
            encoding = FaceEncoding(
                student_id=student_id,
                encoding_data=encoding_data.encode('utf-8'),  # Convert string to bytes
                created_at=datetime.datetime.utcnow()
            )
            db.session.add(encoding)
        
        db.session.commit()
        return jsonify({'success': True, 'message': 'Face encodings saved successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

@students_bp.route('/api/generate-id', methods=['GET'])
@login_required
def generate_student_id():
    # Get the current year's last two digits
    year = datetime.datetime.now().year % 100
    
    # Find the highest student ID for the current year
    current_year_pattern = f"{year}-"
    max_id = 0
    
    students = Student.query.filter(Student.id.like(f"{current_year_pattern}%")).all()
    for student in students:
        try:
            id_number = int(student.id.split('-')[1])
            if id_number > max_id:
                max_id = id_number
        except (IndexError, ValueError):
            pass
    
    # Generate the next ID
    next_id = f"{year}-{(max_id + 1):05d}"
    
    return jsonify({'success': True, 'id': next_id})
