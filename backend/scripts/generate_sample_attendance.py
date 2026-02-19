from __future__ import annotations
import argparse
import os
import random
import sys
from datetime import date, datetime, time, timedelta
from typing import List, Optional, Tuple
from sqlalchemy import text
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
from app import create_app
from extensions import db
from models import AttendanceRecord, AttendanceStatus, Class, ClassSession, Enrollment, InstructorAttendance
from utils.schedule_parser import get_day_code_for_date, parse_schedule_slots
STATUS_WEIGHTS = {AttendanceStatus.PRESENT: 0.75, AttendanceStatus.LATE: 0.15, AttendanceStatus.ABSENT: 0.1}

def parse_end_date(value: Optional[str]) -> date:
    if not value:
        return date.today()
    return datetime.strptime(value, '%Y-%m-%d').date()

def pick_slot_for_date(schedule_string: Optional[str], target_date: date):
    if not schedule_string:
        return None
    slots = parse_schedule_slots(schedule_string)
    if not slots:
        return None
    day_code = get_day_code_for_date(target_date)
    for slot in slots:
        if day_code in slot.get('days', []):
            return slot
    return None

def ensure_class_session(class_obj: Class, target_date: date, slot) -> Tuple[Optional[ClassSession], bool]:
    existing = ClassSession.query.filter_by(class_id=class_obj.id, date=target_date).first()
    if existing:
        return (existing, False)
    start_dt = datetime.combine(target_date, slot['start_time'])
    end_dt = datetime.combine(target_date, slot['end_time'])
    if slot.get('is_overnight') and end_dt <= start_dt:
        end_dt += timedelta(days=1)
    session = ClassSession(class_id=class_obj.id, instructor_id=class_obj.instructor_id, date=target_date, start_time=start_dt, scheduled_start_time=start_dt, scheduled_end_time=end_dt, session_room_number=class_obj.room_number)
    db.session.add(session)
    db.session.flush()
    return (session, True)

def seed_attendance_for_session(session: ClassSession, enrollments: List[Enrollment]) -> int:
    created = 0
    for enrollment in enrollments:
        already = AttendanceRecord.query.filter_by(student_id=enrollment.student_id, class_session_id=session.id).first()
        if already:
            continue
        status = random.choices(population=list(STATUS_WEIGHTS.keys()), weights=list(STATUS_WEIGHTS.values()), k=1)[0]
        time_in = None
        time_out = None
        if status != AttendanceStatus.ABSENT:
            arrival_offset = random.randint(-5, 10) if status == AttendanceStatus.PRESENT else random.randint(10, 25)
            time_in = session.scheduled_start_time + timedelta(minutes=arrival_offset)
            time_out = session.scheduled_end_time + timedelta(minutes=random.randint(0, 10))
        record = AttendanceRecord(student_id=enrollment.student_id, class_session_id=session.id, date=session.scheduled_start_time, status=status, time_in=time_in, time_out=time_out, marked_by=session.instructor_id)
        db.session.add(record)
        created += 1
    return created

def sync_sequence(model, pk_attr: str='id') -> None:
    """Advance Postgres sequence to avoid PK collisions."""
    column = getattr(model, pk_attr).property.columns[0]
    table_name = model.__table__.name
    column_name = column.name

    sequence_name = db.session.execute(
        text("SELECT pg_get_serial_sequence(:table_name, :column_name)"),
        {"table_name": f'"{table_name}"', "column_name": f'"{column_name}"'},
    ).scalar()

    if not sequence_name:
        return

    max_value = db.session.query(db.func.max(column)).scalar() or 0
    db.session.execute(
        text("SELECT setval(CAST(:sequence_name AS regclass), :next_value, false)"),
        {"sequence_name": sequence_name, "next_value": int(max_value) + 1},
    )

def ensure_instructor_attendance(session: ClassSession, class_obj: Class):
    if not class_obj.instructor_id:
        return False
    existing = InstructorAttendance.query.filter_by(instructor_id=class_obj.instructor_id, class_id=class_obj.id, date=session.date).first()
    if existing:
        return False
    eleven_am = datetime.combine(session.date, time(hour=11, minute=0))
    record = InstructorAttendance(instructor_id=class_obj.instructor_id, class_id=class_obj.id, date=session.date, status='Present', time_in=eleven_am, time_out=session.scheduled_end_time)
    db.session.add(record)
    return True

def generate_samples(days: int, end_date: date):
    sync_sequence(ClassSession)
    sync_sequence(AttendanceRecord)
    sync_sequence(InstructorAttendance)
    classes = Class.query.all()
    total_sessions = 0
    total_attendance = 0
    total_instructor = 0
    for class_obj in classes:
        if not class_obj.schedule:
            continue
        enrollments = Enrollment.query.filter_by(class_id=class_obj.id).all()
        if not enrollments:
            continue
        for offset in range(days):
            target_date = end_date - timedelta(days=offset)
            slot = pick_slot_for_date(class_obj.schedule, target_date)
            if not slot:
                continue
            session, created_session = ensure_class_session(class_obj, target_date, slot)
            if not session:
                continue
            if created_session:
                total_sessions += 1
            total_attendance += seed_attendance_for_session(session, enrollments)
            if ensure_instructor_attendance(session, class_obj):
                total_instructor += 1
    db.session.commit()
    return (total_sessions, total_attendance, total_instructor)

def main():
    parser = argparse.ArgumentParser(description='Generate sample class sessions and attendance records.')
    parser.add_argument('--days', type=int, default=6, help='How many days to backfill including end date (default 6)')
    parser.add_argument('--end-date', type=str, default=None, help='End date in YYYY-MM-DD (default today)')
    args = parser.parse_args()
    days = max(1, args.days)
    end_date = parse_end_date(args.end_date)
    app = create_app()
    with app.app_context():
        sessions_created, attendance_created, instructor_created = generate_samples(days, end_date)
if __name__ == '__main__':
    main()
