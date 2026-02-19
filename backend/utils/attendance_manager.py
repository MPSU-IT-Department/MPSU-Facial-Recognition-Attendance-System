from datetime import datetime, timedelta, date
from typing import Optional, Dict, List, Tuple, TYPE_CHECKING
import re
from math import radians, sin, cos, sqrt, atan2
from utils.timezone import pst_now_naive
if TYPE_CHECKING:
    from models import User

class AttendanceTimeValidator:
    """Handles time window validation for attendance check-ins"""
    GRACE_PERIOD_MINUTES = 15
    ABSENT_THRESHOLD_MINUTES = 45
    EARLY_CHECKIN_MINUTES = 30

    @staticmethod
    def is_within_grace_period(actual_start_time: datetime, checkin_time: datetime) -> bool:
        """Check if actual check-in time is within grace period of actual start time"""
        time_diff = abs((checkin_time - actual_start_time).total_seconds() / 60)
        return time_diff <= AttendanceTimeValidator.GRACE_PERIOD_MINUTES

    @staticmethod
    def is_valid_checkin_time(actual_start_time: datetime, checkin_time: datetime) -> Tuple[bool, str]:
        """Validate if check-in time is within acceptable range based on actual start time (when instructor clicked class)"""
        time_diff = (checkin_time - actual_start_time).total_seconds() / 60
        if time_diff < -AttendanceTimeValidator.EARLY_CHECKIN_MINUTES:
            return (False, 'Too early for check-in')
        elif time_diff > AttendanceTimeValidator.ABSENT_THRESHOLD_MINUTES:
            return (False, 'Too late for check-in')
        return (True, 'Valid check-in time')

    @staticmethod
    def determine_attendance_status(actual_start_time: datetime, checkin_time: datetime) -> str:
        """
        Determine attendance status based on check-in time relative to actual class start time.
        
        Logic:
        - If scanned within 15 minutes after actual start → PRESENT (on time)
        - If scanned more than 15 minutes but less than 45 minutes after actual start → LATE
        - If scanned 45 minutes or more after actual start → ABSENT
        - Students who never check in are marked ABSENT at instructor checkout
        
        Args:
            actual_start_time: The actual time when instructor clicked the class (actual start time)
            checkin_time: The time when student checked in
        
        Returns: 'Present', 'Late', or 'Absent'
        """
        time_diff = (checkin_time - actual_start_time).total_seconds() / 60
        if time_diff <= AttendanceTimeValidator.GRACE_PERIOD_MINUTES:
            return 'Present'
        elif time_diff >= AttendanceTimeValidator.ABSENT_THRESHOLD_MINUTES:
            return 'Absent'
        else:
            return 'Late'

class AttendanceStatusManager:
    """Manages attendance status determination and special cases"""

    @staticmethod
    def get_attendance_status(actual_start_time: datetime, checkin_time: datetime, is_leave: bool=False, is_holiday: bool=False) -> str:
        """Determine attendance status considering special cases"""
        if is_holiday:
            return 'Holiday'
        if is_leave:
            return 'On Leave'
        return AttendanceTimeValidator.determine_attendance_status(actual_start_time, checkin_time)

