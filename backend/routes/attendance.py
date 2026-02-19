from flask import Blueprint, render_template, redirect, url_for, request, jsonify, flash, current_app
from flask_login import login_required, current_user
import datetime
from datetime import date, timedelta
from utils.timezone import get_pst_now, pst_now_naive
import calendar
from sqlalchemy import func
from extensions import db
from models import User, Class, Student, Enrollment, AttendanceRecord, FaceEncoding, ClassSession, AttendanceStatus, InstructorAttendance
from decorators import admin_required, instructor_required
attendance_bp = Blueprint('attendance', __name__, url_prefix='/attendance')

def _get_payload_value(payload, *keys, default=None):
    if not payload:
        return default
    for key in keys:
        if key in payload and payload[key] not in (None, ''):
            return payload[key]
    return default

def _normalize_status(raw_status):
    if isinstance(raw_status, AttendanceStatus):
        return raw_status
    text = str(raw_status or '').strip().lower()
    mapping = {
        'present': AttendanceStatus.PRESENT,
        'absent': AttendanceStatus.ABSENT,
        'late': AttendanceStatus.LATE,
    }
    return mapping.get(text)

@attendance_bp.route('/api/classes', methods=['GET'])
@login_required
def get_classes_with_attendance():
    if current_user.role == 'instructor':
        classes = Class.query.filter_by(instructor_id=current_user.id).all()
    else:
        classes = Class.query.all()
    today = date.today()
    class_list = []
    for cls in classes:
        enrolled_count = Enrollment.query.filter_by(class_id=cls.id).count()
        present_count = AttendanceRecord.query.filter(AttendanceRecord.class_id == cls.id, func.date(AttendanceRecord.date) == today, AttendanceRecord.status == AttendanceStatus.PRESENT).count()
        class_list.append({'id': cls.id, 'ClassID': cls.id, 'classCode': cls.class_code, 'ClassCode': cls.class_code, 'className': cls.class_name or cls.description, 'ClassName': cls.class_name or cls.description, 'description': cls.description, 'schedule': cls.schedule, 'roomNumber': cls.room_number, 'RoomNumber': cls.room_number, 'instructorId': cls.instructor_id, 'InstructorID': cls.instructor_id, 'enrolledCount': enrolled_count, 'presentCount': present_count, 'date': today.strftime('%B %d %Y')})
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
        enrolled_count = Enrollment.query.filter_by(class_id=cls.id).count()
        present_count = AttendanceRecord.query.filter(AttendanceRecord.class_id == cls.id, func.date(AttendanceRecord.date) == today, AttendanceRecord.status == AttendanceStatus.PRESENT).count()
        class_list.append({'id': cls.id, 'ClassID': cls.id, 'classCode': cls.class_code, 'ClassCode': cls.class_code, 'className': cls.class_name or cls.description, 'ClassName': cls.class_name or cls.description, 'description': cls.description, 'schedule': cls.schedule, 'roomNumber': cls.room_number, 'RoomNumber': cls.room_number, 'enrolledCount': enrolled_count, 'presentCount': present_count, 'date': today.strftime('%B %d %Y')})
    return jsonify(class_list)

