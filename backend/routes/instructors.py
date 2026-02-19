from flask import Blueprint, render_template, redirect, url_for, request, jsonify, flash, current_app, send_file, make_response
from flask_login import login_required, current_user
import datetime
from datetime import timedelta
from utils.timezone import get_pst_now, pst_now_naive
import os
import uuid
import csv
import io
import re
import numpy as np
import tempfile
from PIL import Image
from werkzeug.utils import secure_filename
from sqlalchemy.orm import joinedload
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func, and_
from models import User, Class, Student, Enrollment, FaceEncoding, AttendanceRecord, InstructorAttendance, InstructorFaceEncoding, ClassSession, AttendanceStatus
from forms import RegisterForm, StudentForm, EnrollmentForm, ProfilePictureForm
from decorators import admin_required, instructor_required
from extensions import db
from utils.schedule_parser import resolve_schedule_window
try:
    from deepface import DeepFace
    DEEPFACE_AVAILABLE = True
except ImportError as e:
    DEEPFACE_AVAILABLE = False
DEEPFACE_MODEL = 'Facenet512'
DEEPFACE_DETECTOR = 'opencv'
DEEPFACE_DISTANCE_METRIC = 'cosine'
instructors_bp = Blueprint('instructors', __name__, url_prefix='/instructors')
DEFAULT_AUTO_TIMEOUT_MINUTES = 60

def sanitize_name_for_folder(name):
    """
    Sanitize a name to be safe for use as a folder name.
    Removes special characters and replaces spaces with underscores.
    """
    if not name:
        return 'unknown'
    sanitized = re.sub('[^a-zA-Z0-9\\s_-]', '', name)
    sanitized = re.sub('\\s+', '_', sanitized.strip())
    if not sanitized:
        return 'unknown'
    return sanitized.lower()

@instructors_bp.route('/manage', methods=['GET'])
@login_required
def manage():
    if current_user.role != 'admin':
        flash('You do not have permission to access this page.', 'danger')
        return redirect(url_for('instructors.dashboard'))
    instructors = User.query.filter_by(role='instructor').all()
    from models import InstructorFaceEncoding
    for instructor in instructors:
        face_count = InstructorFaceEncoding.query.filter_by(instructor_id=instructor.id).count()
        instructor.has_face_images = face_count > 0
    form = RegisterForm()
    form.role.default = 'instructor'
    form.process()
    return render_template('admin/instructors.html', instructors=instructors, form=form)

@instructors_bp.route('/dashboard', methods=['GET'])
@login_required
def dashboard():
    if current_user.role != 'instructor':
        flash('This page is only accessible to instructors.', 'warning')
        if current_user.role == 'admin':
            return redirect(url_for('instructors.manage'))
        return redirect(url_for('auth.login'))
    return render_template('instructors/dashboard.html')

@instructors_bp.route('/api/my-students', methods=['GET'])
@login_required
def get_my_students():
    """Get all students enrolled in instructor's classes"""
    try:
        if current_user.role != 'instructor':
            return (jsonify({'success': False, 'message': 'Unauthorized'}), 403)
        classes = Class.query.filter_by(instructor_id=current_user.id).all()
        class_ids = [cls.id for cls in classes]
        if not class_ids:
            return jsonify({'students': []})
        enrollments = Enrollment.query.filter(Enrollment.class_id.in_(class_ids)).all()
        student_ids = list(set((enrollment.student_id for enrollment in enrollments)))
        student_list = []
        for student_id in student_ids:
            student = Student.query.get(student_id)
            if student:
                has_face = FaceEncoding.query.filter_by(student_id=student.id).first() is not None
                student_list.append({'id': student.id, 'name': f"{student.first_name or ''} {student.last_name or ''}".strip(), 'yearLevel': student.year_level or '', 'phone': '', 'email': '', 'hasFaceImages': has_face})
        student_list.sort(key=lambda x: x['name'])
        return jsonify({'students': student_list})
    except Exception as e:
        return (jsonify({'success': False, 'message': str(e)}), 500)

@instructors_bp.route('/api/upload-pictures', methods=['POST'])
@login_required
def upload_pictures():
    """Upload pictures for a specific student"""
    try:
        if current_user.role != 'instructor':
            return (jsonify({'success': False, 'message': 'Unauthorized'}), 403)
        student_id = request.form.get('student_id')
        if not student_id:
            return (jsonify({'success': False, 'message': 'Student ID is required'}), 400)
        student = Student.query.get(student_id)
        if not student:
            return (jsonify({'success': False, 'message': 'Student not found'}), 404)
        instructor_enrollments = Enrollment.query.join(Class).filter(Class.instructor_id == current_user.id, Enrollment.student_id == student_id).first()
        if not instructor_enrollments:
            return (jsonify({'success': False, 'message': 'Student not found in your classes'}), 403)
        student_name = f'{student.first_name}_{student.last_name}'
        sanitized_student_name = sanitize_name_for_folder(student_name)
        files = request.files.getlist('pictures')
        if not files:
            return (jsonify({'success': False, 'message': 'No files provided'}), 400)
        MAX_IMAGES_PER_STUDENT = 20
        face_encodings = FaceEncoding.query.filter_by(student_id=student_id).all()
        if len(face_encodings) + len(files) > MAX_IMAGES_PER_STUDENT:
            return (jsonify({'success': False, 'message': f'Maximum of {MAX_IMAGES_PER_STUDENT} images allowed per student. You currently have {len(face_encodings)} images and are trying to upload {len(files)} more.'}), 400)
        allowed_extensions = {'png', 'jpg', 'jpeg'}
        uploaded_images = []
        errors = []
        for file in files:
            if not file.filename or '.' not in file.filename or file.filename.rsplit('.', 1)[1].lower() not in allowed_extensions:
                error_msg = f'File {file.filename} type not allowed. Please upload PNG, JPG, or JPEG'
                errors.append(error_msg)
                continue
            try:
                filename = secure_filename(f'{uuid.uuid4()}_{file.filename}')
                uploads_dir = os.path.join(current_app.static_folder, 'uploads', 'students', sanitized_student_name)
                os.makedirs(uploads_dir, exist_ok=True)
                file_path = os.path.join(uploads_dir, filename)
                file.save(file_path)
                relative_image_path = os.path.join('uploads', 'students', sanitized_student_name, filename).replace('\\', '/')
                face_encoding = FaceEncoding(student_id=student_id, encoding_data=bytes([0] * 128), image_path=relative_image_path, created_at=pst_now_naive())
                db.session.add(face_encoding)
                uploaded_images.append({'id': face_encoding.id, 'filename': filename, 'path': url_for('static', filename=face_encoding.image_path)})
            except Exception as e:
                error_msg = f'Error uploading {file.filename}: {str(e)}'
                errors.append(error_msg)
                continue
        try:
            if uploaded_images:
                db.session.commit()
                return jsonify({'success': True, 'message': f'Successfully uploaded {len(uploaded_images)} image(s).' + (f' Failed to upload {len(errors)} image(s).' if errors else ''), 'images': uploaded_images, 'errors': errors if errors else []})
            else:
                return (jsonify({'success': False, 'message': 'No images were uploaded successfully.', 'errors': errors}), 400)
        except Exception as e:
            db.session.rollback()
            return (jsonify({'success': False, 'message': str(e)}), 500)
    except Exception as e:
        return (jsonify({'success': False, 'message': str(e)}), 500)

