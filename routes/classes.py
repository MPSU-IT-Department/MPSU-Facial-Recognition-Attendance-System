from flask import Blueprint, render_template, redirect, url_for, request, jsonify, flash, current_app
from flask_login import login_required, current_user
import datetime
import json

from app import db, app
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

@classes_bp.route('/debug-info', methods=['GET'])
@login_required
def debug_info():
    """Debug endpoint to return information about the system state."""
    try:
        from flask import session as flask_session
        import sys
        import platform
        import flask
        
        # Get database info
        db_uri = app.config.get('SQLALCHEMY_DATABASE_URI', 'Not configured')
        db_uri_safe = db_uri.split('@')[0] + '@' + db_uri.split('@')[1].split('/')[0] + '/****' if '@' in db_uri else db_uri
        
        user_info = {
            'id': current_user.id if current_user else None,
            'username': current_user.username if current_user else None,
            'role': current_user.role if current_user else None,
            'authenticated': current_user.is_authenticated if current_user else False
        }
        
        # Count records in database
        class_count = Class.query.count()
        user_count = User.query.count()
        student_count = Student.query.count()
        enrollment_count = Enrollment.query.count()
        
        debug_info = {
            'timestamp': datetime.datetime.utcnow().isoformat(),
            'python_version': sys.version,
            'platform': platform.platform(),
            'flask_version': flask.__version__,
            'session_keys': list(flask_session.keys()),
            'current_user': user_info,
            'database': {
                'uri': db_uri_safe,
                'class_count': class_count,
                'user_count': user_count,
                'student_count': student_count,
                'enrollment_count': enrollment_count
            }
        }
        
        return jsonify(debug_info)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@classes_bp.route('/api/list', methods=['GET'])
@login_required
def get_classes():
    try:
        print("Fetching classes from database...")
        print(f"User: {current_user.username}, Role: {current_user.role}")
        
        classes = Class.query.all()
        print(f"Found {len(classes)} classes")
        
        # Convert to dictionary
        class_list = []
        for cls in classes:
            try:
                # Get the instructor name
                instructor = User.query.get(cls.instructor_id)
                if instructor:
                    instructor_name = f"{instructor.first_name} {instructor.last_name}"
                else:
                    print(f"Warning: No instructor found for ID {cls.instructor_id}")
                    instructor_name = "Unknown"
                
                # Count enrolled students
                enrolled_count = Enrollment.query.filter_by(class_id=cls.id).count()
                
                class_data = {
                    'id': cls.id,
                    'classCode': cls.class_code,
                    'description': cls.description,
                    'roomNumber': cls.room_number,
                    'schedule': cls.schedule,
                    'instructorId': cls.instructor_id,
                    'instructorName': instructor_name,
                    'enrolledCount': enrolled_count
                }
                
                class_list.append(class_data)
                print(f"Processed class: {cls.class_code}")
                
            except Exception as e:
                print(f"Error processing class {cls.id}: {str(e)}")
                # Continue with the next class rather than failing completely
        
        print(f"Returning {len(class_list)} classes in response")
        return jsonify(class_list)
    except Exception as e:
        import traceback
        print(f"Error in get_classes API: {str(e)}")
        print(traceback.format_exc())
        return jsonify({"error": str(e)}), 500

