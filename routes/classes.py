from flask import Blueprint, render_template, redirect, url_for, request, jsonify, flash
from flask_login import login_required, current_user
import datetime

from app import db
from models import Class, User, Student, Enrollment
from forms import ClassForm, EnrollmentForm

classes_bp = Blueprint('classes', __name__, url_prefix='/classes')

@classes_bp.route('/schedule', methods=['GET'])
@login_required
def schedule():
    form = ClassForm()
    
    # Get all instructors for the dropdown
    instructors = User.query.filter_by(role='instructor').all()
    form.instructor_id.choices = [(i.id, f"{i.first_name} {i.last_name}") for i in instructors]
    
    return render_template('classes/schedule.html', form=form)

@classes_bp.route('/api/list', methods=['GET'])
@login_required
def get_classes():
    classes = Class.query.all()
    
    # Convert to dictionary
    class_list = []
    for cls in classes:
        # Get the instructor name
        instructor = User.query.get(cls.instructor_id)
        instructor_name = f"{instructor.first_name} {instructor.last_name}" if instructor else "Unknown"
        
        # Count enrolled students
        enrolled_count = Enrollment.query.filter_by(class_id=cls.id).count()
        
        class_list.append({
            'id': cls.id,
            'classCode': cls.class_code,
            'description': cls.description,
            'roomNumber': cls.room_number,
            'schedule': cls.schedule,
            'instructorId': cls.instructor_id,
            'instructorName': instructor_name,
            'enrolledCount': enrolled_count
        })
    
    return jsonify(class_list)

@classes_bp.route('/api/create', methods=['POST'])
@login_required
def create_class():
    data = request.get_json()
    
    # Validate data
    if not data or not all(key in data for key in ['classCode', 'description', 'roomNumber', 'schedule', 'instructorId']):
        return jsonify({'success': False, 'message': 'Missing required class data'}), 400
    
    # Check if class code already exists
    existing_class = Class.query.filter_by(class_code=data['classCode']).first()
    if existing_class:
        return jsonify({'success': False, 'message': 'Class code already exists'}), 400
    
    # Create new class
    new_class = Class(
        class_code=data['classCode'],
        description=data['description'],
        room_number=data['roomNumber'],
        schedule=data['schedule'],
        instructor_id=data['instructorId'],
        created_at=datetime.datetime.utcnow()
    )
    
    try:
        db.session.add(new_class)
        db.session.commit()
        
        # Get instructor info
        instructor = User.query.get(new_class.instructor_id)
        instructor_name = f"{instructor.first_name} {instructor.last_name}" if instructor else "Unknown"
        
        return jsonify({
            'success': True, 
            'message': 'Class created successfully',
            'class': {
                'id': new_class.id,
                'classCode': new_class.class_code,
                'description': new_class.description,
                'roomNumber': new_class.room_number,
                'schedule': new_class.schedule,
                'instructorId': new_class.instructor_id,
                'instructorName': instructor_name,
                'enrolledCount': 0
            }
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

@classes_bp.route('/api/update/<int:class_id>', methods=['PUT'])
@login_required
def update_class(class_id):
    cls = Class.query.get(class_id)
    
    if not cls:
        return jsonify({'success': False, 'message': 'Class not found'}), 404
    
    data = request.get_json()
    
    # Update class info
    if 'classCode' in data and data['classCode'] != cls.class_code:
        # Check if new class code already exists
        existing_class = Class.query.filter_by(class_code=data['classCode']).first()
        if existing_class and existing_class.id != class_id:
            return jsonify({'success': False, 'message': 'Class code already exists'}), 400
        cls.class_code = data['classCode']
    
    cls.description = data.get('description', cls.description)
    cls.room_number = data.get('roomNumber', cls.room_number)
    cls.schedule = data.get('schedule', cls.schedule)
    cls.instructor_id = data.get('instructorId', cls.instructor_id)
    
    try:
        db.session.commit()
        return jsonify({'success': True, 'message': 'Class updated successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

@classes_bp.route('/api/delete/<int:class_id>', methods=['DELETE'])
@login_required
def delete_class(class_id):
    cls = Class.query.get(class_id)
    
    if not cls:
        return jsonify({'success': False, 'message': 'Class not found'}), 404
    
    try:
        # This will cascade delete enrollments and attendance records
        db.session.delete(cls)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Class deleted successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

@classes_bp.route('/api/<int:class_id>/students', methods=['GET'])
@login_required
def get_class_students(class_id):
    # Check if class exists
    cls = Class.query.get(class_id)
    if not cls:
        return jsonify({'success': False, 'message': 'Class not found'}), 404
    
    # Get all students enrolled in this class
    enrollments = Enrollment.query.filter_by(class_id=class_id).all()
    
    student_list = []
    for enrollment in enrollments:
        student = Student.query.get(enrollment.student_id)
        if student:
            student_list.append({
                'id': student.id,
                'firstName': student.first_name,
                'lastName': student.last_name,
                'yearLevel': student.year_level,
                'phone': student.phone,
                'email': student.email or '',
                'enrollmentId': enrollment.id,
                'enrollmentDate': enrollment.enrolled_date.strftime('%Y-%m-%d')
            })
    
    return jsonify(student_list)

@classes_bp.route('/api/<int:class_id>/enroll', methods=['POST'])
@login_required
def enroll_student(class_id):
    # Check if class exists
    cls = Class.query.get(class_id)
    if not cls:
        return jsonify({'success': False, 'message': 'Class not found'}), 404
    
    data = request.get_json()
    
    if not data or 'studentId' not in data:
        return jsonify({'success': False, 'message': 'Missing student ID'}), 400
    
    # Check if student exists
    student = Student.query.get(data['studentId'])
    if not student:
        return jsonify({'success': False, 'message': 'Student not found'}), 404
    
    # Check if student is already enrolled
    existing_enrollment = Enrollment.query.filter_by(
        class_id=class_id, 
        student_id=data['studentId']
    ).first()
    
    if existing_enrollment:
        return jsonify({'success': False, 'message': 'Student already enrolled in this class'}), 400
    
    # Create new enrollment
    enrollment = Enrollment(
        student_id=data['studentId'],
        class_id=class_id,
        enrolled_date=datetime.datetime.utcnow()
    )
    
    try:
        db.session.add(enrollment)
        db.session.commit()
        return jsonify({
            'success': True, 
            'message': 'Student enrolled successfully',
            'student': {
                'id': student.id,
                'firstName': student.first_name,
                'lastName': student.last_name,
                'yearLevel': student.year_level,
                'phone': student.phone,
                'email': student.email or '',
                'enrollmentId': enrollment.id,
                'enrollmentDate': enrollment.enrolled_date.strftime('%Y-%m-%d')
            }
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

@classes_bp.route('/api/<int:class_id>/unenroll/<string:student_id>', methods=['DELETE'])
@login_required
def unenroll_student(class_id, student_id):
    # Find the enrollment
    enrollment = Enrollment.query.filter_by(
        class_id=class_id, 
        student_id=student_id
    ).first()
    
    if not enrollment:
        return jsonify({'success': False, 'message': 'Student not enrolled in this class'}), 404
    
    try:
        db.session.delete(enrollment)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Student unenrolled successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