@instructors_bp.route('/add', methods=['POST'])
@login_required
def add():
    if current_user.role != 'admin':
        if request.is_json:
            return (jsonify({'success': False, 'message': 'You do not have permission to perform this action.'}), 403)
        else:
            flash('You do not have permission to perform this action.', 'danger')
            return redirect(url_for('instructors.dashboard'))
    if request.is_json:
        data = request.get_json()
        instructor_id = data.get('instructor_id')
        username = data.get('username')
        first_name = data.get('first_name')
        middle_name = data.get('middle_name')
        last_name = data.get('last_name')
        password = data.get('password')
        confirm_password = data.get('confirm_password')
        department = data.get('department')
    else:
        instructor_id = request.form.get('instructor_id')
        username = request.form.get('username')
        first_name = request.form.get('first_name')
        middle_name = request.form.get('middle_name')
        last_name = request.form.get('last_name')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        department = request.form.get('department')
    if not instructor_id or not username or (not first_name) or (not last_name) or (not password):
        message = 'Missing required fields for instructor creation.'
        if request.is_json:
            return (jsonify({'success': False, 'message': message}), 400)
        else:
            flash(message, 'danger')
            return redirect(url_for('instructors.manage'))
    try:
        instructor_id = int(instructor_id)
    except ValueError:
        message = 'Instructor ID must be a number.'
        if request.is_json:
            return (jsonify({'success': False, 'message': message}), 400)
        else:
            flash(message, 'danger')
            return redirect(url_for('instructors.manage'))
    if len(first_name) < 2 or len(first_name) > 50:
        message = 'First name should be between 2 and 50 characters.'
        if request.is_json:
            return (jsonify({'success': False, 'message': message}), 400)
        else:
            flash(message, 'danger')
            return redirect(url_for('instructors.manage'))
    if len(last_name) < 2 or len(last_name) > 50:
        message = 'Last name should be between 2 and 50 characters.'
        if request.is_json:
            return (jsonify({'success': False, 'message': message}), 400)
        else:
            flash(message, 'danger')
            return redirect(url_for('instructors.manage'))
    if password != confirm_password:
        message = 'Passwords do not match.'
        if request.is_json:
            return (jsonify({'success': False, 'message': message}), 400)
        else:
            flash(message, 'danger')
            return redirect(url_for('instructors.manage'))
    existing_user = User.query.filter((User.id == instructor_id) | User.username.ilike(username)).first()
    if existing_user:
        if str(existing_user.id) == str(instructor_id):
            message = 'Instructor ID already exists.'
        elif existing_user.username.lower() == username.lower():
            message = 'Username already exists.'
        else:
            message = 'Instructor already exists.'
        if request.is_json:
            return (jsonify({'success': False, 'message': message}), 409)
        else:
            flash(message, 'danger')
            return redirect(url_for('instructors.manage'))
    try:
        placeholder_email = f'instructor{instructor_id}@no-reply.local'
        user_kwargs = {'id': instructor_id, 'username': username, 'email': placeholder_email, 'first_name': first_name, 'last_name': last_name, 'role': 'instructor', 'department': department if department else None, 'created_at': pst_now_naive()}
        if hasattr(User, 'middle_name') and middle_name:
            user_kwargs['middle_name'] = middle_name
        user = User(**user_kwargs)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        message = 'Instructor added successfully!'
        if request.is_json:
            return jsonify({'success': True, 'message': message})
        else:
            flash(message, 'success')
    except Exception as e:
        db.session.rollback()
        message = f'Error adding instructor: {str(e)}'
        if request.is_json:
            return (jsonify({'success': False, 'message': message}), 500)
        else:
            flash(message, 'danger')
    if not request.is_json:
        return redirect(url_for('instructors.manage'))

@instructors_bp.route('/update/<int:instructor_id>', methods=['POST'])
@login_required
def update(instructor_id):
    if current_user.role != 'admin':
        if request.is_json:
            return (jsonify({'success': False, 'message': 'You do not have permission to perform this action.'}), 403)
        else:
            flash('You do not have permission to perform this action.', 'danger')
            return redirect(url_for('instructors.dashboard'))
    instructor = User.query.get_or_404(instructor_id)
    if instructor.role == 'admin' and instructor.id != current_user.id:
        message = 'You cannot edit another administrator account.'
        if request.is_json:
            return (jsonify({'success': False, 'message': message}), 403)
        else:
            flash(message, 'danger')
            return redirect(url_for('instructors.manage'))
    if request.is_json:
        data = request.get_json()
        username = data.get('username')
        first_name = data.get('first_name')
        middle_name = data.get('middle_name')
        last_name = data.get('last_name')
        password = data.get('password')
        department = data.get('department')
    else:
        username = request.form.get('username')
        first_name = request.form.get('first_name')
        middle_name = request.form.get('middle_name')
        last_name = request.form.get('last_name')
        password = request.form.get('password')
        department = request.form.get('department')
    if username != instructor.username and User.query.filter_by(username=username).first():
        message = 'Username is already taken.'
        if request.is_json:
            return (jsonify({'success': False, 'message': message}), 409)
        else:
            flash(message, 'danger')
            return redirect(url_for('instructors.manage'))
    try:
        instructor.username = username
        instructor.first_name = first_name
        instructor.last_name = last_name
        instructor.department = department if department else None
        if hasattr(instructor, 'middle_name'):
            instructor.middle_name = middle_name if middle_name else None
        if password:
            instructor.set_password(password)
        db.session.commit()
        message = f'Instructor "{first_name} {last_name}" updated successfully!'
        if request.is_json:
            return jsonify({'success': True, 'message': message})
        else:
            flash(message, 'success')
    except Exception as e:
        db.session.rollback()
        message = f'Error updating instructor: {str(e)}'
        if request.is_json:
            return (jsonify({'success': False, 'message': message}), 500)
        else:
            flash(message, 'danger')
    if not request.is_json:
        return redirect(url_for('instructors.manage'))

@instructors_bp.route('/delete/<int:instructor_id>', methods=['POST'])
@login_required
def delete(instructor_id):
    if current_user.role != 'admin':
        if request.is_json:
            return (jsonify({'success': False, 'message': 'You do not have permission to perform this action.'}), 403)
        else:
            flash('You do not have permission to perform this action.', 'danger')
            return redirect(url_for('instructors.dashboard'))
    instructor = User.query.get_or_404(instructor_id)
    if instructor.id == current_user.id:
        message = 'You cannot delete your own account.'
        if request.is_json:
            return (jsonify({'success': False, 'message': message}), 403)
        else:
            flash(message, 'danger')
            return redirect(url_for('instructors.manage'))
    if instructor.classes:
        for cls in instructor.classes:
            cls.instructor_id = None
        db.session.flush()
    attendance_records = InstructorAttendance.query.filter_by(instructor_id=instructor_id).first()
    if attendance_records:
        message = 'Cannot delete instructor with attendance records. Please delete their attendance records first.'
        if request.is_json:
            return (jsonify({'success': False, 'message': message}), 400)
        else:
            flash(message, 'danger')
            return redirect(url_for('instructors.manage'))
    instructor_name = f'{instructor.first_name} {instructor.last_name}'
    try:
        InstructorFaceEncoding.query.filter_by(instructor_id=instructor_id).delete(synchronize_session=False)
        ClassSession.query.filter_by(instructor_id=instructor_id).update({ClassSession.instructor_id: None}, synchronize_session=False)
        AttendanceRecord.query.filter_by(marked_by=instructor_id).update({AttendanceRecord.marked_by: None}, synchronize_session=False)
        db.session.delete(instructor)
        db.session.commit()
        message = f'Instructor "{instructor_name}" deleted successfully!'
        if request.is_json:
            return jsonify({'success': True, 'message': message})
        else:
            flash(message, 'success')
    except Exception as e:
        db.session.rollback()
        message = f'Error deleting instructor: {str(e)}'
        if request.is_json:
            return (jsonify({'success': False, 'message': message}), 500)
        else:
            flash(message, 'danger')
    if not request.is_json:
        return redirect(url_for('instructors.manage'))

@instructors_bp.route('/attendance', methods=['GET'])
@login_required
def attendance():
    if current_user.role != 'instructor':
        flash('You do not have permission to access this page.', 'danger')
        return redirect(url_for('auth.login'))
    today = get_pst_now().strftime('%Y-%m-%d')
    from models import SystemSettings
    semester_setting = SystemSettings.query.filter_by(key='semester').first()
    school_year_setting = SystemSettings.query.filter_by(key='school_year').first()
    current_semester = semester_setting.value if semester_setting else '1st semester'
    current_school_year = school_year_setting.value if school_year_setting else '2025-2026'
    return render_template('instructors/attendance.html', today=today, current_semester=current_semester, current_school_year=current_school_year)

