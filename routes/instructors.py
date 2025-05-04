from flask import Blueprint, render_template, redirect, url_for, request, jsonify, flash, current_app
from flask_login import login_required, current_user
import datetime
import os
import uuid
from werkzeug.utils import secure_filename
from sqlalchemy.orm import joinedload

from app import db
from models import User, Class, Student, Enrollment, FaceEncoding, AttendanceRecord
from forms import RegisterForm, StudentForm, EnrollmentForm, ProfilePictureForm

instructors_bp = Blueprint('instructors', __name__, url_prefix='/instructors')

@instructors_bp.route('/manage', methods=['GET'])
@login_required
def manage():
    # Only allow admin to access
    if current_user.role != 'admin':
        flash('You do not have permission to access this page.', 'danger')
        return redirect(url_for('instructors.dashboard'))
        
    instructors = User.query.filter_by(role='instructor').all()
    form = RegisterForm()
    # Default to instructor role
    form.role.default = 'instructor'
    form.process()
    
    return render_template('instructors/manage.html', instructors=instructors, form=form)

@instructors_bp.route('/dashboard', methods=['GET'])
@login_required
def dashboard():
    # Only for instructors
    if current_user.role != 'instructor':
        flash('This page is only accessible to instructors.', 'warning')
        if current_user.role == 'admin':
            return redirect(url_for('instructors.manage'))
        return redirect(url_for('auth.login'))
    
    return render_template('instructors/dashboard.html')

@instructors_bp.route('/api/my-classes', methods=['GET'])
@login_required
def get_my_classes():
    # Only for instructors
    if current_user.role != 'instructor':
        return jsonify([])
    
    # Get all classes assigned to the current instructor
    classes = Class.query.filter_by(instructor_id=current_user.id).all()
    
    class_list = []
    for class_obj in classes:
        # Count enrolled students
        enrolled_count = Enrollment.query.filter_by(class_id=class_obj.id).count()
        
        class_list.append({
            'id': class_obj.id,
            'classCode': class_obj.class_code,
            'description': class_obj.description,
            'roomNumber': class_obj.room_number,
            'schedule': class_obj.schedule,
            'enrolledCount': enrolled_count
        })
    
    return jsonify(class_list)

@instructors_bp.route('/api/my-students', methods=['GET'])
@login_required
def get_my_students():
    # Only for instructors
    if current_user.role != 'instructor':
        return jsonify([])
    
    # Get all classes assigned to the current instructor
    classes = Class.query.filter_by(instructor_id=current_user.id).all()
    class_ids = [class_obj.id for class_obj in classes]
    
    # Get all enrollments for these classes
    enrollments = db.session.query(Enrollment, Student, Class) \
        .join(Student, Enrollment.student_id == Student.id) \
        .join(Class, Enrollment.class_id == Class.id) \
        .filter(Enrollment.class_id.in_(class_ids)) \
        .all()
    
    student_list = []
    for enrollment, student, class_obj in enrollments:
        # Check if the student already exists in the list (enrolled in multiple classes)
        existing_student = next((s for s in student_list if s['id'] == student.id), None)
        
        # Don't add duplicates, just update the class list
        if existing_student:
            existing_student['classNames'].append(class_obj.description)
            continue
        
        # Get profile image if any
        from models import FaceEncoding
        face_encoding = FaceEncoding.query.filter_by(student_id=student.id).first()
        profile_image = face_encoding.image_path if face_encoding else None
        
        student_list.append({
            'id': student.id,
            'firstName': student.first_name,
            'lastName': student.last_name,
            'yearLevel': student.year_level,
            'phone': student.phone,
            'email': student.email or '',
            'className': class_obj.description,
            'classCode': class_obj.class_code,
            'classId': class_obj.id,
            'classNames': [class_obj.description],
            'profileImage': profile_image
        })
    
    return jsonify(student_list)

