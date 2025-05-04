from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, SelectField, HiddenField
from wtforms.validators import DataRequired, Email, Length, ValidationError, EqualTo, Regexp
from models import Student, User, Class

# Login Form
class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')

# User Registration Form
class RegisterForm(FlaskForm):
    username = StringField('Username', validators=[
        DataRequired(),
        Length(min=4, max=64)
    ])
    email = StringField('Email', validators=[
        DataRequired(),
        Email(),
        Length(max=120)
    ])
    first_name = StringField('First Name', validators=[
        DataRequired(),
        Length(max=64)
    ])
    last_name = StringField('Last Name', validators=[
        DataRequired(),
        Length(max=64)
    ])
    password = PasswordField('Password', validators=[
        DataRequired(),
        Length(min=8, max=128)
    ])
    confirm_password = PasswordField('Confirm Password', validators=[
        DataRequired(),
        EqualTo('password', message='Passwords must match')
    ])
    role = SelectField('Role', choices=[
        ('instructor', 'Instructor'),
        ('admin', 'Administrator')
    ], validators=[DataRequired()])
    submit = SubmitField('Register')
    
    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError('Username already exists. Please choose a different one.')
    
    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError('Email address already registered.')

# Student Enrollment Form
class StudentForm(FlaskForm):
    first_name = StringField('First Name', validators=[
        DataRequired(),
        Length(max=64)
    ])
    last_name = StringField('Last Name', validators=[
        DataRequired(),
        Length(max=64)
    ])
    student_id = StringField('Student ID', validators=[
        DataRequired(),
        Regexp(r'^\d{2}-\d{5}$', message='Student ID must be in format YY-XXXXX')
    ])
    year_level = SelectField('Year Level', choices=[
        ('1st Year', '1st Year'),
        ('2nd Year', '2nd Year'),
        ('3rd Year', '3rd Year'),
        ('4th Year', '4th Year')
    ], validators=[DataRequired()])
    phone = StringField('Phone Number', validators=[
        DataRequired(),
        Regexp(r'^09\d{9}$', message='Phone number must start with 09 and have 11 digits total')
    ])
    email = StringField('Email', validators=[
        Email(),
        Length(max=120)
    ])
    submit = SubmitField('Enroll Student')
    
    def validate_student_id(self, student_id):
        student = Student.query.get(student_id.data)
        if student:
            raise ValidationError('Student ID already exists.')

# Class Form
class ClassForm(FlaskForm):
    class_code = StringField('Class Code', validators=[
        DataRequired(),
        Length(max=20)
    ])
    description = StringField('Description', validators=[
        DataRequired(),
        Length(max=255)
    ])
    room_number = StringField('Room Number', validators=[
        DataRequired(),
        Length(max=20)
    ])
    schedule = StringField('Schedule', validators=[
        DataRequired(),
        Length(max=100)
    ])
    instructor_id = SelectField('Instructor', coerce=int, validators=[DataRequired()])
    submit = SubmitField('Save Class')
    
    def validate_class_code(self, class_code):
        existing_class = Class.query.filter_by(class_code=class_code.data).first()
        if existing_class:
            raise ValidationError('Class code already exists.')

# Enrollment Form
class EnrollmentForm(FlaskForm):
    student_id = SelectField('Student', validators=[DataRequired()])
    class_id = HiddenField('Class ID', validators=[DataRequired()])
    submit = SubmitField('Enroll Student')

# Attendance Form
class AttendanceForm(FlaskForm):
    student_id = HiddenField('Student ID', validators=[DataRequired()])
    class_id = HiddenField('Class ID', validators=[DataRequired()])
    date = HiddenField('Date', validators=[DataRequired()])
    status = SelectField('Status', choices=[
        ('Present', 'Present'),
        ('Absent', 'Absent'),
        ('Late', 'Late')
    ], validators=[DataRequired()])
    submit = SubmitField('Save')
