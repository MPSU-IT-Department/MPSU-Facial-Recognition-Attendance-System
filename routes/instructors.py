from flask import Blueprint, render_template, redirect, url_for, request, jsonify, flash
from flask_login import login_required, current_user
import datetime

from app import db
from models import User
from forms import RegisterForm

instructors_bp = Blueprint('instructors', __name__, url_prefix='/instructors')

@instructors_bp.route('/manage', methods=['GET'])
@login_required
def manage():
    # Only allow admin to access
    if current_user.role != 'admin':
        flash('You do not have permission to access this page.', 'danger')
        return redirect(url_for('students.enroll'))
        
    instructors = User.query.filter_by(role='instructor').all()
    form = RegisterForm()
    # Default to instructor role
    form.role.default = 'instructor'
    form.process()
    
    return render_template('instructors/manage.html', instructors=instructors, form=form)

@instructors_bp.route('/add', methods=['POST'])
@login_required
def add():
    # Only allow admin to access
    if current_user.role != 'admin':
        flash('You do not have permission to perform this action.', 'danger')
        return redirect(url_for('students.enroll'))
        
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

@instructors_bp.route('/delete/<int:instructor_id>', methods=['POST'])
@login_required
def delete(instructor_id):
    # Only allow admin to access
    if current_user.role != 'admin':
        flash('You do not have permission to perform this action.', 'danger')
        return redirect(url_for('students.enroll'))
        
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