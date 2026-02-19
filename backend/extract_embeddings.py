import os
import sys
import pickle
from pathlib import Path
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'
BASE_DIR = Path(__file__).parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))
from flask import Flask, current_app
from extensions import db
from models import FaceEncoding, InstructorFaceEncoding, Student, User
from config import Config
import numpy as np
try:
    from deepface import DeepFace
    DEEPFACE_AVAILABLE = True
except ImportError as e:
    DEEPFACE_AVAILABLE = False
DEEPFACE_MODEL = 'Facenet512'
DEEPFACE_DETECTOR = 'opencv'
DEEPFACE_DISTANCE_METRIC = 'cosine'

def create_app():
    """Create Flask application."""
    base_dir = Path(__file__).parent
    frontend_dir = base_dir / '..' / 'frontend'
    app = Flask(__name__, static_folder=str(frontend_dir / 'static'), template_folder=str(frontend_dir / 'templates'))
    app.config.from_object(Config)
    db.init_app(app)
    return app

def empty_face_data():
    """Return a fresh dictionary shaped like the cache payload."""
    return {'student_embeddings': [], 'student_names': [], 'student_ids': [], 'instructor_embeddings': [], 'instructor_names': [], 'instructor_ids': []}

def load_existing_face_data(cache_file):
    """Load cached embeddings (if any) to support incremental extraction."""
    data = empty_face_data()
    if not cache_file.exists():
        return data
    try:
        with open(cache_file, 'rb') as f:
            cached = pickle.load(f)
        for key in data.keys():
            if key in cached:
                data[key] = cached[key]
        return data
    except Exception as e:
        return data

def generate_face_embedding(image_path):
    """Generate face embedding using DeepFace with FaceNet-512"""
    if not DEEPFACE_AVAILABLE:
        return np.zeros(512, dtype=np.float32)
    try:
        detectors_to_try = [DEEPFACE_DETECTOR]
        for alt in ('retinaface', 'mtcnn'):
            if alt not in detectors_to_try:
                detectors_to_try.append(alt)
        for detector in detectors_to_try:
            try:
                faces = DeepFace.extract_faces(img_path=image_path, detector_backend=detector, enforce_detection=True, align=True)
                if not faces or len(faces) == 0:
                    continue
            except Exception as detect_error:
                continue
            try:
                embedding_result = DeepFace.represent(img_path=image_path, model_name=DEEPFACE_MODEL, detector_backend=detector, enforce_detection=True, align=True)
            except Exception as rep_error:
                continue
            if embedding_result and len(embedding_result) > 0:
                first = embedding_result[0]
                if isinstance(first, dict) and 'embedding' in first:
                    emb = first['embedding']
                else:
                    emb = first
                face_embedding = np.array(emb, dtype=np.float32)
                return face_embedding
        return None
    except Exception as e:
        return None

def process_student_encodings(student_embeddings, student_names, student_ids, skip_ids=None):
    """Process student face encodings and collect into lists, optionally skipping cached IDs."""
    face_encodings = FaceEncoding.query.filter(FaceEncoding.image_path.isnot(None)).all()
    processed = 0
    successful = 0
    failed = 0
    skipped = 0
    skip_ids = set(skip_ids or [])
    for face_encoding in face_encodings:
        try:
            if skip_ids and face_encoding.student_id in skip_ids:
                skipped += 1
                continue
            image_path = os.path.join(current_app.static_folder, face_encoding.image_path)
            if not os.path.exists(image_path):
                failed += 1
                continue
            embedding = generate_face_embedding(image_path)
            if embedding is not None:
                student = Student.query.get(face_encoding.student_id)
                name = f'{student.first_name} {student.last_name}' if student else f'Student_{face_encoding.student_id}'
                student_embeddings.append(embedding)
                student_names.append(name)
                student_ids.append(face_encoding.student_id)
                successful += 1
            else:
                failed += 1
        except Exception as e:
            failed += 1
        processed += 1

def process_instructor_encodings(instructor_embeddings, instructor_names, instructor_ids, skip_ids=None):
    """Process instructor face encodings, optionally skipping IDs already cached."""
    instructor_encodings = InstructorFaceEncoding.query.filter(InstructorFaceEncoding.image_path.isnot(None)).all()
    processed = 0
    successful = 0
    failed = 0
    skipped = 0
    skip_ids = set(skip_ids or [])
    for instructor_encoding in instructor_encodings:
        try:
            if skip_ids and instructor_encoding.instructor_id in skip_ids:
                skipped += 1
                continue
            image_path = os.path.join(current_app.static_folder, instructor_encoding.image_path)
            if not os.path.exists(image_path):
                failed += 1
                continue
            embedding = generate_face_embedding(image_path)
            if embedding is not None:
                instructor = User.query.filter_by(id=instructor_encoding.instructor_id, role='instructor').first()
                name = f'{instructor.first_name} {instructor.last_name}' if instructor else f'Instructor_{instructor_encoding.instructor_id}'
                instructor_embeddings.append(embedding)
                instructor_names.append(name)
                instructor_ids.append(instructor_encoding.instructor_id)
                successful += 1
            else:
                failed += 1
        except Exception as e:
            failed += 1
        processed += 1

def main(mode='all'):
    """Extract embeddings and persist them to disk.

    mode:
        'all' - rebuild every embedding from scratch.
        'new' - only process IDs not found in the existing cache and append them.
    """
    mode = (mode or 'all').lower()
    if mode not in {'all', 'new'}:
        mode = 'all'
    if not DEEPFACE_AVAILABLE:
        return False
    app = create_app()
    with app.app_context():
        try:
            cache_dir = Path(__file__).parent / '..' / 'cache'
            cache_dir.mkdir(exist_ok=True)
            cache_file = cache_dir / 'face_encodings.pkl'
            if mode == 'new':
                face_data_seed = load_existing_face_data(cache_file)
            else:
                face_data_seed = empty_face_data()
            student_embeddings = face_data_seed['student_embeddings']
            student_names = face_data_seed['student_names']
            student_ids = face_data_seed['student_ids']
            instructor_embeddings = face_data_seed['instructor_embeddings']
            instructor_names = face_data_seed['instructor_names']
            instructor_ids = face_data_seed['instructor_ids']
            student_skip_ids = student_ids if mode == 'new' else None
            instructor_skip_ids = instructor_ids if mode == 'new' else None
            process_student_encodings(student_embeddings, student_names, student_ids, skip_ids=student_skip_ids)
            process_instructor_encodings(instructor_embeddings, instructor_names, instructor_ids, skip_ids=instructor_skip_ids)
            face_data = {'student_embeddings': student_embeddings, 'student_names': student_names, 'student_ids': student_ids, 'instructor_embeddings': instructor_embeddings, 'instructor_names': instructor_names, 'instructor_ids': instructor_ids}
            with open(cache_file, 'wb') as f:
                pickle.dump(face_data, f)
            return True
        except Exception as e:
            return False
if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