@instructors_bp.route('/add', methods=['POST'])
@login_required
def add():
    # Only allow admin to access
    if current_user.role != 'admin':
        flash('You do not have permission to perform this action.', 'danger')
        return redirect(url_for('instructors.dashboard'))
        
    form = RegisterForm()
    
    if form.validate_on_submit():
        user = User(
            username=form.username.data,
            email=form.email.data,
            first_name=form.first_name.data,
            last_name=form.last_name.data,
            role='instructor',  # Force role to be instructor
            created_at=datetime.datetime.utcnow()
        )
        user.set_password(form.password.data)
        
        db.session.add(user)
        db.session.commit()
        
        flash('Instructor added successfully!', 'success')
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f'{getattr(form, field).label.text}: {error}', 'danger')
    
    return redirect(url_for('instructors.manage'))

@instructors_bp.route('/update/<int:instructor_id>', methods=['POST'])
@login_required
def update(instructor_id):
    # Only allow admin to access
    if current_user.role != 'admin':
        flash('You do not have permission to perform this action.', 'danger')
        return redirect(url_for('instructors.dashboard'))
        
    instructor = User.query.get_or_404(instructor_id)
    
    # Don't allow editing admin account
    if instructor.role == 'admin' and instructor.id != current_user.id:
        flash('You cannot edit another administrator account.', 'danger')
        return redirect(url_for('instructors.manage'))
    
    # Get form data
    username = request.form.get('username')
    email = request.form.get('email')
    first_name = request.form.get('first_name')
    last_name = request.form.get('last_name')
    password = request.form.get('password')
    
    # Check if username is already taken
    if username != instructor.username and User.query.filter_by(username=username).first():
        flash('Username is already taken.', 'danger')
        return redirect(url_for('instructors.manage'))
    
    # Check if email is already taken
    if email != instructor.email and User.query.filter_by(email=email).first():
        flash('Email is already taken.', 'danger')
        return redirect(url_for('instructors.manage'))
    
    try:
        # Update instructor details
        instructor.username = username
        instructor.email = email
        instructor.first_name = first_name
        instructor.last_name = last_name
        
        # Update password if provided
        if password:
            instructor.set_password(password)
        
        db.session.commit()
        
        flash(f'Instructor "{first_name} {last_name}" updated successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating instructor: {str(e)}', 'danger')
    
    return redirect(url_for('instructors.manage'))

@instructors_bp.route('/delete/<int:instructor_id>', methods=['POST'])
@login_required
def delete(instructor_id):
    # Only allow admin to access
    if current_user.role != 'admin':
        flash('You do not have permission to perform this action.', 'danger')
        return redirect(url_for('instructors.dashboard'))
        
    instructor = User.query.get_or_404(instructor_id)
    
    # Don't allow deleting own account
    if instructor.id == current_user.id:
        flash('You cannot delete your own account.', 'danger')
        return redirect(url_for('instructors.manage'))
    
    # Check if instructor has classes
    if instructor.classes:
        flash('Cannot delete instructor with assigned classes.', 'danger')
        return redirect(url_for('instructors.manage'))
    
    instructor_name = f"{instructor.first_name} {instructor.last_name}"
    
    try:
        db.session.delete(instructor)
        db.session.commit()
        flash(f'Instructor "{instructor_name}" deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting instructor: {str(e)}', 'danger')
    
    return redirect(url_for('instructors.manage'))

# New instructor interface routes based on the provided design

@instructors_bp.route('/enroll_student', methods=['GET'])
@login_required
def enroll_student():
    # Only allow instructors
    if current_user.role != 'instructor':
        flash('You do not have permission to access this page.', 'danger')
        return redirect(url_for('auth.login'))
    
    form = StudentForm()
    return render_template('instructors/enroll_student.html', form=form)

@instructors_bp.route('/class_schedule', methods=['GET'])
@login_required
def class_schedule():
    # Only allow instructors
    if current_user.role != 'instructor':
        flash('You do not have permission to access this page.', 'danger')
        return redirect(url_for('auth.login'))
    
    return render_template('instructors/class_schedule.html')

@instructors_bp.route('/manage_attendance', methods=['GET'])
@login_required
def manage_attendance():
    # Only allow instructors
    if current_user.role != 'instructor':
        flash('You do not have permission to access this page.', 'danger')
        return redirect(url_for('auth.login'))
    
    # Get all classes taught by this instructor
    classes = Class.query.filter_by(instructor_id=current_user.id).all()
    return render_template('instructors/manage_attendance.html', classes=classes)