@attendance_bp.route('/api/class/<int:class_id>/attendance', methods=['GET'])
@login_required
def get_class_attendance(class_id):
    try:
        if current_user.role == 'instructor':
            class_obj = Class.query.filter_by(id=class_id, instructor_id=current_user.id).first()
            if not class_obj:
                return (jsonify({'success': False, 'message': 'Class not found or not authorized'}), 403)
        elif current_user.role != 'admin':
            return (jsonify({'success': False, 'message': 'Unauthorized'}), 403)
        date_str = request.args.get('date')
        if date_str:
            try:
                attendance_date = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                attendance_date = date.today()
            enrollments = Enrollment.query.filter_by(class_id=class_id).all()
            attendance_list = []
            for enrollment in enrollments:
                student = Student.query.get(enrollment.student_id)
                if not student:
                    continue
                class_session = ClassSession.query.filter_by(class_id=class_id, date=attendance_date).first()
                if class_session:
                    attendance = AttendanceRecord.query.filter_by(class_session_id=class_session.id, student_id=student.id).first()
                else:
                    attendance = None
                if attendance:
                    status = attendance.status.value if attendance.status else 'Absent'
                    time_in = attendance.time_in.strftime('%H:%M') if attendance.time_in else None
                    time_out = attendance.time_out.strftime('%H:%M') if attendance.time_out else None
                else:
                    status = 'Absent'
                    time_in = None
                    time_out = None
                attendance_list.append({'studentId': student.id, 'studentName': f'{student.first_name} {student.last_name}', 'status': status, 'time_in': time_in, 'time_out': time_out})
            return jsonify({'date': attendance_date.strftime('%Y-%m-%d'), 'attendance': attendance_list})
        else:
            class_sessions = ClassSession.query.filter_by(class_id=class_id).order_by(ClassSession.date).all()
            enrollments = Enrollment.query.filter_by(class_id=class_id).all()
            students = [Student.query.get(e.student_id) for e in enrollments if Student.query.get(e.student_id)]
            session_ids = [cs.id for cs in class_sessions]
            attendance_records = AttendanceRecord.query.filter(AttendanceRecord.class_session_id.in_(session_ids)).all()
            attendance_by_date = {}
            dates = set()
            for cs in class_sessions:
                date_str = cs.date.strftime('%Y-%m-%d')
                dates.add(date_str)
                attendance_by_date[date_str] = {}
                for student in students:
                    attendance_by_date[date_str][student.id] = 'A'
            for record in attendance_records:
                session = next((cs for cs in class_sessions if cs.id == record.class_session_id), None)
                if session:
                    date_str = session.date.strftime('%Y-%m-%d')
                    status = record.status.value if record.status else 'Absent'
                    attendance_by_date[date_str][record.student_id] = status[0]
            dates = sorted(list(dates))
            student_attendance = []
            for student in students:
                student_data = {'studentId': student.id, 'studentName': f'{student.first_name} {student.last_name}', 'attendance': {}}
                for date_str in dates:
                    student_data['attendance'][date_str] = attendance_by_date[date_str].get(student.id, 'A')
                student_attendance.append(student_data)
            return jsonify({'dates': dates, 'students': student_attendance})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return (jsonify({'error': str(e)}), 500)

@attendance_bp.route('/api/student/<string:student_id>/attendance', methods=['GET'])
@login_required
@instructor_required
def get_student_attendance(student_id):
    class_id = request.args.get('class_id')
    if not class_id:
        return (jsonify({'success': False, 'message': 'Class ID is required'}), 400)
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
    first_day = date(year, month, 1)
    _, last_day_num = calendar.monthrange(year, month)
    last_day = date(year, month, last_day_num)
    class_sessions_in_month = ClassSession.query.filter(ClassSession.class_id == class_id, ClassSession.date >= first_day, ClassSession.date <= last_day).all()
    session_ids_in_month = [session.id for session in class_sessions_in_month]
    attendance_records = AttendanceRecord.query.filter(AttendanceRecord.class_session_id.in_(session_ids_in_month), AttendanceRecord.student_id == student_id).order_by(AttendanceRecord.date.asc()).all()
    cls = Class.query.get(class_id)
    student = Student.query.get(student_id)
    if not cls or not student:
        return (jsonify({'success': False, 'message': 'Class or student not found'}), 404)
    if current_user.role == 'instructor':
        if cls.instructor_id != current_user.id:
            return (jsonify({'success': False, 'message': 'Class not found or not authorized'}), 403)
    elif current_user.role != 'admin':
        return (jsonify({'success': False, 'message': 'Unauthorized'}), 403)
    enrollment = Enrollment.query.filter_by(class_id=class_id, student_id=student_id).first()
    if not enrollment:
        return (jsonify({'success': False, 'message': 'Student not enrolled in this class'}), 404)
    class_dates_in_month = sorted([session.date for session in class_sessions_in_month])
    attendance_lookup = {}
    for record in attendance_records:
        session = next((s for s in class_sessions_in_month if s.id == record.class_session_id), None)
        if session:
            formatted_date = session.date.strftime('%B %d %Y')
            attendance_lookup[formatted_date] = {'status': record.status, 'attendance_id': record.id}
    attendance_list = []
    present_count = 0
    absent_count = 0
    late_count = 0
    for class_date in class_dates_in_month:
        formatted_date = class_date.strftime('%B %d %Y')
        record_data = attendance_lookup.get(formatted_date)
        if record_data:
            status = record_data['status']
            attendance_id = record_data['attendance_id']
        else:
            status = 'Absent'
            attendance_id = None
        attendance_list.append({'date': formatted_date, 'status': status, 'attendance_id': attendance_id})
        if status == 'Present':
            present_count += 1
        elif status == 'Absent':
            absent_count += 1
        elif status == 'Late':
            late_count += 1
    return jsonify({'success': True, 'studentName': f'{student.first_name} {student.last_name}', 'className': cls.description, 'classCode': cls.class_code, 'month': calendar.month_name[month], 'year': year, 'presentCount': present_count, 'absentCount': absent_count, 'lateCount': late_count, 'attendance': attendance_list})