@instructors_bp.route('/students', methods=['GET'])
@login_required
def students():
    if current_user.role != 'instructor':
        flash('You do not have permission to access this page.', 'danger')
        return redirect(url_for('auth.login'))
    today = get_pst_now().strftime('%Y-%m-%d')
    from models import SystemSettings
    semester_setting = SystemSettings.query.filter_by(key='semester').first()
    school_year_setting = SystemSettings.query.filter_by(key='school_year').first()
    current_semester = semester_setting.value if semester_setting else '1st semester'
    current_school_year = school_year_setting.value if school_year_setting else '2025-2026'
    return render_template('instructors/students.html', today=today, current_semester=current_semester, current_school_year=current_school_year)

@instructors_bp.route('/classes', methods=['GET'])
@login_required
def classes():
    if current_user.role != 'instructor':
        flash('You do not have permission to access this page.', 'danger')
        return redirect(url_for('auth.login'))
    return render_template('instructors/classes.html')

@instructors_bp.route('/classes/<int:class_id>', methods=['GET'])
@login_required
def view_class(class_id):
    if current_user.role != 'instructor':
        flash('You do not have permission to access this page.', 'danger')
        return redirect(url_for('auth.login'))
    try:
        cls = Class.query.filter_by(id=class_id, instructor_id=current_user.id).first_or_404()
        all_students = Student.query.all()
        students_with_status = []
        for s in all_students:
            is_enrolled = Enrollment.query.filter_by(student_id=s.id, class_id=class_id).first() is not None
            students_with_status.append({'student': s, 'is_enrolled': is_enrolled})
        students_count = len([s for s in students_with_status if not s['is_enrolled']])
        return render_template('instructors/class_detail.html', **{'class': cls, 'students_with_status': students_with_status, 'students_count': students_count})
    except Exception as e:
        return (f'Error: {e}', 500)

@instructors_bp.route('/classes/<int:class_id>/enroll', methods=['POST'])
@login_required
def enroll_unenroll_students(class_id):
    if current_user.role != 'instructor':
        flash('You do not have permission to access this page.', 'danger')
        return redirect(url_for('auth.login'))
    try:
        cls = Class.query.filter_by(id=class_id, instructor_id=current_user.id).first_or_404()
        student_ids = request.form.getlist('student_ids')
        action = request.form.get('action')
        if action == 'enroll':
            enrolled_count = 0
            for student_id in student_ids:
                existing = Enrollment.query.filter_by(student_id=student_id, class_id=class_id).first()
                if not existing:
                    enrollment = Enrollment(student_id=student_id, class_id=class_id)
                    db.session.add(enrollment)
                    enrolled_count += 1
            db.session.commit()
            flash(f'Successfully enrolled {enrolled_count} student(s).', 'success')
        elif action == 'unenroll':
            unenrolled_count = 0
            for student_id in student_ids:
                enrollment = Enrollment.query.filter_by(student_id=student_id, class_id=class_id).first()
                if enrollment:
                    db.session.delete(enrollment)
                    unenrolled_count += 1
            db.session.commit()
            flash(f'Successfully unenrolled {unenrolled_count} student(s).', 'success')
        else:
            flash('Invalid action.', 'danger')
        return redirect(url_for('instructors.view_class', class_id=class_id))
    except Exception as e:
        db.session.rollback()
        flash('An error occurred while processing the request.', 'danger')
        return redirect(url_for('instructors.view_class', class_id=class_id))

@instructors_bp.route('/api/class-attendance-overview', methods=['GET'])
@login_required
def get_class_attendance_overview():
    try:
        if current_user.role != 'instructor':
            return (jsonify({'success': False, 'message': 'Unauthorized'}), 403)
        classes = Class.query.filter_by(instructor_id=current_user.id).all()
        date_str = request.args.get('date')
        if date_str:
            try:
                target_date = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                target_date = get_pst_now().date()
        else:
            target_date = get_pst_now().date()
        now = get_pst_now()
        class_list = []
        attendance_changes = False
        for class_obj in classes:
            enrollments = Enrollment.query.filter_by(class_id=class_obj.id).all()
            enrolled_count = len(enrollments)
            today_session = ClassSession.query.filter_by(class_id=class_obj.id, date=target_date).first()
            planned_window = resolve_schedule_window(class_obj.schedule or '', target_date=target_date)
            planned_start_datetime = planned_window['start_datetime'] if planned_window else None
            planned_end_datetime = planned_window['end_datetime'] if planned_window else None
            present_count = 0
            absent_count = 0
            late_count = 0
            session_status = 'none'
            session_start_time = today_session.start_time if today_session else None
            session_scheduled_end = today_session.scheduled_end_time if today_session else None
            session_timeout_deadline = None
            session_room = class_obj.room_number
            session_processed = False
            session_id = today_session.id if today_session else None
            attendance_record = InstructorAttendance.query.filter_by(instructor_id=current_user.id, class_id=class_obj.id, date=target_date).first()
            if today_session:
                session_room = today_session.session_room_number or class_obj.room_number
                session_processed = bool(today_session.is_attendance_processed)
                if session_start_time:
                    session_status = 'active'
                else:
                    session_status = 'scheduled'
                if session_processed:
                    session_status = 'completed'
                if not session_scheduled_end and session_start_time:
                    session_scheduled_end = session_start_time + timedelta(minutes=DEFAULT_AUTO_TIMEOUT_MINUTES)
                session_timeout_deadline = session_scheduled_end or (session_start_time + timedelta(minutes=DEFAULT_AUTO_TIMEOUT_MINUTES) if session_start_time else None)
            elif planned_start_datetime:
                session_status = 'upcoming'
                session_timeout_deadline = planned_end_datetime
            else:
                session_timeout_deadline = None
            if today_session:
                present_time_in = session_start_time or pst_now_naive()
                present_time_out = None
                if not attendance_record:
                    attendance_record = InstructorAttendance(instructor_id=current_user.id, class_id=class_obj.id, date=target_date, status='Present', time_in=present_time_in, time_out=present_time_out)
                    db.session.add(attendance_record)
                    attendance_changes = True
                else:
                    record_updated = False
                    if attendance_record.status != 'Present':
                        attendance_record.status = 'Present'
                        record_updated = True
                    if present_time_in and (attendance_record.time_in is None or attendance_record.time_in > present_time_in):
                        attendance_record.time_in = present_time_in
                        record_updated = True
                    if record_updated:
                        attendance_changes = True
            if today_session:
                today_attendance_records = AttendanceRecord.query.filter_by(class_session_id=today_session.id).all()
                today_attendance = {record.student_id: record.status.value.upper() if record.status else 'ABSENT' for record in today_attendance_records}
                for enrollment in enrollments:
                    student_id = enrollment.student_id
                    status = today_attendance.get(student_id, 'ABSENT')
                    if status == 'PRESENT':
                        present_count += 1
                    elif status == 'ABSENT':
                        absent_count += 1
                    elif status == 'LATE':
                        late_count += 1
            else:
                absent_count = enrolled_count
            class_list.append({'id': class_obj.id, 'classCode': class_obj.class_code, 'description': class_obj.description, 'schedule': class_obj.schedule, 'roomNumber': class_obj.room_number, 'term': class_obj.term, 'schoolYear': class_obj.school_year, 'enrolledCount': enrolled_count, 'presentCount': present_count, 'absentCount': absent_count, 'lateCount': late_count, 'date': target_date.strftime('%B %d %Y'), 'hasSessionToday': today_session is not None, 'sessionId': session_id, 'sessionStatus': session_status, 'sessionStartTime': session_start_time.isoformat() if session_start_time else None, 'sessionScheduledEndTime': session_scheduled_end.isoformat() if session_scheduled_end else None, 'sessionTimeoutDeadline': session_timeout_deadline.isoformat() if session_timeout_deadline else None, 'sessionRoomNumber': session_room, 'sessionProcessed': session_processed, 'plannedStartTime': planned_start_datetime.isoformat() if planned_start_datetime else None, 'plannedEndTime': planned_end_datetime.isoformat() if planned_end_datetime else None, 'serverTimestamp': now.isoformat(), 'instructorAttendanceStatus': attendance_record.status if attendance_record else None, 'instructorAttendanceTimeIn': attendance_record.time_in.isoformat() if attendance_record and attendance_record.time_in else None, 'instructorAttendanceTimeOut': attendance_record.time_out.isoformat() if attendance_record and attendance_record.time_out else None})
        if attendance_changes:
            try:
                db.session.commit()
            except Exception as commit_error:
                db.session.rollback()
        return jsonify({'success': True, 'classes': class_list})
    except Exception as e:
        return (jsonify({'success': False, 'message': str(e)}), 500)

