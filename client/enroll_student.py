"""Instructor-facing student registration window for the kiosk UI."""

import os
import random
import re
import threading
import time
import warnings
import pickle
import tempfile
from datetime import datetime
from io import BytesIO
from tkinter import messagebox
from urllib.parse import urljoin

import customtkinter as ctk
import requests
import cv2
import numpy as np
from PIL import Image

# Try to import DeepFace
try:
	from deepface import DeepFace
	DEEPFACE_AVAILABLE = True
except ImportError:
	DeepFace = None
	DEEPFACE_AVAILABLE = False

from ui_utils import bring_window_to_front
from server import SERVER_URL as DEFAULT_SERVER_URL, API_KEY as DEFAULT_API_KEY

try:  # Silence SSL warnings for self-signed certs
	from urllib3.exceptions import InsecureRequestWarning
	warnings.simplefilter('ignore', InsecureRequestWarning)
except Exception:
	pass



# DEFAULT_SERVER_URL and DEFAULT_API_KEY come from server.py (can be overridden via env)
YEAR_LEVEL_OPTIONS = [
	'All Year Levels',
	'1st Year',
	'2nd Year',
	'3rd Year',
	'4th Year',
]

# Keep table headers/data columns in sync so rows stay visually aligned.
STUDENT_TABLE_COLUMNS = [
	('Name', 3),
	('Student ID', 2),
	('Year Level', 1),
	('Face Status', 1),
	('Actions', 2),
]


REALTIME_REFRESH_MS = 9000  # ~9 seconds between silent updates
POSE_DISPLACEMENT_PX = 45  # requested movement threshold per directional pose
ROLL_SEARCH_ANGLES = (-24, -16, -8, 8, 16, 24)  # degrees scanned when the face is rolled