@attendance_bp.route('/api/attendance/<class_id>/<student_id>/<date>', methods=['PUT'])
@login_required
def update_attendance(class_id, student_id, date):
    data = request.get_json()
    if not data or 'status' not in data:
        return (jsonify({'success': False, 'message': 'Missing status field'}), 400)
    try:
        attendance_date = datetime.datetime.strptime(date, '%Y-%m-%d').date()
    except ValueError:
        return (jsonify({'success': False, 'message': 'Invalid date format'}), 400)
    try:
        class_id_int = int(class_id)
    except (TypeError, ValueError):
        return (jsonify({'success': False, 'message': 'Invalid class ID'}), 400)
    status_enum = _normalize_status(data.get('status'))
    if not status_enum:
        return (jsonify({'success': False, 'message': 'Invalid status value'}), 400)
    attendance = AttendanceRecord.query.filter_by(class_id=class_id_int, student_id=student_id, date=attendance_date).first()
    if attendance:
        attendance.status = status_enum
        attendance.marked_by = current_user.id
        attendance.marked_at = pst_now_naive()
    else:
        attendance = AttendanceRecord(class_id=class_id_int, student_id=student_id, date=attendance_date, status=status_enum, marked_by=current_user.id, marked_at=pst_now_naive())
        db.session.add(attendance)
    try:
        db.session.commit()
        return jsonify({'success': True, 'message': 'Attendance updated successfully', 'attendance': {'id': attendance.id, 'StudentAttendanceID': attendance.id, 'classId': attendance.class_id, 'ClassID': attendance.class_id, 'studentId': attendance.student_id, 'StudentID': attendance.student_id, 'date': attendance_date.strftime('%B %d %Y'), 'status': attendance.status.value if attendance.status else None}})
    except Exception as e:
        db.session.rollback()
        return (jsonify({'success': False, 'message': str(e)}), 500)

@attendance_bp.route('/api/bulk-update', methods=['POST'])
@login_required
def bulk_update_attendance():
    data = request.get_json()
    if not data or 'records' not in data:
        return (jsonify({'success': False, 'message': 'Missing attendance records'}), 400)
    try:
        for record in data['records']:
            class_id = _get_payload_value(record, 'classId', 'class_id', 'ClassID')
            student_id = _get_payload_value(record, 'studentId', 'student_id', 'StudentID')
            date_value = _get_payload_value(record, 'date', 'Date')
            raw_status = _get_payload_value(record, 'status', 'Status')
            status_enum = _normalize_status(raw_status)
            if not class_id or not student_id or not date_value or not status_enum:
                return (jsonify({'success': False, 'message': 'Missing or empty required field in one or more attendance records.'}), 400)
            if current_user.role == 'instructor':
                class_obj = Class.query.filter_by(id=class_id, instructor_id=current_user.id).first()
                if not class_obj:
                    return (jsonify({'success': False, 'message': f'Class ID {class_id} not found or not authorized for one or more records.'}), 403)
            elif current_user.role != 'admin':
                return (jsonify({'success': False, 'message': 'Unauthorized to perform bulk attendance update.'}), 403)
            enrollment = Enrollment.query.filter_by(student_id=student_id, class_id=class_id).first()
            if not enrollment:
                return (jsonify({'success': False, 'message': f'Student ID {student_id} not enrolled in Class ID {class_id} for one or more records.'}), 400)
            try:
                attendance_date = datetime.datetime.strptime(str(date_value), '%Y-%m-%d').date()
            except ValueError:
                try:
                    attendance_date = datetime.datetime.strptime(str(date_value), '%B %d %Y').date()
                except ValueError:
                    continue
            attendance = AttendanceRecord.query.filter_by(class_id=class_id, student_id=student_id, date=attendance_date).first()
            if attendance:
                attendance.status = status_enum
                attendance.marked_by = current_user.id
                attendance.marked_at = pst_now_naive()
            else:
                attendance = AttendanceRecord(class_id=class_id, student_id=student_id, date=attendance_date, status=status_enum, marked_by=current_user.id, marked_at=pst_now_naive())
                db.session.add(attendance)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Attendance records updated successfully'})
    except Exception as e:
        db.session.rollback()
        return (jsonify({'success': False, 'message': str(e)}), 500)

