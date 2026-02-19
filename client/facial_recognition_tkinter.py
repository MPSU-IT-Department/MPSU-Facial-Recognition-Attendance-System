import os
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'
import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
import cv2
import numpy as np
import pickle
import sys
import threading
import time
from datetime import datetime
import pytz
from PIL import Image, ImageTk
from deepface import DeepFace
import requests
import json
import warnings
from instructor_console import InstructorConsoleView
from ui_utils import bring_window_to_front
from server import SERVER_URL as BACKEND_URL, API_KEY
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
warnings.filterwarnings('ignore', category=UserWarning, module='tensorflow')
warnings.filterwarnings('ignore', category=DeprecationWarning, module='tensorflow')
ctk.set_appearance_mode('light')
ctk.set_default_color_theme('green')
HEADERS = {'X-API-Key': API_KEY, 'Content-Type': 'application/json'}

class FacialRecognitionApp:

    def fetch_default_class_id(self):
        """Fetch the first available class ID from the API"""
        try:
            response = requests.get(f'{BACKEND_URL}/classes/api/list', headers=HEADERS, verify=False, timeout=10)
            if response.status_code == 200:
                classes = response.json()
                if classes and len(classes) > 0:
                    return classes[0]['id']
                else:
                    return None
            else:
                return None
        except Exception as e:
            return None

    def fetch_class_session_info(self):
        """Fetch class information to get class details"""
        try:
            response = requests.get(f'{BACKEND_URL}/classes/api/list', headers=HEADERS, verify=False, timeout=10)
            if response.status_code == 200:
                classes = response.json()
                for cls in classes:
                    if cls['id'] == self.class_id:
                        self.class_code = cls.get('classCode') or cls.get('class_code') or f'Class ID {self.class_id}'
                        self.class_name = cls.get('className') or cls.get('class_name') or cls.get('description') or 'Unknown'
                        self.class_schedule = cls.get('schedule') or cls.get('classSchedule') or 'Schedule Unknown'
                        self._capture_class_instructors(cls)
                        break
                else:
                    self.class_code = f'Class ID {self.class_id}'
                    if not self.class_name:
                        self.class_name = 'Unknown'
                    if not self.class_schedule:
                        self.class_schedule = 'Schedule Unknown'
            else:
                self.class_code = f'Class ID {self.class_id}'
                if not self.class_name:
                    self.class_name = 'Unknown'
                if not self.class_schedule:
                    self.class_schedule = 'Schedule Unknown'
        except Exception as e:
            self.class_code = f'Class ID {self.class_id}'
            if not self.class_name:
                self.class_name = 'Unknown'
            if not self.class_schedule:
                self.class_schedule = 'Schedule Unknown'

    def _capture_class_instructors(self, class_info):
        """Store the primary and substitute instructor IDs for the active class."""

        def _to_int(value):
            try:
                return int(value)
            except (TypeError, ValueError):
                return None
        if not isinstance(class_info, dict):
            self.primary_instructor_id = None
            self.substitute_instructor_id = None
            return
        primary_raw = class_info.get('instructorId') or class_info.get('instructor_id')
        substitute_raw = class_info.get('substituteInstructorId') or class_info.get('substitute_instructor_id')
        self.primary_instructor_id = _to_int(primary_raw)
        self.substitute_instructor_id = _to_int(substitute_raw)

    def __init__(self, root, class_id=None, session_id=None, room_number=None, embedded=False, on_exit=None, on_logout=None, acting_instructor_id=None, acting_instructor_role='primary'):
        self.root = root
        self.embedded = embedded
        self.on_exit = on_exit
        self.on_logout = on_logout
        self.running = True
        self._shutdown = False
        self._remote_session_closed = False
        self.acting_instructor_id = acting_instructor_id
        self.acting_instructor_role = acting_instructor_role or 'primary'
        if class_id is not None:
            try:
                self.class_id = int(class_id)
            except (ValueError, TypeError):
                self.class_id = class_id
        else:
            self.class_id = class_id
        if session_id is not None:
            try:
                self.session_id = int(session_id)
            except (ValueError, TypeError):
                self.session_id = session_id
        else:
            self.session_id = session_id
        self.room_number = room_number
        self.primary_instructor_id = None
        self.substitute_instructor_id = None
        if hasattr(self.root, 'title') and (not self.embedded):
            self.root.title('Facial Recognition Scanner')
        else:
            try:
                toplevel = self.root.winfo_toplevel()
                if hasattr(toplevel, 'title'):
                    toplevel.title('Facial Recognition Scanner')
            except Exception:
                pass
        self.load_embeddings()
        self.cap = cv2.VideoCapture(0)
        if not self.cap.isOpened():
            messagebox.showerror('Camera Error', 'Could not open camera device')
            raise RuntimeError('Could not open camera device')
        self.test_camera_and_detection()
        if self.class_id is None:
            self.class_id = self.fetch_default_class_id()
            if self.class_id is None:
                messagebox.showerror('Configuration Error', 'No class ID available. Please provide a class ID or ensure classes exist in the system.')
                raise RuntimeError('No class ID available for facial recognition')
        self.is_recognizing = False
        self.recognized_person = None
        self.recognized_person_id = None
        self.recognized_type = None
        self.confidence = 0.0
        self.current_frame = None
        self.face_count = 0
        self.attendance_marked = False
        self.countdown_active = False
        self.auto_reset_timer = None
        self.already_marked_ids = set()
        self.awaiting_console_auth = False
        self.console_redirect_job = None
        self.console_countdown_remaining = None
        self.console_launch_target = (None, None)
        self.console_modal = None
        self.console_auth_timer = None
        self.console_auth_seconds = None
        self.session_ended = False
        self.class_code = None
        self.class_name = None
        self.class_schedule = None
        if not self.room_number:
            self.room_number = 'Unknown'
        self.fetch_class_session_info()
        self.camera_lock = threading.Lock()
        self.gui_lock = threading.Lock()
        self.camera_image_id = None
        self.camera_photo = None
        self.camera_paused = False
        self.detected_faces = []
        self.face_rectangles = []
        self.create_widgets()
        self.last_cache_mtime = None
        self.update_check_interval = 5.0
        self._try_download_cache_on_startup()
        self._update_cache_mtime()
        self.camera_thread = threading.Thread(target=self.camera_loop, daemon=True)
        self.camera_thread.start()
        self.recognition_thread = threading.Thread(target=self.recognition_loop, daemon=True)
        self.recognition_thread.start()
        self.update_check_thread = threading.Thread(target=self._check_for_updates_loop, daemon=True)
        self.update_check_thread.start()

    def update_camera_display(self, frame):
        """Update camera display in main thread to prevent flickering"""
        try:
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(frame_rgb)
            img.thumbnail((640, 480))
            new_photo = ImageTk.PhotoImage(image=img)
            canvas_width = self.camera_canvas.winfo_width()
            canvas_height = self.camera_canvas.winfo_height()
            if canvas_width > 1 and canvas_height > 1:
                if self.camera_image_id:
                    self.camera_canvas.delete(self.camera_image_id)
                for rect_id in self.face_rectangles:
                    self.camera_canvas.delete(rect_id)
                self.face_rectangles = []
                img_width, img_height = img.size
                x = (canvas_width - img_width) // 2
                y = (canvas_height - img_height) // 2
                self.camera_image_id = self.camera_canvas.create_image(x, y, anchor=tk.NW, image=new_photo)
                with self.camera_lock:
                    detected_faces = self.detected_faces.copy()
                scale_x = img_width / frame.shape[1]
                scale_y = img_height / frame.shape[0]
                for face_x, face_y, face_w, face_h in detected_faces:
                    scaled_x = int(face_x * scale_x) + x
                    scaled_y = int(face_y * scale_y) + y
                    scaled_w = int(face_w * scale_x)
                    scaled_h = int(face_h * scale_y)
                    rect_id = self.camera_canvas.create_rectangle(scaled_x, scaled_y, scaled_x + scaled_w, scaled_y + scaled_h, outline='#00ff00', width=3)
                    self.face_rectangles.append(rect_id)
                self.camera_photo = new_photo
        except Exception as e:
            pass

    def update_recognition_status(self, face_count, status_type, error_msg=None):
        """Update recognition status with reduced flickering"""
        try:
            if status_type == 'processing':
                self.recognition_status.config(text=f'🔍 Face detected - Processing {face_count} face(s)...')
            elif status_type == 'no_faces':
                self.recognition_status.config(text='📷 No faces detected')
            elif status_type == 'error':
                self.recognition_status.config(text=f'⚠️ Recognition error: {error_msg}...')
        except:
            pass

    def ensure_dark_text(self, *widgets):
        """Force widgets to use black text when they still carry a white foreground."""
        for widget in widgets:
            if not widget:
                continue
            try:
                color = widget.cget('text_color')
                if isinstance(color, (tuple, list)):
                    color_value = color[0]
                else:
                    color_value = color
                if isinstance(color_value, str) and color_value.strip().lower() in {'white', '#ffffff', '#fff'}:
                    widget.configure(text_color='#000000')
            except Exception:
                continue

    def pause_scanner(self, status_text=None):
        """Temporarily pause camera updates and optionally update status."""
        with self.camera_lock:
            self.camera_paused = True
        if status_text:
            try:
                self.recognition_status.configure(text=status_text)
            except Exception:
                pass

    def resume_scanner(self):
        """Resume camera feed after a temporary pause."""
        with self.camera_lock:
            self.camera_paused = False

    def cancel_console_auth_timer(self):
        """Cancel pending instructor authentication delay."""
        if self.console_auth_timer:
            try:
                self.root.after_cancel(self.console_auth_timer)
            except Exception:
                pass
            self.console_auth_timer = None
        self.console_auth_seconds = None

    def start_console_auth_countdown(self, seconds=3):
        """Begin countdown before instructor scanner activates."""
        self.cancel_console_auth_timer()
        self.console_auth_seconds = max(0, int(seconds))
        self._continue_console_auth_countdown()

    def _continue_console_auth_countdown(self):
        """Update countdown label until scanner starts."""
        if self.console_auth_seconds is None:
            return
        if self.console_auth_seconds <= 0:
            self.console_auth_seconds = None
            self.console_auth_timer = None
            self._start_instructor_authentication()
            return
        seconds = self.console_auth_seconds
        label = 'second' if seconds == 1 else 'seconds'
        try:
            self.recognition_status.configure(text=f'Instructor scanner starting in {seconds} {label}...')
            self.ensure_dark_text(self.recognition_status)
        except Exception:
            pass
        self.console_auth_seconds -= 1
        self.console_auth_timer = self.root.after(1000, self._continue_console_auth_countdown)

    def close_console_confirmation_modal(self):
        """Close the console confirmation modal if it exists."""
        if self.console_modal:
            try:
                self.console_modal.destroy()
            except Exception:
                pass
            self.console_modal = None

    def show_console_confirmation_modal(self):
        """Display a modal confirmation dialog before entering console mode."""
        if self.console_modal:
            try:
                self.console_modal.focus_force()
            except Exception:
                pass
            return
        modal = ctk.CTkToplevel(self.root)
        modal.title('Authentication Required')
        modal.geometry('420x260')
        modal.resizable(False, False)
        modal.grab_set()
        modal.transient(self.root)
        bring_window_to_front(modal)
        try:
            modal.update_idletasks()
            parent_x = self.root.winfo_rootx()
            parent_y = self.root.winfo_rooty()
            parent_w = self.root.winfo_width()
            parent_h = self.root.winfo_height()
            width = 420
            height = 260
            x = parent_x + parent_w // 2 - width // 2
            y = parent_y + parent_h // 2 - height // 2
            modal.geometry(f'{width}x{height}+{x}+{y}')
        except Exception:
            pass
        container = ctk.CTkFrame(modal, fg_color=('#f8fff8', '#1e4a1e'))
        container.pack(fill='both', expand=True, padx=20, pady=20)
        title = ctk.CTkLabel(container, text='Authentication Required', font=('Arial', 24, 'bold'), text_color=('#006400', '#90EE90'))
        title.pack(pady=(10, 5))
        body = ctk.CTkLabel(container, text='Only instructors may access the console.\nProceed to instructor authentication?', font=('Arial', 16), text_color=('#2d5a2d', '#c1f0c1'), justify='center')
        body.pack(pady=10)
        button_row = ctk.CTkFrame(container, fg_color='transparent')
        button_row.pack(pady=(20, 10))

        def confirm_action():
            self.close_console_confirmation_modal()
            self.cancel_recognition(reset_fields=False)
            self.pause_scanner()
            self.start_console_auth_countdown(3)

        def cancel_action():
            self.close_console_confirmation_modal()
            self.cancel_recognition()
            self.cancel_console_auth_timer()
            self.awaiting_console_auth = False
            self.resume_scanner()
        confirm_btn = ctk.CTkButton(button_row, text='Continue', font=('Arial', 18, 'bold'), width=150, height=50, fg_color=('#228B22', '#32CD32'), hover_color=('#006400', '#90EE90'), command=confirm_action)
        confirm_btn.pack(side='left', padx=10)
        cancel_btn = ctk.CTkButton(button_row, text='Cancel', font=('Arial', 18, 'bold'), width=150, height=50, fg_color=('#dc3545', '#c82333'), hover_color=('#a71d2a', '#7f151f'), command=cancel_action)
        cancel_btn.pack(side='left', padx=10)
        modal.protocol('WM_DELETE_WINDOW', cancel_action)
        self.console_modal = modal

    def _start_instructor_authentication(self):
        """Begin instructor scanning after confirmation delay."""
        self.console_auth_timer = None
        self.console_auth_seconds = None
        self.begin_console_authentication()
        self.resume_scanner()

    def begin_console_authentication(self):
        """Switch the scanner into instructor authentication mode."""
        self.awaiting_console_auth = True
        self.recognition_status.configure(text='Awaiting instructor authentication')
        self.person_label.configure(text='Instructor authentication mode', text_color='#000000')
        self.id_label.configure(text='Scan authorized instructor', text_color='#000000')
        self.attendance_label.configure(text='Instructor authorization required', text_color='#ffc107')
        self.ensure_dark_text(self.recognition_status, self.person_label, self.id_label)

    def _get_cache_file_path(self):
        """Get the path to the face encodings cache file."""
        return os.path.join(os.path.dirname(__file__), '..', 'cache', 'face_encodings.pkl')

    def _try_download_cache_on_startup(self):
        """Try to download the latest cache file on startup if it doesn't exist or is outdated."""
        cache_file = self._get_cache_file_path()
        if not os.path.exists(cache_file):
            if self._download_cache_file():
                pass
            return
        try:
            response = requests.get(f'{BACKEND_URL}/api/face-encodings/meta', headers=HEADERS, verify=False, timeout=3)
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    server_mtime_str = data.get('mtime')
                    if server_mtime_str:
                        server_mtime = datetime.fromisoformat(server_mtime_str.replace('Z', '+00:00')).timestamp()
                        local_mtime = os.path.getmtime(cache_file)
                        if server_mtime > local_mtime:
                            if self._download_cache_file():
                                pass
        except Exception as e:
            pass

    def _update_cache_mtime(self):
        """Update the last known cache file modification time."""
        cache_file = self._get_cache_file_path()
        if os.path.exists(cache_file):
            try:
                self.last_cache_mtime = os.path.getmtime(cache_file)
            except Exception:
                self.last_cache_mtime = None
        else:
            self.last_cache_mtime = None

    def _check_for_updates_loop(self):
        """Background thread that periodically checks for cache file updates."""
        while self.running:
            try:
                try:
                    response = requests.get(f'{BACKEND_URL}/api/face-encodings/meta', headers=HEADERS, verify=False, timeout=3)
                    if response.status_code == 200:
                        data = response.json()
                        if data.get('success'):
                            server_mtime_str = data.get('mtime')
                            if server_mtime_str:
                                server_mtime = datetime.fromisoformat(server_mtime_str.replace('Z', '+00:00')).timestamp()
                                if self.last_cache_mtime is None or server_mtime > self.last_cache_mtime:
                                    self._reload_embeddings()
                                    self.last_cache_mtime = server_mtime
                except Exception as api_error:
                    cache_file = self._get_cache_file_path()
                    if os.path.exists(cache_file):
                        try:
                            current_mtime = os.path.getmtime(cache_file)
                            if self.last_cache_mtime is None or current_mtime > self.last_cache_mtime:
                                self._reload_embeddings()
                                self.last_cache_mtime = current_mtime
                        except Exception:
                            pass
            except Exception as e:
                pass
            time.sleep(self.update_check_interval)

    def _download_cache_file(self):
        """Download the latest cache file from the server."""
        cache_file = self._get_cache_file_path()
        cache_dir = os.path.dirname(cache_file)
        if cache_dir:
            os.makedirs(cache_dir, exist_ok=True)
        temp_path = cache_file + '.tmp'
        try:
            response = requests.get(f'{BACKEND_URL}/api/face-encodings', headers=HEADERS, verify=False, timeout=30, stream=True)
            if response.status_code != 200:
                return False
            with open(temp_path, 'wb') as temp_file:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        temp_file.write(chunk)
            os.replace(temp_path, cache_file)
            return True
        except Exception as e:
            return False
        finally:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception:
                    pass

    def _reload_embeddings(self):
        """Download and reload embeddings from cache file when update is detected."""
        try:
            if not self._download_cache_file():
                with self.gui_lock:
                    self.load_embeddings()
                    self._update_cache_mtime()
                return
            with self.gui_lock:
                self.load_embeddings()
                self._update_cache_mtime()
        except Exception as e:
            pass

    def load_embeddings(self):
        """Load face embeddings from pickle file"""
        cache_file = self._get_cache_file_path()
        if os.path.exists(cache_file):
            try:
                with open(cache_file, 'rb') as f:
                    face_data = pickle.load(f)
                self.student_embeddings = face_data.get('student_embeddings', [])
                self.student_names = face_data.get('student_names', [])
                self.student_ids = face_data.get('student_ids', [])
                self.instructor_embeddings = face_data.get('instructor_embeddings', [])
                self.instructor_names = face_data.get('instructor_names', [])
                self.instructor_ids = face_data.get('instructor_ids', [])

                def normalize_embedding(emb):
                    emb_array = np.array(emb)
                    norm = np.linalg.norm(emb_array)
                    return emb_array / norm if norm > 0 else emb_array
                self.student_embeddings = [normalize_embedding(emb) for emb in self.student_embeddings]
                self.instructor_embeddings = [normalize_embedding(emb) for emb in self.instructor_embeddings]
            except Exception as e:
                self.student_embeddings = []
                self.student_names = []
                self.student_ids = []
                self.instructor_embeddings = []
                self.instructor_names = []
                self.instructor_ids = []
        else:
            self.student_embeddings = []
            self.student_names = []
            self.student_ids = []
            self.instructor_embeddings = []
            self.instructor_names = []
            self.instructor_ids = []

    def create_widgets(self):
        """Create the GUI widgets"""
        title_frame = ctk.CTkFrame(self.root, height=60, fg_color=('#228B22', '#32CD32'))
        title_frame.pack(fill='x')
        console_button = ctk.CTkButton(title_frame, text='Console', font=('Arial', 14, 'bold'), command=self.handle_console_button, width=120, height=35, fg_color=('#006400', '#228B22'), hover_color=('#004d00', '#1e5a1e'))
        console_button.place(x=10, y=12.5)
        title_text = f"{self.class_code or 'Unknown'} | {self.class_name or 'Unknown'} | {self.class_schedule or 'Schedule Unknown'}"
        title_label = ctk.CTkLabel(title_frame, text=title_text, font=('Arial', 16, 'bold'), text_color=('white', '#1a1a1a'))
        title_label.pack(pady=15)
        content_frame = ctk.CTkFrame(self.root, fg_color=('#f0f8f0', '#2d5a2d'))
        content_frame.pack(fill='both', expand=True, padx=20, pady=(0, 20))
        camera_frame = ctk.CTkFrame(content_frame, fg_color=('#e8f5e8', '#1e4a1e'))
        camera_frame.pack(fill='both', expand=True)
        camera_title = ctk.CTkLabel(camera_frame, text='📹 Live Camera Feed', font=('Arial', 12, 'bold'), text_color=('#006400', '#90EE90'))
        camera_title.pack(pady=(10, 5))
        self.camera_canvas = tk.Canvas(camera_frame, bg='#000000', highlightthickness=2, highlightcolor='#228B22')
        self.camera_canvas.pack(fill='both', expand=True, padx=10, pady=10)
        details_frame = ctk.CTkFrame(camera_frame, fg_color=('#f8fff8', '#0f2f0f'))
        details_frame.pack(fill='both', expand=False, padx=10, pady=(0, 10))
        self.recognition_status = ctk.CTkLabel(details_frame, text='Waiting for face detection...', font=('Arial', 22, 'bold'), anchor='center', justify='center', text_color='black')
        self.recognition_status.pack(fill='x', padx=10, pady=(15, 5))
        info_section = ctk.CTkFrame(details_frame, fg_color=('#f0fff0', '#1a3d1a'))
        info_section.pack(fill='x', padx=10, pady=(10, 10))

        def build_detail_row(title, initial_text):
            row_frame = ctk.CTkFrame(info_section, fg_color='transparent')
            row_frame.pack(fill='x', pady=8)
            title_label = ctk.CTkLabel(row_frame, text=title, font=('Arial', 18, 'bold'), text_color='black', anchor='center', justify='center')
            title_label.pack(fill='x')
            value_label = ctk.CTkLabel(row_frame, text=initial_text, font=('Arial', 22), text_color='black', anchor='center', justify='center')
            value_label.pack(fill='x', pady=(4, 0))
            return value_label
        self.id_label = build_detail_row('ID', 'None')
        self.person_label = build_detail_row('Person', 'None')
        self.attendance_label = build_detail_row('Attendance', 'Not Yet Marked')

    def camera_loop(self):
        """Camera capture loop running in separate thread"""
        last_update = 0
        update_interval = 1 / 30
        while self.running:
            current_time = time.time()
            if current_time - last_update < update_interval:
                time.sleep(0.01)
                continue
            ret, frame = self.cap.read()
            if ret:
                with self.camera_lock:
                    self.current_frame = frame.copy()
                    camera_paused = self.camera_paused
                if not camera_paused:
                    self.root.after(0, lambda f=frame: self.update_camera_display(f))
            else:
                pass
            last_update = current_time
            time.sleep(0.01)

    def recognition_loop(self):
        """Face recognition loop running in separate thread"""
        last_gui_update = 0
        gui_update_interval = 0.2
        while self.running:
            current_time = time.time()
            with self.camera_lock:
                frame = self.current_frame.copy() if self.current_frame is not None else None
                camera_paused = self.camera_paused
            if frame is not None and (not camera_paused):
                try:
                    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
                    if face_cascade.empty():
                        continue
                    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                    faces_coords = face_cascade.detectMultiScale(gray, 1.3, 5)
                    detected_faces = []
                    for x, y, w, h in faces_coords:
                        detected_faces.append((x, y, w, h))
                    with self.camera_lock:
                        self.detected_faces = detected_faces
                    if current_time - last_gui_update > gui_update_interval:
                        if detected_faces:
                            face_count = len(detected_faces)
                            self.root.after(0, lambda: self.update_recognition_status(face_count, 'processing'))
                        else:
                            self.root.after(0, lambda: self.update_recognition_status(0, 'no_faces'))
                        last_gui_update = current_time
                    if detected_faces:
                        try:
                            faces = DeepFace.represent(img_path=frame, model_name='Facenet512', detector_backend='opencv', enforce_detection=False)
                            if faces:
                                for face in faces:
                                    embedding = np.array(face['embedding'])
                                    embedding = self.normalize_embedding(embedding)
                                    recognized, person_type, confidence, person_id = self.compare_embeddings(embedding)
                                    with self.camera_lock:
                                        self.camera_paused = True
                                    with self.gui_lock:
                                        if recognized:
                                            self.is_recognizing = True
                                            self.recognized_person = recognized
                                            self.recognized_person_id = person_id
                                            self.recognized_type = person_type
                                            self.confidence = confidence
                                        else:
                                            self.is_recognizing = True
                                            self.recognized_person = None
                                            self.recognized_person_id = None
                                            self.recognized_type = None
                                            self.confidence = 0.0
                                    self.root.after(0, self.show_recognition_result)
                                    break
                        except Exception as e:
                            pass
                except Exception as e:
                    if current_time - last_gui_update > gui_update_interval:
                        self.root.after(0, lambda: self.update_recognition_status(0, 'error', str(e)[:50]))
                        last_gui_update = current_time
            time.sleep(0.1)

    def compare_embeddings(self, embedding):
        """Compare embedding with stored embeddings"""
        min_distance = float('inf')
        recognized_person = None
        person_type = None
        person_id = None
        for i, student_emb in enumerate(self.student_embeddings):
            distance = np.linalg.norm(embedding - student_emb)
            if distance < min_distance:
                min_distance = distance
                recognized_person = self.student_names[i]
                person_type = 'Student'
                person_id = self.student_ids[i]
        for i, instructor_emb in enumerate(self.instructor_embeddings):
            distance = np.linalg.norm(embedding - instructor_emb)
            if distance < min_distance:
                min_distance = distance
                recognized_person = self.instructor_names[i]
                person_type = 'Instructor'
                person_id = self.instructor_ids[i]
        threshold = 0.6
        if min_distance < threshold:
            confidence = (1 - min_distance) * 100
            return (recognized_person, person_type, confidence, person_id)
        return (None, None, 0, None)

    def test_camera_and_detection(self):
        """Test camera and face detection on startup"""
        if not self.cap.isOpened():
            return
        ret, frame = self.cap.read()
        if not ret:
            return
        try:
            face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
            if face_cascade.empty():
                return
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = face_cascade.detectMultiScale(gray, 1.3, 5)
        except Exception as e:
            pass

    def normalize_embedding(self, emb):
        """Normalize embedding to unit length"""
        emb_array = np.array(emb)
        norm = np.linalg.norm(emb_array)
        return emb_array / norm if norm > 0 else emb_array

    def check_attendance_status(self, person_id, person_type):
        """Check if person already has attendance marked for today"""
        try:
            if not person_id or not self.session_id:
                return (False, 'Unknown')
            if person_type == 'Student':
                url = f'{BACKEND_URL}/api/attendance/check'
                data = {'student_id': person_id, 'class_session_id': self.session_id}
            else:
                url = f'{BACKEND_URL}/api/attendance/check/instructor'
                data = {'instructor_id': person_id, 'class_session_id': self.session_id}
            response = requests.post(url, json=data, headers=HEADERS, verify=False, timeout=5)
            if response.status_code == 200:
                result = response.json()
                has_attendance = result.get('has_attendance', False)
                status = result.get('status', 'Unknown')
                return (has_attendance, status)
            else:
                return (False, 'Unknown')
        except Exception as e:
            return (False, 'Unknown')

    def show_recognition_result(self):
        """Update GUI with recognition result and automatically mark attendance"""
        try:
            with self.gui_lock:
                recognized = self.recognized_person
                person_type = self.recognized_type
                confidence = self.confidence
            if self.awaiting_console_auth:
                self.process_console_auth_result(recognized, person_type)
                return
            if recognized:
                self.recognition_status.configure(text='Person Recognized Successfully!')
                self.person_label.configure(text=f'{person_type}: {recognized}')
                self.id_label.configure(text=f"{self.recognized_person_id or 'Unknown'}")
                has_attendance, attendance_status = self.check_attendance_status(self.recognized_person_id, person_type)
                if has_attendance:
                    self.attendance_label.configure(text=f'Already In ({attendance_status})', text_color='#28a745')
                    self.attendance_marked = True
                    self.recognition_status.configure(text='Already in for this class session')
                else:
                    self.attendance_label.configure(text='Marking Attendance...', text_color='#ffc107')
                    self.recognition_status.configure(text='Automatically Marking Attendance...')
                    self.auto_record_time_in()
                self.start_auto_reset_countdown()
            else:
                self.recognition_status.configure(text='Unknown Face')
                self.person_label.configure(text='Unknown Face')
                self.id_label.configure(text='Unknown')
                self.attendance_label.configure(text='Not Recognized', text_color='#dc3545')
                self.recognition_status.configure(text='Unknown face detected')
                self.start_auto_reset_countdown()
        except:
            pass

    def process_console_auth_result(self, recognized, person_type):
        """Handle face scan results when console access has been requested."""
        if recognized and person_type == 'Instructor':
            self.awaiting_console_auth = False
            self.cancel_countdown()
            self.cancel_console_timer()
            self.person_label.configure(text=f'Instructor: {recognized}', text_color='#000000')
            self.id_label.configure(text=f"{self.recognized_person_id or 'Unknown'}", text_color='#000000')
            self.recognition_status.configure(text=f'Instructor {recognized} authenticated')
            self.attendance_label.configure(text='Console access granted', text_color='#28a745')
            self.ensure_dark_text(self.recognition_status, self.person_label, self.id_label)
            self.start_console_launch_countdown(recognized, self.recognized_person_id, seconds=3)
        else:
            self.cancel_recognition()
            self.awaiting_console_auth = True
            self.recognition_status.configure(text='Instructor authentication required')
            self.attendance_label.configure(text='Awaiting instructor authorization', text_color='#ffc107')
            self.recognition_status.configure(text='Please have the instructor scan their face to continue.')

    def launch_instructor_console(self, instructor_name=None, instructor_id=None):
        """Stop the scanner and show the instructor console placeholder."""
        self.cancel_console_timer()
        try:
            self.cancel_recognition()
        except Exception:
            pass
        try:
            self.shutdown(destroy_root=False)
        except Exception:
            pass
        self._render_instructor_console(instructor_name, instructor_id)

    def _render_instructor_console(self, instructor_name, instructor_id):
        """Replace the scanner UI with the instructor console view."""
        try:
            for widget in list(self.root.winfo_children()):
                widget.destroy()
            console_view = InstructorConsoleView(self.root, instructor_name=instructor_name, instructor_id=instructor_id, server_url=BACKEND_URL, api_key=API_KEY, on_close=self.handle_console_exit, on_logout=self.handle_console_logout, on_end_class=self.handle_console_end_class)
            console_view.pack(fill='both', expand=True)
        except Exception as e:
            messagebox.showerror('Instructor Console', f'Failed to open console: {e}')
            self.handle_console_exit(resume_scanner=True)

    def handle_console_exit(self, resume_scanner=False):
        """Close the console view and either resume scanning or exit."""
        for widget in list(self.root.winfo_children()):
            try:
                widget.destroy()
            except Exception:
                pass
        if resume_scanner:
            self._restart_scanner_ui()
            return
        self._notify_parent_exit()
        if not self.embedded:
            try:
                self.root.destroy()
            except Exception:
                pass

    def _restart_scanner_ui(self):
        try:
            new_app = FacialRecognitionApp(self.root, class_id=self.class_id, session_id=self.session_id, room_number=self.room_number, embedded=self.embedded, on_exit=self.on_exit, on_logout=self.on_logout, acting_instructor_id=self.acting_instructor_id, acting_instructor_role=self.acting_instructor_role)
            if hasattr(self.root, 'scanner_app'):
                try:
                    self.root.scanner_app = new_app
                except Exception:
                    pass
        except Exception as exc:
            messagebox.showerror('Scanner', f'Unable to return to scanner view: {exc}')
            self._notify_parent_exit()
            if not self.embedded:
                try:
                    self.root.destroy()
                except Exception:
                    pass

    def handle_console_logout(self):
        """Logout the instructor from the client application."""
        self.cancel_countdown()
        self.cancel_console_timer()
        for widget in list(self.root.winfo_children()):
            try:
                widget.destroy()
            except Exception:
                pass
        try:
            self.shutdown(destroy_root=False)
        except Exception:
            pass
        self._notify_parent_logout()
        if not self.embedded:
            try:
                self.root.destroy()
            except Exception:
                pass

    def handle_console_end_class(self):
        """Trigger class termination workflow from the console view."""
        self.end_class()

    def cancel_recognition(self, reset_fields=True):
        """Cancel current recognition and countdown."""
        try:
            self.cancel_countdown()
            self.cancel_console_timer()
            self.cancel_console_auth_timer()
            with self.gui_lock:
                self.is_recognizing = False
                self.recognized_person = None
                self.recognized_person_id = None
                self.recognized_type = None
                self.confidence = 0.0
            with self.camera_lock:
                self.camera_paused = False
                self.detected_faces = []
            for rect_id in self.face_rectangles:
                self.camera_canvas.delete(rect_id)
            self.face_rectangles = []
            if reset_fields:
                self.recognition_status.configure(text='Ready to scan face')
                self.person_label.configure(text='')
                self.id_label.configure(text='')
                self.attendance_label.configure(text='', text_color='#dc3545')
                self.attendance_marked = False
                self.recognition_status.configure(text='Ready to scan face - Position yourself in front of the camera')
        except Exception as e:
            pass

    def auto_record_time_in(self):
        """Automatically record time-in for recognized person without confirmation"""
        if self.recognized_person:
            if self.recognized_person_id and self.recognized_person_id in self.already_marked_ids:
                self.attendance_marked = True
                self.attendance_label.configure(text='✅ Already In', text_color='#28a745')
                self.recognition_status.configure(text='Already in for this class session')
                return
            pst = pytz.timezone('Asia/Manila')
            now_pst = datetime.now(pst)
            timestamp = now_pst.strftime('%Y-%m-%d %H:%M:%S')
            date_only = now_pst.strftime('%Y-%m-%d')
            status = 'late'
            attendance_data = {'person_type': self.recognized_type, 'person_name': self.recognized_person, 'person_id': self.recognized_person_id, 'confidence': round(self.confidence, 2), 'timestamp': timestamp, 'date': date_only, 'method': 'facial_recognition', 'status': status}
            api_result = self.send_attendance_to_api(attendance_data)
            api_success, error_type, error_message = api_result
            icon = '👨\u200d🎓' if self.recognized_type == 'Student' else '👨\u200d🏫'
            if api_success:
                self.attendance_marked = True
                if error_type == 'already_recorded':
                    self.attendance_label.configure(text='✅ Already In', text_color='#28a745')
                    self.recognition_status.configure(text='Already in for this class session')
                else:
                    self.attendance_label.configure(text='✅ Marked Successfully', text_color='#28a745')
                    self.recognition_status.configure(text='Attendance recorded successfully')
                if self.recognized_person_id:
                    self.already_marked_ids.add(self.recognized_person_id)
            elif error_type == 'not_enrolled_in_class':
                self.attendance_label.configure(text='🚫 Not Enrolled', text_color='#dc3545')
                self.recognition_status.configure(text='Person is not enrolled in this class')
            elif error_type == 'not_assigned_to_class':
                self.attendance_label.configure(text='🚫 Not Assigned', text_color='#dc3545')
                self.recognition_status.configure(text='Instructor not assigned to this class')
            else:
                self.attendance_label.configure(text='❌ Recording Failed', text_color='#dc3545')
                self.recognition_status.configure(text='Failed to record attendance')

    def record_time_in(self):
        """Record time-in for recognized person (legacy method for button click)"""
        if self.recognized_person:
            pst = pytz.timezone('Asia/Manila')
            now_pst = datetime.now(pst)
            timestamp = now_pst.strftime('%Y-%m-%d %H:%M:%S')
            date_only = now_pst.strftime('%Y-%m-%d')
            status = 'late'
            attendance_data = {'person_type': self.recognized_type, 'person_name': self.recognized_person, 'person_id': self.recognized_person_id, 'confidence': round(self.confidence, 2), 'timestamp': timestamp, 'date': date_only, 'method': 'facial_recognition', 'status': status}
            api_result = self.send_attendance_to_api(attendance_data)
            api_success, error_type, error_message = api_result
            icon = '👨\u200d🎓' if self.recognized_type == 'Student' else '👨\u200d🏫'
            if api_success:
                self.attendance_marked = True
                self.attendance_label.configure(text='✅ Marked', text_color='#28a745')
                if error_type == 'already_recorded':
                    status_msg = 'ℹ️ Already In'
                    detail_msg = f'{icon} {self.recognized_person} already has attendance recorded today\n🆔 ID: {self.recognized_person_id}\n📚 Class: {self.class_code}\n🏫 Room: {self.room_number}\n📊 Confidence: {self.confidence:.1f}%\n🕒 Timestamp: {timestamp}\n💾 Record already exists in database'
                else:
                    status_msg = '✅ Time-In Recorded Successfully'
                    detail_msg = f'{icon} Time-In recorded for {self.recognized_type} {self.recognized_person}\n🆔 ID: {self.recognized_person_id}\n📚 Class: {self.class_code}\n🏫 Room: {self.room_number}\n📊 Confidence: {self.confidence:.1f}%\n🕒 Timestamp: {timestamp}\n💾 Synced to database'
            elif error_type == 'not_enrolled_in_class':
                status_msg = '🚫 Not Enrolled in Class'
                detail_msg = f'{icon} {self.recognized_person} is not enrolled in this class.\nPlease enroll in this class before marking attendance.'
            elif error_type == 'not_assigned_to_class':
                status_msg = '🚫 Not Assigned to Class'
                detail_msg = f'{icon} {self.recognized_person} is not assigned to teach this class.\nOnly instructors assigned to this class can mark attendance.'
            elif error_type == 'connection_error':
                status_msg = '❌ Connection Error'
                detail_msg = f'Failed to connect to database for {self.recognized_person}\nPlease check backend server connection.'
            else:
                status_msg = '❌ Time-In Recording Failed'
                detail_msg = f'Failed to record attendance for {self.recognized_person}\n{error_message}'
            messagebox.showinfo(status_msg, detail_msg)
            self.cancel_recognition()

    def send_attendance_to_api(self, attendance_data):
        """Send attendance record to backend API"""
        try:
            person_type = attendance_data['person_type']
            person_id = attendance_data['person_id']
            if person_type == 'Student':
                api_endpoint = f'{BACKEND_URL}/api/attendance/record'
                person_name = attendance_data['person_name']
                name_parts = person_name.split()
                first_name = name_parts[0] if name_parts else ''
                last_name = ' '.join(name_parts[1:]) if len(name_parts) > 1 else ''
                payload = {'student_id': person_id, 'first_name': first_name, 'last_name': last_name, 'class_id': self.class_id, 'confidence': attendance_data['confidence'], 'method': attendance_data['method'], 'status': attendance_data['status']}
            elif person_type == 'Instructor':
                api_endpoint = f'{BACKEND_URL}/api/instructor-attendance'
                proxy_instructor_id = None
                recorded_instructor_id = person_id
                try:
                    person_id_int = int(person_id)
                except (TypeError, ValueError):
                    person_id_int = None
                if self.primary_instructor_id is not None and person_id_int is not None and (self.substitute_instructor_id is not None) and (person_id_int == self.substitute_instructor_id):
                    recorded_instructor_id = self.primary_instructor_id
                    proxy_instructor_id = person_id_int
                payload = {'instructor_id': recorded_instructor_id, 'class_id': self.class_id, 'date': attendance_data['date'], 'status': attendance_data['status']}
                if proxy_instructor_id is not None:
                    payload['proxy_instructor_id'] = proxy_instructor_id
            else:
                return False
            response = requests.post(api_endpoint, json=payload, headers=HEADERS, verify=False, timeout=10)
            if response.status_code == 201:
                return (True, None, None)
            elif response.status_code == 200:
                return (True, 'already_recorded', f"Attendance already recorded today for {attendance_data['person_name']}")
            elif response.status_code == 409:
                return (True, 'already_recorded', f"Attendance already recorded today for {attendance_data['person_name']}")
            elif response.status_code == 404:
                return (False, 'not_found', f'{person_type} not found in database')
            elif response.status_code == 403:
                error_data = response.json()
                error_type = error_data.get('error_type', '')
                if error_type == 'not_enrolled_in_class':
                    pass
                elif error_type == 'not_assigned_to_class':
                    pass
                return (False, error_type, error_data.get('message', 'Access denied'))
            else:
                return (False, 'api_error', f'API error: {response.status_code}')
        except requests.exceptions.Timeout:
            return (False, 'connection_error', 'API request timed out')
        except requests.exceptions.ConnectionError:
            return (False, 'connection_error', 'Could not connect to backend API')
        except Exception as e:
            return (False, 'unknown_error', str(e))

    def start_auto_reset_countdown(self):
        """Start 3-second countdown before auto-reset"""
        if self.countdown_active or not self.running:
            return
        self.countdown_active = True
        self.countdown_auto_reset(3)

    def countdown_auto_reset(self, seconds_left):
        """Countdown timer for auto-reset"""
        if not self.running:
            self.countdown_active = False
            return
        if seconds_left > 0:
            self.recognition_status.configure(text=f'Resetting in {seconds_left} seconds...')
            self.auto_reset_timer = self.root.after(1000, lambda: self.countdown_auto_reset(seconds_left - 1))
        else:
            self.countdown_active = False
            self.cancel_recognition()

    def cancel_countdown(self):
        """Cancel the auto-reset countdown"""
        if self.auto_reset_timer:
            self.root.after_cancel(self.auto_reset_timer)
            self.auto_reset_timer = None
        self.countdown_active = False

    def cancel_console_timer(self):
        """Cancel any pending instructor-console countdown."""
        if self.console_redirect_job:
            try:
                self.root.after_cancel(self.console_redirect_job)
            except Exception:
                pass
            self.console_redirect_job = None
        self.console_countdown_remaining = None
        self.console_launch_target = (None, None)

    def start_console_launch_countdown(self, instructor_name, instructor_id=None, seconds=3):
        """Begin a visible countdown before opening the instructor console."""
        self.console_countdown_remaining = max(0, int(seconds))
        self.console_launch_target = (instructor_name, instructor_id)
        self._continue_console_launch_countdown()

    def _continue_console_launch_countdown(self):
        """Update the countdown label and launch console when it reaches zero."""
        self.console_redirect_job = None
        if self.console_countdown_remaining is None:
            return
        instructor_name, instructor_id = self.console_launch_target or (None, None)
        if self.console_countdown_remaining <= 0:
            self.console_countdown_remaining = None
            self.launch_instructor_console(instructor_name, instructor_id)
            return
        self.recognition_status.configure(text=f'Opening instructor console in {self.console_countdown_remaining}...')
        self.console_countdown_remaining -= 1
        self.console_redirect_job = self.root.after(1000, self._continue_console_launch_countdown)

    def shutdown(self, destroy_root=True):
        """Gracefully stop camera/threads and optionally destroy the UI container."""
        if self._shutdown:
            return
        self._shutdown = True
        self.running = False
        self.cancel_countdown()
        self.cancel_console_timer()
        self.cancel_console_auth_timer()
        if hasattr(self, 'cap') and self.cap:
            try:
                self.cap.release()
            except Exception:
                pass
        if destroy_root:
            try:
                self.root.destroy()
            except Exception:
                pass

    def _notify_parent_exit(self):
        if self.on_exit:
            try:
                self.on_exit(self.session_ended)
            except Exception:
                pass
        self.session_ended = False

    def handle_remote_session_end(self, notice=None):
        """Close the scanner if another device ends the session."""
        if self._remote_session_closed:
            return
        self._remote_session_closed = True
        self.session_ended = True
        message = notice or 'Logged out'
        try:
            pass
        except Exception:
            pass
        try:
            self.shutdown(destroy_root=False)
        except Exception:
            pass
        self._notify_parent_exit()
        if not self.embedded:
            try:
                self.root.quit()
            except Exception:
                pass
            try:
                self.root.destroy()
            except Exception:
                pass

    def end_session(self):
        """End the session remotely."""
        self.handle_remote_session_end()

    def _notify_parent_logout(self):
        if self.on_logout:
            try:
                self.on_logout()
            except Exception:
                pass

    def handle_console_button(self):
        """Prompt the instructor to authenticate before showing the console."""
        if self._shutdown:
            return
        if self.awaiting_console_auth:
            messagebox.showinfo('Instructor Console', "Awaiting instructor authentication. Please scan the instructor's face.")
            return
        if not self.instructor_embeddings:
            messagebox.showerror('Instructor Console', 'No instructor facial data available for authentication.')
            return
        self.show_console_confirmation_modal()

    def go_back_to_classes(self):
        """Go back to class selection without ending the session"""
        if not messagebox.askyesno('Go Back', 'Are you sure you want to go back to class selection?\n\nThe session will remain active.'):
            return
        self.session_ended = False
        if self.embedded:
            self.shutdown(destroy_root=False)
            try:
                self.root.destroy()
            except Exception:
                pass
            self._notify_parent_exit()
        else:
            self.shutdown(destroy_root=True)

    def end_class(self):
        """End the class session and mark absent students for this specific class only"""
        if messagebox.askyesno('🏁 End Class', "Are you sure you want to end this class session?\n\nAll students who haven't checked in for this class will be marked as ABSENT."):
            if self.class_id:
                try:
                    instructor_id = self.acting_instructor_id
                    if instructor_id is None:
                        classes_response = requests.get(f'{BACKEND_URL}/classes/api/list', headers=HEADERS, verify=False, timeout=10)
                        if classes_response.status_code == 200:
                            classes = classes_response.json()
                            try:
                                target_class_id = int(self.class_id)
                                class_data = next((c for c in classes if int(c.get('id', 0)) == target_class_id), None)
                                if class_data:
                                    pass
                            except (ValueError, TypeError) as e:
                                class_data = None
                            if class_data:
                                instructor_id = class_data.get('instructorId')
                            else:
                                messagebox.showerror('Error', 'Could not find class in the system.')
                                return
                        else:
                            messagebox.showerror('Error', f'Could not fetch class list: {classes_response.status_code}')
                            return
                    if instructor_id:
                        checkout_data = {'instructor_id': instructor_id, 'class_id': self.class_id}
                        if self.session_id:
                            checkout_data['class_session_id'] = self.session_id
                        checkout_response = requests.post(f'{BACKEND_URL}/api/checkout/instructor', json=checkout_data, headers=HEADERS, verify=False, timeout=10)
                        if checkout_response.status_code != 200:
                            try:
                                error_payload = checkout_response.json()
                            except ValueError:
                                error_payload = {}
                            error_message = error_payload.get('error') or error_payload.get('message') or checkout_response.text or 'Unknown server response'
                            messagebox.showerror('Error', f'Failed to end class: {error_message}')
                            return
                    else:
                        messagebox.showerror('Error', 'Could not find instructor for this class.')
                        return
                except Exception as e:
                    messagebox.showerror('Error', f'Failed to end class: {str(e)}')
                    return
            self.session_ended = True
            if self.embedded:
                self.shutdown(destroy_root=False)
                try:
                    self.root.destroy()
                except Exception:
                    pass
                self._notify_parent_exit()
            else:
                try:
                    self.root.quit()
                except Exception:
                    pass
                self.shutdown(destroy_root=True)

def main():
    import sys
    class_id = sys.argv[1] if len(sys.argv) > 1 else None
    session_id = sys.argv[2] if len(sys.argv) > 2 else None
    room_number = sys.argv[3] if len(sys.argv) > 3 else None
    root = ctk.CTk()
    root.configure(fg_color=('#f0f8f0', '#1e4a1e'))
    try:
        root.update_idletasks()
    except Exception:
        pass
    try:
        screen_width = root.winfo_screenwidth()
        screen_height = root.winfo_screenheight()
    except Exception:
        screen_width = screen_height = None
    if screen_width and screen_height:
        try:
            root.geometry(f'{screen_width}x{screen_height}+0+0')
        except Exception:
            pass
    try:
        root.state('zoomed')
    except Exception:
        pass
    app = FacialRecognitionApp(root, class_id, session_id, room_number)
    root.mainloop()
if __name__ == '__main__':
    main()