class FaceCaptureWindow(ctk.CTkToplevel):
	"""Camera-driven dialog for capturing and uploading a student's face."""

	def __init__(self, master, student, server_url, api_key, on_success=None):
		super().__init__(master)
		self.student = student
		self.student_id = student.get('id')
		self.server_url = (server_url or DEFAULT_SERVER_URL).rstrip('/')
		self.api_key = api_key
		self.headers = {'X-API-Key': self.api_key}
		self.on_success = on_success
		self.cap = None
		self.running = False
		self.current_frame = None
		self.captured_frame = None
		self.saved_photos = 0
		self.preview_image = None
		self.status_var = ctk.StringVar(value="Click Start to begin automatic face capture every 3 seconds.")
		self.face_detector = self._load_face_detector()
		self.roll_search_angles = ROLL_SEARCH_ANGLES
		self.liveness_enabled = False  # Disable pose detection
		self.liveness_var = ctk.StringVar(value='Face will be captured automatically every 3 seconds when started.')
		self.liveness_steps = []
		self.current_liveness_step = 0
		self.baseline_face_center = None
		self.liveness_complete = False
		self.auto_capture_triggered = False
		self.movement_threshold = 42
		self.pose_hold_counter = 0
		self.pose_hold_required = 8
		self.center_tolerance = 18
		self.pending_pose = None
		self.capture_btn = None
		self.save_btn = None
		
		# Auto-capture settings
		self.auto_capture_enabled = False
		self.auto_capture_interval = 3.0  # Capture every 3 seconds
		self.auto_capture_timer = None
		self.last_capture_time = 0
		self.is_paused = False
		self.countdown_timer = None
		self.countdown_seconds = 3
		self.uploaded_image_paths = []  # Store paths of uploaded images for embedding extraction

		self.title(f"Capture Face - {student.get('name') or self.student_id}")
		self.geometry('760x660')
		self.resizable(False, False)
		self.protocol('WM_DELETE_WINDOW', self._handle_close)
		bring_window_to_front(self)
		self._enter_fullscreen()
		self.bind('<Escape>', lambda _event=None: self._handle_close())

		self._build_ui()
		# Don't reset liveness flow - we're using auto-capture instead
		self.after(150, self._start_camera)

	def _enter_fullscreen(self):
		"""Expand capture dialog to match kiosk fullscreen layout."""
		try:
			screen_w = self.winfo_screenwidth()
			screen_h = self.winfo_screenheight()
			if screen_w and screen_h:
				self.geometry(f"{screen_w}x{screen_h}+0+0")
		except Exception:
			pass

		try:
			self.overrideredirect(True)
		except Exception:
			pass

		try:
			self.attributes('-fullscreen', True)
		except Exception:
			try:
				self.state('zoomed')
			except Exception:
				pass

	def _build_ui(self):
		container = ctk.CTkFrame(self, fg_color=('#f8fff8', '#0f200f'))
		container.pack(fill='both', expand=True, padx=20, pady=20)

		name_label = ctk.CTkLabel(
			container,
			text=f"Student: {self.student.get('name') or self.student_id}",
			font=('Arial', 20, 'bold'),
			text_color=('#006400', '#90EE90'),
		)
		name_label.pack(pady=(10, 20))

		self.preview_label = ctk.CTkLabel(
			container,
			text='Initializing camera...',
			width=680,
			height=480,
			fg_color=('#000000', '#000000'),
			corner_radius=12,
		)
		self.preview_label.pack(pady=10)

		liveness_panel = ctk.CTkFrame(container, fg_color='transparent')
		liveness_panel.pack(pady=(4, 14))

		self.liveness_label = ctk.CTkLabel(
			liveness_panel,
			textvariable=self.liveness_var,
			font=('Arial', 16, 'bold'),
			text_color=('#0b5f0b', '#b6f7b6'),
		)
		self.liveness_label.pack(pady=(0, 6))

		self.liveness_progress = ctk.CTkProgressBar(liveness_panel, width=420, height=14)
		self.liveness_progress.pack()
		self.liveness_progress.set(0.0 if self.liveness_enabled else 1.0)

		button_row = ctk.CTkFrame(container, fg_color='transparent')
		button_row.pack(pady=15)

		# Combined start/pause button
		self.start_pause_btn = ctk.CTkButton(
			button_row,
			text='Start',
			width=120,
			height=50,
			command=self._toggle_start_pause,
			fg_color=('#28a745', '#218838'),
			hover_color=('#218838', '#1e7e34'),
		)
		self.start_pause_btn.pack(side='left', padx=8)

		self.restart_btn = ctk.CTkButton(
			button_row,
			text='Restart',
			width=120,
			height=50,
			command=self._restart_capture,
			fg_color=('#6c757d', '#4a4f54'),
			hover_color=('#545b62', '#3a3f44'),
		)
		self.restart_btn.pack(side='left', padx=8)

		close_btn = ctk.CTkButton(
			button_row,
			text='Close',
			width=120,
			height=50,
			command=self._handle_close,
			fg_color=('#dc3545', '#c82333'),
			hover_color=('#a71d2a', '#7f151f'),
		)
		close_btn.pack(side='left', padx=8)

		self.status_label = ctk.CTkLabel(
			container,
			textvariable=self.status_var,
			font=('Arial', 14),
			text_color=('#0b5f0b', '#b6f7b6'),
		)
		self.status_label.pack(pady=(5, 0))

		self.saved_label = ctk.CTkLabel(
			container,
			text='Photos saved this session: 0',
			font=('Arial', 13),
			text_color=('#0b5f0b', '#b6f7b6'),
		)
		self.saved_label.pack(pady=(2, 10))

	def _start_camera(self):
		try:
			self.cap = cv2.VideoCapture(0)
			if not self.cap.isOpened():
				raise RuntimeError('Unable to access camera device')
			self.running = True
			self._update_preview()
		except Exception as exc:
			messagebox.showerror('Camera Error', str(exc), parent=self)
			self._handle_close()

	def _update_preview(self):
		if not self.running:
			return

		frame_to_show = None
		if self.captured_frame is not None:
			frame_to_show = self.captured_frame
		else:
			ret, frame = self.cap.read()
			if ret:
				self.current_frame = frame
				frame_to_show = frame

		if frame_to_show is not None:
			if self.captured_frame is None:
				# Check for auto-capture every 3 seconds
				if self.auto_capture_enabled and not self.is_paused and self.countdown_timer is None:
					current_time = datetime.now().timestamp()
					if current_time - self.last_capture_time >= self.auto_capture_interval:
						# Check if face is detected before capturing
						if self._detect_face_center(frame_to_show) is not None:
							self._start_countdown()
							self.last_capture_time = current_time
			rgb_frame = cv2.cvtColor(frame_to_show, cv2.COLOR_BGR2RGB)
			image = Image.fromarray(rgb_frame)
			image = image.resize((680, 480))
			self.preview_image = ctk.CTkImage(light_image=image, dark_image=image, size=(680, 480))
			self.preview_label.configure(image=self.preview_image, text='')

		self.after(40, self._update_preview)

	def _capture_frame(self):
		if self.current_frame is None:
			self.status_var.set('No frame available. Please try again.')
			return
		self.captured_frame = self.current_frame.copy()
		if self.capture_btn:
			self.capture_btn.configure(state='disabled')
		if self.save_btn:
			self.save_btn.configure(state='normal')
		self.retake_btn.configure(state='normal')
		self.status_var.set('Capture frozen. Restart the sequence if you need another pose.')

	def _toggle_start_pause(self):
		"""Toggle between start and pause."""
		if not self.running or self.cap is None:
			self.status_var.set('Camera not ready. Please wait...')
			return
		
		if not self.auto_capture_enabled or self.is_paused:
			# Start
			self.auto_capture_enabled = True
			self.is_paused = False
			self.last_capture_time = datetime.now().timestamp()
			self.captured_frame = None
			
			self.start_pause_btn.configure(text='Pause', fg_color=('#ffc107', '#e0a800'), hover_color=('#e0a800', '#d39e00'))
			self.restart_btn.configure(state='normal')
			
			self.status_var.set('Auto-capture started. Face will be captured every 3 seconds.')
			self.liveness_var.set('Auto-capturing... Make sure your face is visible in the frame.')
		else:
			# Pause
			self.is_paused = True
			if self.countdown_timer:
				self.after_cancel(self.countdown_timer)
				self.countdown_timer = None
			
			self.start_pause_btn.configure(text='Start', fg_color=('#28a745', '#218838'), hover_color=('#218838', '#1e7e34'))
			self.status_var.set('Auto-capture paused. Click Start to resume.')
			self.liveness_var.set('Paused - Click Start to resume capturing.')

	def _start_countdown(self):
		"""Start countdown before capturing."""
		if self.countdown_timer:
			return
		
		self.countdown_seconds = 3
		self._update_countdown()

	def _update_countdown(self):
		"""Update countdown display."""
		if not self.auto_capture_enabled or self.is_paused:
			self.countdown_timer = None
			return
		
		if self.countdown_seconds > 0:
			self.liveness_var.set(f'Capturing in {self.countdown_seconds}...')
			self.countdown_seconds -= 1
			self.countdown_timer = self.after(1000, self._update_countdown)
		else:
			self.countdown_timer = None
			self.liveness_var.set('Capturing now!')
			self._auto_capture_frame()

	def _restart_capture(self):
		"""Restart the capture sequence."""
		self.auto_capture_enabled = False
		self.is_paused = False
		self.captured_frame = None
		self.last_capture_time = 0
		self.saved_photos = 0
		self.uploaded_image_paths = []
		
		if self.countdown_timer:
			self.after_cancel(self.countdown_timer)
			self.countdown_timer = None
		
		if hasattr(self, 'saved_label') and self.saved_label is not None:
			self.saved_label.configure(text='Photos saved this session: 0')
		
		self.start_pause_btn.configure(text='Start', fg_color=('#28a745', '#218838'), hover_color=('#218838', '#1e7e34'))
		self.restart_btn.configure(state='normal')
		
		self.status_var.set('Capture sequence restarted. Click Start to begin capturing.')
		self.liveness_var.set('Ready to start. Click Start to begin auto-capture.')

	def _auto_capture_frame(self):
		"""Automatically capture the current frame."""
		if self.current_frame is None:
			return
		
		self.captured_frame = self.current_frame.copy()
		self.status_var.set(f'Capturing photo {self.saved_photos + 1}...')
		self._save_capture()

	def _save_capture(self, auto_pose=None):
		if self.captured_frame is None:
			self.status_var.set('Capture an image before saving.')
			return

		success, buffer = cv2.imencode('.jpg', self.captured_frame)
		if not success:
			messagebox.showerror('Capture Error', 'Failed to encode captured image. Please try again.', parent=self)
			return

		pose_label = None  # No pose labels for auto-capture
		self.status_var.set('Uploading photo automatically...')

		image_bytes = buffer.tobytes()
		threading.Thread(target=self._upload_image, args=(image_bytes, pose_label), daemon=True).start()

	def _upload_image(self, image_bytes, pose_label=None):
		url = f"{self.server_url}/students/api/upload-image"
		files = {'image': ('capture.jpg', image_bytes, 'image/jpeg')}
		data = {'student_id': self.student_id}
		if pose_label:
			data['pose_label'] = pose_label
		try:
			response = requests.post(url, headers=self.headers, data=data, files=files, verify=False, timeout=30)
			payload = response.json()
			if response.status_code >= 400 or not payload.get('success', True):
				raise RuntimeError(payload.get('message', 'Failed to upload image'))
			self.after(0, lambda: self._handle_upload_success(payload, pose_label))
		except Exception as exc:
			self.after(0, lambda: self._handle_upload_error(str(exc), pose_label))

	def _handle_upload_success(self, payload, pose_label=None):
		self.saved_photos += 1
		if hasattr(self, 'saved_label') and self.saved_label is not None:
			self.saved_label.configure(text=f'Photos saved this session: {self.saved_photos}')
		self.captured_frame = None
		
		# Store the image path for embedding extraction
		image_data = payload.get('image', {})
		image_path = image_data.get('path')
		if image_path:
			# Convert relative path to absolute path
			full_path = os.path.join(self.server_url.replace('https://', '').replace('http://', '').split(':')[0], image_path.lstrip('/'))
			# Store server URL and relative path for later use
			self.uploaded_image_paths.append({
				'student_id': self.student_id,
				'image_path': image_path,
				'server_url': self.server_url
			})
		
		if callable(self.on_success):
			self.on_success(self.student_id, payload.get('image'))

		# For auto-capture, just show success and continue
		if self.auto_capture_enabled and not self.is_paused:
			self.status_var.set(f'Photo {self.saved_photos} saved. Next capture in 3 seconds...')
			self.liveness_var.set(f'Auto-capturing... ({self.saved_photos} photos saved)')
		else:
			messagebox.showinfo('Capture Saved', payload.get('message', 'Photo uploaded successfully.'), parent=self)
			self.status_var.set('Photo saved. Click Start to continue capturing or Close when finished.')

	def _handle_upload_error(self, message, pose_label=None):
		self.status_var.set(f'Upload failed: {message}')
		self.captured_frame = None
		
		if self.auto_capture_enabled and not self.is_paused:
			self.status_var.set(f'Upload failed: {message}. Will retry on next capture.')
			self.liveness_var.set('Upload error - will retry automatically...')
		else:
			messagebox.showerror('Capture Error', message, parent=self)
			self.status_var.set('Upload failed. Click Start to try again.')

	def _handle_close(self):
		# Stop auto-capture
		self.auto_capture_enabled = False
		self.is_paused = True
		
		if self.countdown_timer:
			try:
				self.after_cancel(self.countdown_timer)
			except Exception:
				pass
		
		# Extract embeddings from uploaded images before closing
		if self.uploaded_image_paths:
			self.status_var.set('Extracting embeddings from captured images...')
			self.liveness_var.set('Please wait, processing embeddings...')
			self.update()  # Force UI update
			
			# Extract embeddings in a thread to avoid blocking
			threading.Thread(target=self._extract_and_save_embeddings, daemon=True).start()
			
			# Wait a bit for the thread to start, then close
			self.after(500, self._final_close)
		else:
			self._final_close()
	
	def _final_close(self):
		"""Final cleanup and window close."""
		self.running = False
		if self.cap:
			try:
				self.cap.release()
			except Exception:
				pass
			self.cap = None
		if self.auto_capture_timer:
			try:
				self.after_cancel(self.auto_capture_timer)
			except Exception:
				pass
		if self.master is not None and getattr(self.master, 'winfo_exists', lambda: False)():
			bring_window_to_front(self.master)
		self.destroy()
	
	def _extract_and_save_embeddings(self):
		"""Extract embeddings from uploaded images and append to pickle file."""
		if not DEEPFACE_AVAILABLE:
			print("⚠️ DeepFace not available, skipping embedding extraction")
			return
		
		try:
			cache_file = self._get_cache_file_path()
			cache_dir = os.path.dirname(cache_file)
			if cache_dir:
				os.makedirs(cache_dir, exist_ok=True)
			
			# Load existing cache file
			if os.path.exists(cache_file):
				try:
					with open(cache_file, 'rb') as f:
						face_data = pickle.load(f)
				except Exception as e:
					print(f"⚠️ Error loading existing cache: {e}")
					face_data = {
						'student_embeddings': [],
						'student_names': [],
						'student_ids': [],
						'instructor_embeddings': [],
						'instructor_names': [],
						'instructor_ids': []
					}
			else:
				face_data = {
					'student_embeddings': [],
					'student_names': [],
					'student_ids': [],
					'instructor_embeddings': [],
					'instructor_names': [],
					'instructor_ids': []
				}
			
			# Get existing student IDs to avoid duplicates
			existing_student_ids = set(face_data.get('student_ids', []))
			
			# Get student name from the student object
			student_name = self.student.get('name') or f"{self.student.get('firstName', '')} {self.student.get('lastName', '')}".strip()
			if not student_name:
				student_name = f"Student_{self.student_id}"
			
			# Process each uploaded image - extract embeddings from ALL captured faces
			extracted_count = 0
			processed_images = []
			
			for img_info in self.uploaded_image_paths:
				if img_info['student_id'] != self.student_id:
					continue
				
				image_path = img_info['image_path']
				server_url = img_info['server_url']
				
				# Download image from server
				try:
					# Construct full URL - image_path might be relative or absolute
					if image_path.startswith('http'):
						full_url = image_path
					else:
						full_url = f"{server_url.rstrip('/')}/{image_path.lstrip('/')}"
					response = requests.get(full_url, headers=self.headers, verify=False, timeout=10)
					if response.status_code != 200:
						print(f"⚠️ Failed to download image: {image_path}")
						continue
					
					# Save to temp file
					with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp_file:
						tmp_file.write(response.content)
						tmp_path = tmp_file.name
					
					try:
						# Extract embedding using DeepFace
						embedding_result = DeepFace.represent(
							img_path=tmp_path,
							model_name="Facenet512",
							detector_backend="opencv",
							enforce_detection=False,
							align=True
						)
						
						if embedding_result and len(embedding_result) > 0:
							embedding = np.array(embedding_result[0]['embedding'], dtype=np.float32)
							
							# Append to face_data - extract from ALL images, not just one
							face_data['student_embeddings'].append(embedding.tolist())
							face_data['student_names'].append(student_name)
							face_data['student_ids'].append(self.student_id)
							extracted_count += 1
							processed_images.append(image_path)
							print(f"✅ Extracted embedding {extracted_count} for student {self.student_id} ({student_name}) from {os.path.basename(image_path)}")
					finally:
						# Clean up temp file
						try:
							os.remove(tmp_path)
						except Exception:
							pass
					
				except Exception as e:
					print(f"⚠️ Error processing image {image_path}: {e}")
					continue
			
			if extracted_count == 0 and self.uploaded_image_paths:
				print(f"⚠️ No embeddings extracted from {len(self.uploaded_image_paths)} uploaded image(s) for student {self.student_id}")
			
			# Save updated cache file
			if extracted_count > 0:
				try:
					with open(cache_file, 'wb') as f:
						pickle.dump(face_data, f)
					print(f"✅ Successfully saved {extracted_count} new embedding(s) to cache file")
					print(f"📊 Total embeddings for student {self.student_id}: {extracted_count} face(s)")
				except Exception as e:
					print(f"⚠️ Error saving cache file: {e}")
			else:
				if self.uploaded_image_paths:
					print(f"⚠️ No embeddings extracted from {len(self.uploaded_image_paths)} uploaded image(s)")
				else:
					print("ℹ️ No images uploaded, skipping embedding extraction")
				
		except Exception as e:
			print(f"⚠️ Error in embedding extraction: {e}")
	
	def _get_cache_file_path(self):
		"""Get the path to the face encodings cache file."""
		return os.path.join(os.path.dirname(__file__), '..', 'cache', 'face_encodings.pkl')

	def _load_face_detector(self):
		try:
			cascade_path = getattr(cv2.data, 'haarcascades', '')
			classifier = cv2.CascadeClassifier(os.path.join(cascade_path, 'haarcascade_frontalface_default.xml'))
			if classifier.empty():
				return None
			return classifier
		except Exception:
			return None

	def _reset_liveness_flow(self, *, initial=False):
		if not self.liveness_enabled:
			self.liveness_steps = []
			self.current_liveness_step = 0
			self.baseline_face_center = None
			self.pose_hold_counter = 0
			self.liveness_complete = True
			self.auto_capture_triggered = False
			self.pending_pose = None
			if hasattr(self, 'liveness_progress'):
				self.liveness_progress.set(0.0)
			self.liveness_var.set('Guided capture unavailable. Use manual controls instead.')
			if self.capture_btn:
				self.capture_btn.configure(state='normal')
			if self.retake_btn:
				self.retake_btn.configure(state='disabled')
			if self.save_btn:
				self.save_btn.configure(state='disabled')
			if initial:
				self.status_var.set("Align the student's face within the frame and hold still for automatic capture.")
			return

		self.liveness_steps = self._select_liveness_steps()
		self.current_liveness_step = 0
		self.baseline_face_center = None
		self.pose_hold_counter = 0
		self.liveness_complete = False
		self.auto_capture_triggered = False
		self.pending_pose = None
		self.captured_frame = None
		if self.capture_btn:
			self.capture_btn.configure(state='disabled')
		if self.retake_btn:
			self.retake_btn.configure(state='normal')
		if self.save_btn:
			self.save_btn.configure(state='disabled')
		if initial:
			self.status_var.set('Follow the prompts below; each pose is captured automatically.')
		self._update_liveness_progress()
		self._update_liveness_display()

	def _select_liveness_steps(self):
		return ['center', 'left', 'right', 'up', 'down']

	def _update_liveness_display(self, message=None):
		if not hasattr(self, 'liveness_var'):
			return
		if message:
			self.liveness_var.set(message)
			return
		if not self.liveness_enabled:
			self.liveness_var.set('Guided capture unavailable. Use manual controls instead.')
			return
		if not self.liveness_steps:
			self.liveness_var.set('Preparing pose guidance...')
			return
		total = len(self.liveness_steps)
		if self.liveness_complete:
			self.liveness_var.set(f'All {total} poses captured. Close or restart if you need another set.')
			return
		step = min(self.current_liveness_step, total - 1)
		self.liveness_var.set(f"Pose {step + 1} of {total}: {self._describe_pose(self.liveness_steps[step])}")

	def _update_liveness_progress(self):
		if not hasattr(self, 'liveness_progress'):
			return
		total_steps = max(len(self.liveness_steps), 1)
		if self.liveness_complete:
			self.liveness_progress.set(1.0)
			return
		progress = self.current_liveness_step / total_steps
		self.liveness_progress.set(progress)

	def _describe_pose(self, direction):
		return {
			'center': 'Face forward and hold still',
			'left': 'Tilt your head to the left',
			'right': 'Tilt your head to the right',
			'up': 'Tilt your chin upward',
			'down': 'Tilt your chin downward',
		}.get(direction, direction)

	def _detect_face_center(self, frame):
		if self.face_detector is None:
			return None

		gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
		center = self._detect_center_in_gray(gray)
		if center is not None:
			return center
		if not self.roll_search_angles:
			return None
		return self._detect_center_with_rotation(gray)

	def _detect_center_in_gray(self, gray):
		faces = self.face_detector.detectMultiScale(
			gray,
			scaleFactor=1.15,
			minNeighbors=5,
			minSize=(90, 90),
		)
		if len(faces) == 0:
			return None
		x, y, w, h = max(faces, key=lambda box: box[2] * box[3])
		return (x + (w / 2.0), y + (h / 2.0))

	def _detect_center_with_rotation(self, gray):
		height, width = gray.shape[:2]
		frame_center = (width / 2.0, height / 2.0)
		for angle in self.roll_search_angles:
			rotation_matrix = cv2.getRotationMatrix2D(frame_center, angle, 1.0)
			# Searching rotated frames keeps the cascade useful even when the student's head is tilted.
			rotated = cv2.warpAffine(
				gray,
				rotation_matrix,
				(width, height),
				flags=cv2.INTER_LINEAR,
				borderMode=cv2.BORDER_REPLICATE,
			)
			center = self._detect_center_in_gray(rotated)
			if center is None:
				continue
			return self._map_point_from_rotation(center, rotation_matrix)
		return None

	def _map_point_from_rotation(self, point, rotation_matrix):
		inverse = cv2.invertAffineTransform(rotation_matrix)
		homogenous = np.array([point[0], point[1], 1.0])
		mapped = inverse.dot(homogenous)
		return (float(mapped[0]), float(mapped[1]))

	def _process_liveness(self, frame):
		if (
			not self.liveness_enabled
			or not self.liveness_steps
			or self.liveness_complete
			or self.auto_capture_triggered
		):
			return
		if self.current_liveness_step >= len(self.liveness_steps):
			return

		current_center = self._detect_face_center(frame)
		if current_center is None:
			self._update_liveness_display('Move closer and keep your face within the frame.')
			self.baseline_face_center = None
			self.pose_hold_counter = 0
			return

		if self.baseline_face_center is None:
			self.baseline_face_center = current_center

		pose = self.liveness_steps[self.current_liveness_step]
		if pose == 'center':
			satisfied = self._center_pose_satisfied(current_center)
			if not satisfied:
				self._update_liveness_display('Face forward and hold steady for a moment.')
		else:
			satisfied, remaining = self._check_direction_pose(pose, current_center)
			if not satisfied and remaining and remaining > int(self.movement_threshold * 0.4):
				self._update_liveness_display(f"{self._describe_pose(pose)} a little more ({remaining} px).")

		if satisfied:
			self._complete_pose_capture(frame, pose)

	def _center_pose_satisfied(self, current_center):
		dx = current_center[0] - self.baseline_face_center[0]
		dy = current_center[1] - self.baseline_face_center[1]
		tolerance = self.center_tolerance
		if abs(dx) <= tolerance and abs(dy) <= tolerance:
			self.pose_hold_counter += 1
			if self.pose_hold_counter >= self.pose_hold_required:
				self.pose_hold_counter = 0
				return True
		else:
			self.pose_hold_counter = 0
			self.baseline_face_center = current_center
		return False

	def _check_direction_pose(self, direction, current_center):
		dx = current_center[0] - self.baseline_face_center[0]
		dy = current_center[1] - self.baseline_face_center[1]
		threshold = self.movement_threshold
		if direction == 'left':
			delta = -threshold - dx
			satisfied = dx <= -threshold
		elif direction == 'right':
			delta = threshold - dx
			satisfied = dx >= threshold
		elif direction == 'up':
			delta = -threshold - dy
			satisfied = dy <= -threshold
		else:  # down
			delta = threshold - dy
			satisfied = dy >= threshold

		remaining = max(0, int(delta))
		if satisfied:
			self.baseline_face_center = current_center
		return satisfied, remaining

	def _complete_pose_capture(self, frame, pose):
		self.pose_hold_counter = 0
		self.baseline_face_center = None
		self._update_liveness_display(f"{self._describe_pose(pose)} detected. Capturing photo...")
		self._auto_capture_pose(frame, pose)

	def _auto_capture_pose(self, frame, pose):
		if self.auto_capture_triggered:
			return
		self.auto_capture_triggered = True
		self.pending_pose = pose
		self.captured_frame = frame.copy()
		if self.capture_btn:
			self.capture_btn.configure(state='disabled')
		if self.save_btn:
			self.save_btn.configure(state='disabled')
		self.retake_btn.configure(state='disabled')
		self.status_var.set(f"{self._describe_pose(pose)} pose confirmed. Uploading photo...")
		self._save_capture(auto_pose=pose)

	def _advance_pose_sequence(self):
		self.pending_pose = None
		self.baseline_face_center = None
		self.pose_hold_counter = 0
		self.auto_capture_triggered = False
		self.captured_frame = None
		if self.retake_btn:
			self.retake_btn.configure(state='normal')
		self.current_liveness_step += 1
		total_steps = len(self.liveness_steps)
		if self.current_liveness_step >= total_steps:
			self.liveness_complete = True
			self._update_liveness_progress()
			self._update_liveness_display()
			self.status_var.set(f'All {total_steps} poses captured and uploaded. Close this window or restart if needed.')
			if self.capture_btn:
				self.capture_btn.configure(state='normal')
			if self.retake_btn:
				self.retake_btn.configure(state='normal')
			return
		self._update_liveness_progress()
		self._update_liveness_display()