@instructors_bp.route('/api/class-students/<int:class_id>', methods=['GET'])
@login_required
def get_class_students(class_id):
    try:
        if current_user.role != 'instructor':
            return (jsonify({'success': False, 'message': 'Unauthorized'}), 403)
        class_obj = Class.query.filter_by(id=class_id, instructor_id=current_user.id).first()
        if not class_obj:
            return (jsonify({'success': False, 'message': 'Class not found or not authorized'}), 404)
        enrollments = Enrollment.query.filter_by(class_id=class_id).all()
        date_str = request.args.get('date')
        if date_str:
            try:
                target_date = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                target_date = get_pst_now().date()
        else:
            target_date = get_pst_now().date()
        student_list = []
        for enrollment in enrollments:
            student = Student.query.get(enrollment.student_id)
            if student:
                has_face = FaceEncoding.query.filter_by(student_id=student.id).first() is not None
                status = 'UNKNOWN'
                student_list.append({'id': student.id, 'name': f"{student.first_name or ''} {student.last_name or ''}".strip(), 'yearLevel': student.year_level or '', 'phone': '', 'email': '', 'status': status, 'enrollmentId': enrollment.id, 'classId': class_id, 'className': class_obj.description or '', 'hasFaceImages': has_face})
        response = {'students': student_list, 'counts': {'present': 0, 'absent': 0, 'late': 0}}
        return jsonify(response)
    except Exception as e:
        return (jsonify({'success': False, 'message': str(e)}), 500)

@instructors_bp.route('/api/student-attendance/<string:student_id>/<int:class_id>', methods=['GET'])
@login_required
def get_student_attendance(student_id, class_id):
    try:
        if current_user.role != 'instructor':
            return (jsonify({'success': False, 'message': 'Unauthorized'}), 403)
        class_obj = Class.query.filter_by(id=class_id, instructor_id=current_user.id).first()
        if not class_obj:
            return (jsonify({'success': False, 'message': 'Class not found or not authorized'}), 403)
        enrollment = Enrollment.query.filter_by(class_id=class_id, student_id=student_id).first()
        if not enrollment:
            return (jsonify({'success': False, 'message': 'Student not enrolled in this class'}), 400)
        student = Student.query.get(student_id)
        if not student:
            return (jsonify({'success': False, 'message': 'Student not found'}), 404)
        date_str = request.args.get('date')
        if date_str:
            try:
                target_date = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                target_date = get_pst_now().date()
        else:
            target_date = get_pst_now().date()
        target_month = target_date.month
        target_year = target_date.year
        class_sessions = ClassSession.query.filter(ClassSession.class_id == class_id, db.extract('month', ClassSession.date) == target_month, db.extract('year', ClassSession.date) == target_year).all()
        attendance_data = {}
        for session in class_sessions:
            attendance = AttendanceRecord.query.filter_by(class_session_id=session.id, student_id=student_id).first()
            if attendance:
                attendance_data[session.date.strftime('%B %d %Y')] = {'status': attendance.status.value.upper() if attendance.status else 'ABSENT', 'class_session_id': session.id, 'attendance_id': attendance.id}
        present_count = sum((1 for record in attendance_data.values() if record['status'] == 'PRESENT'))
        absent_count = sum((1 for record in attendance_data.values() if record['status'] == 'ABSENT'))
        late_count = sum((1 for record in attendance_data.values() if record['status'] == 'LATE'))
        return jsonify({'success': True, 'student': {'id': student.id, 'name': f'{student.first_name} {student.last_name}', 'yearLevel': student.year_level}, 'class': {'id': class_obj.id, 'code': class_obj.class_code, 'description': class_obj.description}, 'attendance': {'month': target_date.strftime('%B'), 'year': target_date.year, 'presentCount': present_count, 'absentCount': absent_count, 'lateCount': late_count, 'records': attendance_data}})
    except Exception as e:
        return (jsonify({'success': False, 'message': str(e)}), 500)

@instructors_bp.route('/api/enroll-student', methods=['POST'])
@login_required
def enroll_student_api():
    if current_user.role != 'instructor':
        return (jsonify({'success': False, 'message': 'Unauthorized'}), 403)
    data = request.get_json()
    if not data or not all((key in data for key in ['student_id', 'class_id'])):
        return (jsonify({'success': False, 'message': 'Missing student_id or class_id'}), 400)
    student_id = data['student_id']
    class_id = data['class_id']
    class_obj = Class.query.filter_by(id=class_id, instructor_id=current_user.id).first()
    if not class_obj:
        return (jsonify({'success': False, 'message': 'Class not found or not authorized'}), 403)
    student = Student.query.get(student_id)
    if not student:
        return (jsonify({'success': False, 'message': 'Student not found'}), 404)
    existing_enrollment = Enrollment.query.filter_by(class_id=class_id, student_id=student_id).first()
    if existing_enrollment:
        return (jsonify({'success': False, 'message': 'Student already enrolled in this class'}), 409)
    try:
        new_enrollment = Enrollment(student_id=student_id, class_id=class_id)
        db.session.add(new_enrollment)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Student enrolled successfully'})
    except IntegrityError as e:
        db.session.rollback()
        return (jsonify({'success': False, 'message': 'Database integrity error: ' + str(e)}), 500)
    except Exception as e:
        db.session.rollback()
        return (jsonify({'success': False, 'message': 'An unexpected error occurred: ' + str(e)}), 500)

def allowed_file(filename):
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def sanitize_name_for_folder(name):
    """
    Sanitize a name to be safe for use as a folder name.
    Removes special characters and replaces spaces with underscores.
    """
    if not name:
        return 'unknown'
    sanitized = re.sub('[^a-zA-Z0-9\\s_-]', '', name)
    sanitized = re.sub('\\s+', '_', sanitized.strip())
    if not sanitized:
        return 'unknown'
    return sanitized.lower()

def generate_face_embedding(image_path):
    """Generate face embedding using DeepFace with FaceNet-512"""
    if not DEEPFACE_AVAILABLE:
        return bytes([0] * 512)
    try:
        embedding_result = DeepFace.represent(img_path=image_path, model_name=DEEPFACE_MODEL, detector_backend=DEEPFACE_DETECTOR, enforce_detection=True, align=True)
        if embedding_result and len(embedding_result) > 0:
            face_embedding = np.array(embedding_result[0]['embedding'], dtype=np.float32)
            embedding_bytes = face_embedding.tobytes()
            return embedding_bytes
        else:
            return None
    except Exception as e:
        try:
            embedding_result = DeepFace.represent(img_path=image_path, model_name=DEEPFACE_MODEL, detector_backend=DEEPFACE_DETECTOR, enforce_detection=False, align=True)
            if embedding_result and len(embedding_result) > 0:
                face_embedding = np.array(embedding_result[0]['embedding'], dtype=np.float32)
                embedding_bytes = face_embedding.tobytes()
                return embedding_bytes
            else:
                return None
        except Exception as e2:
            return None

def save_image(file, folder='students', person_name=None):
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filename = f'{uuid.uuid4().hex}_{filename}'
        if person_name:
            sanitized_name = sanitize_name_for_folder(person_name)
            folder_path = f'{folder}/{sanitized_name}'
        else:
            folder_path = folder
        upload_path = os.path.join(current_app.static_folder, 'uploads', folder_path)
        os.makedirs(upload_path, exist_ok=True)
        file_path = os.path.join(upload_path, filename)
        file.save(file_path)
        return f'uploads/{folder_path}/{filename}'
    return None

