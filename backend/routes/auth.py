from flask import Blueprint, render_template, redirect, url_for, flash, request, session, current_app, jsonify
from flask_login import login_user, logout_user, current_user, login_required
from werkzeug.utils import secure_filename
import datetime
from utils.timezone import pst_now_naive
import os
import uuid
import re
from models import User, Student, Class, Enrollment, AttendanceRecord, FaceEncoding
from forms import LoginForm, RegisterForm, ProfileUpdateForm, ProfilePictureForm
from extensions import db
auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

@auth_bp.route('/', methods=['GET'])
def index():
    if current_user.is_authenticated:
        if current_user.role == 'admin':
            return redirect(url_for('students.enroll'))
        elif current_user.role == 'instructor':
            return redirect(url_for('instructors.attendance'))
    return redirect(url_for('auth.login'))

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        if current_user.role == 'admin':
            return redirect(url_for('students.enroll'))
        elif current_user.role == 'instructor':
            return redirect(url_for('instructors.attendance'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user:
            pass
        if user and user.check_password(form.password.data):
            login_user(user)
            session['user_id'] = user.id
            session['user_name'] = f'{user.first_name} {user.last_name}'
            session['user_role'] = user.role
            next_page = request.args.get('next')
            if next_page:
                return redirect(next_page)
            if user.role == 'admin':
                return redirect(url_for('students.enroll'))
            elif user.role == 'instructor':
                return redirect(url_for('instructors.attendance'))
            else:
                return redirect(url_for('students.enroll'))
        else:
            flash('Invalid username or password', 'danger')
    return render_template('login.html', form=form)

@auth_bp.route('/check-auth', methods=['GET'])
@login_required
def check_auth():
    """
    Endpoint to check if the user is authenticated.
    Used by frontend to verify session validity.
    """
    return jsonify({'authenticated': True, 'user': {'id': current_user.id, 'username': current_user.username, 'role': current_user.role, 'name': f'{current_user.first_name} {current_user.last_name}'}})

@auth_bp.route('/logout', methods=['GET'])
@login_required
def logout():
    logout_user()
    session.clear()
    return redirect(url_for('auth.login'))

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        user = User(username=form.username.data, email=form.email.data, first_name=form.first_name.data, last_name=form.last_name.data, role=form.role.data, created_at=pst_now_naive())
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash('Registration successful! You can now log in.', 'success')
        return redirect(url_for('auth.login'))
    return render_template('login.html', form=form, register=True)

@auth_bp.route('/profile', methods=['GET'])
@login_required
def profile():
    if current_user.profile_picture:
        normalized_path = current_user.profile_picture.replace('\\', '/')
        if 'uploads/uploads/' in normalized_path:
            normalized_path = normalized_path.replace('uploads/uploads/', 'uploads/')
        full_path = os.path.join(current_app.static_folder, normalized_path)
    profile_form = ProfileUpdateForm(first_name=current_user.first_name, last_name=current_user.last_name, email=current_user.email)
    picture_form = ProfilePictureForm()
    return render_template('profile.html', profile_form=profile_form, picture_form=picture_form)

@auth_bp.route('/settings', methods=['GET'])
@login_required
def settings():
    if current_user.role not in ['admin', 'instructor']:
        flash('You do not have permission to access this page.', 'danger')
        return redirect(url_for('auth.login'))
    if current_user.profile_picture:
        normalized_path = current_user.profile_picture.replace('\\', '/')
        if 'uploads/uploads/' in normalized_path:
            normalized_path = normalized_path.replace('uploads/uploads/', 'uploads/')
        full_path = os.path.join(current_app.static_folder, normalized_path)
    profile_form = ProfileUpdateForm(first_name=current_user.first_name, last_name=current_user.last_name, email=current_user.email)
    picture_form = ProfilePictureForm()
    return render_template('settings.html', profile_form=profile_form, picture_form=picture_form)

@auth_bp.route('/profile/update', methods=['POST'])
@login_required
def update_profile():
    if request.is_json:
        data = request.get_json()
        errors = {}
        first_name = data.get('first_name', '').strip()
        last_name = data.get('last_name', '').strip()
        email = data.get('email', '').strip()
        current_password = data.get('current_password', '')
        new_password = data.get('new_password', '')
        confirm_password = data.get('confirm_password', '')
        if not first_name:
            errors['first_name'] = ['First name is required.']
        if not last_name:
            errors['last_name'] = ['Last name is required.']
        if email:
            if not re.match('^[^@]+@[^@]+\\.[^@]+$', email):
                errors['email'] = ['Invalid email address.']
            elif email != current_user.email:
                user = User.query.filter_by(email=email).first()
                if user:
                    errors['email'] = ['Email address already taken.']
        if new_password:
            if not current_password:
                errors['current_password'] = ['Current password is required to change password.']
            elif not current_user.check_password(current_password):
                errors['current_password'] = ['Current password is incorrect.']
            if len(new_password) < 8:
                errors['new_password'] = ['Password must be at least 8 characters long.']
            if new_password != confirm_password:
                errors['confirm_password'] = ['Passwords must match.']
        if errors:
            return (jsonify({'success': False, 'message': 'Validation failed', 'errors': errors}), 400)
        password_updated = bool(new_password)
        db_user = User.query.get(current_user.id)
        db_user.first_name = first_name
        db_user.last_name = last_name
        if email:
            db_user.email = email
        if password_updated:
            db_user.set_password(new_password)
        session['user_name'] = f'{first_name} {last_name}'
        try:
            db.session.commit()
            message = 'Profile and password updated successfully!' if password_updated else 'Profile updated successfully!'
            return jsonify({'success': True, 'message': message})
        except Exception as e:
            db.session.rollback()
            return (jsonify({'success': False, 'message': 'Failed to update profile.'}), 500)
    else:
        profile_form = ProfileUpdateForm()
        if profile_form.validate_on_submit():
            password_updated = False
            if profile_form.new_password.data:
                if not current_user.check_password(profile_form.current_password.data):
                    flash('Current password is incorrect.', 'danger')
                    return redirect(url_for('auth.settings'))
                db_user = User.query.get(current_user.id)
                db_user.set_password(profile_form.new_password.data)
                password_updated = True
            if not 'db_user' in locals():
                db_user = User.query.get(current_user.id)
            db_user.first_name = profile_form.first_name.data
            db_user.last_name = profile_form.last_name.data
            db_user.email = profile_form.email.data
            session['user_name'] = f'{db_user.first_name} {db_user.last_name}'
            try:
                db.session.commit()
                message = 'Profile and password updated successfully!' if password_updated else 'Profile updated successfully!'
                flash(message, 'success')
            except Exception as e:
                db.session.rollback()
                flash('Failed to update profile.', 'danger')
                return redirect(url_for('auth.settings'))
            return redirect(url_for('auth.settings'))
        picture_form = ProfilePictureForm()
        return render_template('settings.html', profile_form=profile_form, picture_form=picture_form)

@auth_bp.route('/profile/picture', methods=['POST'])
@login_required
def update_profile_picture():
    picture_form = ProfilePictureForm()
    if picture_form.validate_on_submit():
        if picture_form.profile_picture.data:
            try:
                file = picture_form.profile_picture.data
                filename = secure_filename(f'{uuid.uuid4()}_{file.filename}')
                uploads_dir = os.path.join(current_app.static_folder, 'uploads', 'profile_pictures')
                os.makedirs(uploads_dir, exist_ok=True)
                file_path = os.path.join(uploads_dir, filename)
                file.save(file_path)
                if current_user.profile_picture:
                    old_file_path = os.path.join(current_app.static_folder, current_user.profile_picture)
                    if os.path.exists(old_file_path):
                        try:
                            os.remove(old_file_path)
                        except Exception as e:
                            pass
                relative_path = 'uploads/profile_pictures/' + filename
                current_user.profile_picture = relative_path
                db.session.commit()
                flash('Profile picture updated successfully!', 'success')
            except Exception as e:
                flash('Error updating profile picture. Please try again.', 'danger')
        else:
            flash('No picture selected.', 'warning')
    return redirect(url_for('auth.settings'))