class StudentPhotoViewer(ctk.CTkToplevel):
	"""Modal window that previews all saved facial images for a student."""

	def __init__(self, master, student, server_url, api_key):
		super().__init__(master)
		self.student = student
		self.student_id = student.get('id')
		self.server_url = (server_url or DEFAULT_SERVER_URL).rstrip('/')
		self.headers = {'X-API-Key': api_key}
		self.image_refs = []
		self.status_var = ctk.StringVar(value='Loading saved photos...')
		self.auto_refresh_interval = 8000
		self.auto_refresh_job = None

		self.title(f"Saved Photos - {student.get('name') or self.student_id}")
		self.geometry('900x620')
		self.minsize(720, 520)
		bring_window_to_front(self)
		self.protocol('WM_DELETE_WINDOW', self.destroy)

		self._build_ui()
		self._load_images_async()

	def _build_ui(self):
		header = ctk.CTkLabel(
			self,
			text=f"Photos for {self.student.get('name') or self.student_id}",
			font=('Arial', 24, 'bold'),
			text_color=('#006400', '#90EE90'),
		)
		header.pack(pady=20)

		self.gallery = ctk.CTkScrollableFrame(self, fg_color=('#f8fff8', '#0f200f'))
		self.gallery.pack(fill='both', expand=True, padx=20, pady=10)
		self.gallery.grid_columnconfigure((0, 1, 2), weight=1)

		self.placeholder_label = ctk.CTkLabel(
			self.gallery,
			textvariable=self.status_var,
			font=('Arial', 18),
			text_color=('#0b5f0b', '#b6f7b6'),
		)
		self.placeholder_label.grid(row=0, column=0, columnspan=3, pady=40)

		close_btn = ctk.CTkButton(
			self,
			text='Close',
			width=180,
			height=48,
			fg_color=('#dc3545', '#c82333'),
			hover_color=('#a71d2a', '#7f151f'),
			command=self.destroy,
		)
		close_btn.pack(pady=10)

	def _load_images_async(self, silent=False):
		if not silent:
			self.status_var.set('Loading saved photos...')

		def task():
			url = f"{self.server_url}/students/api/images/{self.student_id}"
			try:
				response = requests.get(url, headers=self.headers, verify=False, timeout=20)
				payload = response.json()
				if response.status_code >= 400 or not payload.get('success', True):
					raise RuntimeError(payload.get('message', 'Failed to load photos'))
				images = payload.get('images', [])
				loaded = []
				for image_meta in images:
					path = self._resolve_image_url(image_meta.get('path'))
					if not path:
						continue
					resp = requests.get(path, verify=False, timeout=20)
					resp.raise_for_status()
					img = Image.open(BytesIO(resp.content))
					img.thumbnail((260, 260))
					loaded.append((image_meta, img.copy()))
				self.after(0, lambda: self._display_images(loaded, silent=silent))
			except Exception as exc:
				self.after(0, lambda: self._show_error(str(exc)))

		threading.Thread(target=task, daemon=True).start()

	def _display_images(self, loaded_images, silent=False):
		for widget in self.gallery.winfo_children():
			widget.destroy()

		self.image_refs.clear()

		if not loaded_images:
			self.status_var.set('No saved photos for this student yet.')
			self.placeholder_label = ctk.CTkLabel(
				self.gallery,
				textvariable=self.status_var,
				font=('Arial', 18),
				text_color=('#b35c00', '#ffdd99'),
			)
			self.placeholder_label.grid(row=0, column=0, columnspan=3, pady=40)
			return

		for index, (meta, image) in enumerate(loaded_images):
			row = index // 3
			col = index % 3
			card = ctk.CTkFrame(self.gallery, fg_color=('#ffffff', '#1b2b1b'))
			card.grid(row=row, column=col, padx=12, pady=12, sticky='n')

			preview = ctk.CTkImage(light_image=image, dark_image=image, size=image.size)
			self.image_refs.append(preview)

			ctk.CTkLabel(card, text='', image=preview).pack(padx=10, pady=10)

			timestamp = meta.get('createdAt') or 'Uploaded'
			timestamp = self._format_timestamp(timestamp)
			ctk.CTkLabel(
				card,
				text=timestamp,
				font=('Arial', 14),
				text_color=('#0b5f0b', '#b6f7b6'),
			).pack(pady=(0, 10))

		self.status_var.set(f"Loaded {len(loaded_images)} photo(s).")
		self._schedule_auto_refresh()

	def _format_timestamp(self, value):
		if not value:
			return ''
		try:
			parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
			return parsed.strftime('Captured %b %d, %Y %I:%M %p')
		except Exception:
			return value

	def _resolve_image_url(self, path):
		if not path:
			return None
		path = path.strip()
		if path.startswith('http://') or path.startswith('https://'):
			return path
		base = self.server_url.rstrip('/') + '/'
		return urljoin(base, path.lstrip('/'))

	def _show_error(self, message):
		for widget in self.gallery.winfo_children():
			widget.destroy()
		self.status_var.set(f'Unable to load photos: {message}')
		self.placeholder_label = ctk.CTkLabel(
			self.gallery,
			textvariable=self.status_var,
			font=('Arial', 18),
			text_color=('#b91c1c', '#ffb3b3'),
		)
		self.placeholder_label.grid(row=0, column=0, columnspan=3, pady=40)
		self._schedule_auto_refresh()

	def _schedule_auto_refresh(self):
		self._cancel_auto_refresh()
		if self.auto_refresh_interval:
			self.auto_refresh_job = self.after(
				self.auto_refresh_interval,
				lambda: self._load_images_async(silent=True)
			)

	def _cancel_auto_refresh(self):
		if self.auto_refresh_job is not None:
			try:
				self.after_cancel(self.auto_refresh_job)
			except Exception:
				pass
			self.auto_refresh_job = None

	def destroy(self):
		self._cancel_auto_refresh()
		super().destroy()