@instructors_bp.route('/api/student-images/<string:student_id>', methods=['GET'])
@login_required
def get_student_images(student_id):
    """Get all facial recognition images for a student"""
    try:
        student = Student.query.get(student_id)
        if not student:
            return (jsonify({'success': False, 'message': 'Student not found'}), 404)
        face_encodings = FaceEncoding.query.filter_by(student_id=student_id).all()
        images = []
        for encoding in face_encodings:
            if encoding.image_path:
                image_path_for_url = encoding.image_path.replace('\\', '/')
                images.append({'id': encoding.id, 'path': url_for('static', filename=image_path_for_url), 'created_at': encoding.created_at.strftime('%Y-%m-%d %H:%M:%S')})
        return jsonify({'success': True, 'student': {'id': student.id, 'name': f'{student.first_name} {student.last_name}'}, 'images': images})
    except Exception as e:
        return (jsonify({'success': False, 'message': str(e)}), 500)

@instructors_bp.route('/api/upload-student-image/<string:student_id>', methods=['POST'])
@login_required
def upload_student_image(student_id):
    """Upload a facial recognition image for a student"""
    try:
        student = Student.query.get(student_id)
        if not student:
            return (jsonify({'success': False, 'message': 'Student not found'}), 404)
        if 'image' not in request.files:
            return (jsonify({'success': False, 'message': 'No file part'}), 400)
        file = request.files['image']
        if file.filename == '':
            return (jsonify({'success': False, 'message': 'No selected file'}), 400)
        if not allowed_file(file.filename):
            return (jsonify({'success': False, 'message': 'File type not allowed. Please upload JPG, JPEG, or PNG files.'}), 400)
        file.seek(0, os.SEEK_END)
        file_size = file.tell()
        file.seek(0)
        if file_size > 5 * 1024 * 1024:
            return (jsonify({'success': False, 'message': 'File size too large. Maximum size is 5MB.'}), 400)
        face_encodings = FaceEncoding.query.filter_by(student_id=student_id).all()
        if len(face_encodings) >= 6:
            return (jsonify({'success': False, 'message': 'Maximum of 6 images allowed per student. Please delete an existing image first.'}), 400)
        student_name = f'{student.first_name}_{student.last_name}'
        image_path = save_image(file, folder='students', person_name=student_name)
        if not image_path:
            return (jsonify({'success': False, 'message': 'Error saving file'}), 500)
        try:
            face_encoding = FaceEncoding(student_id=student_id, encoding=bytes([0] * 128), image_path=image_path, created_at=pst_now_naive())
            db.session.add(face_encoding)
            db.session.commit()
            return jsonify({'success': True, 'message': 'Image uploaded successfully. Please process this image on the Raspberry Pi device.', 'image': {'id': face_encoding.id, 'path': url_for('static', filename=image_path), 'created_at': face_encoding.created_at.strftime('%Y-%m-%d %H:%M:%S')}})
        except Exception as db_error:
            if image_path:
                file_path = os.path.join(current_app.static_folder, image_path)
                if os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                    except Exception as cleanup_error:
                        pass
            db.session.rollback()
            return (jsonify({'success': False, 'message': f'Database error after file save: {str(db_error)}'}), 500)
    except Exception as e:
        db.session.rollback()
        return (jsonify({'success': False, 'message': f'An unexpected error occurred: {str(e)}'}), 500)

@instructors_bp.route('/api/update-face-encoding/<int:encoding_id>', methods=['POST'])
def update_face_encoding(encoding_id):
    """Update face encoding data (called by Raspberry Pi)"""
    try:
        data = request.get_json()
        if not data or 'encoding_data' not in data:
            return (jsonify({'success': False, 'message': 'No encoding data provided'}), 400)
        face_encoding = FaceEncoding.query.get(encoding_id)
        if not face_encoding:
            return (jsonify({'success': False, 'message': 'Face encoding not found'}), 404)
        face_encoding.encoding_data = data['encoding_data']
        db.session.commit()
        return jsonify({'success': True, 'message': 'Face encoding updated successfully'})
    except Exception as e:
        db.session.rollback()
        return (jsonify({'success': False, 'message': str(e)}), 500)

@instructors_bp.route('/api/face-encodings', methods=['GET', 'POST'])
def handle_face_encodings():
    api_key = request.headers.get('X-API-Key')
    if not api_key or api_key != current_app.config['API_KEY']:
        return (jsonify({'success': False, 'message': 'Unauthorized'}), 401)
    if request.method == 'GET':
        try:
            face_encodings = FaceEncoding.query.all()
            encodings_list = []
            for encoding in face_encodings:
                try:
                    embedding_data = None
                    if hasattr(encoding, 'encoding') and encoding.encoding:
                        embedding_array = np.frombuffer(encoding.encoding, dtype=np.float32)
                        embedding_data = embedding_array.tolist()
                    elif hasattr(encoding, 'encoding_data') and encoding.encoding_data:
                        embedding_data = encoding.encoding_data.hex()
                    encodings_list.append({'id': encoding.id, 'student_id': encoding.student_id, 'embedding': embedding_data, 'image_path': encoding.image_path})
                except Exception as e:
                    continue
            return jsonify({'success': True, 'encodings': encodings_list})
        except Exception as e:
            return (jsonify({'success': False, 'message': str(e)}), 500)
    elif request.method == 'POST':
        try:
            data = request.get_json()
            if not data or 'student_id' not in data or 'encoding_data' not in data:
                return (jsonify({'success': False, 'message': 'Missing required fields'}), 400)
            student = Student.query.get(data['student_id'])
            if not student:
                return (jsonify({'success': False, 'message': 'Student not found'}), 404)
            face_encoding = FaceEncoding(student_id=data['student_id'], encoding_data=bytes.fromhex(data['encoding_data']), image_path=data.get('image_path'))
            db.session.add(face_encoding)
            db.session.commit()
            return (jsonify({'success': True, 'message': 'Face encoding created successfully', 'encoding_id': face_encoding.id}), 201)
        except Exception as e:
            db.session.rollback()
            return (jsonify({'success': False, 'message': str(e)}), 500)

@instructors_bp.route('/api/instructor-face-encodings', methods=['GET'])
def get_instructor_face_encodings():
    """Get all face encodings for instructors"""
    api_key = request.headers.get('X-API-Key')
    if not api_key or api_key != current_app.config['API_KEY']:
        return (jsonify({'error': 'Unauthorized: Missing or invalid API Key'}), 401)
    try:
        instructors = User.query.filter_by(role='instructor').all()
        encodings = []
        for instructor in instructors:
            face_encodings = InstructorFaceEncoding.query.filter_by(instructor_id=instructor.id).all()
            for encoding in face_encodings:
                if encoding.encoding:
                    try:
                        embedding_array = np.frombuffer(encoding.encoding, dtype=np.float32)
                        encodings.append({'instructor_id': instructor.id, 'embedding': embedding_array.tolist(), 'image_path': encoding.image_path})
                    except Exception as e:
                        continue
        return jsonify({'success': True, 'encodings': encodings})
    except Exception as e:
        return (jsonify({'success': False, 'message': str(e)}), 500)

