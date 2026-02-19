"""Align physical table/column names to ERD entities

Revision ID: 20260219_entity_name_alignment
Revises: 20260219_erd_alignment
Create Date: 2026-02-19 16:40:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260219_entity_name_alignment"
down_revision = "20260219_erd_alignment"
branch_labels = None
depends_on = None


def _inspector():
    return sa.inspect(op.get_bind())


def _has_table(table_name):
    return table_name in _inspector().get_table_names()


def _has_column(table_name, column_name):
    if not _has_table(table_name):
        return False
    return any(col["name"] == column_name for col in _inspector().get_columns(table_name))


def _rename_table_if_needed(old_name, new_name):
    if _has_table(old_name) and not _has_table(new_name):
        op.rename_table(old_name, new_name)


def _rename_column_if_needed(table_name, old_name, new_name):
    if _has_column(table_name, old_name) and not _has_column(table_name, new_name):
        op.alter_column(table_name, old_name, new_column_name=new_name)


def _rename_columns(table_name, mapping):
    for old_name, new_name in mapping:
        _rename_column_if_needed(table_name, old_name, new_name)


def upgrade():
    _rename_table_if_needed("courses", "Course")
    _rename_table_if_needed("users", "Instructor")
    _rename_table_if_needed("students", "Student")
    _rename_table_if_needed("classes", "Class")
    _rename_table_if_needed("enrollments", "Enrolled")
    _rename_table_if_needed("attendance_records", "StudentAttendance")
    _rename_table_if_needed("instructor_attendance", "InstructorAttendance")

    _rename_columns(
        "Course",
        [
            ("id", "CourseID"),
            ("code", "CourseCode"),
            ("description", "CourseDescription"),
        ],
    )

    _rename_columns(
        "Instructor",
        [
            ("id", "InstructorID"),
            ("first_name", "FirstName"),
            ("middle_name", "MiddleName"),
            ("last_name", "LastName"),
            ("department", "Department"),
            ("school_year", "SchoolYear"),
            ("term", "Term"),
            ("face_encoding", "FaceEncoding"),
            ("image_path", "ImagePath"),
        ],
    )

    _rename_columns(
        "Student",
        [
            ("id", "StudentID"),
            ("first_name", "FirstName"),
            ("middle_name", "MiddleName"),
            ("last_name", "LastName"),
            ("year_level", "YearLevel"),
            ("department", "Department"),
            ("face_encoding", "FaceEncoding"),
            ("image_path", "ImagePath"),
        ],
    )

    _rename_columns(
        "Class",
        [
            ("id", "ClassID"),
            ("class_code", "ClassCode"),
            ("class_name", "ClassName"),
            ("description", "ClassDescription"),
            ("class_date", "Date"),
            ("class_time", "Time"),
            ("room_number", "RoomNumber"),
            ("school_year", "SchoolYear"),
            ("term", "Term"),
            ("course_id", "CourseID"),
            ("instructor_id", "InstructorID"),
            ("substitute_instructor_id", "SubstituteInstructorID"),
            ("schedule", "Schedule"),
        ],
    )

    _rename_columns(
        "Enrolled",
        [
            ("id", "EnrollmentID"),
            ("school_year", "SchoolYear"),
            ("term", "Term"),
            ("class_id", "ClassID"),
            ("student_id", "StudentID"),
        ],
    )

    _rename_columns(
        "StudentAttendance",
        [
            ("id", "StudentAttendanceID"),
            ("date", "Date"),
            ("attendance_time", "Time"),
            ("class_id", "ClassID"),
            ("student_id", "StudentID"),
            ("class_session_id", "ClassSessionID"),
        ],
    )

    _rename_columns(
        "InstructorAttendance",
        [
            ("id", "InstructorAttendanceID"),
            ("date", "Date"),
            ("attendance_time", "Time"),
            ("class_id", "ClassID"),
            ("instructor_id", "InstructorID"),
            ("class_session_id", "ClassSessionID"),
        ],
    )


def downgrade():
    _rename_columns(
        "InstructorAttendance",
        [
            ("InstructorAttendanceID", "id"),
            ("Date", "date"),
            ("Time", "attendance_time"),
            ("ClassID", "class_id"),
            ("InstructorID", "instructor_id"),
            ("ClassSessionID", "class_session_id"),
        ],
    )

    _rename_columns(
        "StudentAttendance",
        [
            ("StudentAttendanceID", "id"),
            ("Date", "date"),
            ("Time", "attendance_time"),
            ("ClassID", "class_id"),
            ("StudentID", "student_id"),
            ("ClassSessionID", "class_session_id"),
        ],
    )

    _rename_columns(
        "Enrolled",
        [
            ("EnrollmentID", "id"),
            ("SchoolYear", "school_year"),
            ("Term", "term"),
            ("ClassID", "class_id"),
            ("StudentID", "student_id"),
        ],
    )

    _rename_columns(
        "Class",
        [
            ("ClassID", "id"),
            ("ClassCode", "class_code"),
            ("ClassName", "class_name"),
            ("ClassDescription", "description"),
            ("Date", "class_date"),
            ("Time", "class_time"),
            ("RoomNumber", "room_number"),
            ("SchoolYear", "school_year"),
            ("Term", "term"),
            ("CourseID", "course_id"),
            ("InstructorID", "instructor_id"),
            ("SubstituteInstructorID", "substitute_instructor_id"),
            ("Schedule", "schedule"),
        ],
    )

    _rename_columns(
        "Student",
        [
            ("StudentID", "id"),
            ("FirstName", "first_name"),
            ("MiddleName", "middle_name"),
            ("LastName", "last_name"),
            ("YearLevel", "year_level"),
            ("Department", "department"),
            ("FaceEncoding", "face_encoding"),
            ("ImagePath", "image_path"),
        ],
    )

    _rename_columns(
        "Instructor",
        [
            ("InstructorID", "id"),
            ("FirstName", "first_name"),
            ("MiddleName", "middle_name"),
            ("LastName", "last_name"),
            ("Department", "department"),
            ("SchoolYear", "school_year"),
            ("Term", "term"),
            ("FaceEncoding", "face_encoding"),
            ("ImagePath", "image_path"),
        ],
    )

    _rename_columns(
        "Course",
        [
            ("CourseID", "id"),
            ("CourseCode", "code"),
            ("CourseDescription", "description"),
        ],
    )

    _rename_table_if_needed("InstructorAttendance", "instructor_attendance")
    _rename_table_if_needed("StudentAttendance", "attendance_records")
    _rename_table_if_needed("Enrolled", "enrollments")
    _rename_table_if_needed("Class", "classes")
    _rename_table_if_needed("Student", "students")
    _rename_table_if_needed("Instructor", "users")
    _rename_table_if_needed("Course", "courses")
