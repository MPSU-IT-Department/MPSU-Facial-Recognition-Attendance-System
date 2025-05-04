from flask import Blueprint, render_template, redirect, url_for, request, jsonify, flash
from flask_login import login_required, current_user
import datetime
from datetime import date, timedelta
import calendar

from app import db
from models import Class, Student, Enrollment, AttendanceRecord, FaceEncoding

attendance_bp = Blueprint('attendance', __name__, url_prefix='/attendance')

@attendance_bp.route('/manage', methods=['GET'])
@login_required
def manage():
    # Get selected class_id from query params if provided
    class_id = request.args.get('class_id')
    
    # If instructor, filter to show only their classes
    if current_user.role == 'instructor':
        classes = Class.query.filter_by(instructor_id=current_user.id).all()
    else:
        classes = Class.query.all()
    
    return render_template('attendance/manage.html', classes=classes, selected_class_id=class_id)

@attendance_bp.route('/api/classes', methods=['GET'])
@login_required
def get_classes_with_attendance():
    # If instructor, only show their classes
    if current_user.role == 'instructor':
        classes = Class.query.filter_by(instructor_id=current_user.id).all()
    else:
        classes = Class.query.all()
        
    today = date.today()
    
    # Convert to dictionary
    class_list = []
    for cls in classes:
        # Count enrolled students
        enrolled_count = Enrollment.query.filter_by(class_id=cls.id).count()
        
        # Count students present today
        present_count = AttendanceRecord.query.filter_by(
            class_id=cls.id,
            date=today,
            status='Present'
        ).count()
        
        class_list.append({
            'id': cls.id,
            'classCode': cls.class_code,
            'description': cls.description,
            'schedule': cls.schedule,
            'roomNumber': cls.room_number,
            'instructorId': cls.instructor_id,
            'enrolledCount': enrolled_count,
            'presentCount': present_count,
            'date': today.strftime('%B %d %Y')
        })
    
    return jsonify(class_list)

@attendance_bp.route('/api/my-classes-today', methods=['GET'])
@login_required
def get_my_classes_today():
    """Get classes taught by the current instructor with attendance for today."""
    if current_user.role != 'instructor':
        return jsonify([])
        
    classes = Class.query.filter_by(instructor_id=current_user.id).all()
    today = date.today()
    
    class_list = []
    for cls in classes:
        # Count enrolled students
        enrolled_count = Enrollment.query.filter_by(class_id=cls.id).count()
        
        # Count students present today
        present_count = AttendanceRecord.query.filter_by(
            class_id=cls.id,
            date=today,
            status='Present'
        ).count()
        
        class_list.append({
            'id': cls.id,
            'classCode': cls.class_code,
            'description': cls.description,
            'schedule': cls.schedule,
            'roomNumber': cls.room_number,
            'enrolledCount': enrolled_count,
            'presentCount': present_count,
            'date': today.strftime('%B %d %Y')
        })
    
    return jsonify(class_list)

@attendance_bp.route('/api/class/<int:class_id>/attendance', methods=['GET'])
@login_required
def get_class_attendance(class_id):
    # Get date from request query parameters, default to today
    date_str = request.args.get('date')
    
    if date_str:
        try:
            attendance_date = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            attendance_date = date.today()
    else:
        attendance_date = date.today()
    
    # Get all students enrolled in this class
    enrollments = Enrollment.query.filter_by(class_id=class_id).all()
    
    attendance_list = []
    for enrollment in enrollments:
        student = Student.query.get(enrollment.student_id)
        
        if not student:
            continue
        
        # Check if attendance record exists for this date
        attendance = AttendanceRecord.query.filter_by(
            class_id=class_id,
            student_id=student.id,
            date=attendance_date
        ).first()
        
        status = attendance.status if attendance else 'Present'  # Default to Present
        
        attendance_list.append({
            'studentId': student.id,
            'studentName': f"{student.first_name} {student.last_name}",
            'status': status
        })
    
    return jsonify({
        'date': attendance_date.strftime('%Y-%m-%d'),
        'attendance': attendance_list
    })