class ManualStudentEnrollDialog(ctk.CTkToplevel):
	"""Collects core student details and posts them to the server."""

	def __init__(self, master, server_url, headers, target_class=None, on_success=None):
		super().__init__(master)
		self.server_url = (server_url or DEFAULT_SERVER_URL).rstrip('/')
		self.headers = headers or {}
		self.target_class = target_class
		self.on_success = on_success
		self.submit_btn = None
		self.status_var = ctk.StringVar(value='Enter the student information below.')
		self.first_name_var = ctk.StringVar()
		self.last_name_var = ctk.StringVar()
		self.student_id_var = ctk.StringVar()
		self.year_level_var = ctk.StringVar(value=YEAR_LEVEL_OPTIONS[1])

		self.title('Enroll New Student')
		self.geometry('760x520')
		self.resizable(False, False)
		self.configure(fg_color=('#f5fff5', '#0f200f'))
		self.protocol('WM_DELETE_WINDOW', self._close)
		bring_window_to_front(self)
		self.grab_set()

		self._build_form()

	def _build_form(self):
		container = ctk.CTkFrame(self, fg_color=('#ffffff', '#102010'))
		container.pack(fill='both', expand=True, padx=30, pady=30)

		ctk.CTkLabel(
			container,
			text='Enroll Student',
			font=('Arial', 28, 'bold'),
			text_color=('#006400', '#90EE90'),
		).pack(pady=(10, 20))

		form_grid = ctk.CTkFrame(container, fg_color='transparent')
		form_grid.pack(fill='x', padx=10)
		form_grid.grid_columnconfigure((0, 1), weight=1)

		self._add_entry(form_grid, 'First Name', self.first_name_var, 0, 0)
		self._add_entry(form_grid, 'Last Name', self.last_name_var, 0, 1)
		self._add_entry(form_grid, 'Student ID (YY-XXXXX)', self.student_id_var, 1, 0)

		year_frame = ctk.CTkFrame(form_grid, fg_color='transparent')
		year_frame.grid(row=1, column=1, padx=8, pady=8, sticky='we')
		ctk.CTkLabel(year_frame, text='Year Level', anchor='w').pack(anchor='w', pady=(0, 4))
		ctk.CTkOptionMenu(year_frame, variable=self.year_level_var, values=YEAR_LEVEL_OPTIONS[1:], width=220).pack(fill='x')

		self.status_label = ctk.CTkLabel(
			container,
			textvariable=self.status_var,
			font=('Arial', 16),
			text_color=('#0b5f0b', '#b6f7b6'),
		)
		self.status_label.pack(pady=(18, 8))

		button_row = ctk.CTkFrame(container, fg_color='transparent')
		button_row.pack(pady=10)

		ctk.CTkButton(
			button_row,
			text='Cancel',
			width=140,
			height=48,
			fg_color=('#6c757d', '#4a4f54'),
			hover_color=('#545b62', '#3a3f44'),
			command=self._close,
		).pack(side='left', padx=10)

		self.submit_btn = ctk.CTkButton(
			button_row,
			text='Save Student',
			width=180,
			height=52,
			fg_color=('#0d6efd', '#0a58ca'),
			hover_color=('#0b5ed7', '#0946a6'),
			command=self._handle_submit,
		)
		self.submit_btn.pack(side='left', padx=10)

	def _add_entry(self, parent, label_text, var, row, column):
		frame = ctk.CTkFrame(parent, fg_color='transparent')
		frame.grid(row=row, column=column, padx=8, pady=8, sticky='we')
		frame.grid_columnconfigure(0, weight=1)
		ctk.CTkLabel(frame, text=label_text, anchor='w').pack(anchor='w', pady=(0, 4))
		ctk.CTkEntry(frame, textvariable=var).pack(fill='x')

	def _handle_submit(self):
		first = self.first_name_var.get().strip()
		last = self.last_name_var.get().strip()
		student_id = self.student_id_var.get().strip()
		year_level = self.year_level_var.get()

		if not first or not last or not student_id:
			self.status_var.set('All fields are required before saving.')
			return
		if not re.match(r'^\d{2}-\d{5}$', student_id):
			self.status_var.set('Student ID must use the YY-XXXXX format.')
			return

		payload = {
			'firstName': first,
			'lastName': last,
			'id': student_id,
			'yearLevel': year_level or YEAR_LEVEL_OPTIONS[1],
		}
		self._set_busy(True, 'Saving student...')
		threading.Thread(target=self._submit_async, args=(payload,), daemon=True).start()

	def _submit_async(self, payload):
		url = f"{self.server_url}/students/api/create"
		headers = dict(self.headers)
		headers['Content-Type'] = 'application/json'
		try:
			response = requests.post(url, headers=headers, json=payload, verify=False, timeout=20)
			data = response.json()
			if response.status_code >= 400 or not data.get('success'):
				raise RuntimeError(data.get('message', 'Failed to enroll student'))
			self.after(0, lambda: self._handle_success(data))
		except Exception as exc:
			self.after(0, lambda: self._handle_error(str(exc)))

	def _handle_success(self, payload):
		self._set_busy(False, 'Student saved successfully.')
		message = payload.get('message') or 'Student created.'
		student = payload.get('student')
		if student:
			messagebox.showinfo('Enroll Student', message, parent=self)
			if callable(self.on_success):
				self.on_success(student, self.target_class)
		self._close()

	def _handle_error(self, message):
		self._set_busy(False, message)
		messagebox.showerror('Enroll Student', message, parent=self)

	def _set_busy(self, busy, status_message=None):
		if self.submit_btn:
			self.submit_btn.configure(state='disabled' if busy else 'normal')
		if status_message:
			self.status_var.set(status_message)

	def _close(self):
		try:
			self.grab_release()
		except Exception:
			pass
		self.destroy()