@classes_bp.route('/api/create', methods=['POST'])
@login_required
def create_class():
    data = request.get_json()
    print(f"Received class creation data: {data}")
    
    # Validate data
    if not data or not all(key in data for key in ['classCode', 'description', 'roomNumber', 'schedule', 'instructorId']):
        missing_keys = [key for key in ['classCode', 'description', 'roomNumber', 'schedule', 'instructorId'] if key not in data]
        print(f"Missing required class data: {missing_keys}")
        return jsonify({'success': False, 'message': f'Missing required class data: {", ".join(missing_keys)}'}), 400
    
    # Check if class code already exists
    existing_class = Class.query.filter_by(class_code=data['classCode']).first()
    if existing_class:
        print(f"Class code already exists: {data['classCode']}")
        return jsonify({'success': False, 'message': 'Class code already exists'}), 400
    
    # Log schedule value
    print(f"Schedule value for new class: '{data['schedule']}'")
    
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
        print(f"Class not found with ID: {class_id}")
        return jsonify({'success': False, 'message': 'Class not found'}), 404
    
    data = request.get_json()
    print(f"Received update data for class {class_id}: {data}")
    
    # Get current schedule before updating
    current_schedule = cls.schedule if cls.schedule else "None"
    print(f"Current schedule before update: '{current_schedule}'")
    
    # Update class info
    if 'classCode' in data and data['classCode'] != cls.class_code:
        # Check if new class code already exists
        existing_class = Class.query.filter_by(class_code=data['classCode']).first()
        if existing_class and existing_class.id != class_id:
            print(f"Class code already exists: {data['classCode']}")
            return jsonify({'success': False, 'message': 'Class code already exists'}), 400
        print(f"Updating class code from {cls.class_code} to {data['classCode']}")
        cls.class_code = data['classCode']
    
    if 'description' in data:
        print(f"Updating description from '{cls.description}' to '{data['description']}'")
    cls.description = data.get('description', cls.description)
    
    if 'roomNumber' in data:
        print(f"Updating room number from '{cls.room_number}' to '{data['roomNumber']}'")
    cls.room_number = data.get('roomNumber', cls.room_number)
    
    if 'schedule' in data:
        print(f"Updating schedule from '{cls.schedule}' to '{data['schedule']}'")
    cls.schedule = data.get('schedule', cls.schedule)
    
    if 'instructorId' in data:
        print(f"Updating instructor ID from {cls.instructor_id} to {data['instructorId']}")
    cls.instructor_id = data.get('instructorId', cls.instructor_id)
    
    try:
        db.session.commit()
        
        # Get the updated instructor information
        instructor = User.query.get(cls.instructor_id)
        instructor_name = f"{instructor.first_name} {instructor.last_name}" if instructor else "Unknown"
        
        # Count enrolled students
        enrolled_count = Enrollment.query.filter_by(class_id=cls.id).count()
        
        return jsonify({
            'success': True, 
            'message': 'Class updated successfully',
            'class': {
                'id': cls.id,
                'classCode': cls.class_code,
                'description': cls.description,
                'roomNumber': cls.room_number,
                'schedule': cls.schedule,
                'instructorId': cls.instructor_id,
                'instructorName': instructor_name,
                'enrolledCount': enrolled_count
            }
        })
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
    # Restrict access to instructors only
    if current_user.role != 'instructor':
        return jsonify({'success': False, 'message': 'Only instructors can enroll students'}), 403
    
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

@classes_bp.route('/api/<int:class_id>/unenroll/<int:enrollment_id>', methods=['DELETE'])
@login_required
def unenroll_student_by_enrollment(class_id, enrollment_id):
    # Restrict access to instructors only
    if current_user.role != 'instructor':
        return jsonify({'success': False, 'message': 'Only instructors can unenroll students'}), 403
    
    # Check if class exists
    cls = Class.query.get(class_id)
    if not cls:
        return jsonify({'success': False, 'message': 'Class not found'}), 404
    
    # Check if enrollment exists
    enrollment = Enrollment.query.get(enrollment_id)
    if not enrollment:
        return jsonify({'success': False, 'message': 'Enrollment record not found'}), 404
    
    # Verify the enrollment belongs to the specified class
    if enrollment.class_id != class_id:
        return jsonify({'success': False, 'message': 'Enrollment does not belong to this class'}), 400
    
    # Save student info before deletion for response
    student = Student.query.get(enrollment.student_id)
    student_info = {
        'id': student.id,
        'firstName': student.first_name,
        'lastName': student.last_name
    }
    
    try:
        # Delete enrollment (cascade will delete attendance records)
        db.session.delete(enrollment)
        db.session.commit()
        return jsonify({
            'success': True, 
            'message': f'Student {student_info["firstName"]} {student_info["lastName"]} unenrolled successfully'
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

@classes_bp.route('/api/<int:class_id>/unenroll/<string:student_id>', methods=['DELETE'])
@login_required
def unenroll_student_by_id(class_id, student_id):
    # Restrict access to instructors only
    if current_user.role != 'instructor':
        return jsonify({'success': False, 'message': 'Only instructors can unenroll students'}), 403
    
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