@attendance_bp.route('/api/student/<string:student_id>/attendance', methods=['GET'])
@login_required
def get_student_attendance(student_id):
    # Get class ID from request
    class_id = request.args.get('class_id')
    if not class_id:
        return jsonify({'success': False, 'message': 'Class ID is required'}), 400
    
    # Get month from request, default to current month
    month_str = request.args.get('month')
    
    if month_str:
        try:
            month_date = datetime.datetime.strptime(month_str, '%Y-%m')
            year = month_date.year
            month = month_date.month
        except ValueError:
            today = date.today()
            year = today.year
            month = today.month
    else:
        today = date.today()
        year = today.year
        month = today.month
    
    # Get all attendance records for this student in this class for the given month
    first_day = date(year, month, 1)
    _, last_day_num = calendar.monthrange(year, month)
    last_day = date(year, month, last_day_num)
    
    attendance_records = AttendanceRecord.query.filter(
        AttendanceRecord.class_id == class_id,
        AttendanceRecord.student_id == student_id,
        AttendanceRecord.date >= first_day,
        AttendanceRecord.date <= last_day
    ).all()
    
    # Get the class and student information
    cls = Class.query.get(class_id)
    student = Student.query.get(student_id)
    
    if not cls or not student:
        return jsonify({'success': False, 'message': 'Class or student not found'}), 404
    
    # Generate all dates in the month based on class schedule
    # Parse schedule string (assumed format like "MWF 9:00-10:30 AM")
    schedule_days = {
        'M': 0,  # Monday
        'T': 1,  # Tuesday
        'W': 2,  # Wednesday
        'TH': 3, # Thursday
        'F': 4,  # Friday
        'S': 5   # Saturday
    }
    
    # Extract day codes from schedule (e.g. "MWF" from "MWF 9:00-10:30 AM")
    day_codes = ''.join([c for c in cls.schedule.split(' ')[0] if c.upper() in 'MTWTHFS'])
    class_days = []
    
    # Handle "TH" specially since it's two characters
    i = 0
    while i < len(day_codes):
        if i < len(day_codes) - 1 and day_codes[i:i+2].upper() == 'TH':
            class_days.append(schedule_days['TH'])
            i += 2
        else:
            class_days.append(schedule_days[day_codes[i].upper()])
            i += 1
    
    # Generate all dates in the month that match the class schedule
    class_dates = []
    current_date = first_day
    while current_date <= last_day:
        weekday = current_date.weekday()
        if weekday in class_days:
            formatted_date = current_date.strftime('%B %d %Y')
            class_dates.append(formatted_date)
        current_date += timedelta(days=1)
    
    # Format attendance records
    attendance_data = {}
    for record in attendance_records:
        formatted_date = record.date.strftime('%B %d %Y')
        attendance_data[formatted_date] = record.status
    
    # Create attendance list for all class dates
    attendance_list = []
    for date_str in class_dates:
        attendance_list.append({
            'date': date_str,
            'status': attendance_data.get(date_str, 'Present')  # Default to Present
        })
    
    # Count present and absent days
    present_count = sum(1 for date_str in class_dates if attendance_data.get(date_str, 'Present') == 'Present')
    absent_count = sum(1 for date_str in class_dates if attendance_data.get(date_str, 'Present') == 'Absent')
    
    return jsonify({
        'studentName': f"{student.first_name} {student.last_name}",
        'className': cls.description,
        'classCode': cls.class_code,
        'month': calendar.month_name[month],
        'year': year,
        'presentCount': present_count,
        'absentCount': absent_count,
        'totalDays': len(class_dates),
        'attendance': attendance_list
    })

@attendance_bp.route('/api/update', methods=['POST'])
@login_required
def update_attendance():
    data = request.get_json()
    
    if not data or not all(key in data for key in ['classId', 'studentId', 'date', 'status']):
        return jsonify({'success': False, 'message': 'Missing required attendance data'}), 400
    
    # Parse the date string
    try:
        attendance_date = datetime.datetime.strptime(data['date'], '%B %d %Y').date()
    except ValueError:
        try:
            attendance_date = datetime.datetime.strptime(data['date'], '%Y-%m-%d').date()
        except ValueError:
            return jsonify({'success': False, 'message': 'Invalid date format'}), 400
    
    # Find existing attendance record
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
        return jsonify({
            'success': True, 
            'message': 'Attendance updated successfully',
            'attendance': {
                'id': attendance.id,
                'classId': attendance.class_id,
                'studentId': attendance.student_id,
                'date': attendance_date.strftime('%B %d %Y'),
                'status': attendance.status
            }
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

@attendance_bp.route('/api/bulk-update', methods=['POST'])
@login_required
def bulk_update_attendance():
    data = request.get_json()
    
    if not data or 'records' not in data:
        return jsonify({'success': False, 'message': 'Missing attendance records'}), 400
    
    try:
        for record in data['records']:
            # Parse the date
            try:
                attendance_date = datetime.datetime.strptime(record['date'], '%Y-%m-%d').date()
            except ValueError:
                try:
                    attendance_date = datetime.datetime.strptime(record['date'], '%B %d %Y').date()
                except ValueError:
                    continue
            
            # Find existing record
            attendance = AttendanceRecord.query.filter_by(
                class_id=record['classId'],
                student_id=record['studentId'],
                date=attendance_date
            ).first()
            
            if attendance:
                # Update existing record
                attendance.status = record['status']
                attendance.marked_by = current_user.id
                attendance.marked_at = datetime.datetime.utcnow()
            else:
                # Create new record
                attendance = AttendanceRecord(
                    class_id=record['classId'],
                    student_id=record['studentId'],
                    date=attendance_date,
                    status=record['status'],
                    marked_by=current_user.id,
                    marked_at=datetime.datetime.utcnow()
                )
                db.session.add(attendance)
        
        db.session.commit()
        return jsonify({'success': True, 'message': 'Attendance records updated successfully'})
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