@instructors_bp.route('/api/class-attendance-overview', methods=['GET'])
@login_required
def get_class_attendance_overview():
    # Only for instructors
    if current_user.role != 'instructor':
        return jsonify([])
    
    # Get current date
    today = datetime.datetime.now().date()
    
    # Get all classes assigned to the current instructor
    classes = Class.query.filter_by(instructor_id=current_user.id).all()
    
    class_list = []
    for class_obj in classes:
        # Count enrolled students
        enrollments = Enrollment.query.filter_by(class_id=class_obj.id).all()
        enrolled_count = len(enrollments)
        
        # Count present students today
        present_count = 0
        for enrollment in enrollments:
            attendance = AttendanceRecord.query.filter_by(
                class_id=class_obj.id,
                student_id=enrollment.student_id,
                date=today,
                status='Present'
            ).first()
            
            if attendance:
                present_count += 1
        
        class_list.append({
            'id': class_obj.id,
            'classCode': class_obj.class_code,
            'description': class_obj.description,
            'schedule': class_obj.schedule,
            'roomNumber': class_obj.room_number,
            'enrolledCount': enrolled_count,
            'presentCount': present_count,
            'date': today.strftime('%B %d %Y')
        })
    
    return jsonify(class_list)

@instructors_bp.route('/api/class-students/<int:class_id>', methods=['GET'])
@login_required
def get_class_students(class_id):
    # Only allow instructors
    if current_user.role != 'instructor':
        return jsonify({'success': False, 'message': 'Unauthorized'})
    
    # Check if class exists and belongs to this instructor
    class_obj = Class.query.filter_by(id=class_id, instructor_id=current_user.id).first()
    if not class_obj:
        return jsonify({'success': False, 'message': 'Class not found or not authorized'})
    
    # Get all students in this class
    enrollments = Enrollment.query.filter_by(class_id=class_id).all()
    
    student_list = []
    for enrollment in enrollments:
        student = Student.query.get(enrollment.student_id)
        if student:
            # Determine attendance status for today
            today = datetime.datetime.now().date()
            attendance = AttendanceRecord.query.filter_by(
                class_id=class_id,
                student_id=student.id,
                date=today
            ).first()
            
            status = attendance.status if attendance else 'Present'  # Default to Present
            
            student_list.append({
                'id': student.id,
                'name': f"{student.first_name} {student.last_name}",
                'yearLevel': student.year_level,
                'phone': student.phone,
                'email': student.email or '',
                'status': status
            })
    
    return jsonify(student_list)

@instructors_bp.route('/api/student-attendance/<string:student_id>/<int:class_id>', methods=['GET'])
@login_required
def get_student_attendance(student_id, class_id):
    # Only allow instructors
    if current_user.role != 'instructor':
        return jsonify({'success': False, 'message': 'Unauthorized'})
    
    # Check if class exists and belongs to this instructor
    class_obj = Class.query.filter_by(id=class_id, instructor_id=current_user.id).first()
    if not class_obj:
        return jsonify({'success': False, 'message': 'Class not found or not authorized'})
    
    # Check if student is enrolled in this class
    enrollment = Enrollment.query.filter_by(class_id=class_id, student_id=student_id).first()
    if not enrollment:
        return jsonify({'success': False, 'message': 'Student not enrolled in this class'})
    
    # Get student details
    student = Student.query.get(student_id)
    if not student:
        return jsonify({'success': False, 'message': 'Student not found'})
    
    # Get attendance records for current month
    today = datetime.datetime.now()
    current_month = today.month
    current_year = today.year
    
    # Get all attendance records for this student in this class
    attendance_records = AttendanceRecord.query.filter(
        AttendanceRecord.class_id == class_id,
        AttendanceRecord.student_id == student_id,
        db.extract('month', AttendanceRecord.date) == current_month,
        db.extract('year', AttendanceRecord.date) == current_year
    ).all()
    
    # Format attendance data
    attendance_data = {record.date.strftime('%B %d %Y'): record.status for record in attendance_records}
    
    # Count present and absent days
    present_count = sum(1 for record in attendance_records if record.status == 'Present')
    absent_count = sum(1 for record in attendance_records if record.status == 'Absent')
    
    return jsonify({
        'student': {
            'id': student.id,
            'name': f"{student.first_name} {student.last_name}",
            'yearLevel': student.year_level
        },
        'class': {
            'id': class_obj.id,
            'code': class_obj.class_code,
            'description': class_obj.description
        },
        'attendance': {
            'month': today.strftime('%B'),
            'year': today.year,
            'presentCount': present_count,
            'absentCount': absent_count,
            'records': attendance_data
        }
    })

