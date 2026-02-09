import sys
import os
sys.path.append('..')

try:
    import pickle
    import cv2
    import numpy as np
    from deepface import DeepFace
    print('✓ All imports successful')

    # Test cache loading
    cache_file = '../cache/face_encodings.pkl'
    if os.path.exists(cache_file):
        with open(cache_file, 'rb') as f:
            face_data = pickle.load(f)
        print(f'✓ Loaded {len(face_data["student_embeddings"])} student and {len(face_data["instructor_embeddings"])} instructor embeddings')
    else:
        print('✗ Cache file not found')

    # Test camera
    cap = cv2.VideoCapture(0)
    if cap.isOpened():
        print('✓ Camera opened successfully')
        ret, frame = cap.read()
        if ret:
            print(f'✓ Frame captured: {frame.shape}')
        else:
            print('✗ Failed to capture frame')
        cap.release()
    else:
        print('✗ Failed to open camera')

    # Test DeepFace on captured frame
    if 'frame' in locals() and ret:
        print('Testing DeepFace on captured frame...')
        try:
            faces = DeepFace.represent(
                img_path=frame,
                model_name="Facenet512",
                detector_backend="opencv",
                enforce_detection=False
            )
            if faces:
                print(f'✓ DeepFace detected {len(faces)} face(s)')
                embedding = np.array(faces[0]['embedding'])
                print(f'✓ Embedding shape: {embedding.shape}')
            else:
                print('✗ No faces detected in frame')
        except Exception as e:
            print(f'✗ DeepFace error: {e}')

except Exception as e:
    print(f'✗ Error: {e}')
    import traceback
    traceback.print_exc()