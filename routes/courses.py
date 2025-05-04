from flask import Blueprint, render_template, redirect, url_for, request, jsonify, flash, session
from flask_login import login_required, current_user
import datetime

from app import db
from models import Class
from forms import ClassForm

courses_bp = Blueprint('courses', __name__, url_prefix='/courses')

@courses_bp.route('/api/list', methods=['GET'])
@login_required
def get_courses():
    """API endpoint to get all unique courses"""
    # Get courses from database
    db_courses = db.session.query(Class.class_code, Class.description).distinct().all()
    course_list = [{'code': code, 'description': desc} for code, desc in db_courses]
    
    # Add courses from session if they don't exist in the database yet
    if 'courses' in session:
        for code, course_data in session['courses'].items():
            # Only add if not already in our result list
            if not any(c['code'] == code for c in course_list):
                course_list.append({
                    'code': course_data['code'],
                    'description': course_data['description']
                })
    
    return jsonify(course_list)

@courses_bp.route('/manage', methods=['GET'])
@login_required
def manage():
    # Only allow admin to access
    if current_user.role != 'admin':
        flash('You do not have permission to access this page.', 'danger')
        return redirect(url_for('students.enroll'))
    
    # Get all unique courses from database
    db_courses = db.session.query(Class.class_code, Class.description).distinct().all()
    courses = list(db_courses)  # Convert to list for appending
    
    # Add courses from session if they don't exist in the database yet
    if 'courses' in session:
        existing_codes = {code for code, _ in courses}
        for code, course_data in session['courses'].items():
            if code not in existing_codes:
                courses.append((code, course_data['description']))
    
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
    
    try:
        # Store course info in session for use when creating a class
        # This avoids creating a Class entry prematurely
        if 'courses' not in session:
            session['courses'] = {}
        
        session['courses'][class_code] = {
            'code': class_code,
            'description': description
        }
        
        flash(f'Course "{class_code}: {description}" has been added.', 'success')
    except Exception as e:
        flash(f'Error adding course: {str(e)}', 'danger')
    
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
        # Check if this course exists in the session
        if 'courses' in session and course_code in session['courses']:
            # Simply remove from session
            del session['courses'][course_code]
            flash(f'Course "{course_code}" removed successfully!', 'success')
            return redirect(url_for('courses.manage'))
        
        # If not in session, look for it in the database
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