@attendance_bp.route('/manual', methods=['POST'])
@login_required
@instructor_required
def add_manual_attendance():
    try:
        data = request.get_json()
        if not data:
            return (jsonify({'error': 'No data provided'}), 400)
        student_id = _get_payload_value(data, 'student_id', 'studentId', 'StudentID')
        class_id = _get_payload_value(data, 'class_id', 'classId', 'ClassID')
        date_str = _get_payload_value(data, 'date', 'Date')
        status_str = _get_payload_value(data, 'status', 'Status')
        if not all((student_id, class_id, date_str, status_str)):
            return (jsonify({'error': 'Missing required fields'}), 400)
        try:
            attendance_date = datetime.datetime.strptime(str(date_str), '%Y-%m-%d').date()
            if attendance_date > get_pst_now().date():
                return (jsonify({'error': 'Cannot add attendance for future dates'}), 400)
        except ValueError:
            return (jsonify({'error': 'Invalid date format'}), 400)
        class_obj = Class.query.filter_by(id=class_id, instructor_id=current_user.id).first()
        if not class_obj:
            return (jsonify({'error': 'Class not found or not authorized'}), 403)
        enrollment = Enrollment.query.filter_by(student_id=student_id, class_id=class_id).first()
        if not enrollment:
            return (jsonify({'error': 'Student not enrolled in this class'}), 400)
        class_session = ClassSession.query.filter_by(class_id=class_id, date=attendance_date).first()
        if not class_session:
            now = pst_now_naive()
            scheduled_start_time = datetime.time(hour=9, minute=0)
            try:
                schedule_parts = class_obj.schedule.split()
                if len(schedule_parts) > 1:
                    time_str = schedule_parts[-1]
                    import re
                    time_match = re.search('\\d{1,2}:\\d{2}(?:[ ]?(?:AM|PM))?', class_obj.schedule, re.IGNORECASE)
                    if time_match:
                        time_obj = datetime.datetime.strptime(time_match.group(0), '%I:%M %p').time() if 'AM' in time_match.group(0).upper() or 'PM' in time_match.group(0).upper() else datetime.datetime.strptime(time_match.group(0), '%H:%M').time()
                        scheduled_start_time = time_obj
            except Exception as e:
                pass
            class_session = ClassSession(class_id=class_id, instructor_id=current_user.id, date=attendance_date, start_time=datetime.datetime.combine(attendance_date, get_pst_now().time()), scheduled_start_time=datetime.datetime.combine(attendance_date, scheduled_start_time), is_attendance_processed=False, session_room_number=getattr(class_obj, 'room_number', None))
            db.session.add(class_session)
            db.session.flush()
        existing_attendance = AttendanceRecord.query.filter_by(class_session_id=class_session.id, student_id=student_id).first()
        status_enum = _normalize_status(status_str)
        if not status_enum:
            return (jsonify({'error': 'Invalid status'}), 400)
        if existing_attendance:
            existing_attendance.status = status_enum
            existing_attendance.class_id = class_id
            existing_attendance.time_in = pst_now_naive() if status_enum == AttendanceStatus.PRESENT else existing_attendance.time_in
            db.session.commit()
            return (jsonify({'success': True, 'message': 'Attendance record updated successfully', 'attendance': {'id': existing_attendance.id, 'StudentAttendanceID': existing_attendance.id, 'student_id': existing_attendance.student_id, 'StudentID': existing_attendance.student_id, 'class_id': existing_attendance.class_id, 'ClassID': existing_attendance.class_id, 'class_session_id': existing_attendance.class_session_id, 'date': attendance_date.strftime('%Y-%m-%d'), 'status': existing_attendance.status.value if existing_attendance.status else 'absent'}}), 200)
        new_attendance = AttendanceRecord(class_id=class_id, class_session_id=class_session.id, student_id=student_id, status=status_enum, date=pst_now_naive())
        db.session.add(new_attendance)
        db.session.commit()
        return (jsonify({'success': True, 'message': 'Attendance record added successfully', 'attendance': {'id': new_attendance.id, 'StudentAttendanceID': new_attendance.id, 'student_id': new_attendance.student_id, 'StudentID': new_attendance.student_id, 'class_id': new_attendance.class_id, 'ClassID': new_attendance.class_id, 'class_session_id': new_attendance.class_session_id, 'date': attendance_date.strftime('%Y-%m-%d'), 'status': new_attendance.status.value if new_attendance.status else 'absent'}}), 201)
    except Exception as e:
        return (jsonify({'error': str(e)}), 500)

