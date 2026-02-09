from enum import Enum


class AttendanceStatus(str, Enum):
    PRESENT = 'present'
    ABSENT = 'absent'
    LATE = 'late'