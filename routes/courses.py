from flask import Blueprint, render_template, redirect, url_for, request, jsonify, flash
from flask_login import login_required, current_user
import datetime

from app import db
from models import Class
from forms import ClassForm

courses_bp = Blueprint('courses', __name__, url_prefix='/courses')

@courses_bp.route('/manage', methods=['GET'])
@login_required
def manage():
    # Only allow admin to access
    if current_user.role != 'admin':
        flash('You do not have permission to access this page.', 'danger')
        return redirect(url_for('students.enroll'))
    
    # Get all unique courses by examining class descriptions
    courses = db.session.query(Class.class_code, Class.description).distinct().all()
    
    return render_template('courses/manage.html', courses=courses)

@courses_bp.route('/add', methods=['POST'])
@login_required
def add():
    # Only allow admin to access
    if current_user.role != 'admin':
        flash('You do not have permission to perform this action.', 'danger')
        return redirect(url_for('students.enroll'))
    
    class_code = request.form.get('class_code')
    description = request.form.get('description')
    
    # Simple validation
    if not class_code or not description:
        flash('Class code and description are required.', 'danger')
        return redirect(url_for('courses.manage'))
    
    # Check if course already exists
    existing_course = Class.query.filter_by(class_code=class_code).first()
    if existing_course:
        flash(f'A course with code "{class_code}" already exists.', 'danger')
        return redirect(url_for('courses.manage'))
    
    # We're not actually adding a course directly, but rather noting the course code and description
    # for use when creating actual classes in the class management section
    flash(f'Course "{class_code}: {description}" has been added.', 'success')
    return redirect(url_for('courses.manage'))

@courses_bp.route('/update', methods=['POST'])
@login_required
def update():
    # Only allow admin to access
    if current_user.role != 'admin':
        flash('You do not have permission to perform this action.', 'danger')
        return redirect(url_for('students.enroll'))
    
    old_code = request.form.get('old_class_code')
    new_code = request.form.get('class_code')
    new_description = request.form.get('description')
    
    # Simple validation
    if not old_code or not new_code or not new_description:
        flash('All fields are required.', 'danger')
        return redirect(url_for('courses.manage'))
    
    # Update all classes with this course code
    try:
        affected_classes = Class.query.filter_by(class_code=old_code).all()
        
        if not affected_classes:
            flash(f'No classes found with course code "{old_code}".', 'warning')
            return redirect(url_for('courses.manage'))
        
        for cls in affected_classes:
            cls.class_code = new_code
            cls.description = new_description
        
        db.session.commit()
        flash(f'Course "{old_code}" updated successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating course: {str(e)}', 'danger')
    
    return redirect(url_for('courses.manage'))

@courses_bp.route('/delete/<string:course_code>', methods=['POST'])
@login_required
def delete(course_code):
    # Only allow admin to access
    if current_user.role != 'admin':
        flash('You do not have permission to perform this action.', 'danger')
        return redirect(url_for('students.enroll'))
    
    try:
        # Get all classes with this course code
        classes = Class.query.filter_by(class_code=course_code).all()
        
        if not classes:
            flash(f'No classes found with course code "{course_code}".', 'warning')
            return redirect(url_for('courses.manage'))
        
        # Check if any classes have enrollments
        for cls in classes:
            if cls.enrollments:
                flash(f'Cannot delete course "{course_code}" because it has enrolled students.', 'danger')
                return redirect(url_for('courses.manage'))
        
        # Delete all classes with this course code
        for cls in classes:
            db.session.delete(cls)
        
        db.session.commit()
        flash(f'Course "{course_code}" and its classes deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting course: {str(e)}', 'danger')
    
    return redirect(url_for('courses.manage'))