# Helper function to check allowed file extensions
def allowed_file(filename):
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Helper function to save an uploaded file
def save_image(file, folder='students'):
    if file and allowed_file(file.filename):
        # Create a unique filename with UUID
        filename = secure_filename(file.filename)
        filename = f"{uuid.uuid4().hex}_{filename}"
        
        # Ensure the upload folder exists
        upload_path = os.path.join(current_app.config['UPLOAD_FOLDER'], folder)
        os.makedirs(upload_path, exist_ok=True)
        
        # Save the file
        file_path = os.path.join(upload_path, filename)
        file.save(file_path)
        
        # Return the relative path for storing in database
        return os.path.join('uploads', folder, filename)
    
    return None

@instructors_bp.route('/api/student-images/<string:student_id>', methods=['GET'])
@login_required
def get_student_images(student_id):
    """Get all facial recognition images for a student"""
    # Access check - instructors can only view students in their classes
    if current_user.role == 'instructor':
        # Check if student is in any of this instructor's classes
        classes = Class.query.filter_by(instructor_id=current_user.id).all()
        class_ids = [class_obj.id for class_obj in classes]
        
        enrollment = Enrollment.query.filter(
            Enrollment.student_id == student_id,
            Enrollment.class_id.in_(class_ids)
        ).first()
        
        if not enrollment:
            return jsonify({'success': False, 'message': 'Student not found in your classes'})
    elif current_user.role != 'admin':
        return jsonify({'success': False, 'message': 'Unauthorized'})
    
    # Get student details
    student = Student.query.get(student_id)
    if not student:
        return jsonify({'success': False, 'message': 'Student not found'})
    
    # Get face encodings
    face_encodings = FaceEncoding.query.filter_by(student_id=student_id).all()
    
    # Format response
    images = []
    for encoding in face_encodings:
        if encoding.image_path:
            images.append({
                'id': encoding.id,
                'url': url_for('static', filename=encoding.image_path.replace('static/', '')),
                'created_at': encoding.created_at.strftime('%Y-%m-%d %H:%M:%S')
            })
    
    return jsonify({
        'success': True,
        'student': {
            'id': student.id,
            'name': f"{student.first_name} {student.last_name}"
        },
        'images': images
    })

@instructors_bp.route('/api/upload-student-image/<string:student_id>', methods=['POST'])
@login_required
def upload_student_image(student_id):
    """Upload a facial recognition image for a student"""
    # Access check - instructors can only upload for students in their classes
    if current_user.role == 'instructor':
        # Check if student is in any of this instructor's classes
        classes = Class.query.filter_by(instructor_id=current_user.id).all()
        class_ids = [class_obj.id for class_obj in classes]
        
        enrollment = Enrollment.query.filter(
            Enrollment.student_id == student_id,
            Enrollment.class_id.in_(class_ids)
        ).first()
        
        if not enrollment:
            return jsonify({'success': False, 'message': 'Student not found in your classes'})
    elif current_user.role != 'admin':
        return jsonify({'success': False, 'message': 'Unauthorized'})
    
    # Check if student exists
    student = Student.query.get(student_id)
    if not student:
        return jsonify({'success': False, 'message': 'Student not found'})
    
    # Check if the post request has the file part
    if 'image' not in request.files:
        return jsonify({'success': False, 'message': 'No file part'})
    
    file = request.files['image']
    
    # If user does not select file, browser may submit an empty file
    if file.filename == '':
        return jsonify({'success': False, 'message': 'No selected file'})
    
    if not allowed_file(file.filename):
        return jsonify({'success': False, 'message': 'File type not allowed. Please upload JPG, JPEG, or PNG files.'})
    
    try:
        # Save the image
        image_path = save_image(file, folder='students')
        
        if not image_path:
            return jsonify({'success': False, 'message': 'Error saving file'})
        
        # Create a new face encoding record
        face_encoding = FaceEncoding(
            student_id=student_id,
            encoding_data=b'',  # Empty bytes, will be processed by facial recognition system later
            image_path=image_path,
            created_at=datetime.datetime.utcnow()
        )
        
        db.session.add(face_encoding)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Image uploaded successfully',
            'image': {
                'id': face_encoding.id,
                'url': url_for('static', filename=image_path.replace('static/', '')),
                'created_at': face_encoding.created_at.strftime('%Y-%m-%d %H:%M:%S')
            }
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Error uploading image: {str(e)}'})

