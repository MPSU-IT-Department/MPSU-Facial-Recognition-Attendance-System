from flask import Blueprint, render_template, redirect, url_for, flash, request, session, current_app
from flask_login import login_user, logout_user, current_user, login_required
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import datetime
import os
import uuid

from app import db
from models import User
from forms import LoginForm, RegisterForm, ProfileUpdateForm, ProfilePictureForm

# Create the blueprint for authentication routes
auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

@auth_bp.route('/', methods=['GET'])
def index():
    if current_user.is_authenticated:
        # Redirect based on role
        if current_user.role == 'admin':
            return redirect(url_for('students.enroll'))
        elif current_user.role == 'instructor':
            return redirect(url_for('instructors.dashboard'))
    return redirect(url_for('auth.login'))

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        # Redirect based on role
        if current_user.role == 'admin':
            return redirect(url_for('students.enroll'))
        elif current_user.role == 'instructor':
            return redirect(url_for('instructors.dashboard'))
    
    form = LoginForm()
    
    if form.validate_on_submit():
        # Find the user by username
        user = User.query.filter_by(username=form.username.data).first()
        
        # Check if user exists and password is correct
        if user and user.check_password(form.password.data):
            login_user(user)
            session['user_id'] = user.id
            session['user_name'] = f"{user.first_name} {user.last_name}"
            session['user_role'] = user.role
            
            # Get the next page from query params
            next_page = request.args.get('next')
            
            # If next page is provided, go there
            if next_page:
                return redirect(next_page)
                
            # Otherwise, redirect based on role
            if user.role == 'admin':
                return redirect(url_for('students.enroll'))
            elif user.role == 'instructor':
                return redirect(url_for('instructors.dashboard'))
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
    return jsonify({
        'authenticated': True,
        'user': {
            'id': current_user.id,
            'username': current_user.username,
            'role': current_user.role,
            'name': f"{current_user.first_name} {current_user.last_name}"
        }
    })

@auth_bp.route('/logout', methods=['GET'])
@login_required
def logout():
    logout_user()
    # Clear the session
    session.clear()
    return redirect(url_for('auth.login'))

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    # In a production environment, you'd likely restrict registration to admins only
    form = RegisterForm()
    
    if form.validate_on_submit():
        # Create a new user
        user = User(
            username=form.username.data,
            email=form.email.data,
            first_name=form.first_name.data,
            last_name=form.last_name.data,
            role=form.role.data,
            created_at=datetime.datetime.utcnow()
        )
        user.set_password(form.password.data)
        
        # Add the user to the database
        db.session.add(user)
        db.session.commit()
        
        flash('Registration successful! You can now log in.', 'success')
        return redirect(url_for('auth.login'))
    
    return render_template('login.html', form=form, register=True)

@auth_bp.route('/profile', methods=['GET'])
@login_required
def profile():
    profile_form = ProfileUpdateForm(
        first_name=current_user.first_name,
        last_name=current_user.last_name,
        email=current_user.email
    )
    picture_form = ProfilePictureForm()
    
    return render_template('profile.html', profile_form=profile_form, picture_form=picture_form)

@auth_bp.route('/profile/update', methods=['POST'])
@login_required
def update_profile():
    profile_form = ProfileUpdateForm()
    
    if profile_form.validate_on_submit():
        # First check if the current password is provided and correct for any changes
        if profile_form.current_password.data:
            if not current_user.check_password(profile_form.current_password.data):
                flash('Current password is incorrect.', 'danger')
                return redirect(url_for('auth.profile'))
            
            # If new password is provided, update it
            if profile_form.new_password.data:
                current_user.set_password(profile_form.new_password.data)
                flash('Password updated successfully.', 'success')
        
        # Update the user profile
        current_user.first_name = profile_form.first_name.data
        current_user.last_name = profile_form.last_name.data
        current_user.email = profile_form.email.data
        
        # Update the session with the new name
        session['user_name'] = f"{current_user.first_name} {current_user.last_name}"
        
        # Commit changes to the database
        db.session.commit()
        
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('auth.profile'))
    
    # If form validation fails, go back to the profile page with errors
    picture_form = ProfilePictureForm()
    return render_template('profile.html', profile_form=profile_form, picture_form=picture_form)

@auth_bp.route('/profile/picture', methods=['POST'])
@login_required
def update_profile_picture():
    picture_form = ProfilePictureForm()
    
    if picture_form.validate_on_submit():
        # Check if a picture file was uploaded
        if picture_form.profile_picture.data:
            # Get the uploaded file
            file = picture_form.profile_picture.data
            
            # Create a unique filename
            filename = secure_filename(f"{uuid.uuid4()}_{file.filename}")
            
            # Create the uploads directory if it doesn't exist
            uploads_dir = os.path.join(current_app.static_folder, 'uploads')
            os.makedirs(uploads_dir, exist_ok=True)
            
            # Save the file
            file_path = os.path.join(uploads_dir, filename)
            file.save(file_path)
            
            # Delete the old profile picture if it exists
            if current_user.profile_picture:
                old_file_path = os.path.join(uploads_dir, current_user.profile_picture)
                if os.path.exists(old_file_path):
                    os.remove(old_file_path)
            
            # Update the user's profile picture in the database
            current_user.profile_picture = filename
            db.session.commit()
            
            flash('Profile picture updated successfully!', 'success')
        else:
            flash('No picture selected.', 'warning')
    
    return redirect(url_for('auth.profile'))