@instructors_bp.route('/api/upload-instructor-images/<int:instructor_id>', methods=['POST'])
@login_required
@admin_required
def upload_instructor_images(instructor_id):
    """Upload multiple instructor images"""
    try:
        if 'image' not in request.files:
            return (jsonify({'success': False, 'message': 'No image file provided'}), 400)
        instructor = User.query.filter_by(id=instructor_id, role='instructor').first()
        if not instructor:
            return (jsonify({'success': False, 'message': 'Instructor not found'}), 404)
        files = request.files.getlist('image')
        if not files:
            return (jsonify({'success': False, 'message': 'No image files provided'}), 400)
        instructor_name = f'{instructor.first_name}_{instructor.last_name}'
        sanitized_instructor_name = sanitize_name_for_folder(instructor_name)
        allowed_extensions = {'png', 'jpg', 'jpeg'}
        uploaded_files = []
        errors = []
        for file in files:
            if not file.filename:
                errors.append('Empty filename provided')
                continue
            file_ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else ''
            if file_ext not in allowed_extensions:
                errors.append(f'File type not allowed for {file.filename}. Please upload PNG, JPG, or JPEG')
                continue
            try:
                filename = secure_filename(f'{uuid.uuid4()}_{file.filename}')
                uploads_dir = os.path.join(current_app.static_folder, 'uploads', 'instructors', sanitized_instructor_name)
                os.makedirs(uploads_dir, exist_ok=True)
                file_path = os.path.join(uploads_dir, filename)
                file.save(file_path)
                relative_image_path = os.path.join('uploads', 'instructors', sanitized_instructor_name, filename).replace('\\', '/')
                face_encoding = InstructorFaceEncoding(instructor_id=instructor_id, encoding=bytes([0] * 128), image_path=relative_image_path, created_at=pst_now_naive())
                db.session.add(face_encoding)
                db.session.flush()
                uploaded_files.append({'id': face_encoding.id, 'filename': filename, 'path': url_for('static', filename=relative_image_path)})
            except Exception as e:
                errors.append(f'Error processing {file.filename}: {str(e)}')
                if 'file_path' in locals() and os.path.exists(file_path):
                    os.remove(file_path)
                continue
        if uploaded_files:
            try:
                db.session.commit()
                return jsonify({'success': True, 'message': f'Successfully uploaded {len(uploaded_files)} images', 'images': uploaded_files, 'errors': errors if errors else None})
            except Exception as db_error:
                db.session.rollback()
                for file_info in uploaded_files:
                    static_path = file_info['path'].replace('/static/', '')
                    file_path = os.path.join(current_app.static_folder, static_path)
                    if os.path.exists(file_path):
                        os.remove(file_path)
                return (jsonify({'success': False, 'message': f'Database error: {str(db_error)}'}), 500)
        else:
            return (jsonify({'success': False, 'message': 'No images were uploaded successfully', 'errors': errors}), 400)
    except Exception as e:
        return (jsonify({'success': False, 'message': str(e)}), 500)

@instructors_bp.route('/api/instructor-images/<int:instructor_id>', methods=['GET'])
@login_required
@admin_required
def get_instructor_images(instructor_id):
    """Get all facial recognition images for an instructor"""
    instructor = User.query.get(instructor_id)
    if not instructor or instructor.role != 'instructor':
        return (jsonify({'success': False, 'message': 'Instructor not found'}), 404)
    face_encodings = InstructorFaceEncoding.query.filter_by(instructor_id=instructor_id).all()
    images = []
    for encoding in face_encodings:
        if encoding.image_path:
            images.append({'id': encoding.id, 'filename': encoding.image_path, 'path': f'/static/{encoding.image_path}', 'createdAt': encoding.created_at.isoformat() if encoding.created_at else None})
    return jsonify({'success': True, 'instructor': {'id': instructor.id, 'name': f'{instructor.first_name} {instructor.last_name}'}, 'images': images})

@instructors_bp.route('/api/delete-instructor-image/<int:image_id>', methods=['DELETE'])
@login_required
@admin_required
def delete_instructor_image(image_id):
    """Deletes an instructor image by image ID"""
    face_encoding = InstructorFaceEncoding.query.get(image_id)
    if not face_encoding:
        return (jsonify({'success': False, 'message': 'Image not found'}), 404)
    try:
        if face_encoding.image_path:
            file_path = os.path.join(current_app.static_folder, face_encoding.image_path)
            if os.path.exists(file_path):
                os.remove(file_path)
        db.session.delete(face_encoding)
        db.session.commit()
        remaining_images = InstructorFaceEncoding.query.filter_by(instructor_id=face_encoding.instructor_id).count()
        return jsonify({'success': True, 'message': 'Image deleted successfully', 'remaining_images': remaining_images})
    except Exception as e:
        db.session.rollback()
        return (jsonify({'success': False, 'message': str(e)}), 500)

@instructors_bp.route('/api/student/<string:student_id>', methods=['GET'])
def get_student_details(student_id):
    """Get student details"""
    try:
        student = Student.query.get(student_id)
        if not student:
            return (jsonify({'success': False, 'message': 'Student not found'}), 404)
        return jsonify({'success': True, 'student': {'id': student.id, 'firstName': student.first_name, 'lastName': student.last_name, 'yearLevel': student.year_level, 'phone': student.phone, 'email': student.email or ''}})
    except Exception as e:
        return (jsonify({'success': False, 'message': str(e)}), 500)

@instructors_bp.route('/api/instructor/<int:instructor_id>', methods=['GET'])
def get_instructor_details(instructor_id):
    """Get instructor details"""
    try:
        instructor = User.query.get(instructor_id)
        if not instructor or instructor.role != 'instructor':
            return (jsonify({'success': False, 'message': 'Instructor not found'}), 404)
        return jsonify({'success': True, 'instructor': {'id': instructor.id, 'firstName': instructor.first_name, 'lastName': instructor.last_name, 'email': instructor.email, 'username': instructor.username}})
    except Exception as e:
        return (jsonify({'success': False, 'message': str(e)}), 500)

