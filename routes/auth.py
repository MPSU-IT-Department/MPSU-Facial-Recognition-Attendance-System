from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from flask_login import login_user, logout_user, current_user, login_required
from werkzeug.security import generate_password_hash
import datetime

from app import db
from models import User
from forms import LoginForm, RegisterForm

# Create the blueprint for authentication routes
auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/', methods=['GET'])
def index():
    if current_user.is_authenticated:
        return redirect(url_for('students.enroll'))
    return redirect(url_for('auth.login'))

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('students.enroll'))
    
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
            
            # Redirect to the page user wanted to access or default to students.enroll
            next_page = request.args.get('next')
            return redirect(next_page or url_for('students.enroll'))
        else:
            flash('Invalid username or password', 'danger')
    
    return render_template('login.html', form=form)

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