@attendance_bp.route('/update', methods=['PUT'])
@login_required
def update_manual_attendance():
    try:
        data = request.get_json()
        student_id = _get_payload_value(data, 'student_id', 'studentId', 'StudentID')
        class_id = _get_payload_value(data, 'class_id', 'classId', 'ClassID')
        date_str = _get_payload_value(data, 'date', 'Date')
        status_str = _get_payload_value(data, 'status', 'Status')
        if not all((student_id, class_id, date_str, status_str)):
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
            status_enum = _normalize_status(status_str)
            if not status_enum:
                return (jsonify({'success': False, 'message': 'Invalid status value'}), 400)
            attendance_record.status = status_enum
            attendance_record.class_id = class_id
            attendance_record.updated_at = pst_now_naive()
            db.session.commit()
            return jsonify({'success': True, 'message': 'Attendance record updated successfully'})
        except Exception as e:
            db.session.rollback()
            return (jsonify({'success': False, 'message': f'Database error: {str(e)}'}), 500)
    except Exception as e:
        db.session.rollback()
        return (jsonify({'success': False, 'message': str(e)}), 500)

@attendance_bp.route('/api/instructor/update', methods=['POST'])
@login_required
@admin_required
def update_instructor_attendance():
    data = request.get_json()
    if not data:
        return (jsonify({'success': False, 'message': 'No data provided'}), 400)
    class_id = _get_payload_value(data, 'classId', 'class_id', 'ClassID')
    instructor_name = _get_payload_value(data, 'instructorName', 'instructor_name', 'InstructorName')
    date_str = _get_payload_value(data, 'date', 'Date')
    status = _get_payload_value(data, 'status', 'Status')
    time_in = _get_payload_value(data, 'timeIn', 'time_in', 'TimeIn')
    if not all([class_id, instructor_name, date_str]):
        return (jsonify({'success': False, 'message': 'Missing required fields'}), 400)
    try:
        try:
            attendance_date = datetime.datetime.strptime(date_str, '%B %d, %Y').date()
        except ValueError:
            attendance_date = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return (jsonify({'success': False, 'message': 'Invalid date format'}), 400)
    name_parts = instructor_name.split(' ', 1)
    if len(name_parts) != 2:
        return (jsonify({'success': False, 'message': 'Invalid instructor name format'}), 400)
    first_name, last_name = name_parts
    instructor = User.query.filter_by(first_name=first_name, last_name=last_name, role='instructor').first()
    if not instructor:
        return (jsonify({'success': False, 'message': 'Instructor not found'}), 404)
    class_obj = Class.query.get(class_id)
    if not class_obj:
        return (jsonify({'success': False, 'message': 'Class not found'}), 404)
    class_session = ClassSession.query.filter_by(class_id=class_id, date=attendance_date).first()
    attendance = InstructorAttendance.query.filter_by(instructor_id=instructor.id, class_id=class_id, date=attendance_date).first()
    if attendance:
        if status:
            attendance.status = status
        if time_in:
            attendance.time_in = datetime.datetime.combine(attendance_date, datetime.datetime.strptime(time_in, '%H:%M').time())
        if class_session and not attendance.class_session_id:
            attendance.class_session_id = class_session.id
    else:
        time_in_dt = None
        if time_in:
            time_in_dt = datetime.datetime.combine(attendance_date, datetime.datetime.strptime(time_in, '%H:%M').time())
        attendance = InstructorAttendance(instructor_id=instructor.id, class_id=class_id, class_session_id=class_session.id if class_session else None, date=attendance_date, status=status or 'Present', time_in=time_in_dt)
        db.session.add(attendance)
    try:
        db.session.commit()
        return jsonify({'success': True, 'message': 'Attendance updated successfully'})
    except Exception as e:
        db.session.rollback()
        return (jsonify({'success': False, 'message': str(e)}), 500)

@attendance_bp.route('/api/instructor/get', methods=['GET'])
@login_required
@admin_required
def get_instructor_attendance():
    class_id = request.args.get('classId')
    if not class_id:
        return (jsonify({'success': False, 'message': 'Missing classId'}), 400)
    class_obj = Class.query.get(class_id)
    if not class_obj or not class_obj.instructor_id:
        return (jsonify([]), 200)
    instructor_id = class_obj.instructor_id
    attendance_records = InstructorAttendance.query.filter_by(instructor_id=instructor_id, class_id=class_id).order_by(InstructorAttendance.date.desc()).all()
    attendance_data = []
    for attendance in attendance_records:
        attendance_data.append({'date': attendance.date.strftime('%B %d, %Y'), 'status': attendance.status, 'time_in': attendance.time_in.strftime('%I:%M %p') if attendance.time_in else None, 'time_out': attendance.time_out.strftime('%I:%M %p') if attendance.time_out else None})
    return jsonify(attendance_data)