@instructors_bp.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint for Raspberry Pi"""
    return jsonify({'success': True, 'status': 'healthy', 'timestamp': get_pst_now().isoformat()})

@instructors_bp.route('/api/create-student', methods=['POST'])
def create_student():
    """Create a new student (API key required)"""
    api_key = request.headers.get('X-API-Key')
    if not api_key or api_key != current_app.config['API_KEY']:
        return (jsonify({'success': False, 'message': 'Unauthorized'}), 401)
    try:
        data = request.get_json()
        required_fields = ['firstName', 'lastName', 'id', 'yearLevel']
        for field in required_fields:
            if field not in data or not data[field]:
                return (jsonify({'success': False, 'message': f'Missing or empty required field: {field}'}), 400)
        existing_student = Student.query.get(data['id'])
        if existing_student:
            return (jsonify({'success': False, 'message': 'Student ID already exists'}), 400)
        student = Student(id=data['id'], first_name=data['firstName'], last_name=data['lastName'], year_level=data['yearLevel'], email=data.get('email'))
        db.session.add(student)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Student created successfully', 'student': {'id': student.id, 'firstName': student.first_name, 'lastName': student.last_name, 'yearLevel': student.year_level, 'phone': student.phone, 'email': student.email}})
    except Exception as e:
        db.session.rollback()
        return (jsonify({'success': False, 'message': str(e)}), 500)

@instructors_bp.route('/api/update-student/<string:student_id>', methods=['PUT'])
@login_required
def update_student(student_id):
    """Update an existing student"""
    try:
        student = Student.query.get_or_404(student_id)
        data = request.get_json()
        required_fields = ['firstName', 'lastName', 'yearLevel']
        for field in required_fields:
            if field not in data or not data[field]:
                return (jsonify({'success': False, 'message': f'Missing or empty required field for update: {field}'}), 400)
        student.first_name = data['firstName']
        student.last_name = data['lastName']
        student.year_level = data['yearLevel']
        student.email = data.get('email')
        if hasattr(student, 'middle_name') and 'middleName' in data:
            student.middle_name = data.get('middleName') or None
        db.session.commit()
        return jsonify({'success': True, 'message': 'Student updated successfully'})
    except Exception as e:
        db.session.rollback()
        return (jsonify({'success': False, 'message': str(e)}), 500)

@instructors_bp.route('/api/delete-student/<string:student_id>', methods=['DELETE'])
@login_required
def delete_student(student_id):
    """Delete a student"""
    try:
        student = Student.query.get_or_404(student_id)
        if student.enrollments:
            return (jsonify({'success': False, 'message': 'Cannot delete student who is enrolled in classes'}), 400)
        db.session.delete(student)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Student deleted successfully'})
    except Exception as e:
        db.session.rollback()
        return (jsonify({'success': False, 'message': str(e)}), 500)

@instructors_bp.route('/api/delete-student-image/<int:image_id>', methods=['DELETE', 'POST'])
@login_required
def delete_student_image(image_id):
    """Delete a student facial recognition image"""
    try:
        face_encoding = FaceEncoding.query.get(image_id)
        if not face_encoding:
            return (jsonify({'success': False, 'message': 'Image not found'}), 404)
        image_path = face_encoding.image_path
        db.session.delete(face_encoding)
        db.session.commit()
        if image_path:
            file_path = os.path.join(current_app.static_folder, image_path)
            if os.path.exists(file_path):
                os.remove(file_path)
        remaining_images = FaceEncoding.query.filter_by(student_id=face_encoding.student_id).count()
        return jsonify({'success': True, 'message': 'Image deleted successfully', 'remaining_images': remaining_images})
    except Exception as e:
        db.session.rollback()
        return (jsonify({'success': False, 'message': str(e)}), 500)

@instructors_bp.route('/api/update-attendance', methods=['POST'])
@login_required
def update_attendance():
    """Manually update student attendance status"""
    try:
        data = request.get_json()
        student_id = data.get('student_id') or data.get('studentId') or data.get('StudentID')
        class_id = data.get('class_id') or data.get('classId') or data.get('ClassID')
        date_str = data.get('date') or data.get('Date')
        status = (data.get('status') or data.get('Status') or '').lower()
        if not all((student_id, class_id, date_str, status)):
            return (jsonify({'success': False, 'message': 'Missing required attendance fields'}), 400)
        try:
            attendance_date = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError as e:
            return (jsonify({'success': False, 'message': 'Invalid date format. Use YYYY-MM-DD.'}), 400)
        if current_user.role == 'instructor':
            class_obj = Class.query.filter_by(id=class_id, instructor_id=current_user.id).first()
            if not class_obj:
                return (jsonify({'success': False, 'message': 'Class not found or not authorized'}), 403)
        elif current_user.role != 'admin':
            return (jsonify({'success': False, 'message': 'Unauthorized'}), 403)
        enrollment = Enrollment.query.filter_by(student_id=student_id, class_id=class_id).first()
        if not enrollment:
            return (jsonify({'success': False, 'message': 'Student not enrolled in this class'}), 400)
        class_session = ClassSession.query.filter_by(class_id=class_id, date=attendance_date).first()
        if not class_session:
            return (jsonify({'success': False, 'message': 'No class session found for this date'}), 404)
        attendance_record = AttendanceRecord.query.filter_by(class_session_id=class_session.id, student_id=student_id).first()
        try:
            status_enum = AttendanceStatus[status.upper()]
            if attendance_record:
                attendance_record.status = status_enum
                attendance_record.class_id = class_id
                attendance_record.updated_at = pst_now_naive()
                db.session.commit()
                return jsonify({'success': True, 'message': 'Attendance record updated successfully', 'attendance_id': attendance_record.id})
            else:
                new_record = AttendanceRecord(student_id=student_id, class_id=class_id, class_session_id=class_session.id, status=status_enum, created_at=pst_now_naive(), updated_at=pst_now_naive(), marked_by=current_user.id if hasattr(current_user, 'id') else None, date=datetime.datetime.combine(attendance_date, pst_now_naive().time()))
                db.session.add(new_record)
                db.session.commit()
                return jsonify({'success': True, 'message': 'Attendance record created successfully', 'attendance_id': new_record.id})
        except Exception as e:
            db.session.rollback()
            return (jsonify({'success': False, 'message': f'Database error: {str(e)}'}), 500)
    except Exception as e:
        db.session.rollback()
        return (jsonify({'success': False, 'message': str(e)}), 500)

@instructors_bp.route('/api/unenroll-student/<int:enrollment_id>', methods=['DELETE'])
@login_required
def unenroll_student(enrollment_id):
    try:
        if current_user.role != 'instructor':
            return (jsonify({'success': False, 'message': 'Unauthorized'}), 403)
        enrollment = Enrollment.query.get_or_404(enrollment_id)
        class_obj = Class.query.filter_by(id=enrollment.class_id, instructor_id=current_user.id).first()
        if not class_obj:
            return (jsonify({'success': False, 'message': 'Class not found or not authorized'}), 403)
        db.session.delete(enrollment)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Student unenrolled successfully'})
    except Exception as e:
        db.session.rollback()
        return (jsonify({'success': False, 'message': str(e)}), 500)

@instructors_bp.route('/api/delete-attendance', methods=['POST'])
@login_required
def delete_attendance():
    """Delete a student attendance record"""
    try:
        data = request.get_json()
        student_id = data.get('student_id') or data.get('studentId') or data.get('StudentID')
        class_id = data.get('class_id') or data.get('classId') or data.get('ClassID')
        date_str = data.get('date') or data.get('Date')
        if not all((student_id, class_id, date_str)):
            return (jsonify({'success': False, 'message': 'Missing required attendance fields'}), 400)
        try:
            attendance_date = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError as e:
            return (jsonify({'success': False, 'message': 'Invalid date format. Use YYYY-MM-DD.'}), 400)
        if current_user.role == 'instructor':
            class_obj = Class.query.filter_by(id=class_id, instructor_id=current_user.id).first()
            if not class_obj:
                return (jsonify({'success': False, 'message': 'Class not found or not authorized'}), 403)
        elif current_user.role != 'admin':
            return (jsonify({'success': False, 'message': 'Unauthorized'}), 403)
        enrollment = Enrollment.query.filter_by(student_id=student_id, class_id=class_id).first()
        if not enrollment:
            return (jsonify({'success': False, 'message': 'Student not enrolled in this class'}), 400)
        class_session = ClassSession.query.filter_by(class_id=class_id, date=attendance_date).first()
        if not class_session:
            return (jsonify({'success': False, 'message': 'No class session found for this date'}), 404)
        attendance_record = AttendanceRecord.query.filter_by(class_session_id=class_session.id, student_id=student_id).first()
        if not attendance_record:
            return (jsonify({'success': False, 'message': 'No attendance record found'}), 404)
        try:
            db.session.delete(attendance_record)
            db.session.commit()
            return jsonify({'success': True, 'message': 'Attendance record deleted successfully'})
        except Exception as e:
            db.session.rollback()
            return (jsonify({'success': False, 'message': f'Database error: {str(e)}'}), 500)
    except Exception as e:
        db.session.rollback()
        return (jsonify({'success': False, 'message': str(e)}), 500)

@instructors_bp.route('/export_csv', methods=['GET'])
@login_required
@admin_required
def export_csv():
    """Export all instructors to CSV"""
    try:
        instructors = User.query.filter_by(role='instructor').all()
        output = io.StringIO()
        writer = csv.writer(output)
        for instructor in instructors:
            writer.writerow([instructor.username, instructor.email, instructor.first_name, instructor.last_name])
        output.seek(0)
        response = make_response(output.getvalue())
        response.headers['Content-Type'] = 'text/csv'
        response.headers['Content-Disposition'] = f"attachment; filename=instructors_export_{get_pst_now().strftime('%Y%m%d_%H%M%S')}.csv"
        flash(f'Successfully exported {len(instructors)} instructors.', 'success')
        return response
    except Exception as e:
        flash(f'Error exporting instructors: {str(e)}', 'danger')
        return redirect(url_for('instructors.manage'))

@instructors_bp.route('/import_csv', methods=['POST'])
@login_required
@admin_required
def import_csv():
    """Import instructors from CSV"""
    try:
        if 'csvFile' not in request.files:
            flash('No file selected.', 'danger')
            return redirect(url_for('instructors.manage'))
        file = request.files['csvFile']
        if file.filename == '':
            flash('No file selected.', 'danger')
            return redirect(url_for('instructors.manage'))
        if not file.filename.lower().endswith('.csv'):
            flash('Please upload a CSV file.', 'danger')
            return redirect(url_for('instructors.manage'))
        file_content = file.stream.read().decode('UTF8')
        stream = io.StringIO(file_content, newline=None)
        csv_input = csv.DictReader(stream)
        required_columns = ['username', 'email', 'first_name', 'last_name', 'password']
        header_row = [col.strip().lower() for col in csv_input.fieldnames or [] if col]
        has_header_row = all((col in header_row for col in required_columns))
        if not has_header_row:
            stream.seek(0)
            csv_input = csv.DictReader(stream, fieldnames=required_columns)
            row_start_index = 1
        else:
            row_start_index = 2
        skip_duplicates = request.form.get('skipDuplicates') == 'on'
        imported_count = 0
        skipped_count = 0
        error_count = 0
        for row_num, row in enumerate(csv_input, start=row_start_index):
            try:
                if not all((row.get(col, '').strip() for col in required_columns)):
                    flash(f'Row {row_num}: Missing required fields', 'warning')
                    error_count += 1
                    continue
                username = row['username'].strip()
                email = row['email'].strip().lower()
                first_name = row['first_name'].strip()
                last_name = row['last_name'].strip()
                password = row['password'].strip()
                existing_user = User.query.filter((User.username == username) | (User.email == email)).first()
                if existing_user:
                    if skip_duplicates:
                        skipped_count += 1
                        continue
                    else:
                        flash(f'Row {row_num}: Username "{username}" or email "{email}" already exists', 'warning')
                        error_count += 1
                        continue
                instructor = User(username=username, email=email, first_name=first_name, last_name=last_name, role='instructor')
                instructor.set_password(password)
                db.session.add(instructor)
                imported_count += 1
            except Exception as e:
                flash(f'Row {row_num}: Error processing row - {str(e)}', 'warning')
                error_count += 1
                continue
        db.session.commit()
        if imported_count > 0:
            flash(f'Successfully imported {imported_count} instructors.', 'success')
        if skipped_count > 0:
            flash(f'Skipped {skipped_count} duplicate entries.', 'info')
        if error_count > 0:
            flash(f'Failed to import {error_count} entries due to errors.', 'warning')
        if imported_count == 0 and error_count == 0 and (skipped_count == 0):
            flash('No valid entries found in the CSV file.', 'warning')
    except Exception as e:
        db.session.rollback()
        flash(f'Error importing instructors: {str(e)}', 'danger')
    return redirect(url_for('instructors.manage'))

@instructors_bp.route('/api/import-instructors', methods=['POST'])
@login_required
@admin_required
def import_instructors():
    data = request.get_json()
    instructors = data.get('instructors', [])
    dry_run = data.get('dry_run', False)
    update_existing = data.get('update_existing', False)
    if not instructors:
        return (jsonify({'success': False, 'message': 'No instructors provided.'}), 400)
    conflicts = []
    new_instructors = []
    update_instructors = []
    for inst in instructors:
        username = inst.get('username', '').strip()
        email = inst.get('email', '').strip().lower()
        if not username or not email:
            continue
        existing = User.query.filter(User.username.ilike(username) | User.email.ilike(email)).first()
        if existing:
            conflicts.append(username or email)
            update_instructors.append((existing, inst))
        else:
            new_instructors.append(inst)
    if dry_run:
        return jsonify({'success': True, 'conflicts': conflicts})
    if conflicts and (not update_existing):
        return (jsonify({'success': False, 'message': 'Conflicts found', 'conflicts': conflicts}), 409)
    added, updated = (0, 0)
    for inst in new_instructors:
        try:
            user = User(username=inst.get('username'), email=inst.get('email').lower(), first_name=inst.get('name', '').split(' ')[0], last_name=' '.join(inst.get('name', '').split(' ')[1:]) or '', role='instructor', created_at=pst_now_naive())
            if inst.get('password'):
                user.set_password(inst.get('password'))
            else:
                user.set_password('changeme123')
            db.session.add(user)
            added += 1
        except Exception as e:
            db.session.rollback()
            continue
    for existing, inst in update_instructors:
        try:
            existing.first_name = inst.get('name', '').split(' ')[0]
            existing.last_name = ' '.join(inst.get('name', '').split(' ')[1:]) or ''
            existing.email = inst.get('email').lower()
            if inst.get('password'):
                existing.set_password(inst.get('password'))
            db.session.commit()
            updated += 1
        except Exception as e:
            db.session.rollback()
            continue
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return (jsonify({'success': False, 'message': f'Database error: {str(e)}'}), 500)
    return jsonify({'success': True, 'message': f'Import complete. Added: {added}, Updated: {updated}.'})

@instructors_bp.route('/api/check-instructor-classes/<int:instructor_id>')
@login_required
def check_instructor_classes(instructor_id):
    instructor = User.query.get_or_404(instructor_id)
    assigned_classes = [cls.class_code for cls in instructor.classes] if hasattr(instructor, 'classes') else []
    return jsonify({'assigned_classes': assigned_classes})

@instructors_bp.route('/api/class-attendance/<int:class_id>', methods=['GET'])
@login_required
@instructor_required
def get_class_attendance_dates(class_id):
    try:
        class_obj = Class.query.filter_by(id=class_id, instructor_id=current_user.id).first()
        if not class_obj:
            return (jsonify({'success': False, 'message': 'Class not found or not authorized'}), 403)
        dates_str = request.args.get('dates')
        if not dates_str:
            return (jsonify({'success': False, 'message': 'Dates parameter is required'}), 400)
        dates = []
        for date_str in dates_str.split(','):
            try:
                dates.append(datetime.datetime.strptime(date_str.strip(), '%Y-%m-%d').date())
            except ValueError:
                continue
        if not dates:
            return (jsonify({'success': False, 'message': 'No valid dates provided'}), 400)
        enrollments = Enrollment.query.filter_by(class_id=class_id).all()
        students = [Student.query.get(e.student_id) for e in enrollments if Student.query.get(e.student_id)]
        class_sessions = ClassSession.query.filter_by(class_id=class_id).filter(ClassSession.date.in_(dates)).all()
        sessions_by_date = {session.date: session for session in class_sessions}
        attendance_data = {}
        for student in students:
            student_attendance = {}
            for target_date in dates:
                date_str = target_date.strftime('%Y-%m-%d')
                class_session = sessions_by_date.get(target_date)
                if class_session:
                    attendance = AttendanceRecord.query.filter_by(class_session_id=class_session.id, student_id=student.id).first()
                    if attendance:
                        student_attendance[date_str] = {'status': attendance.status.value.upper() if attendance.status else 'ABSENT', 'time_in': attendance.time_in.strftime('%H:%M') if attendance.time_in else '', 'time_out': attendance.time_out.strftime('%H:%M') if attendance.time_out else '', 'marked_by': attendance.marked_by, 'has_session': True}
                    else:
                        student_attendance[date_str] = {'status': 'ABSENT', 'time_in': '', 'time_out': '', 'has_session': True}
                else:
                    student_attendance[date_str] = {'status': 'ABSENT', 'time_in': '', 'time_out': '', 'has_session': False}
            attendance_data[student.id] = student_attendance
        return jsonify({'success': True, 'attendance': attendance_data})
    except Exception as e:
        return (jsonify({'success': False, 'message': str(e)}), 500)

@instructors_bp.route('/api/attendance', methods=['GET'])
@login_required
@instructor_required
def get_instructor_own_attendance():
    if current_user.role != 'instructor':
        return (jsonify({'success': False, 'message': 'Unauthorized'}), 403)
    class_id = request.args.get('classId')
    if not class_id:
        return (jsonify([]), 200)
    class_obj = Class.query.filter_by(id=class_id, instructor_id=current_user.id).first()
    if not class_obj:
        return (jsonify({'success': False, 'message': 'Class not found or not assigned to you'}), 404)
    attendance_records = InstructorAttendance.query.filter_by(instructor_id=current_user.id, class_id=class_id).order_by(InstructorAttendance.date.desc()).all()
    attendance_data = []
    for attendance in attendance_records:
        attendance_data.append({'date': attendance.date.strftime('%B %d %Y'), 'status': attendance.status, 'time_in': attendance.time_in.strftime('%H:%M') if attendance.time_in else None, 'time_out': attendance.time_out.strftime('%H:%M') if attendance.time_out else None})
    return jsonify(attendance_data)
