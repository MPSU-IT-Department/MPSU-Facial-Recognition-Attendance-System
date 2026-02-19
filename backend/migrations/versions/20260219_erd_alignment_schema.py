"""Align schema with ERD entities while preserving compatibility

Revision ID: 20260219_erd_alignment
Revises: 20260204_consolidated
Create Date: 2026-02-19 14:20:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260219_erd_alignment"
down_revision = "20260204_consolidated"
branch_labels = None
depends_on = None


def _get_inspector():
    return sa.inspect(op.get_bind())


def _has_column(table_name, column_name):
    inspector = _get_inspector()
    return any(col["name"] == column_name for col in inspector.get_columns(table_name))


def _has_index(table_name, index_name):
    inspector = _get_inspector()
    return any(idx["name"] == index_name for idx in inspector.get_indexes(table_name))


def _has_fk(table_name, constrained_columns, referred_table):
    return _get_fk_name(table_name, constrained_columns, referred_table) is not None


def _get_fk_name(table_name, constrained_columns, referred_table):
    inspector = _get_inspector()
    expected = list(constrained_columns)
    for fk in inspector.get_foreign_keys(table_name):
        if fk.get("referred_table") != referred_table:
            continue
        if list(fk.get("constrained_columns") or []) == expected:
            return fk.get("name")
    return None


def upgrade():
    if not _has_column("users", "school_year"):
        op.add_column("users", sa.Column("school_year", sa.String(length=9), nullable=True))
    if not _has_column("users", "term"):
        op.add_column("users", sa.Column("term", sa.String(length=20), nullable=True))
    if not _has_column("users", "face_encoding"):
        op.add_column("users", sa.Column("face_encoding", sa.LargeBinary(), nullable=True))
    if not _has_column("users", "image_path"):
        op.add_column("users", sa.Column("image_path", sa.String(length=255), nullable=True))

    if not _has_column("students", "face_encoding"):
        op.add_column("students", sa.Column("face_encoding", sa.LargeBinary(), nullable=True))
    if not _has_column("students", "image_path"):
        op.add_column("students", sa.Column("image_path", sa.String(length=255), nullable=True))

    if not _has_column("classes", "class_name"):
        op.add_column("classes", sa.Column("class_name", sa.String(length=200), nullable=True))
    if not _has_column("classes", "class_date"):
        op.add_column("classes", sa.Column("class_date", sa.Date(), nullable=True))
    if not _has_column("classes", "class_time"):
        op.add_column("classes", sa.Column("class_time", sa.Time(), nullable=True))

    if not _has_column("enrollments", "school_year"):
        op.add_column("enrollments", sa.Column("school_year", sa.String(length=9), nullable=True))
    if not _has_column("enrollments", "term"):
        op.add_column("enrollments", sa.Column("term", sa.String(length=20), nullable=True))

    if not _has_column("attendance_records", "class_id"):
        op.add_column("attendance_records", sa.Column("class_id", sa.Integer(), nullable=True))
    if not _has_column("attendance_records", "attendance_time"):
        op.add_column("attendance_records", sa.Column("attendance_time", sa.Time(), nullable=True))

    if not _has_column("instructor_attendance", "class_session_id"):
        op.add_column("instructor_attendance", sa.Column("class_session_id", sa.Integer(), nullable=True))
    if not _has_column("instructor_attendance", "attendance_time"):
        op.add_column("instructor_attendance", sa.Column("attendance_time", sa.Time(), nullable=True))

    op.execute(
        """
        UPDATE classes
        SET class_name = COALESCE(class_name, description, class_code)
        WHERE class_name IS NULL
        """
    )

    if _has_column("attendance_records", "class_id"):
        op.execute(
            """
            UPDATE attendance_records ar
            SET class_id = cs.class_id
            FROM class_sessions cs
            WHERE ar.class_session_id = cs.id
              AND ar.class_id IS NULL
            """
        )
        op.execute(
            """
            UPDATE attendance_records
            SET attendance_time = COALESCE(
                attendance_time,
                CAST(time_in AS time),
                CAST(date AS time),
                CAST(marked_at AS time)
            )
            WHERE attendance_time IS NULL
            """
        )

    if _has_column("instructor_attendance", "class_session_id"):
        op.execute(
            """
            UPDATE instructor_attendance ia
            SET class_session_id = cs.id
            FROM class_sessions cs
            WHERE ia.class_id = cs.class_id
              AND ia.date = cs.date
              AND ia.class_session_id IS NULL
            """
        )
        op.execute(
            """
            UPDATE instructor_attendance
            SET attendance_time = COALESCE(attendance_time, CAST(time_in AS time))
            WHERE attendance_time IS NULL
            """
        )

    op.execute(
        """
        UPDATE users
        SET image_path = COALESCE(image_path, profile_picture)
        WHERE image_path IS NULL
        """
    )

    op.execute(
        """
        UPDATE students s
        SET face_encoding = fe.encoding_data,
            image_path = COALESCE(s.image_path, fe.image_path)
        FROM (
            SELECT DISTINCT ON (student_id)
                student_id,
                encoding_data,
                image_path
            FROM face_encodings
            ORDER BY student_id, id
        ) fe
        WHERE s.id = fe.student_id
          AND (s.face_encoding IS NULL OR s.image_path IS NULL)
        """
    )

    op.execute(
        """
        UPDATE users u
        SET face_encoding = ife.encoding,
            image_path = COALESCE(u.image_path, ife.image_path)
        FROM (
            SELECT DISTINCT ON (instructor_id)
                instructor_id,
                encoding,
                image_path
            FROM instructor_face_encodings
            ORDER BY instructor_id, id
        ) ife
        WHERE u.id = ife.instructor_id
          AND (u.face_encoding IS NULL OR u.image_path IS NULL)
        """
    )

    if not _has_fk("attendance_records", ["class_id"], "classes"):
        op.create_foreign_key(
            "fk_attendance_records_class_id_classes",
            "attendance_records",
            "classes",
            ["class_id"],
            ["id"],
        )

    if not _has_fk("instructor_attendance", ["class_session_id"], "class_sessions"):
        op.create_foreign_key(
            "fk_instructor_attendance_class_session_id_class_sessions",
            "instructor_attendance",
            "class_sessions",
            ["class_session_id"],
            ["id"],
        )

    if not _has_index("enrollments", "ix_enrollments_class_student_term_year"):
        op.create_index(
            "ix_enrollments_class_student_term_year",
            "enrollments",
            ["class_id", "student_id", "term", "school_year"],
            unique=False,
        )

    if not _has_index("attendance_records", "ix_attendance_records_class_student_date"):
        op.create_index(
            "ix_attendance_records_class_student_date",
            "attendance_records",
            ["class_id", "student_id", "date"],
            unique=False,
        )

    if not _has_index("instructor_attendance", "ix_instructor_attendance_instructor_class_date"):
        op.create_index(
            "ix_instructor_attendance_instructor_class_date",
            "instructor_attendance",
            ["instructor_id", "class_id", "date"],
            unique=False,
        )


def downgrade():
    if _has_index("instructor_attendance", "ix_instructor_attendance_instructor_class_date"):
        op.drop_index("ix_instructor_attendance_instructor_class_date", table_name="instructor_attendance")
    if _has_index("attendance_records", "ix_attendance_records_class_student_date"):
        op.drop_index("ix_attendance_records_class_student_date", table_name="attendance_records")
    if _has_index("enrollments", "ix_enrollments_class_student_term_year"):
        op.drop_index("ix_enrollments_class_student_term_year", table_name="enrollments")

    instructor_session_fk = _get_fk_name("instructor_attendance", ["class_session_id"], "class_sessions")
    if instructor_session_fk:
        op.drop_constraint(
            instructor_session_fk,
            "instructor_attendance",
            type_="foreignkey",
        )
    attendance_class_fk = _get_fk_name("attendance_records", ["class_id"], "classes")
    if attendance_class_fk:
        op.drop_constraint(
            attendance_class_fk,
            "attendance_records",
            type_="foreignkey",
        )

    if _has_column("instructor_attendance", "attendance_time"):
        op.drop_column("instructor_attendance", "attendance_time")
    if _has_column("instructor_attendance", "class_session_id"):
        op.drop_column("instructor_attendance", "class_session_id")

    if _has_column("attendance_records", "attendance_time"):
        op.drop_column("attendance_records", "attendance_time")
    if _has_column("attendance_records", "class_id"):
        op.drop_column("attendance_records", "class_id")

    if _has_column("enrollments", "term"):
        op.drop_column("enrollments", "term")
    if _has_column("enrollments", "school_year"):
        op.drop_column("enrollments", "school_year")

    if _has_column("classes", "class_time"):
        op.drop_column("classes", "class_time")
    if _has_column("classes", "class_date"):
        op.drop_column("classes", "class_date")
    if _has_column("classes", "class_name"):
        op.drop_column("classes", "class_name")

    if _has_column("students", "image_path"):
        op.drop_column("students", "image_path")
    if _has_column("students", "face_encoding"):
        op.drop_column("students", "face_encoding")

    if _has_column("users", "image_path"):
        op.drop_column("users", "image_path")
    if _has_column("users", "face_encoding"):
        op.drop_column("users", "face_encoding")
    if _has_column("users", "term"):
        op.drop_column("users", "term")
    if _has_column("users", "school_year"):
        op.drop_column("users", "school_year")
