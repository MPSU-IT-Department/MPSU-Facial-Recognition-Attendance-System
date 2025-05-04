from flask import Blueprint, render_template, redirect, url_for, request, jsonify, flash
from flask_login import login_required, current_user
import datetime
from sqlalchemy.orm import joinedload

from app import db
from models import User, Class, Student, Enrollment
from forms import RegisterForm

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