class LocationValidator:
    """Validates check-in location against expected class location"""
    MAX_DISTANCE_METERS = 50

    @staticmethod
    def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate distance between two points using Haversine formula"""
        R = 6371000
        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
        c = 2 * atan2(sqrt(a), sqrt(1 - a))
        distance = R * c
        return distance

    @staticmethod
    def validate_checkin_location(instructor_id: int, class_id: int, location_data: Dict[str, float]) -> Tuple[bool, str]:
        """Validate if check-in location is within acceptable range of class location"""
        try:
            from models import Class
            from extensions import db
            class_obj = Class.query.get(class_id)
            if not class_obj:
                return (False, 'Class not found')
            class_lat = class_obj.latitude
            class_lon = class_obj.longitude
            if not class_lat or not class_lon:
                return (True, 'Location validation skipped - no class location set')
            distance = LocationValidator.calculate_distance(class_lat, class_lon, location_data['latitude'], location_data['longitude'])
            if distance <= LocationValidator.MAX_DISTANCE_METERS:
                return (True, 'Location verified')
            else:
                return (False, f'Location mismatch - {distance:.1f}m from expected location')
        except Exception as e:
            return (False, 'Location validation failed')

class AttendanceNotifier:
    """Handles real-time notifications for attendance events"""

    @staticmethod
    def send_notification(instructor_id: int, status: str, checkin_time: datetime, notification_type: str='all') -> bool:
        """Send notification through specified channels"""
        try:
            from models import User
            from extensions import db
            instructor = User.query.get(instructor_id)
            if not instructor:
                return False
            message = AttendanceNotifier._generate_notification_message(instructor, status, checkin_time)
            if notification_type in ['email', 'all']:
                AttendanceNotifier._send_email_notification(instructor.email, message)
            if notification_type in ['sms', 'all']:
                AttendanceNotifier._send_sms_notification(instructor.phone, message)
            if notification_type in ['in_app', 'all']:
                AttendanceNotifier._send_in_app_notification(instructor_id, message)
            return True
        except Exception as e:
            return False

    @staticmethod
    def _generate_notification_message(instructor: 'User', status: str, checkin_time: datetime) -> str:
        """Generate notification message based on attendance status"""
        time_str = checkin_time.strftime('%I:%M %p')
        return f'Attendance marked as {status} at {time_str}'

    @staticmethod
    def _send_email_notification(email: str, message: str) -> None:
        """Send email notification"""
        pass

    @staticmethod
    def _send_sms_notification(phone: str, message: str) -> None:
        """Send SMS notification"""
        pass

    @staticmethod
    def _send_in_app_notification(user_id: int, message: str) -> None:
        """Send in-app notification"""
        pass

class AttendanceAnalytics:
    """Generates attendance analytics and reports"""

    @staticmethod
    def calculate_attendance_metrics(instructor_id: int, month: int, year: int) -> Dict:
        """Calculate comprehensive attendance metrics"""
        try:
            from models import InstructorAttendance, Class
            from extensions import db
            first_day = date(year, month, 1)
            last_day = date(year, month + 1, 1) - timedelta(days=1)
            records = InstructorAttendance.query.filter(InstructorAttendance.instructor_id == instructor_id, InstructorAttendance.date >= first_day, InstructorAttendance.date <= last_day).all()
            total_days = len(records)
            status_counts = {'Present': 0, 'Absent': 0}
            for record in records:
                status_counts[record.status] += 1
            present_rate = status_counts['Present'] / total_days * 100 if total_days > 0 else 0
            classes = Class.query.filter_by(instructor_id=instructor_id).all()
            class_analysis = {}
            for cls in classes:
                class_records = [r for r in records if r.class_id == cls.id]
                class_total = len(class_records)
                class_present = sum((1 for r in class_records if r.status == 'Present'))
                class_analysis[cls.class_code] = {'total_sessions': class_total, 'attendance_rate': class_present / class_total * 100 if class_total > 0 else 0}
            return {'basic_metrics': {'total_days': total_days, 'status_counts': status_counts, 'present_rate': round(present_rate, 1)}, 'class_analysis': class_analysis}
        except Exception as e:
            return {}

class AttendanceReporter:
    """Generates detailed attendance reports"""

    @staticmethod
    def generate_attendance_report(instructor_id: int, start_date: date, end_date: date) -> Dict:
        """Generate comprehensive attendance report"""
        try:
            from models import InstructorAttendance, Class
            from extensions import db
            records = InstructorAttendance.query.filter(InstructorAttendance.instructor_id == instructor_id, InstructorAttendance.date >= start_date, InstructorAttendance.date <= end_date).order_by(InstructorAttendance.date).all()
            summary = {'total_days': len(records), 'status_counts': {'Present': 0, 'Absent': 0}, 'attendance_rate': 0}
            detailed_records = []
            for record in records:
                summary['status_counts'][record.status] += 1
                class_name = record.class_ref.class_code if record.class_ref else 'General Attendance'
                detailed_records.append({'date': record.date.strftime('%Y-%m-%d'), 'status': record.status, 'class': class_name, 'notes': record.notes})
            total_days = summary['total_days']
            if total_days > 0:
                summary['attendance_rate'] = round(summary['status_counts']['Present'] / total_days * 100, 1)
                summary['late_rate'] = round(summary['status_counts']['Late'] / total_days * 100, 1)
            return {'summary': summary, 'detailed_records': detailed_records, 'recommendations': AttendanceReporter._generate_recommendations(summary)}
        except Exception as e:
            return {}

    @staticmethod
    def _generate_recommendations(summary: Dict) -> List[str]:
        """Generate recommendations based on attendance data"""
        recommendations = []
        if summary['attendance_rate'] < 90:
            recommendations.append('Consider improving attendance rate')
        if summary['late_rate'] > 10:
            recommendations.append('High late arrival rate - consider earlier arrival')
        if summary['status_counts']['Absent'] > 0:
            recommendations.append('Address absences with instructor')
        return recommendations

class ScheduleManager:
    """Manages class schedules and schedule-related operations"""

    @staticmethod
    def get_scheduled_classes(instructor_id: int, date: date) -> List[Dict]:
        """Get all classes scheduled for an instructor on a specific date"""
        try:
            from models import Class
            from extensions import db
            classes = Class.query.filter_by(instructor_id=instructor_id).all()
            scheduled_classes = []
            for cls in classes:
                if ScheduleManager._is_class_scheduled(cls.schedule, date):
                    scheduled_classes.append({'id': cls.id, 'code': cls.class_code, 'description': cls.description, 'room': cls.room_number, 'schedule': cls.schedule})
            return scheduled_classes
        except Exception as e:
            return []

    @staticmethod
    def _is_class_scheduled(schedule: str, date: date) -> bool:
        """Check if a class is scheduled for a specific date"""
        try:
            day_abbr = ScheduleManager._get_day_abbreviation(date.weekday())
            schedule_parts = schedule.split(',')
            for part in schedule_parts:
                if day_abbr in part.split()[0]:
                    return True
            return False
        except Exception as e:
            return False

    @staticmethod
    def _get_day_abbreviation(weekday: int) -> str:
        """Convert weekday number to abbreviation"""
        return ['M', 'T', 'W', 'TH', 'F', 'S', 'U'][weekday]

class AttendanceLogger:
    """Handles logging of attendance-related events"""

    @staticmethod
    def log_attendance_event(instructor_id: int, status: str, error: Optional[str]=None) -> None:
        """Log attendance-related events"""
        try:
            from models import AttendanceLog
            from extensions import db
            log_entry = AttendanceLog(instructor_id=instructor_id, event_type='attendance', status=status, error_message=error, timestamp=pst_now_naive())
            db.session.add(log_entry)
            db.session.commit()
        except Exception as e:
            pass