@instructors_bp.route('/api/delete-student-image/<int:image_id>', methods=['POST'])
@login_required
def delete_student_image(image_id):
    """Delete a facial recognition image"""
    # Get the face encoding
    face_encoding = FaceEncoding.query.get(image_id)
    
    if not face_encoding:
        return jsonify({'success': False, 'message': 'Image not found'})
    
    # Access check - instructors can only delete for students in their classes
    if current_user.role == 'instructor':
        # Check if student is in any of this instructor's classes
        classes = Class.query.filter_by(instructor_id=current_user.id).all()
        class_ids = [class_obj.id for class_obj in classes]
        
        enrollment = Enrollment.query.filter(
            Enrollment.student_id == face_encoding.student_id,
            Enrollment.class_id.in_(class_ids)
        ).first()
        
        if not enrollment:
            return jsonify({'success': False, 'message': 'Student not found in your classes'})
    elif current_user.role != 'admin':
        return jsonify({'success': False, 'message': 'Unauthorized'})
    
    try:
        # Delete the file if it exists
        if face_encoding.image_path:
            file_path = os.path.join(current_app.static_folder, face_encoding.image_path.replace('static/', ''))
            if os.path.exists(file_path):
                os.remove(file_path)
        
        # Delete the database record
        db.session.delete(face_encoding)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Image deleted successfully'
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Error deleting image: {str(e)}'})

@instructors_bp.route('/api/update-attendance', methods=['POST'])
@login_required
def update_attendance():
    # Only allow instructors
    if current_user.role != 'instructor':
        return jsonify({'success': False, 'message': 'Unauthorized'})
    
    data = request.get_json()
    if not data or not all(key in data for key in ['classId', 'studentId', 'date', 'status']):
        return jsonify({'success': False, 'message': 'Missing required data'})
    
    # Check if class exists and belongs to this instructor
    class_obj = Class.query.filter_by(id=data['classId'], instructor_id=current_user.id).first()
    if not class_obj:
        return jsonify({'success': False, 'message': 'Class not found or not authorized'})
    
    # Parse date
    try:
        attendance_date = datetime.datetime.strptime(data['date'], '%B %d %Y').date()
    except ValueError:
        try:
            attendance_date = datetime.datetime.strptime(data['date'], '%Y-%m-%d').date()
        except ValueError:
            return jsonify({'success': False, 'message': 'Invalid date format'})
    
    # Check if student is enrolled in this class
    enrollment = Enrollment.query.filter_by(class_id=data['classId'], student_id=data['studentId']).first()
    if not enrollment:
        return jsonify({'success': False, 'message': 'Student not enrolled in this class'})
    
    # Find existing attendance record or create new one
    attendance = AttendanceRecord.query.filter_by(
        class_id=data['classId'],
        student_id=data['studentId'],
        date=attendance_date
    ).first()
    
    if attendance:
        # Update existing record
        attendance.status = data['status']
        attendance.marked_by = current_user.id
        attendance.marked_at = datetime.datetime.utcnow()
    else:
        # Create new record
        attendance = AttendanceRecord(
            class_id=data['classId'],
            student_id=data['studentId'],
            date=attendance_date,
            status=data['status'],
            marked_by=current_user.id,
            marked_at=datetime.datetime.utcnow()
        )
        db.session.add(attendance)
    
    try:
        db.session.commit()
        return jsonify({'success': True, 'message': f'Attendance updated to {data["status"]}'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})