import sys
import os
sys.path.append('..')
try:
    import pickle
    import cv2
    import numpy as np
    from deepface import DeepFace
    cache_file = '../cache/face_encodings.pkl'
    if os.path.exists(cache_file):
        with open(cache_file, 'rb') as f:
            face_data = pickle.load(f)
    cap = cv2.VideoCapture(0)
    if cap.isOpened():
        ret, frame = cap.read()
        if ret:
            pass
        cap.release()
    if 'frame' in locals() and ret:
        try:
            faces = DeepFace.represent(img_path=frame, model_name='Facenet512', detector_backend='opencv', enforce_detection=False)
            if faces:
                embedding = np.array(faces[0]['embedding'])
        except Exception as e:
            pass
except Exception as e:
    import traceback
    traceback.print_exc()