class StudentRegistrationWindow(ctk.CTkToplevel):
	"""Replicates the instructor web students page inside the kiosk console."""

	def __init__(self, master=None, instructor_id=None, server_url=None, api_key=None, preselected_class_id=None, preselected_class_label=None, **kwargs):
		self._owns_master = master is None
		if master is None:
			master = ctk.CTk()
			master.withdraw()
		super().__init__(master, **kwargs)

		self.title("Student Registration")
		self.geometry("1120x740")
		self.minsize(980, 640)
		self.configure(fg_color=('#e8f5e8', '#0f240f'))
		self.resizable(True, True)
		self.protocol('WM_DELETE_WINDOW', self._handle_close)
		bring_window_to_front(self)

		self.instructor_id = instructor_id
		self.server_url = server_url or DEFAULT_SERVER_URL
		self.api_key = api_key or DEFAULT_API_KEY
		self.headers = {'X-API-Key': self.api_key}
		self.preselected_class_id = preselected_class_id
		self.preselected_class_label = preselected_class_label
		self._preselect_applied = False
		self._preload_requested = False

		self.classes = []
		self.class_options = {'All Classes': None}
		self.selected_class_id = preselected_class_id or None
		self.current_students = []
		self.filtered_students = []
		self._table_rows = []
		self.realtime_job = None
		self._manual_students = {}
		self._manual_dialog = None

		self.status_var = ctk.StringVar(value='Ready')
		self.search_var = ctk.StringVar(value='')
		self.year_filter_var = ctk.StringVar(value=YEAR_LEVEL_OPTIONS[0])
		self.class_var = ctk.StringVar(value='All Classes')

		# Cache reloading for embeddings
		self.last_cache_mtime = None
		self.update_check_interval = 5.0  # Check every 5 seconds
		self.update_check_thread = None
		self._running = True

		self._build_layout()
		self.after(200, self._load_initial_data)
		self.after(500, self._start_realtime_updates)
		self.after(1000, self._start_cache_update_checking)  # Start cache checking after 1 second
		self.focus_force()
		self._enter_fullscreen()

	def _enter_fullscreen(self):
		"""Match the kiosk's full-screen look regardless of platform quirks."""
		try:
			screen_w = self.winfo_screenwidth()
			screen_h = self.winfo_screenheight()
			if screen_w and screen_h:
				self.geometry(f"{screen_w}x{screen_h}+0+0")
		except Exception:
			pass

		try:
			self.overrideredirect(True)
		except Exception:
			pass

		try:
			self.attributes('-fullscreen', True)
		except Exception:
			try:
				self.state('zoomed')
			except Exception:
				pass

	def _parse_api_response(self, response, default_error):
		"""Safely decode JSON responses and raise helpful errors."""
		text_body = response.text or ''
		try:
			payload = response.json()
		except ValueError:
			payload = None

		if response.status_code >= 400 or (isinstance(payload, dict) and not payload.get('success', True)):
			message = None
			if isinstance(payload, dict):
				message = payload.get('message') or payload.get('error')
			if not message:
				message = text_body.strip() or default_error
			raise RuntimeError(message)

		return payload if payload is not None else {}

	def _build_layout(self):
		header = ctk.CTkFrame(self, fg_color=('#228B22', '#155c15'))
		header.pack(fill='x')
		header.grid_columnconfigure(0, weight=1)
		header.grid_columnconfigure(1, weight=0)
		header.grid_columnconfigure(2, weight=0)
		ctk.CTkLabel(
			header,
			text='Students Registered',
			font=('Arial', 28, 'bold'),
			text_color=('#ffffff', '#e6ffe6'),
		).grid(row=0, column=0, padx=30, pady=(20, 4), sticky='w')

		self.class_hint_label = None
		if self.preselected_class_label:
			self.class_hint_label = ctk.CTkLabel(
				header,
				text=f"Enrolling for: {self.preselected_class_label}",
				font=('Arial', 20, 'bold'),
				text_color=('#fdfde1', '#d4f8d4'),
			)
			self.class_hint_label.grid(row=1, column=0, padx=30, pady=(0, 18), sticky='w')

		ctk.CTkButton(
			header,
			text='Back',
			width=140,
			height=48,
			fg_color=('#6c757d', '#4a4f54'),
			hover_color=('#545b62', '#3a3f44'),
			command=self._handle_close,
		).grid(row=0, column=2, rowspan=2, padx=30, pady=20, sticky='e')

		content = ctk.CTkFrame(self, fg_color='transparent')
		content.pack(fill='both', expand=True, padx=30, pady=20)

		self._build_filter_row(content)
		self._build_table(content)
		self._build_status_bar()

	def _open_manual_enroll_dialog(self):
		if self._manual_dialog and self._manual_dialog.winfo_exists():
			bring_window_to_front(self._manual_dialog)
			return

		target_class = self.selected_class_id
		self._manual_dialog = ManualStudentEnrollDialog(
			self,
			self.server_url,
			self.headers,
			target_class=target_class,
			on_success=self._handle_manual_enroll_success,
		)
		self._manual_dialog.bind('<Destroy>', lambda _event: setattr(self, '_manual_dialog', None))

	def _build_filter_row(self, parent):
		filters = ctk.CTkFrame(parent, fg_color=('#f5fff5', '#1b3b1b'))
		filters.pack(fill='x', pady=(0, 15))
		filters.grid_columnconfigure((0, 1, 2, 3, 4), weight=1)

		ctk.CTkLabel(filters, text='Class', font=('Arial', 16, 'bold')).grid(row=0, column=0, padx=10, pady=12, sticky='w')
		self.class_menu = ctk.CTkOptionMenu(
			filters,
			variable=self.class_var,
			values=list(self.class_options.keys()),
			command=self._handle_class_change,
			width=240,
		)
		self.class_menu.grid(row=1, column=0, padx=10, pady=(0, 12), sticky='we')

		ctk.CTkLabel(filters, text='Search', font=('Arial', 16, 'bold')).grid(row=0, column=1, padx=10, pady=12, sticky='w')
		self.search_entry = ctk.CTkEntry(
			filters,
			textvariable=self.search_var,
			placeholder_text='Search students by name or ID...',
			width=260,
		)
		self.search_entry.grid(row=1, column=1, padx=10, pady=(0, 12), sticky='we')
		self.search_entry.bind('<KeyRelease>', lambda _event: self._apply_filters())

		self.clear_search_btn = ctk.CTkButton(
			filters,
			text='Clear',
			width=80,
			command=self._clear_search,
			fg_color=('#dc3545', '#a71d2a'),
			hover_color=('#b02a37', '#7f1f28'),
		)
		self.clear_search_btn.grid(row=1, column=2, padx=10, pady=(0, 12))

		ctk.CTkLabel(filters, text='Year Level', font=('Arial', 16, 'bold')).grid(row=0, column=3, padx=10, pady=12, sticky='w')
		self.year_filter = ctk.CTkOptionMenu(
			filters,
			variable=self.year_filter_var,
			values=YEAR_LEVEL_OPTIONS,
			command=lambda _val: self._apply_filters(),
			width=200,
		)
		self.year_filter.grid(row=1, column=3, padx=10, pady=(0, 12), sticky='we')

		self.count_badge = ctk.CTkLabel(
			filters,
			text='Total Students: 0',
			font=('Arial', 18, 'bold'),
			text_color=('#006400', '#90EE90'),
		)
		self.count_badge.grid(row=0, column=4, rowspan=2, padx=10, sticky='e')

	def _build_table(self, parent):
		table_wrapper = ctk.CTkFrame(parent, fg_color=('#ffffff', '#102010'))
		table_wrapper.pack(fill='both', expand=True)

		self.table = ctk.CTkScrollableFrame(table_wrapper, fg_color=('#ffffff', '#102010'))
		self.table.pack(fill='both', expand=True, padx=5, pady=5)
		self.table.grid_columnconfigure(0, weight=1)
		self._build_table_header()
		self._show_placeholder('Loading students...')

	def _build_table_header(self):
		self.header_frame = ctk.CTkFrame(self.table, fg_color=('#228B22', '#155015'))
		self.header_frame.grid(row=0, column=0, sticky='ew', pady=(0, 6))
		for idx, (title, weight) in enumerate(STUDENT_TABLE_COLUMNS):
			self.header_frame.grid_columnconfigure(idx, weight=weight, uniform='students_table')
			ctk.CTkLabel(
				self.header_frame,
				text=title,
				font=('Arial', 16, 'bold'),
				text_color=('#ffffff', '#e6ffe6'),
				anchor='w',
			).grid(row=0, column=idx, padx=12, pady=12, sticky='w')

	def _build_status_bar(self):
		status_frame = ctk.CTkFrame(self, fg_color=('#d3f2d3', '#122212'))
		status_frame.pack(fill='x', padx=30, pady=(0, 20))
		self.status_label = ctk.CTkLabel(status_frame, textvariable=self.status_var, anchor='w')
		self.status_label.pack(fill='x', padx=12, pady=6)

	def _handle_manual_enroll_success(self, student_payload, target_class):
		if not isinstance(student_payload, dict):
			return
		student_id = student_payload.get('id')
		if not student_id:
			return
		full_name = f"{(student_payload.get('firstName') or '').strip()} {(student_payload.get('lastName') or '').strip()}".strip()
		manual_record = {
			'id': student_id,
			'name': full_name or student_id,
			'yearLevel': student_payload.get('yearLevel') or '',
			'hasFaceImages': bool(student_payload.get('profileImage')),
			'_target_class': target_class,
		}
		self._manual_students[student_id] = manual_record
		self._apply_filters()
		self._set_status(f"Student {manual_record['name']} saved. Assign them to a class when ready.", 'success')

	def _manual_students_for_context(self):
		context = self.selected_class_id
		matches = []
		for student in self._manual_students.values():
			target = student.get('_target_class')
			if (context is None and target is None) or (context is not None and target == context):
				matches.append(student)
		return matches

	def _sync_manual_students(self):
		active_ids = {student.get('id') for student in self.current_students if student.get('id')}
		for student_id in list(self._manual_students.keys()):
			if student_id in active_ids:
				self._manual_students.pop(student_id, None)

	def _load_initial_data(self):
		if not self.instructor_id:
			self._set_status('Instructor ID missing. Unable to load students.', 'error')
			messagebox.showerror('Instructor Required', 'Unable to load students without an instructor login.', parent=self)
			return

		self._load_classes_async()
		if self.preselected_class_id:
			self.selected_class_id = self.preselected_class_id
			self._preload_requested = True
			self._load_class_students_async(self.preselected_class_id)
		else:
			self._load_all_students_async()

	def _load_classes_async(self):
		def task():
			try:
				response = requests.get(
					f"{self.server_url}/api/instructors/{self.instructor_id}/classes",
					headers=self.headers,
					verify=False,
					timeout=15,
				)
				classes_data = self._parse_api_response(response, 'Failed to load classes')
				classes = classes_data.get('classes', [])
			except Exception as exc:
				error_message = f'Failed to load classes: {exc}'
				self.after(0, lambda msg=error_message: self._set_status(msg, 'error'))
				return
			self.after(0, lambda: self._on_classes_loaded(classes))

		threading.Thread(target=task, daemon=True).start()

	def _on_classes_loaded(self, classes):
		self.classes = classes
		self.class_options = {'All Classes': None}
		for cls in classes:
			label = f"{cls.get('classCode') or 'Class'} - {cls.get('description') or 'Untitled'}"
			self.class_options[label] = cls['id']

		values = list(self.class_options.keys()) or ['All Classes']
		self.class_menu.configure(values=values)

		target_id = self.selected_class_id or self.preselected_class_id
		selected_label = None
		if target_id is not None:
			for label, class_id in self.class_options.items():
				if class_id == target_id:
					selected_label = label
					self.selected_class_id = class_id
					break

		if selected_label:
			self.class_var.set(selected_label)
		else:
			default_label = values[0]
			self.class_var.set(default_label)
			self.selected_class_id = self.class_options.get(default_label)

		if self.preselected_class_id and not self._preselect_applied:
			self._preselect_applied = True
			if not self._preload_requested:
				if self.selected_class_id:
					self._preload_requested = True
					self._load_class_students_async(self.selected_class_id)
				else:
					self._load_all_students_async()
		self._set_status('Classes loaded', 'success')

	def _load_all_students_async(self, silent=False):
		if not silent:
			self._show_placeholder('Loading all students...')

		def task():
			try:
				response = requests.get(
					f"{self.server_url}/api/instructors/{self.instructor_id}/students",
					headers=self.headers,
					verify=False,
					timeout=20,
				)
				data = self._parse_api_response(response, 'Failed to load students')
				students = data.get('students', [])
			except Exception as exc:
				error_message = str(exc)
				self.after(0, lambda msg=error_message: self._show_error_state(msg))
				return
			self.after(0, lambda: self._on_students_loaded(students, silent=silent))

		threading.Thread(target=task, daemon=True).start()

	def _load_class_students_async(self, class_id, silent=False):
		if not silent:
			self._show_placeholder('Loading class students...')

		def task():
			try:
				response = requests.get(
					f"{self.server_url}/api/instructors/{self.instructor_id}/classes/{class_id}/students",
					headers=self.headers,
					verify=False,
					timeout=20,
				)
				data = self._parse_api_response(response, 'Failed to load class students')
				students = data.get('students', [])
			except Exception as exc:
				error_message = str(exc)
				self.after(0, lambda msg=error_message: self._show_error_state(msg))
				return
			self.after(0, lambda: self._on_students_loaded(students, silent=silent))

		threading.Thread(target=task, daemon=True).start()

	def _on_students_loaded(self, students, silent=False):
		self.current_students = students
		self._sync_manual_students()
		self._apply_filters()
		if not silent:
			self._set_status('Students loaded successfully', 'success')

	def _apply_filters(self):
		students = list(self.current_students)
		manual_candidates = self._manual_students_for_context()
		existing_ids = {student.get('id') for student in students}
		for manual in manual_candidates:
			identifier = manual.get('id')
			if identifier and identifier not in existing_ids:
				students.append(manual)
				existing_ids.add(identifier)
		needle = self.search_var.get().strip().lower()
		year_filter = self.year_filter_var.get()

		if needle:
			students = [
				student
				for student in students
				if needle in (student.get('name') or '').lower()
				or needle in (student.get('id') or '').lower()
			]

		if year_filter and year_filter != YEAR_LEVEL_OPTIONS[0]:
			students = [
				student
				for student in students
				if (student.get('yearLevel') or '').lower() == year_filter.lower()
			]

		self.filtered_students = students
		self._update_student_table(students)
		self.count_badge.configure(text=f'Total Students: {len(students)}')

	def _update_student_table(self, students):
		self._clear_table_rows()
		if not students:
			self._show_placeholder('No students found for the selected filters.')
			return

		for index, student in enumerate(students, start=1):
			row = ctk.CTkFrame(self.table, fg_color=('#f6fff6', '#1a2a1a'))
			row.grid(row=index, column=0, sticky='ew', padx=2, pady=4)
			for idx, (_title, weight) in enumerate(STUDENT_TABLE_COLUMNS):
				row.grid_columnconfigure(idx, weight=weight, uniform='students_table')
			self._table_rows.append(row)

			ctk.CTkLabel(row, text=student.get('name') or 'Unnamed', anchor='w').grid(row=0, column=0, padx=12, pady=10, sticky='w')
			ctk.CTkLabel(row, text=student.get('id') or 'N/A', anchor='w').grid(row=0, column=1, padx=12, pady=10, sticky='w')
			ctk.CTkLabel(row, text=student.get('yearLevel') or '-', anchor='w').grid(row=0, column=2, padx=12, pady=10, sticky='w')

			status_text, status_color = self._face_status(student)
			ctk.CTkLabel(
				row,
				text=status_text,
				text_color=status_color,
				font=('Arial', 15, 'bold'),
			).grid(row=0, column=3, padx=12, pady=10, sticky='w')

			actions = ctk.CTkFrame(row, fg_color='transparent')
			actions.grid(row=0, column=4, padx=8, pady=6, sticky='e')
			ctk.CTkButton(
				actions,
				text='Capture Face',
				width=120,
				height=34,
				command=lambda s=student: self._open_capture_window(s),
			).pack(side='left', padx=4)
			ctk.CTkButton(
				actions,
				text='View Photos',
				width=120,
				height=34,
				fg_color=('#6c757d', '#4a4f54'),
				hover_color=('#545b62', '#3a3f44'),
				command=lambda s=student: self._open_photo_viewer(s),
			).pack(side='left', padx=4)

	def _face_status(self, student):
		if student.get('hasFaceImages'):
			return 'Captured', '#1c7c2c'
		return 'Not Captured', '#c82333'

	def _show_placeholder(self, message):
		self._clear_table_rows()
		label = ctk.CTkLabel(self.table, text=message, font=('Arial', 18))
		label.grid(row=1, column=0, pady=60)
		self._table_rows.append(label)

	def _clear_table_rows(self):
		for widget in self._table_rows:
			try:
				widget.destroy()
			except Exception:
				pass
		self._table_rows.clear()

	def _show_error_state(self, message):
		self._show_placeholder('Unable to load students.')
		self._set_status(message, 'error')
		messagebox.showerror('Student List', message, parent=self)

	def _handle_class_change(self, selected_label):
		class_id = self.class_options.get(selected_label)
		self.selected_class_id = class_id
		if class_id:
			self._load_class_students_async(class_id)
		else:
			self._load_all_students_async()

	def _clear_search(self):
		self.search_var.set('')
		self._apply_filters()

	def _start_realtime_updates(self):
		if self.realtime_job is not None:
			return

	def _perform_realtime_refresh(self):
		self.realtime_job = None
		if not self.winfo_exists():
			return
		if self.selected_class_id:
			self._load_class_students_async(self.selected_class_id, silent=True)
		else:
			self._load_all_students_async(silent=True)

	def _stop_realtime_updates(self):
		if self.realtime_job is not None:
			try:
				self.after_cancel(self.realtime_job)
			except Exception:
				pass
			self.realtime_job = None

	def _get_cache_file_path(self):
		"""Get the path to the face encodings cache file."""
		return os.path.join(os.path.dirname(__file__), '..', 'cache', 'face_encodings.pkl')

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

	def _try_download_cache_on_startup(self):
		"""Try to download the latest cache file on startup if it doesn't exist or is outdated."""
		cache_file = self._get_cache_file_path()
		
		# If cache file doesn't exist, try to download it
		if not os.path.exists(cache_file):
			print("📥 Cache file not found, downloading from server...")
			if self._download_cache_file():
				print("✅ Successfully downloaded cache file on startup")
			else:
				print("⚠️ Failed to download cache file on startup, will use local if available")
			return
		
		# If cache file exists, check if server has a newer version
		try:
			response = requests.get(
				f"{self.server_url}/api/face-encodings/meta",
				headers=self.headers,
				verify=False,
				timeout=3
			)
			if response.status_code == 200:
				data = response.json()
				if data.get('success'):
					server_mtime_str = data.get('mtime')
					if server_mtime_str:
						from datetime import datetime
						server_mtime = datetime.fromisoformat(server_mtime_str.replace('Z', '+00:00')).timestamp()
						local_mtime = os.path.getmtime(cache_file)
						
						# If server has a newer version, download it
						if server_mtime > local_mtime:
							print("📥 Server has newer cache file, downloading...")
							if self._download_cache_file():
								print("✅ Successfully updated cache file on startup")
		except Exception as e:
			# Silently fail on startup - we'll check periodically anyway
			pass

	def _download_cache_file(self):
		"""Download the latest cache file from the server."""
		cache_file = self._get_cache_file_path()
		cache_dir = os.path.dirname(cache_file)
		if cache_dir:
			os.makedirs(cache_dir, exist_ok=True)
		
		temp_path = cache_file + '.tmp'
		try:
			response = requests.get(
				f"{self.server_url}/api/face-encodings",
				headers=self.headers,
				verify=False,
				timeout=30,
				stream=True,
			)
			if response.status_code != 200:
				print(f"⚠️ Failed to download cache file: HTTP {response.status_code}")
				return False
			
			with open(temp_path, 'wb') as temp_file:
				for chunk in response.iter_content(chunk_size=8192):
					if chunk:
						temp_file.write(chunk)
			
			# Atomically replace the old file with the new one
			os.replace(temp_path, cache_file)
			return True
		except Exception as e:
			print(f"⚠️ Error downloading cache file: {e}")
			return False
		finally:
			# Clean up temp file if it exists
			if os.path.exists(temp_path):
				try:
					os.remove(temp_path)
				except Exception:
					pass

	def _start_cache_update_checking(self):
		"""Start the background thread to check for cache file updates."""
		if self.update_check_thread is not None:
			return
		
		# Try to download/update cache file on startup
		self._try_download_cache_on_startup()
		self._update_cache_mtime()
		
		# Start update checking thread
		self.update_check_thread = threading.Thread(target=self._check_for_updates_loop, daemon=True)
		self.update_check_thread.start()

	def _check_for_updates_loop(self):
		"""Background thread that periodically checks for cache file updates."""
		while self._running and self.winfo_exists():
			try:
				# Check via API first (more reliable for network scenarios)
				try:
					response = requests.get(
						f"{self.server_url}/api/face-encodings/meta",
						headers=self.headers,
						verify=False,
						timeout=3
					)
					if response.status_code == 200:
						data = response.json()
						if data.get('success'):
							server_mtime_str = data.get('mtime')
							if server_mtime_str:
								# Parse ISO format timestamp
								from datetime import datetime
								server_mtime = datetime.fromisoformat(server_mtime_str.replace('Z', '+00:00')).timestamp()
								
								# Check if cache file has been updated
								if self.last_cache_mtime is None or server_mtime > self.last_cache_mtime:
									print(f"🔄 Detected cache file update (server mtime: {server_mtime_str})")
									self._reload_cache()
									self.last_cache_mtime = server_mtime
				except Exception as api_error:
					# Fallback to local file check if API fails
					cache_file = self._get_cache_file_path()
					if os.path.exists(cache_file):
						try:
							current_mtime = os.path.getmtime(cache_file)
							if self.last_cache_mtime is None or current_mtime > self.last_cache_mtime:
								print(f"🔄 Detected local cache file update")
								self._reload_cache()
								self.last_cache_mtime = current_mtime
						except Exception:
							pass
			except Exception as e:
				# Silently handle errors to avoid spamming logs
				pass
			
			# Sleep before next check
			time.sleep(self.update_check_interval)

	def _reload_cache(self):
		"""Download and reload cache file when update is detected."""
		print("🔄 Downloading updated face embeddings from server...")
		try:
			# First, download the updated cache file from the server
			if not self._download_cache_file():
				print("⚠️ Failed to download cache file, using local version")
				self._update_cache_mtime()
				return
			
			# Update the modification time
			self._update_cache_mtime()
			print("✅ Successfully reloaded cache file in enroll panel")
			
			# Optionally show a status message to the user
			if hasattr(self, 'status_var'):
				self.after(0, lambda: self._set_status('Face embeddings cache updated', 'success'))
		except Exception as e:
			print(f"⚠️ Error reloading cache: {e}")

	def _open_capture_window(self, student):
		student_id = student.get('id')
		if not student_id:
			messagebox.showerror('Capture Face', 'Student information is incomplete. Please refresh and try again.', parent=self)
			return

		FaceCaptureWindow(
			self,
			student,
			self.server_url,
			self.api_key,
			on_success=self._handle_capture_success,
		)

	def _handle_capture_success(self, student_id, _image_payload=None):
		updated = False
		for student in self.current_students:
			if student.get('id') == student_id:
				student['hasFaceImages'] = True
				updated = True
				break

		if updated:
			self._apply_filters()
		self._set_status(f'Capture saved for student {student_id}.', 'success')

	def _open_photo_viewer(self, student):
		student_id = student.get('id')
		if not student_id:
			messagebox.showerror('View Photos', 'Student information is incomplete. Please refresh and try again.', parent=self)
			return

		StudentPhotoViewer(self, student, self.server_url, self.api_key)

	def _set_status(self, message, level='info'):
		colors = {
			'info': '#0b5f0b',
			'success': '#0d6c0d',
			'warning': '#b35c00',
			'error': '#b91c1c',
		}
		self.status_var.set(message)
		self.status_label.configure(text_color=colors.get(level, '#0b5f0b'))

	def _handle_close(self):
		self.destroy()
		if self._owns_master:
			self.master.destroy()

	def destroy(self):
		# Stop cache update checking
		self._running = False
		if self.update_check_thread is not None:
			# Thread will exit naturally when _running is False
			self.update_check_thread = None
		
		self._stop_realtime_updates()
		super().destroy()


if __name__ == '__main__':
	ctk.set_appearance_mode('light')
	ctk.set_default_color_theme('green')
	based_on_env = os.environ.get('INSTRUCTOR_ID')
	root = ctk.CTk()
	root.withdraw()
	StudentRegistrationWindow(root, instructor_id=based_on_env)
	root.mainloop()
