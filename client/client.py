import customtkinter as ctk
from tkinter import messagebox
import requests
import warnings
import sys
import os
import socket
import uuid
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'
import threading
import time
import pickle
import re
import json
from datetime import datetime, date, timedelta
import cv2
import numpy as np
from PIL import Image, ImageTk
from server import SERVER_URL, API_KEY
from ui_utils import bring_window_to_front
try:
    from deepface import DeepFace
    _DEEPFACE_IMPORT_ERROR = None
except Exception as deepface_error:
    DeepFace = None
    _DEEPFACE_IMPORT_ERROR = deepface_error
warnings.filterwarnings('ignore', message='Unverified HTTPS request')
CLIENT_INSTANCE_ID = os.environ.get('FRCAS_CLIENT_ID') or f"{socket.gethostname() or 'kiosk'}-{uuid.uuid4().hex}"
HEADERS = {'X-API-Key': API_KEY}
JSON_HEADERS = {**HEADERS, 'Content-Type': 'application/json'}
FACE_ENCODINGS_CACHE = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'cache', 'face_encodings.pkl'))
FACE_ENCODINGS_ENDPOINT = f'{SERVER_URL}/api/face-encodings'
MPSU_LOGO_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), 'MPSU.png'))
CLASS_STATE_CACHE_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'cache', 'class_state.json'))
WEEKDAY_CODES = ['M', 'T', 'W', 'Th', 'F', 'S', 'Su']
# Temporary kiosk policy: all class sessions run in a single fixed room.
FIXED_ROOM_NUMBER = '310'
DEFAULT_ROOM_OPTIONS = [FIXED_ROOM_NUMBER]
ROOM_CACHE_TTL_SECONDS = 120
DEFAULT_AUTO_TIMEOUT_MINUTES = 60
TIME_RANGE_PATTERN = re.compile('(\\d{1,2}:\\d{2}\\s*(?:[AaPp][Mm])?)\\s*-\\s*(\\d{1,2}:\\d{2}\\s*(?:[AaPp][Mm])?)', re.IGNORECASE)
_ROOM_OPTIONS_CACHE = {'rooms': DEFAULT_ROOM_OPTIONS.copy(), 'timestamp': 0}

def normalize_room_label(room_text):
    """Return a case-insensitive key for room comparisons."""
    if room_text is None:
        return ''
    return str(room_text).strip().lower()

def get_day_code_for_date(target_date=None):
    """Return the schedule day token (e.g., 'M', 'Th') for the given date."""
    target = target_date or datetime.now().date()
    weekday_index = target.weekday()
    return WEEKDAY_CODES[weekday_index] if 0 <= weekday_index < len(WEEKDAY_CODES) else None

def get_current_day_code():
    """Return the schedule day token (e.g., 'M', 'Th') for the local weekday."""
    return get_day_code_for_date(datetime.now().date())

def extract_schedule_days(schedule_string):
    """Extract day tokens (M, T, W, Th, F, S, Su) from a schedule string."""
    if not schedule_string:
        return set()
    days_found = set()
    for slot in schedule_string.split(','):
        slot = slot.strip()
        if not slot:
            continue
        parts = slot.split(' ', 1)
        if not parts:
            continue
        days_part = parts[0]
        idx = 0
        while idx < len(days_part):
            if days_part[idx:idx + 2] in ('Th', 'Su'):
                days_found.add(days_part[idx:idx + 2])
                idx += 2
            else:
                days_found.add(days_part[idx])
                idx += 1
    return days_found

def class_occurs_today(schedule_string):
    """Return True if the provided schedule string includes today's day code."""
    today_code = get_current_day_code()
    if today_code is None:
        return False
    return today_code in extract_schedule_days(schedule_string)
TIME_PATTERN = re.compile('(\\d{1,2}:\\d{2}\\s*(?:[AaPp][Mm])?)')

def _parse_time_token(value):
    text = (value or '').strip()
    if not text:
        return None
    upper_text = text.upper()
    if upper_text.endswith(('AM', 'PM')) and ' ' not in upper_text[-3:]:
        upper_text = upper_text[:-2].strip() + ' ' + upper_text[-2:]
    try:
        return datetime.strptime(upper_text, '%I:%M %p').time()
    except ValueError:
        try:
            return datetime.strptime(text, '%H:%M').time()
        except ValueError:
            return None

def _split_schedule_days(days_text):
    cleaned = re.sub('[^A-Za-z]', '', (days_text or '').strip())
    if not cleaned:
        return WEEKDAY_CODES[:]
    tokens = []
    idx = 0
    while idx < len(cleaned):
        two_char = cleaned[idx:idx + 2]
        if two_char.lower() in {'th', 'su'}:
            tokens.append(two_char.title())
            idx += 2
        else:
            tokens.append(cleaned[idx].upper())
            idx += 1
    normalized = []
    for token in tokens:
        if token in WEEKDAY_CODES:
            normalized.append(token)
        elif token.upper() in {'M', 'T', 'W', 'F', 'S'}:
            normalized.append(token.upper())
    return normalized or WEEKDAY_CODES[:]

def _split_day_and_time(chunk):
    chunk = (chunk or '').strip()
    if not chunk:
        return ('', '')
    idx = 0
    while idx < len(chunk) and chunk[idx].isalpha():
        idx += 1
    days_part = chunk[:idx].strip()
    time_part = chunk[idx:].strip()
    return (days_part, time_part or chunk)

def parse_schedule_slots(schedule_string):
    slots = []
    if not schedule_string:
        return slots
    for raw_slot in schedule_string.split(','):
        chunk = raw_slot.strip()
        if not chunk:
            continue
        days_part, time_part = _split_day_and_time(chunk)
        match = TIME_RANGE_PATTERN.search(time_part)
        if not match:
            continue
        start_token, end_token = match.groups()
        start_time = _parse_time_token(start_token)
        end_time = _parse_time_token(end_token)
        if not start_time or not end_time:
            continue
        days = _split_schedule_days(days_part)
        start_dt = datetime.combine(date.today(), start_time)
        end_dt = datetime.combine(date.today(), end_time)
        is_overnight = False
        if end_dt <= start_dt:
            end_dt += timedelta(days=1)
            is_overnight = True
        duration_minutes = max(1, (end_dt - start_dt).total_seconds() / 60)
        slots.append({'days': days, 'start_time': start_time, 'end_time': end_time, 'duration_minutes': duration_minutes, 'is_overnight': is_overnight, 'label': chunk})
    return slots

def resolve_schedule_window(schedule_string, target_date=None):
    target_date = target_date or datetime.now().date()
    slots = parse_schedule_slots(schedule_string)
    if not slots:
        return None
    day_code = get_day_code_for_date(target_date)
    selected = None
    if day_code:
        for slot in slots:
            if day_code in slot['days']:
                selected = slot
                break
    if selected is None:
        selected = slots[0]
    start_dt = datetime.combine(target_date, selected['start_time'])
    end_dt = datetime.combine(target_date, selected['end_time'])
    if selected.get('is_overnight') or end_dt <= start_dt:
        end_dt += timedelta(days=1)
    return {'start_datetime': start_dt, 'end_datetime': end_dt, 'duration_minutes': selected['duration_minutes'], 'days': selected['days'], 'label': selected['label']}

def compute_class_timeout_info(class_obj, target_date=None):
    schedule = (class_obj.get('schedule') or '').strip() if isinstance(class_obj, dict) else ''
    window = resolve_schedule_window(schedule, target_date=target_date)
    if window:
        return {'duration_minutes': max(1, window['duration_minutes']), 'window': window, 'source': 'schedule'}
    return {'duration_minutes': DEFAULT_AUTO_TIMEOUT_MINUTES, 'window': None, 'source': 'fallback'}

def parse_schedule_start_time(schedule_string):
    """Parse the first time token from a schedule string and return a time object."""
    if not schedule_string:
        return None
    match = TIME_PATTERN.search(schedule_string)
    if not match:
        return None
    time_text = match.group(1).strip()
    upper_text = time_text.upper()
    if upper_text.endswith(('AM', 'PM')) and ' ' not in upper_text[-3:]:
        time_text = upper_text[:-2].strip() + ' ' + upper_text[-2:]
    elif upper_text.endswith(('AM', 'PM')):
        time_text = upper_text
    try:
        return datetime.strptime(time_text, '%I:%M %p').time()
    except ValueError:
        pass
    try:
        return datetime.strptime(time_text, '%H:%M').time()
    except ValueError:
        return None

def class_start_sort_key(cls):
    """Return a tuple so classes can be sorted from earliest to latest."""
    if isinstance(cls, dict):
        schedule = cls.get('schedule', '')
        class_code = cls.get('class_code') or cls.get('classCode') or ''
    else:
        schedule = ''
        class_code = ''
    start_time = parse_schedule_start_time(schedule)
    if start_time is None:
        return (1, class_code)
    minutes = start_time.hour * 60 + start_time.minute
    return (0, minutes, class_code)

def fetch_available_rooms(force_refresh=False):
    """Return the single fixed kiosk room."""
    _ROOM_OPTIONS_CACHE['rooms'] = [FIXED_ROOM_NUMBER]
    _ROOM_OPTIONS_CACHE['timestamp'] = time.time()
    return _ROOM_OPTIONS_CACHE['rooms']

def fetch_active_sessions():
    """Ask the backend for currently running class sessions."""
    try:
        response = requests.get(f'{SERVER_URL}/api/sessions/active', headers=HEADERS, verify=False, timeout=10)
    except requests.exceptions.RequestException:
        return None
    if response.status_code != 200:
        return None
    try:
        payload = response.json() or {}
    except ValueError:
        return None
    sessions = payload.get('sessions') or []
    normalized = {}
    for session in sessions:
        class_id = session.get('class_id')
        session_id = session.get('class_session_id')
        try:
            class_id = int(class_id)
        except (TypeError, ValueError):
            continue
        try:
            session_id = int(session_id) if session_id is not None else None
        except (TypeError, ValueError):
            session_id = None
        room_number = (session.get('room_number') or '').strip()
        normalized[class_id] = {'class_id': class_id, 'class_session_id': session_id, 'room_number': room_number or None, 'start_time': session.get('start_time'), 'class_code': session.get('class_code') or '', 'description': session.get('description') or '', 'instructor_id': session.get('instructor_id'), 'view_lock_owner': session.get('view_lock_owner')}
    return normalized

def _request_session_view_lock(session_id, locker_id, action, force=False):
    payload = {'locker_id': locker_id, 'action': action}
    if force:
        payload['force'] = True
    try:
        response = requests.post(f'{SERVER_URL}/api/sessions/{session_id}/view-lock', headers=JSON_HEADERS, json=payload, verify=False, timeout=10)
    except requests.exceptions.RequestException as exc:
        return (False, str(exc), None)
    if response.status_code == 200:
        try:
            data = response.json() or {}
        except ValueError:
            data = {}
        return (True, data, response.status_code)
    try:
        error_payload = response.json() or {}
        error_message = error_payload.get('error') or error_payload.get('message')
    except ValueError:
        error_payload = {}
        error_message = None
    if not error_message:
        error_message = response.text or f'HTTP {response.status_code}'
    return (False, error_message, response.status_code)

def acquire_remote_view_lock(class_id, session_id):
    """Attempt to lock the class session for exclusive viewing across kiosks."""
    if session_id is None:
        locked_view_classes.add(class_id)
        client_view_lock_sessions[class_id] = None
        session_view_locks[class_id] = CLIENT_INSTANCE_ID
        return (True, None)
    success, data_or_error, status = _request_session_view_lock(session_id, CLIENT_INSTANCE_ID, action='lock')
    if not success:
        return (False, data_or_error)
    client_view_lock_sessions[class_id] = session_id
    locked_view_classes.add(class_id)
    owner = data_or_error.get('view_lock_owner') if isinstance(data_or_error, dict) else CLIENT_INSTANCE_ID
    session_view_locks[class_id] = owner or CLIENT_INSTANCE_ID
    return (True, None)

def release_remote_view_lock(class_id, session_id=None, force=False):
    """Release the remote view lock if this kiosk currently holds it."""
    held_session_id = client_view_lock_sessions.pop(class_id, None)
    target_session_id = session_id or held_session_id
    locked_view_classes.discard(class_id)
    if target_session_id is None:
        session_view_locks.pop(class_id, None)
        return (True, None)
    success, data_or_error, status = _request_session_view_lock(target_session_id, CLIENT_INSTANCE_ID, action='unlock', force=force)
    if success or status in (404,):
        session_view_locks.pop(class_id, None)
        return (True, None)
    return (False, data_or_error)

def download_face_encoding_cache():
    """Download the shared face encoding cache from the backend server."""
    cache_dir = os.path.dirname(FACE_ENCODINGS_CACHE)
    if cache_dir:
        os.makedirs(cache_dir, exist_ok=True)
    temp_path = FACE_ENCODINGS_CACHE + '.tmp'
    try:
        response = requests.get(FACE_ENCODINGS_ENDPOINT, headers=HEADERS, verify=False, timeout=30, stream=True)
    except requests.exceptions.RequestException:
        return False
    if response.status_code != 200:
        return False
    try:
        with open(temp_path, 'wb') as temp_file:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    temp_file.write(chunk)
        os.replace(temp_path, FACE_ENCODINGS_CACHE)
        return True
    except OSError:
        return False
    finally:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass

def parse_iso_datetime(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).strip()
    if not text:
        return None
    try:
        cleaned = text.replace('Z', '+00:00') if text.endswith('Z') else text
        parsed = datetime.fromisoformat(cleaned)
        if parsed.tzinfo:
            parsed = parsed.astimezone().replace(tzinfo=None)
        return parsed
    except ValueError:
        pass
    for fmt in ('%Y-%m-%d %H:%M:%S', '%m/%d/%Y %H:%M:%S'):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None

def rebuild_class_timeout_metadata(class_payloads, target_date=None):
    target_date = target_date or datetime.now().date()
    class_timeout_metadata.clear()
    for cls in class_payloads or []:
        if not isinstance(cls, dict):
            continue
        class_id = cls.get('id')
        if class_id is None:
            continue
        class_timeout_metadata[class_id] = compute_class_timeout_info(cls, target_date=target_date)

def format_timeout_label_text(class_id, is_ongoing=False):
    if class_id in ended_classes:
        return ''
    info = class_timeout_metadata.get(class_id)
    duration_minutes = info.get('duration_minutes') if info else None
    if duration_minutes is None:
        duration_minutes = DEFAULT_AUTO_TIMEOUT_MINUTES
    duration_minutes = max(1, int(round(duration_minutes)))
    if is_ongoing:
        deadline = class_session_deadlines.get(class_id)
        if deadline:
            remaining_seconds = (deadline - datetime.now()).total_seconds()
            remaining_minutes = max(0, int(remaining_seconds // 60))
            deadline_text = deadline.strftime('%I:%M %p').lstrip('0')
            if remaining_minutes <= 0:
                return f'Auto timeout imminent ({deadline_text})'
            return f'Auto timeout at {deadline_text} ({remaining_minutes} min left)'
    return ''

def cancel_class_timeout(class_id):
    parent = globals().get('root')
    job = class_timeout_jobs.pop(class_id, None)
    if parent and job:
        try:
            parent.after_cancel(job)
        except Exception:
            pass
    class_session_deadlines.pop(class_id, None)
    class_session_start_times.pop(class_id, None)

def schedule_class_timeout(class_id, start_time=None, class_payload=None, timeout_deadline=None):
    parent = globals().get('root')
    if parent is None or class_id is None:
        return
    payload = class_payload or class_metadata_by_id.get(class_id)
    if payload:
        class_metadata_by_id[class_id] = payload
        existing = class_timeout_metadata.get(class_id)
        if not existing or existing.get('source') == 'fallback':
            class_timeout_metadata[class_id] = compute_class_timeout_info(payload)
    info = class_timeout_metadata.get(class_id)
    duration_minutes = DEFAULT_AUTO_TIMEOUT_MINUTES
    if info and info.get('duration_minutes'):
        duration_minutes = max(1, int(round(info['duration_minutes'])))
    existing_start = class_session_start_times.get(class_id)
    cancel_class_timeout(class_id)
    if start_time is None:
        start_time = existing_start
    if isinstance(start_time, str):
        start_time = parse_iso_datetime(start_time)
    if start_time is None:
        start_time = datetime.now()
    class_session_start_times[class_id] = start_time
    explicit_deadline = timeout_deadline
    if isinstance(explicit_deadline, str):
        explicit_deadline = parse_iso_datetime(explicit_deadline)
    elif explicit_deadline is not None and (not isinstance(explicit_deadline, datetime)):
        explicit_deadline = parse_iso_datetime(str(explicit_deadline))
    deadline = explicit_deadline or start_time + timedelta(minutes=duration_minutes)
    window = info.get('window') if info else None
    schedule_end = window.get('end_datetime') if window else None
    if schedule_end and schedule_end < deadline:
        deadline = schedule_end
    class_session_deadlines[class_id] = deadline
    delay_ms = max(0, int((deadline - datetime.now()).total_seconds() * 1000))

    def _dispatch_timeout(target_id=class_id):
        _handle_class_timeout(target_id)
    if delay_ms <= 0:
        parent.after_idle(_dispatch_timeout)
    else:
        job = parent.after(delay_ms, _dispatch_timeout)
        class_timeout_jobs[class_id] = job

def prune_stale_class_timeouts():
    stale_ids = [cid for cid in list(class_timeout_jobs.keys()) if cid not in ongoing_classes]
    for class_id in stale_ids:
        cancel_class_timeout(class_id)

def _handle_class_timeout(class_id):
    global _timeout_message_shown
    cancel_class_timeout(class_id)
    if class_id not in ongoing_classes:
        return
    if class_id in _timeout_message_shown:
        return
    cls = class_metadata_by_id.get(class_id) or {'id': class_id, 'class_code': f'Class {class_id}'}
    ended = end_class_session_and_reset(cls, auto=True)
    if not ended:
        return
    _timeout_message_shown.add(class_id)

    def clear_timeout_flag():
        _timeout_message_shown.discard(class_id)
    if root:
        root.after(5000, clear_timeout_flag)
    scanner_app = getattr(root, 'scanner_app', None)
    if scanner_app and getattr(scanner_app, 'class_id', None) == class_id:
        try:
            scanner_app.session_ended = True
            scanner_app.shutdown(destroy_root=False)
        except Exception:
            pass
        setattr(root, 'scanner_app', None)

def sync_active_sessions_from_server(active_sessions, classes_by_id):
    """Mirror server-provided session state locally so every kiosk matches."""
    global ongoing_classes, class_session_ids, class_rooms, class_instructor_assignments
    global session_view_locks, client_view_lock_sessions
    if active_sessions is None:
        return
    previous_ongoing = set(ongoing_classes)
    active_ids = set(active_sessions.keys())
    newly_ended_ids = previous_ongoing - active_ids
    ongoing_classes.clear()
    ongoing_classes.update(active_ids)
    for active_id in active_ids:
        clear_class_recent_end_marker(active_id)
    for ended_id in newly_ended_ids:
        mark_class_recently_ended(ended_id)
        locked_view_classes.discard(ended_id)
        session_view_locks.pop(ended_id, None)
        client_view_lock_sessions.pop(ended_id, None)
        cancel_class_timeout(ended_id)
    class_session_ids.clear()
    class_rooms.clear()
    session_view_locks.clear()
    for class_id, session in active_sessions.items():
        class_session_ids[class_id] = session.get('class_session_id')
        room_number = session.get('room_number')
        if room_number:
            class_rooms[class_id] = room_number
        owner = session.get('view_lock_owner')
        if owner:
            session_view_locks[class_id] = owner
        schedule_class_timeout(class_id, start_time=session.get('start_time'), class_payload=(classes_by_id or {}).get(class_id), timeout_deadline=session.get('timeout_deadline') or session.get('scheduled_end_time'))
    for stale_id in list(class_instructor_assignments.keys()):
        if stale_id not in active_ids:
            class_instructor_assignments.pop(stale_id, None)
    classes_by_id = classes_by_id or {}
    for class_id, session in active_sessions.items():
        instructor_id = session.get('instructor_id')
        if not instructor_id:
            continue
        cls = classes_by_id.get(class_id)
        role = None
        if cls:
            try:
                if instructor_id == cls.get('instructor_id'):
                    role = 'primary'
                elif instructor_id == cls.get('substitute_instructor_id'):
                    role = 'substitute'
            except Exception:
                role = None
        class_instructor_assignments[class_id] = {'id': instructor_id, 'role': role or 'primary'}
    prune_stale_class_timeouts()
    persist_class_state()

def build_room_session_map(active_sessions):
    """Group active sessions by room for quick occupancy lookups."""
    room_map = {}
    if not active_sessions:
        return room_map
    for session in active_sessions.values():
        room_number = session.get('room_number')
        normalized = normalize_room_label(room_number)
        if not normalized:
            continue
        room_map.setdefault(normalized, []).append(session)
    return room_map

def room_has_active_session(room_value, room_session_map, exempt_class_id=None):
    """Return True if the supplied room value has an active session not yet ended."""
    prune_expired_ended_classes()
    if not ongoing_classes:
        return False
    normalized = normalize_room_label(room_value)
    if not normalized:
        return False
    sessions = room_session_map.get(normalized) or []
    for session in sessions:
        occupant_class_id = _coerce_int(session.get('class_id') or session.get('classId') or session.get('id'))
        if occupant_class_id is not None:
            if exempt_class_id is not None and occupant_class_id == exempt_class_id:
                continue
            if occupant_class_id in ended_classes:
                continue
            if occupant_class_id not in ongoing_classes:
                continue
        else:
            continue
        ended_flag = session.get('ended') or session.get('ended_at') or session.get('endedAt')
        if ended_flag:
            continue
        return True
    return False

def normalize_class_payload(raw_class):
    """Ensure class dictionaries expose the snake_case keys expected by the UI."""
    raw_class = raw_class or {}

    def _value(*keys):
        for key in keys:
            if key in raw_class and raw_class[key] is not None:
                return raw_class[key]
        return None
    normalized = {'id': _value('id', 'class_id'), 'class_code': _value('class_code', 'classCode') or '', 'description': _value('description') or '', 'schedule': _value('schedule') or '', 'room_number': _value('room_number', 'roomNumber') or '', 'instructor_id': _value('instructor_id', 'instructorId'), 'substitute_instructor_id': _value('substitute_instructor_id', 'substituteInstructorId'), 'instructor_name': _value('instructor_name', 'instructorName') or '', 'substitute_instructor_name': _value('substitute_instructor_name', 'substituteInstructorName') or ''}
    normalized['classCode'] = normalized['class_code']
    normalized['roomNumber'] = normalized['room_number']
    normalized['instructorId'] = normalized['instructor_id']
    normalized['substituteInstructorId'] = normalized['substitute_instructor_id']
    normalized['instructorName'] = normalized['instructor_name']
    normalized['substituteInstructorName'] = normalized['substitute_instructor_name']
    for key, value in raw_class.items():
        if key not in normalized:
            normalized[key] = value
    return normalized
latest_room_session_map = {}

def _clone_room_session_map(room_map):
    cloned = {}
    for key, sessions in (room_map or {}).items():
        cloned[key] = [dict(session) for session in sessions]
    return cloned

def update_latest_room_session_map(room_map):
    """Store a snapshot of the most recent room/session occupancy map."""
    global latest_room_session_map
    latest_room_session_map = _clone_room_session_map(room_map)

def refresh_latest_room_session_map():
    """Fetch the newest active sessions and rebuild the room occupancy snapshot."""
    classes_snapshot = class_metadata_by_id or {}
    active_sessions = fetch_active_sessions()
    if active_sessions is None:
        return None
    sync_active_sessions_from_server(active_sessions, classes_snapshot)
    fresh_map = build_room_session_map(active_sessions or {})
    update_latest_room_session_map(fresh_map)
    return latest_room_session_map

class InstructorLoginScanner:
    """Minimal facial recognition scanner used for instructor authentication."""

    def __init__(self, parent, on_success, on_closed=None):
        if DeepFace is None:
            raise RuntimeError(f'DeepFace library is unavailable: {_DEEPFACE_IMPORT_ERROR}')
        self.parent = parent
        self.on_success = on_success
        self.on_closed = on_closed
        self.running = True
        self.current_frame = None
        self.success_emitted = False
        self._closed = False
        self.cap = None
        self.instructor_embeddings = []
        self.instructor_names = []
        self.instructor_ids = []
        self.window = ctk.CTkToplevel(parent)
        self.window.title('Instructor Facial Login')
        self.window.geometry('900x650')
        self.window.configure(fg_color=('#f0f8f0', '#1e4a1e'))
        self.window.grab_set()
        self.window.focus_force()
        self.window.protocol('WM_DELETE_WINDOW', self.close)
        bring_window_to_front(self.window)
        self._enter_fullscreen()
        self.window.bind('<Escape>', lambda _event=None: self.close())
        self.video_label = ctk.CTkLabel(self.window, text='Initializing camera...', width=820, height=480, corner_radius=16, fg_color='#000000', anchor='center', justify='center', font=('Arial', 20, 'bold'), text_color='#ffffff')
        self.video_label.pack(fill='both', expand=True, padx=20, pady=(20, 10))
        self.status_label = ctk.CTkLabel(self.window, text='Align your face with the camera', font=('Arial', 20), text_color=('#006400', '#90EE90'))
        self.status_label.pack(pady=(0, 10))
        self.cancel_button = ctk.CTkButton(self.window, text='Cancel Scan', font=('Arial', 18, 'bold'), width=220, height=55, fg_color=('#dc3545', '#c82333'), hover_color=('#a71d2a', '#7f151f'), command=self.close)
        self.cancel_button.pack(pady=(0, 20))
        self.face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        try:
            self.cap = cv2.VideoCapture(0)
            if not self.cap or not self.cap.isOpened():
                raise RuntimeError('Unable to access camera device for scanning.')
            cache_updated = download_face_encoding_cache()
            if not cache_updated and (not os.path.exists(FACE_ENCODINGS_CACHE)):
                raise RuntimeError('Unable to download face encoding cache from the server.')
            self._load_embeddings()
            if not self.instructor_embeddings:
                raise RuntimeError('No instructor face data found. Run the embedding extractor before using facial login.')
        except Exception:
            self.close(silent=True)
            raise
        self.last_cache_mtime = None
        self.update_check_interval = 5.0
        self._try_download_cache_on_startup()
        self._update_cache_mtime()
        self.update_frame()
        self.recognition_thread = threading.Thread(target=self._recognition_loop, daemon=True)
        self.recognition_thread.start()
        self.update_check_thread = threading.Thread(target=self._check_for_updates_loop, daemon=True)
        self.update_check_thread.start()

    def _enter_fullscreen(self):
        """Expand the scanner window to cover the entire kiosk display."""
        try:
            screen_w = self.window.winfo_screenwidth()
            screen_h = self.window.winfo_screenheight()
            if screen_w and screen_h:
                self.window.geometry(f'{screen_w}x{screen_h}+0+0')
        except Exception:
            pass
        try:
            self.window.overrideredirect(True)
        except Exception:
            pass
        try:
            self.window.attributes('-fullscreen', True)
        except Exception:
            try:
                self.window.state('zoomed')
            except Exception:
                pass

    def _try_download_cache_on_startup(self):
        """Try to download the latest cache file on startup if it doesn't exist or is outdated."""
        if not os.path.exists(FACE_ENCODINGS_CACHE):
            if self._download_cache_file():
                pass
            return
        try:
            response = requests.get(f'{SERVER_URL}/api/face-encodings/meta', headers=HEADERS, verify=False, timeout=3)
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    server_mtime_str = data.get('mtime')
                    if server_mtime_str:
                        server_mtime = datetime.fromisoformat(server_mtime_str.replace('Z', '+00:00')).timestamp()
                        local_mtime = os.path.getmtime(FACE_ENCODINGS_CACHE)
                        if server_mtime > local_mtime:
                            if self._download_cache_file():
                                pass
        except Exception as e:
            pass

    def _update_cache_mtime(self):
        """Update the last known cache file modification time."""
        if os.path.exists(FACE_ENCODINGS_CACHE):
            try:
                self.last_cache_mtime = os.path.getmtime(FACE_ENCODINGS_CACHE)
            except Exception:
                self.last_cache_mtime = None
        else:
            self.last_cache_mtime = None

    def _check_for_updates_loop(self):
        """Background thread that periodically checks for cache file updates."""
        while self.running:
            try:
                try:
                    response = requests.get(f'{SERVER_URL}/api/face-encodings/meta', headers=HEADERS, verify=False, timeout=3)
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
                    if os.path.exists(FACE_ENCODINGS_CACHE):
                        try:
                            current_mtime = os.path.getmtime(FACE_ENCODINGS_CACHE)
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
        cache_dir = os.path.dirname(FACE_ENCODINGS_CACHE)
        if cache_dir:
            os.makedirs(cache_dir, exist_ok=True)
        temp_path = FACE_ENCODINGS_CACHE + '.tmp'
        try:
            response = requests.get(FACE_ENCODINGS_ENDPOINT, headers=HEADERS, verify=False, timeout=30, stream=True)
            if response.status_code != 200:
                return False
            with open(temp_path, 'wb') as temp_file:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        temp_file.write(chunk)
            os.replace(temp_path, FACE_ENCODINGS_CACHE)
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
                self._load_embeddings()
                self._update_cache_mtime()
                return
            self._load_embeddings()
            self._update_cache_mtime()
        except Exception as e:
            pass

    def _load_embeddings(self):
        """Load instructor embeddings from the shared cache file."""
        if not os.path.exists(FACE_ENCODINGS_CACHE):
            raise RuntimeError(f'Face encoding cache not found at {FACE_ENCODINGS_CACHE}.')
        try:
            with open(FACE_ENCODINGS_CACHE, 'rb') as cache_file:
                face_data = pickle.load(cache_file)
        except Exception as exc:
            raise RuntimeError(f'Failed to load face encodings: {exc}')
        instructor_embeds = face_data.get('instructor_embeddings') or []
        self.instructor_embeddings = [self._normalize_embedding(np.array(embedding)) for embedding in instructor_embeds]
        self.instructor_names = face_data.get('instructor_names') or []
        self.instructor_ids = face_data.get('instructor_ids') or []

    @staticmethod
    def _normalize_embedding(embedding):
        norm = np.linalg.norm(embedding)
        return embedding / norm if norm > 0 else embedding

    def update_frame(self):
        if not self.running or not self.cap:
            return
        ret, frame = self.cap.read()
        if ret:
            self.current_frame = frame
            try:
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                img = Image.fromarray(frame_rgb)
                img.thumbnail((840, 500))
                photo = ImageTk.PhotoImage(img)
                self.video_label.configure(image=photo, text='')
                self.video_label.image = photo
            except Exception:
                pass
        if self.running:
            self.window.after(30, self.update_frame)

    def _recognition_loop(self):
        while self.running:
            frame = self.current_frame
            if frame is None:
                time.sleep(0.1)
                continue
            if not self.face_cascade.empty():
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                faces = self.face_cascade.detectMultiScale(gray, 1.2, 5)
                if len(faces) == 0:
                    self._update_status('No face detected. Please step closer.')
                    time.sleep(0.2)
                    continue
            try:
                representations = DeepFace.represent(img_path=frame, model_name='Facenet512', detector_backend='opencv', enforce_detection=False)
            except Exception:
                time.sleep(0.4)
                continue
            if not representations:
                time.sleep(0.3)
                continue
            recognized = False
            for rep in representations:
                embedding = self._normalize_embedding(np.array(rep['embedding']))
                match = self._compare_embeddings(embedding)
                if match:
                    name, instructor_id, confidence = match
                    recognized = True
                    self.window.after(0, lambda i=instructor_id, n=name: self._handle_success(i, n))
                    break
            if not recognized:
                self._update_status('Face not recognized. Please try again.')
                time.sleep(0.4)
            else:
                return

    def _compare_embeddings(self, embedding):
        best_idx = -1
        min_distance = float('inf')
        for idx, stored in enumerate(self.instructor_embeddings):
            try:
                distance = np.linalg.norm(embedding - stored)
            except Exception:
                continue
            if distance < min_distance:
                min_distance = distance
                best_idx = idx
        threshold = 0.6
        if best_idx >= 0 and min_distance < threshold:
            instructor_name = self.instructor_names[best_idx] if best_idx < len(self.instructor_names) else 'Instructor'
            instructor_id = self.instructor_ids[best_idx] if best_idx < len(self.instructor_ids) else None
            if instructor_id:
                confidence = max(0.0, (1 - min_distance) * 100)
                return (instructor_name, instructor_id, confidence)
        return None

    def _update_status(self, text):
        if not self.running:
            return
        try:
            self.status_label.configure(text=text)
        except Exception:
            pass

    def _handle_success(self, instructor_id, instructor_name):
        if self.success_emitted:
            return
        self.success_emitted = True
        self._update_status(f'Instructor recognized: {instructor_name}')
        callback = self.on_success
        self.close()
        if callback:
            callback(instructor_id, instructor_name)

    def close(self, silent=False):
        if self._closed:
            return
        self._closed = True
        self.running = False
        try:
            if self.cap:
                self.cap.release()
        except Exception:
            pass
        try:
            self.window.grab_release()
        except Exception:
            pass
        try:
            self.window.destroy()
        except Exception:
            pass
        if not silent and (not self.success_emitted) and (self.on_success is None):
            pass
        if self.on_closed:
            try:
                self.on_closed()
            except Exception:
                pass
active_login_scanner = None
pending_login_success_handler = None
AUTO_REFRESH_INTERVAL_MS = 5000
SCANNER_SESSION_MONITOR_INTERVAL_MS = 4000
classes_auto_refresh_job = None
ongoing_classes = set()
class_rooms = {}
class_session_ids = {}
class_instructor_assignments = {}
datetime_update_job = None
class_timeout_metadata = {}
class_timeout_jobs = {}
class_session_deadlines = {}
class_session_start_times = {}
class_metadata_by_id = {}
ended_classes = set()
ended_classes_day = datetime.now().date()
ENDED_CLASS_REENABLE_HOURS = 12
ENDED_CLASS_REENABLE_DELTA = timedelta(hours=ENDED_CLASS_REENABLE_HOURS)
ended_class_expirations = {}
_timeout_message_shown = set()
class_card_widgets = {}
current_displayed_class_ids = set()
locked_view_classes = set()
session_view_locks = {}
client_view_lock_sessions = {}
scanner_session_monitor_job = None
_CLASS_STATE_LOCK = threading.Lock()
_last_persisted_state_snapshot = None

def class_schedule_has_passed(class_id):
    info = class_timeout_metadata.get(class_id)
    if not info:
        return False
    window = info.get('window')
    if not window:
        return False
    end_dt = window.get('end_datetime')
    if not end_dt:
        return False
    return datetime.now() >= end_dt

def _coerce_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None

def _coerce_datetime(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(value)
    except (ValueError, TypeError):
        return None

def _serialize_datetime_map(source_map):
    serialized = {}
    for key, value in source_map.items():
        coerced_key = _coerce_int(key)
        if coerced_key is None or not isinstance(value, datetime):
            continue
        serialized[str(coerced_key)] = value.isoformat()
    return serialized

def _update_set_from_payload(target_set, payload):
    target_set.clear()
    for value in payload or []:
        coerced = _coerce_int(value)
        if coerced is None:
            continue
        target_set.add(coerced)

def _update_map_from_payload(target_map, payload, transform=None):
    target_map.clear()
    if not isinstance(payload, dict):
        return
    for key, raw_value in payload.items():
        coerced_key = _coerce_int(key)
        if coerced_key is None:
            continue
        value = transform(raw_value) if transform else raw_value
        if value is None:
            continue
        target_map[coerced_key] = value

def _update_datetime_map_from_payload(target_map, payload):
    target_map.clear()
    if not isinstance(payload, dict):
        return
    for key, raw_value in payload.items():
        coerced_key = _coerce_int(key)
        if coerced_key is None:
            continue
        dt_value = _coerce_datetime(raw_value)
        if dt_value is None:
            continue
        target_map[coerced_key] = dt_value

def _serialize_simple_map(source_map):
    serialized = {}
    for key, value in source_map.items():
        coerced_key = _coerce_int(key)
        if coerced_key is None:
            continue
        serialized[str(coerced_key)] = value
    return serialized

def _serialize_instructor_map():
    serialized = {}
    for key, value in class_instructor_assignments.items():
        coerced_key = _coerce_int(key)
        if coerced_key is None or not isinstance(value, dict):
            continue
        serialized[str(coerced_key)] = {'id': _coerce_int(value.get('id')), 'role': value.get('role')}
    return serialized

def _coerce_instructor_assignment(value):
    if not isinstance(value, dict):
        return None
    return {'id': _coerce_int(value.get('id')), 'role': value.get('role')}

def mark_class_recently_ended(class_id, reference_time=None):
    if class_id is None:
        return
    reference_time = reference_time or datetime.now()
    expiry = reference_time + ENDED_CLASS_REENABLE_DELTA
    ended_classes.add(class_id)
    ended_class_expirations[class_id] = expiry

def clear_class_recent_end_marker(class_id):
    if class_id is None:
        return
    ended_classes.discard(class_id)
    ended_class_expirations.pop(class_id, None)

def prune_expired_ended_classes(force=False):
    now = datetime.now()
    removed = False
    for class_id in list(ended_classes):
        expiry = ended_class_expirations.get(class_id)
        if expiry is None:
            if force:
                ended_classes.discard(class_id)
                removed = True
            continue
        if expiry <= now:
            ended_classes.discard(class_id)
            ended_class_expirations.pop(class_id, None)
            removed = True
    for class_id in list(ended_class_expirations.keys()):
        if class_id not in ended_classes:
            ended_class_expirations.pop(class_id, None)
            removed = True
    return removed

def _build_state_snapshot():
    day = ended_classes_day or datetime.now().date()
    return {'ended_classes_day': day.isoformat(), 'ended_classes': sorted((int(cid) for cid in ended_classes)), 'ended_class_expirations': _serialize_datetime_map(ended_class_expirations), 'ongoing_classes': sorted((int(cid) for cid in ongoing_classes)), 'class_rooms': _serialize_simple_map(class_rooms), 'class_session_ids': _serialize_simple_map(class_session_ids), 'class_instructor_assignments': _serialize_instructor_map()}

def persist_class_state():
    global _last_persisted_state_snapshot
    snapshot = _build_state_snapshot()
    if snapshot == _last_persisted_state_snapshot:
        return
    payload = dict(snapshot)
    payload['saved_at'] = datetime.now().isoformat()
    try:
        cache_dir = os.path.dirname(CLASS_STATE_CACHE_PATH)
        if cache_dir:
            os.makedirs(cache_dir, exist_ok=True)
        with _CLASS_STATE_LOCK:
            with open(CLASS_STATE_CACHE_PATH, 'w', encoding='utf-8') as cache_file:
                json.dump(payload, cache_file, indent=2)
        _last_persisted_state_snapshot = snapshot
    except Exception:
        pass

def load_class_state_cache():
    global ended_classes_day, _last_persisted_state_snapshot
    today = datetime.now().date()
    if not os.path.exists(CLASS_STATE_CACHE_PATH):
        ended_classes_day = today
        return
    try:
        with open(CLASS_STATE_CACHE_PATH, 'r', encoding='utf-8') as cache_file:
            data = json.load(cache_file) or {}
    except Exception:
        ended_classes_day = today
        return
    stored_day = data.get('ended_classes_day')
    try:
        stored_date = datetime.fromisoformat(stored_day).date() if stored_day else None
    except ValueError:
        stored_date = None
    if stored_date:
        ended_classes_day = stored_date
    else:
        ended_classes_day = today
    _update_set_from_payload(ended_classes, data.get('ended_classes'))
    _update_set_from_payload(ongoing_classes, data.get('ongoing_classes'))
    _update_map_from_payload(class_rooms, data.get('class_rooms'), lambda v: str(v) if v else None)
    _update_map_from_payload(class_session_ids, data.get('class_session_ids'), _coerce_int)
    _update_map_from_payload(class_instructor_assignments, data.get('class_instructor_assignments'), _coerce_instructor_assignment)
    _update_datetime_map_from_payload(ended_class_expirations, data.get('ended_class_expirations'))
    prune_expired_ended_classes(force=True)
    _last_persisted_state_snapshot = _build_state_snapshot()
load_class_state_cache()

def start_instructor_face_login(on_success=None):
    """Launch (or refocus) the instructor facial login scanner."""
    global active_login_scanner, pending_login_success_handler
    if active_login_scanner:
        try:
            active_login_scanner.window.focus_force()
        except Exception:
            pass
        return
    pending_login_success_handler = on_success
    parent = globals().get('root')
    if parent is None:
        return

    def _scanner_closed():
        global active_login_scanner, pending_login_success_handler
        scanner_ref = active_login_scanner
        was_success = getattr(scanner_ref, 'success_emitted', False) if scanner_ref else False
        active_login_scanner = None
        if not was_success:
            pending_login_success_handler = None

    def _dispatch_success(instructor_id, instructor_name):
        global pending_login_success_handler
        handler = pending_login_success_handler
        pending_login_success_handler = None
        if handler:
            handler(instructor_id, instructor_name)
    try:
        active_login_scanner = InstructorLoginScanner(parent, on_success=_dispatch_success, on_closed=_scanner_closed)
    except Exception as exc:
        _scanner_closed()
        messagebox.showerror('Scanner Error', str(exc))
ctk.set_appearance_mode('light')
ctk.set_default_color_theme('green')

def start_datetime_clock(label):
    """Continuously update the supplied label with system time in real-time."""
    global datetime_update_job

    def _refresh_label():
        global datetime_update_job
        try:
            now = datetime.now()
            time_text = now.strftime('%I:%M %p').lstrip('0') or now.strftime('%I:%M %p')
            date_text = f"{now.strftime('%B')} {now.day}, {now.year}"
            label.configure(text=f'{time_text} - {date_text}')
            datetime_update_job = label.after(1000, _refresh_label)
        except Exception:
            datetime_update_job = None
    if datetime_update_job:
        try:
            root.after_cancel(datetime_update_job)
        except Exception:
            pass
        datetime_update_job = None
    _refresh_label()

def cancel_classes_auto_refresh():
    """Stop any pending auto-refresh callback for the class list."""
    global classes_auto_refresh_job
    parent = globals().get('root')
    job = classes_auto_refresh_job
    if parent and job:
        try:
            parent.after_cancel(job)
        except Exception:
            pass
    classes_auto_refresh_job = None

def schedule_classes_auto_refresh():
    """Schedule the next automatic reload of today's classes."""
    global classes_auto_refresh_job
    parent = globals().get('root')
    if parent is None or AUTO_REFRESH_INTERVAL_MS <= 0:
        return
    cancel_classes_auto_refresh()
    try:
        classes_auto_refresh_job = parent.after(AUTO_REFRESH_INTERVAL_MS, refresh_class_statuses)
    except Exception:
        classes_auto_refresh_job = None

def cancel_scanner_session_monitor():
    """Stop polling the active session while the scanner UI is open."""
    global scanner_session_monitor_job
    parent = globals().get('root')
    job = scanner_session_monitor_job
    if parent and job:
        try:
            parent.after_cancel(job)
        except Exception:
            pass
    scanner_session_monitor_job = None

def schedule_scanner_session_monitor(class_id, session_id):
    """Poll the server to detect when another kiosk ends the class."""
    global scanner_session_monitor_job
    parent = globals().get('root')
    if parent is None or SCANNER_SESSION_MONITOR_INTERVAL_MS <= 0:
        return
    cancel_scanner_session_monitor()

    def _dispatch_check():
        global scanner_session_monitor_job
        scanner_session_monitor_job = None
        scanner_app = getattr(root, 'scanner_app', None)
        if scanner_app is None or getattr(scanner_app, 'class_id', None) != class_id:
            return
        active_sessions = fetch_active_sessions()
        if active_sessions is None:
            schedule_scanner_session_monitor(class_id, session_id)
            return
        remote_session = active_sessions.get(class_id)
        remote_session_id = remote_session.get('class_session_id') if remote_session else None
        if remote_session_id is None:
            remote_session_id = remote_session.get('session_id') if remote_session else None
        remote_session_id = _coerce_int(remote_session_id)
        expected_session_id = _coerce_int(session_id)
        session_missing = remote_session is None
        session_mismatch = not session_missing and expected_session_id is not None and (remote_session_id is not None) and (remote_session_id != expected_session_id)
        if session_missing or session_mismatch:
            try:
                scanner_app.handle_remote_session_end()
            except Exception:
                pass
            return
        schedule_scanner_session_monitor(class_id, session_id)
    try:
        scanner_session_monitor_job = parent.after(SCANNER_SESSION_MONITOR_INTERVAL_MS, _dispatch_check)
    except Exception:
        scanner_session_monitor_job = None

def determine_class_ui_state(cls, room_session_map):
    """Return the visual state metadata for a class card."""
    prune_expired_ended_classes()
    class_id = cls.get('id')
    is_ongoing = class_id in ongoing_classes
    class_has_ended = class_id in ended_classes
    room_key = normalize_room_label(FIXED_ROOM_NUMBER)
    room_is_occupied = room_has_active_session(room_key, room_session_map, exempt_class_id=class_id)
    schedule_passed = class_schedule_has_passed(class_id)
    server_lock_owner = session_view_locks.get(class_id)
    lock_owned_by_self = bool(server_lock_owner and server_lock_owner == CLIENT_INSTANCE_ID)
    remote_lock_active = bool(server_lock_owner and (not lock_owned_by_self))
    local_lock_active = class_id in locked_view_classes or lock_owned_by_self
    view_locked = local_lock_active or remote_lock_active
    if is_ongoing:
        status_text = 'Class Ongoing'
        status_color = ('#dc3545', '#c82333')
        action_mode = 'view'
        if local_lock_active:
            action_state = 'disabled'
            action_fg = ('#6c757d', '#5a6268')
            action_hover = ('#6c757d', '#5a6268')
        elif remote_lock_active:
            action_state = 'normal'
            action_fg = ('#ffc107', '#d39e00')
            action_hover = ('#e0a800', '#b88600')
        else:
            action_state = 'normal'
            action_fg = ('#ffc107', '#d39e00')
            action_hover = ('#e0a800', '#b88600')
        action_text = '👁 View (Locked)'
    else:
        locked_view_classes.discard(class_id)
        if not is_ongoing:
            session_view_locks.pop(class_id, None)
        if class_has_ended:
            status_text = 'Class Ended'
            status_color = ('#6c757d', '#5a6268')
        elif schedule_passed:
            status_text = 'Class Duration Passed'
            status_color = ('#6c757d', '#5a6268')
        elif room_is_occupied:
            status_text = 'Room Occupied'
            status_color = ('#dc3545', '#c82333')
        else:
            status_text = cls.get('description') or ''
            status_color = ('#006400', '#90EE90')
        disabled = class_has_ended or schedule_passed
        action_mode = 'start'
        action_state = 'disabled' if disabled else 'normal'
        if disabled:
            action_fg = ('#6c757d', '#5a6268')
            action_hover = ('#6c757d', '#5a6268')
        else:
            action_fg = ('#228B22', '#32CD32')
            action_hover = ('#006400', '#90EE90')
        action_text = '▶ Start Class'
    timeout_text = format_timeout_label_text(class_id, is_ongoing=is_ongoing)
    return {'status_text': status_text, 'status_color': status_color, 'status_font': ('Arial', 22, 'bold' if is_ongoing else 'normal'), 'timeout_text': timeout_text, 'action': {'mode': action_mode, 'text': action_text, 'state': action_state, 'fg_color': action_fg, 'hover_color': action_hover}, 'room_is_occupied': room_is_occupied, 'is_ongoing': is_ongoing, 'class_has_ended': class_has_ended, 'schedule_passed': schedule_passed}

def apply_class_state_to_widgets(class_id, cls, state):
    """Update an existing class card's widgets with the latest state."""
    widgets = class_card_widgets.get(class_id)
    if not widgets:
        return False
    status_label = widgets.get('status_label')
    if status_label:
        try:
            status_label.configure(text=state['status_text'], text_color=state['status_color'], font=state['status_font'])
        except Exception:
            pass
    timeout_label = widgets.get('timeout_label')
    if timeout_label:
        try:
            timeout_label.configure(text=state['timeout_text'])
        except Exception:
            pass
    action_button = widgets.get('action_button')
    if action_button:
        command = None
        if state['action']['mode'] == 'view':
            command = widgets.get('view_command')
        else:
            command = widgets.get('start_command')
        try:
            action_button.configure(text=state['action']['text'], state=state['action']['state'], fg_color=state['action']['fg_color'], hover_color=state['action']['hover_color'], command=command)
        except Exception:
            pass
    return True

def refresh_class_statuses():
    """Refresh only the class status indicators without rebuilding the UI."""
    cancel_classes_auto_refresh()
    should_reschedule = True
    if prune_expired_ended_classes():
        persist_class_state()
    scanner_app = getattr(root, 'scanner_app', None)
    if scanner_app is not None:
        active_sessions = fetch_active_sessions()
        if active_sessions is not None:
            sync_active_sessions_from_server(active_sessions, class_metadata_by_id)
            class_id = getattr(scanner_app, 'class_id', None)
            expected_session_id = getattr(scanner_app, 'session_id', None)
            remote_session = active_sessions.get(class_id) if class_id is not None else None
            remote_session_id = remote_session.get('class_session_id') if remote_session else None
            session_missing = remote_session is None
            session_mismatch = not session_missing and expected_session_id is not None and (remote_session_id is not None) and (remote_session_id != expected_session_id)
            if session_missing or session_mismatch:
                try:
                    scanner_app.handle_remote_session_end()
                except Exception:
                    pass
            schedule_classes_auto_refresh()
            return
    try:
        response = requests.get(f'{SERVER_URL}/classes/api/list', headers=HEADERS, verify=False)
        if response.status_code != 200:
            return
        raw_classes = response.json()
        classes = [normalize_class_payload(cls) for cls in raw_classes]
        classes_by_id = {cls['id']: cls for cls in classes if cls.get('id') is not None}
        class_metadata_by_id.clear()
        class_metadata_by_id.update(classes_by_id)
        rebuild_class_timeout_metadata(classes_by_id.values())
        active_sessions = fetch_active_sessions()
        sync_active_sessions_from_server(active_sessions, classes_by_id)
        room_session_map = build_room_session_map(active_sessions or {})
        update_latest_room_session_map(room_session_map)
        prune_stale_class_timeouts()
        todays_classes = [cls for cls in classes if class_occurs_today(cls.get('schedule', ''))]
        displayed_ids = {cls['id'] for cls in todays_classes if cls.get('id') is not None}
        if displayed_ids != current_displayed_class_ids:
            should_reschedule = False
            show_today_classes()
            return
        for cls in todays_classes:
            class_id = cls.get('id')
            if class_id is None:
                continue
            state = determine_class_ui_state(cls, room_session_map)
            if not apply_class_state_to_widgets(class_id, cls, state):
                should_reschedule = False
                show_today_classes()
                return
    except Exception:
        pass
    finally:
        if should_reschedule:
            schedule_classes_auto_refresh()

def show_today_classes():
    """Display classes scheduled for the current weekday."""
    global ended_classes_day
    cancel_classes_auto_refresh()
    if getattr(root, 'scanner_app', None):
        return
    now = datetime.now()
    today_date = now.date()
    day_changed = ended_classes_day != today_date
    if day_changed:
        ended_classes_day = today_date
    if prune_expired_ended_classes(force=day_changed) or day_changed:
        persist_class_state()
    today_label = now.strftime('%A')
    for widget in root.winfo_children():
        widget.destroy()
    class_card_widgets.clear()
    current_displayed_class_ids.clear()
    title_frame = ctk.CTkFrame(root, fg_color=('#f0f8f0', '#2d5a2d'))
    title_frame.pack(pady=20, fill='x')
    header_container = ctk.CTkFrame(title_frame, fg_color=('#e8f5e8', '#1e4a1e'))
    header_container.pack(fill='x', padx=20, pady=10)
    header_row = ctk.CTkFrame(header_container, fg_color='transparent')
    header_row.pack(fill='x', padx=10, pady=10)
    title_column = ctk.CTkFrame(header_row, fg_color='transparent')
    title_column.pack(side='left', pady=10)
    title_label = ctk.CTkLabel(title_column, text=f'Classes for {today_label}', font=('Arial', 26, 'bold'), text_color=('#006400', '#90EE90'))
    title_label.pack(anchor='w')
    room_label = ctk.CTkLabel(title_column, text=f'Room: {FIXED_ROOM_NUMBER}', font=('Arial', 21, 'bold'), text_color=('#006400', '#90EE90'))
    room_label.pack(anchor='w', pady=(4, 0))
    datetime_label = ctk.CTkLabel(title_column, text='', font=('Arial', 20), text_color=('#2d5a2d', '#b8e6b8'))
    datetime_label.pack(anchor='w', pady=(4, 0))
    start_datetime_clock(datetime_label)
    refresh_btn = ctk.CTkButton(header_row, text='↻ Refresh', font=('Arial', 18, 'bold'), width=160, height=48, fg_color=('#228B22', '#32CD32'), hover_color=('#006400', '#90EE90'), command=show_today_classes)
    refresh_btn.pack(side='right')
    try:
        response = requests.get(f'{SERVER_URL}/classes/api/list', headers=HEADERS, verify=False)
        if response.status_code != 200:
            error_label = ctk.CTkLabel(root, text=f'Failed to load classes: {response.status_code} - {response.text}', font=('Arial', 18))
            error_label.pack(pady=20)
            return
        raw_classes = response.json()
        classes = [normalize_class_payload(cls) for cls in raw_classes]
        classes_by_id = {cls['id']: cls for cls in classes if cls.get('id') is not None}
        class_metadata_by_id.clear()
        class_metadata_by_id.update(classes_by_id)
        rebuild_class_timeout_metadata(classes_by_id.values())
        active_sessions = fetch_active_sessions()
        sync_active_sessions_from_server(active_sessions, classes_by_id)
        room_session_map = build_room_session_map(active_sessions or {})
        update_latest_room_session_map(room_session_map)
        prune_stale_class_timeouts()
        todays_classes = [cls for cls in classes if class_occurs_today(cls.get('schedule', ''))]
        if not todays_classes:
            no_classes_label = ctk.CTkLabel(root, text=f'No classes scheduled for {today_label}.', font=('Arial', 20, 'bold'), text_color=('#006400', '#90EE90'))
            no_classes_label.pack(pady=40)
        else:
            scrollable_frame = ctk.CTkScrollableFrame(root, width=600, height=400, fg_color=('#f8fff8', '#2d5a2d'), scrollbar_button_color=('#228B22', '#32CD32'))
            scrollable_frame.pack(pady=20, fill='both', expand=True)
            displayed_classes = sorted(todays_classes, key=class_start_sort_key)
            current_displayed_class_ids.update((cls['id'] for cls in displayed_classes if cls.get('id') is not None))
            available_rooms = fetch_available_rooms()

            def get_active_room_map(force_refresh=False):
                if force_refresh:
                    refreshed = refresh_latest_room_session_map()
                    if refreshed:
                        return refreshed
                if latest_room_session_map:
                    return latest_room_session_map
                return room_session_map

            def room_is_currently_occupied(room_value, exempt_class_id=None, force_refresh=False, room_map_override=None):
                """Return True if the supplied room has an active session."""
                active_map = room_map_override if room_map_override is not None else get_active_room_map(force_refresh=force_refresh)
                return room_has_active_session(room_value, active_map, exempt_class_id=exempt_class_id)

            def room_occupant_summary(room_value, exempt_class_id=None, force_refresh=False, room_map_override=None):
                active_map = room_map_override if room_map_override is not None else get_active_room_map(force_refresh=force_refresh)
                normalized = normalize_room_label(room_value)
                sessions = (active_map or {}).get(normalized) or []
                lines = []
                for session in sessions:
                    occupant_code = session.get('class_code') or f"Class {session.get('class_id') or ''}".strip()
                    occupant_desc = session.get('description') or ''
                    instructor_id = session.get('instructor_id')
                    instructor_name = None
                    if instructor_id:
                        try:
                            instructor_id_int = int(instructor_id)
                        except (TypeError, ValueError):
                            instructor_id_int = None
                        if instructor_id_int is not None:
                            instructor_name = None
                            for cls_payload in class_metadata_by_id.values():
                                if cls_payload.get('id') == session.get('class_id'):
                                    instructor_name = cls_payload.get('instructor_name') or cls_payload.get('instructorName')
                                    break
                    occupant_class_id = session.get('class_id')
                    try:
                        occupant_class_id = int(occupant_class_id)
                    except (TypeError, ValueError):
                        occupant_class_id = None
                    if occupant_class_id is not None and exempt_class_id is not None and (occupant_class_id == exempt_class_id):
                        continue
                    details = occupant_code or 'Another class'
                    if occupant_desc:
                        details += f' — {occupant_desc}'
                    if instructor_name:
                        details += f' (Instructor: {instructor_name})'
                    lines.append(details)
                return '\n'.join(lines)

            def confirm_room_override(room_value, exempt_class_id=None, room_map_override=None):
                summary = room_occupant_summary(room_value, exempt_class_id, force_refresh=room_map_override is None, room_map_override=room_map_override)
                message = f'Room {room_value} is currently marked as occupied.\n\nOnly continue if you are sure no instructor is already running a session in this room or the kiosk was reset.'
                if summary:
                    message += f'\n\nCurrently running:\n{summary}'
                message += '\n\nPlease choose a different room or wait until the current class ends.'
                try:
                    messagebox.showerror('Room Occupied', message)
                except Exception:
                    pass
                return False

            def refresh_class_card(target):
                if isinstance(target, dict):
                    class_obj = target
                else:
                    class_obj = next((c for c in displayed_classes if c.get('id') == target), None)
                    if class_obj is None:
                        class_obj = class_metadata_by_id.get(target)
                if not class_obj or class_obj.get('id') is None:
                    return
                state = determine_class_ui_state(class_obj, room_session_map)
                apply_class_state_to_widgets(class_obj['id'], class_obj, state)

            def _open_scanner_window(class_id, room_input, session_id=None):
                """Replace the client UI with the embedded facial recognition scanner."""
                cancel_classes_auto_refresh()
                scanner_dir = os.path.dirname(__file__)
                if scanner_dir not in sys.path:
                    sys.path.append(scanner_dir)
                try:
                    from facial_recognition_tkinter import FacialRecognitionApp
                except Exception as e:
                    messagebox.showerror('Error', f'Failed to import scanner module: {e}')
                    return False
                for widget in root.winfo_children():
                    widget.destroy()
                scanner_frame = ctk.CTkFrame(root, fg_color=('#f0f8f0', '#1e4a1e'))
                scanner_frame.pack(fill='both', expand=True)

                def cleanup_scanner_container():
                    cancel_scanner_session_monitor()
                    try:
                        scanner_frame.destroy()
                    except Exception:
                        pass
                    setattr(root, 'scanner_app', None)

                def on_scanner_exit(session_ended=False):
                    release_remote_view_lock(class_id, session_id)
                    cleanup_scanner_container()
                    locked_view_classes.discard(class_id)
                    refresh_class_card(class_id)
                    if session_ended:
                        ongoing_classes.discard(class_id)
                        class_rooms.pop(class_id, None)
                        class_session_ids.pop(class_id, None)
                        class_instructor_assignments.pop(class_id, None)
                        cancel_class_timeout(class_id)
                        mark_class_recently_ended(class_id)
                        persist_class_state()
                    show_today_classes()

                def on_scanner_logout():
                    release_remote_view_lock(class_id, session_id)
                    cleanup_scanner_container()
                    locked_view_classes.discard(class_id)
                    refresh_class_card(class_id)
                    show_today_classes()
                try:
                    instructor_binding = class_instructor_assignments.get(class_id) or {}
                    app = FacialRecognitionApp(scanner_frame, class_id=class_id, session_id=session_id, room_number=room_input, embedded=True, on_exit=on_scanner_exit, on_logout=on_scanner_logout, acting_instructor_id=instructor_binding.get('id'), acting_instructor_role=instructor_binding.get('role'))
                    root.scanner_app = app
                    if session_id is not None:
                        schedule_scanner_session_monitor(class_id, session_id)
                except Exception as e:
                    scanner_frame.destroy()
                    setattr(root, 'scanner_app', None)
                    messagebox.showerror('Scanner Error', f'Failed to open facial recognition scanner:\n{e}')
                    show_today_classes()
                    return False
                return True

            def start_facial_recognition_for_class_show_room_modal(class_id_for_modal):
                """Show the room verification modal and return the selected room."""
                modal = ctk.CTkToplevel(root)
                modal.title('Room Verification')
                modal.geometry('860x700')
                modal.configure(fg_color=('#f0f8f0', '#1e4a1e'))
                modal.transient(root)
                modal.grab_set()
                modal.focus()
                modal.resizable(False, False)
                modal.minsize(860, 700)
                modal.maxsize(860, 700)
                modal.update_idletasks()
                x = modal.winfo_screenwidth() // 2 - 860 // 2
                y = modal.winfo_screenheight() // 2 - 700 // 2
                modal.geometry(f'860x700+{x}+{y}')
                bring_window_to_front(modal)
                result = {'room': None}
                main_frame = ctk.CTkFrame(modal, fg_color=('#e8f5e8', '#2d5a2d'))
                main_frame.pack(fill='both', expand=True, padx=20, pady=20)
                title_label = ctk.CTkLabel(main_frame, text='🏫 Room Verification Required', font=('Arial', 28, 'bold'), text_color=('#006400', '#90EE90'))
                title_label.pack(pady=(30, 20))
                selected_class = next((c for c in displayed_classes if c.get('id') == class_id_for_modal), None)
                class_display = selected_class['class_code'] if selected_class else str(class_id_for_modal)
                class_label = ctk.CTkLabel(main_frame, text=f'Class: {class_display}', font=('Arial', 22), text_color=('#006400', '#90EE90'))
                class_label.pack(pady=10)
                instruction_label = ctk.CTkLabel(main_frame, text='Please select the room number to start facial recognition:', font=('Arial', 18), text_color=('#2d5a2d', '#b8e6b8'))
                instruction_label.pack(pady=20)
                room_frame = ctk.CTkFrame(main_frame, fg_color='transparent')
                room_frame.pack(pady=20, fill='x')
                placeholder = 'Select a room'
                room_options = available_rooms or DEFAULT_ROOM_OPTIONS
                modal_room_map = get_active_room_map(force_refresh=True)
                room_entries = []
                for option in room_options:
                    occupied = room_is_currently_occupied(option, class_id_for_modal, room_map_override=modal_room_map)
                    display_text = f'{option} (Occupied)' if occupied else option
                    room_entries.append({'display': display_text, 'value': option, 'occupied': occupied})
                option_values = [placeholder] + [entry['display'] for entry in room_entries]
                room_var = ctk.StringVar(value=placeholder)
                room_lookup = {entry['display']: entry for entry in room_entries}
                dropdown = ctk.CTkOptionMenu(room_frame, values=option_values, variable=room_var, width=420, height=70, font=('Arial', 20, 'bold'), dropdown_font=('Arial', 18), fg_color=('#228B22', '#32CD32'), text_color='#ffffff', button_color=('#006400', '#004d00'), button_hover_color=('#004d00', '#003000'), dropdown_fg_color=('#e8f5e8', '#1e4a1e'), dropdown_hover_color=('#cdeacc', '#2f6a2f'))
                dropdown.pack(pady=10)
                feedback_label = ctk.CTkLabel(main_frame, text='', font=('Arial', 18), text_color='#dc3545')
                feedback_label.pack(pady=(0, 10))
                hint_label = ctk.CTkLabel(main_frame, text='Rooms marked as Occupied are locked until that class finishes.', font=('Arial', 16), text_color=('#8B0000', '#f8d7da'))
                hint_label.pack(pady=(0, 10))
                room_status_label = ctk.CTkLabel(main_frame, text='', font=('Arial', 17), text_color=('#8B0000', '#f5c6cb'), justify='left')
                room_status_label.pack(pady=(0, 10), fill='x')

                def update_room_status(*_args):
                    selected = room_var.get()
                    entry = room_lookup.get(selected)
                    if entry:
                        active_map = get_active_room_map(force_refresh=True)
                        if room_is_currently_occupied(entry['value'], class_id_for_modal, room_map_override=active_map):
                            summary = room_occupant_summary(entry['value'], class_id_for_modal, room_map_override=active_map)
                            if not summary:
                                summary = 'Another kiosk reports this room is busy.'
                            room_status_label.configure(text=f'Room in use:\n{summary}')
                            return
                    room_status_label.configure(text='')
                update_room_status()
                try:
                    room_var.trace_add('write', update_room_status)
                except AttributeError:
                    room_var.trace('w', lambda *_: update_room_status())

                def confirm_room():
                    selected = room_var.get()
                    if selected == placeholder:
                        feedback_label.configure(text='Please pick a room before continuing.')
                        return
                    entry = room_lookup.get(selected)
                    actual_value = entry['value'] if entry else selected
                    active_map = get_active_room_map(force_refresh=True)
                    if room_is_currently_occupied(actual_value, class_id_for_modal, room_map_override=active_map):
                        confirm_room_override(actual_value, class_id_for_modal, room_map_override=active_map)
                        feedback_label.configure(text='That room is currently in use. Please choose another room.')
                        room_var.set(placeholder)
                        update_room_status()
                        return
                    result['room'] = actual_value
                    modal.destroy()
                button_frame = ctk.CTkFrame(main_frame, fg_color='transparent')
                button_frame.pack(pady=30, fill='x')
                button_frame.columnconfigure(0, weight=1)
                button_frame.columnconfigure(1, weight=1)
                confirm_btn = ctk.CTkButton(button_frame, text='Confirm', font=('Arial', 25, 'bold'), height=90, fg_color=('#228B22', '#32CD32'), hover_color=('#006400', '#90EE90'), text_color='#ffffff', command=confirm_room)
                confirm_btn.grid(row=0, column=0, padx=15, pady=5, sticky='nsew')

                def cancel_action():
                    modal.destroy()
                cancel_btn = ctk.CTkButton(button_frame, text='Cancel', font=('Arial', 25, 'bold'), height=90, fg_color='#dc3545', hover_color='#c82333', text_color='#ffffff', command=cancel_action)
                cancel_btn.grid(row=0, column=1, padx=15, pady=5, sticky='nsew')
                dropdown.focus()
                modal.wait_window()
                return result['room']

            def record_instructor_checkin(cls, instructor_id, room_input):
                class_id = cls['id']
                try:
                    instructor_id_int = int(instructor_id)
                except (TypeError, ValueError):
                    messagebox.showerror('Check-In Failed', 'Instructor identifier is invalid. Please rescan.')
                    return None
                payload = {'instructor_id': instructor_id_int, 'class_id': class_id, 'room_number': room_input, 'timestamp': datetime.now().astimezone().isoformat()}
                try:
                    response = requests.post(f'{SERVER_URL}/api/checkin/instructor', headers=JSON_HEADERS, json=payload, verify=False, timeout=15)
                except requests.exceptions.RequestException as exc:
                    messagebox.showerror('Check-In Failed', f'Unable to reach the server for instructor check-in.\n{exc}')
                    return None
                if response.status_code != 200:
                    messagebox.showerror('Check-In Failed', f'Server rejected the instructor check-in (status {response.status_code}).\n{response.text}')
                    return None
                try:
                    data = response.json()
                except Exception:
                    data = {}
                session_id = data.get('class_session_id') or data.get('session_id')
                if not session_id:
                    messagebox.showerror('Check-In Failed', 'Server did not return an active class session ID.')
                    return None
                return {'session_id': session_id, 'scheduled_start_time': data.get('scheduled_start_time') or data.get('scheduledStartTime'), 'scheduled_end_time': data.get('scheduled_end_time') or data.get('scheduledEndTime'), 'timeout_deadline': data.get('timeout_deadline') or data.get('timeoutDeadline')}

            def launch_scanner_for_session(cls, room_input, session_id, timeout_deadline=None):
                class_id = cls['id']
                class_rooms[class_id] = room_input
                class_session_ids[class_id] = session_id
                ongoing_classes.add(class_id)
                clear_class_recent_end_marker(class_id)
                if not _open_scanner_window(class_id, room_input, session_id):
                    ongoing_classes.discard(class_id)
                    class_rooms.pop(class_id, None)
                    class_session_ids.pop(class_id, None)
                    class_instructor_assignments.pop(class_id, None)
                    persist_class_state()
                    show_today_classes()
                    return False
                schedule_class_timeout(class_id, datetime.now(), cls, timeout_deadline=timeout_deadline)
                persist_class_state()
                return True

            def show_override_modal(parent, lock_owner=None, context='override'):
                is_start_confirmation = context == 'start'
                is_view_confirmation = context == 'view'
                modal = ctk.CTkToplevel(parent)
                if is_start_confirmation:
                    modal_title = 'Confirm Start Class'
                elif is_view_confirmation:
                    modal_title = 'Confirm View Session'
                else:
                    modal_title = 'Override View Lock'
                modal.title(modal_title)
                modal.geometry('600x400')
                modal.configure(fg_color=('#f0f8f0', '#1e4a1e'))
                modal.transient(parent)
                modal.grab_set()
                modal.focus()
                modal.resizable(False, False)
                modal.update_idletasks()
                x = modal.winfo_screenwidth() // 2 - 600 // 2
                y = modal.winfo_screenheight() // 2 - 400 // 2
                modal.geometry(f'600x400+{x}+{y}')
                result = {'override': False}
                main_frame = ctk.CTkFrame(modal, fg_color=('#e8f5e8', '#2d5a2d'))
                main_frame.pack(fill='both', expand=True, padx=20, pady=20)
                title_label = ctk.CTkLabel(main_frame, text=modal_title, font=('Arial', 28, 'bold'), text_color=('#006400', '#90EE90'))
                title_label.pack(pady=(30, 20))
                if is_start_confirmation:
                    message = 'Are you sure you want to start this class session?\n\nThis will begin facial recognition attendance.'
                    confirm_text = 'Start Class'
                elif is_view_confirmation:
                    message = 'Are you sure you want to view this ongoing class session?\n\nContinue only if you are the assigned instructor or authorized staff.'
                    confirm_text = 'View Session'
                else:
                    display_owner = lock_owner or 'on another kiosk'
                    message = 'Only continue if there is no instructor Present or if the system has accidentally shutdown. Do you wish to continue?'
                    confirm_text = 'Override'
                message_label = ctk.CTkLabel(main_frame, text=message, font=('Arial', 18), text_color=('#2d5a2d', '#b8e6b8'), wraplength=500)
                message_label.pack(pady=20)
                button_frame = ctk.CTkFrame(main_frame, fg_color='transparent')
                button_frame.pack(pady=30)

                def confirm():
                    result['override'] = True
                    modal.destroy()

                def cancel():
                    modal.destroy()
                confirm_btn = ctk.CTkButton(button_frame, text=confirm_text, font=('Arial', 20, 'bold'), width=150, height=50, fg_color=('#228B22', '#32CD32'), hover_color=('#006400', '#90EE90'), command=confirm)
                confirm_btn.pack(side='left', padx=15)
                cancel_btn = ctk.CTkButton(button_frame, text='Cancel', font=('Arial', 20, 'bold'), width=150, height=50, fg_color='#dc3545', hover_color='#c82333', command=cancel)
                cancel_btn.pack(side='left', padx=15)
                modal.wait_window()
                return result['override']

            def view_ongoing_class(cls):
                class_id = cls['id']
                session_id = class_session_ids.get(class_id)
                if not session_id:
                    messagebox.showerror('Session Missing', 'Unable to locate the active session for this class. Please start the class again.')
                    ongoing_classes.discard(class_id)
                    class_rooms.pop(class_id, None)
                    class_session_ids.pop(class_id, None)
                    class_instructor_assignments.pop(class_id, None)
                    locked_view_classes.discard(class_id)
                    persist_class_state()
                    return
                lock_owner = session_view_locks.get(class_id)
                lock_owned_by_self = bool(lock_owner and lock_owner == CLIENT_INSTANCE_ID)
                remote_lock_active = bool(lock_owner and (not lock_owned_by_self))
                if remote_lock_active:
                    allow_override = show_override_modal(root, lock_owner)
                    if not allow_override:
                        return
                    unlock_success, unlock_error = release_remote_view_lock(class_id, session_id, force=True)
                    if not unlock_success:
                        messagebox.showerror('Override Failed', f"Unable to free the session for viewing.\n{unlock_error or 'Unknown error.'}")
                        refresh_class_card(cls)
                        return
                    locked_view_classes.discard(class_id)
                    refresh_class_card(cls)
                else:
                    confirm_view = show_override_modal(root, context='view')
                    if not confirm_view:
                        return

                def _safe_int(value):
                    try:
                        return int(value)
                    except (TypeError, ValueError):
                        return None
                allowed_roles = {}
                binding = class_instructor_assignments.get(class_id)
                binding_id = _safe_int(binding.get('id') if binding else None)
                if binding_id is not None:
                    allowed_roles[binding_id] = binding.get('role') or 'primary'
                if not allowed_roles:
                    primary_int = _safe_int(cls.get('instructor_id') or cls.get('instructorId'))
                    if primary_int is not None:
                        allowed_roles[primary_int] = 'primary'
                    substitute_int = _safe_int(cls.get('substitute_instructor_id') or cls.get('substituteInstructorId'))
                    if substitute_int is not None:
                        allowed_roles[substitute_int] = 'substitute'
                if not allowed_roles:
                    messagebox.showerror('Instructor Verification', 'Unable to verify the assigned instructor for this class.')
                    return

                def _after_scan(instructor_id, instructor_name):
                    instructor_id_int = _safe_int(instructor_id)
                    if instructor_id_int is None:
                        messagebox.showerror('Instructor Verification', 'Unable to determine the instructor identity from the scan.')
                        return
                    if instructor_id_int not in allowed_roles:
                        messagebox.showerror('Instructor Verification', 'The recognized instructor is not assigned to this class.')
                        return
                    welcome_name = instructor_name or 'Instructor'
                    try:
                        messagebox.showinfo('Instructor Verified', f'Welcome back, {welcome_name}!')
                    except Exception:
                        pass
                    success, lock_error = acquire_remote_view_lock(class_id, session_id)
                    if not success:
                        locked_view_classes.discard(class_id)
                        refresh_class_card(cls)
                        messagebox.showerror('Instructor Verification', f'Unable to reserve the scanner for this session:\n{lock_error}')
                        return
                    refresh_class_card(cls)
                    class_instructor_assignments[class_id] = {'id': instructor_id_int, 'role': allowed_roles[instructor_id_int]}
                    persist_class_state()
                    # Viewing an ongoing class should reuse known room, otherwise fall back to fixed room.
                    room_input = class_rooms.get(class_id) or FIXED_ROOM_NUMBER
                    if room_input is None:
                        release_remote_view_lock(class_id, session_id)
                        refresh_class_card(cls)
                        return
                    if not _open_scanner_window(class_id, room_input, session_id):
                        release_remote_view_lock(class_id, session_id)
                        refresh_class_card(cls)
                start_instructor_face_login(_after_scan)

            def start_class_with_instructor_verification(cls):
                class_id = cls['id']
                if class_id in ongoing_classes:
                    view_ongoing_class(cls)
                    return
                primary_candidate = cls.get('instructor_id') or cls.get('instructorId')
                substitute_candidate = cls.get('substitute_instructor_id') or cls.get('substituteInstructorId')

                def _safe_int(value):
                    try:
                        return int(value)
                    except (TypeError, ValueError):
                        return None
                allowed_roles = {}
                primary_int = _safe_int(primary_candidate)
                if primary_int is not None:
                    allowed_roles[primary_int] = 'primary'
                substitute_int = _safe_int(substitute_candidate)
                if substitute_int is not None:
                    allowed_roles[substitute_int] = 'substitute'
                if not allowed_roles:
                    messagebox.showerror('Instructor Required', 'This class does not have an assigned instructor or substitute. Please assign one before starting the session.')
                    return

                def _after_scan(instructor_id, instructor_name):
                    if not instructor_id:
                        messagebox.showerror('Instructor Verification', 'Unable to determine the instructor identity from the scan.')
                        return
                    try:
                        instructor_id_int = int(instructor_id)
                    except (TypeError, ValueError):
                        messagebox.showerror('Instructor Validation', 'Unable to validate the instructor assignment for this class.')
                        return
                    instructor_role = allowed_roles.get(instructor_id_int)
                    if not instructor_role:
                        messagebox.showerror('Instructor Mismatch', 'The recognized instructor is not assigned to this class.')
                        return
                    if instructor_name:
                        try:
                            messagebox.showinfo('Instructor Verified', f'Welcome, {instructor_name}!')
                        except Exception:
                            pass
                    # New class start no longer asks for room selection; use fixed room directly.
                    room_input = FIXED_ROOM_NUMBER
                    active_map = get_active_room_map(force_refresh=True)
                    if room_is_currently_occupied(room_input, class_id, room_map_override=active_map):
                        confirm_room_override(room_input, class_id, room_map_override=active_map)
                        return
                    session_info = record_instructor_checkin(cls, instructor_id_int, room_input)
                    if not session_info:
                        return
                    session_id = session_info.get('session_id')
                    if not session_id:
                        return
                    timeout_deadline = session_info.get('timeout_deadline') or session_info.get('scheduled_end_time')
                    class_instructor_assignments[class_id] = {'id': instructor_id_int, 'role': instructor_role}
                    launch_scanner_for_session(cls, room_input, session_id, timeout_deadline)
                start_instructor_face_login(_after_scan)
            for cls in displayed_classes:
                class_id = cls['id']
                if class_id is None:
                    continue
                state = determine_class_ui_state(cls, room_session_map)
                is_ongoing = state['is_ongoing']
                class_has_ended = state.get('class_has_ended')
                schedule_passed = state.get('schedule_passed')
                ended_theme = bool(class_has_ended or schedule_passed)
                if is_ongoing:
                    frame_colors = ('#f0f0f0', '#404040')
                    headline_color = ('#6c757d', '#5a6268')
                    detail_color = ('#6c757d', '#5a6268')
                    timeout_color = ('#8B0000', '#f8d7da')
                elif ended_theme:
                    frame_colors = ('#f5f5f5', '#3a3a3a')
                    headline_color = ('#6c757d', '#5a6268')
                    detail_color = ('#6c757d', '#5a6268')
                    timeout_color = ('#6c757d', '#adb5bd')
                else:
                    frame_colors = ('#e8f5e8', '#1e4a1e')
                    headline_color = ('#006400', '#90EE90')
                    detail_color = ('#2d5a2d', '#b8e6b8')
                    timeout_color = ('#495057', '#ced4da')
                class_frame = ctk.CTkFrame(scrollable_frame, fg_color=frame_colors)
                class_frame.pack(pady=15, fill='x', padx=50)
                inline_frame = ctk.CTkFrame(class_frame, fg_color='transparent')
                inline_frame.pack(pady=15, fill='x', padx=15)
                class_code_label = ctk.CTkLabel(inline_frame, text=cls['class_code'], font=('Arial', 24, 'bold'), text_color=headline_color)
                class_code_label.pack(side='left', padx=(0, 20))
                class_desc_label = ctk.CTkLabel(inline_frame, text=state['status_text'], font=state['status_font'], text_color=state['status_color'])
                class_desc_label.pack(side='left', padx=(0, 20))
                schedule_label = ctk.CTkLabel(inline_frame, text=f"Schedule: {cls['schedule']}", font=('Arial', 20), text_color=detail_color)
                schedule_label.pack(side='left', padx=(0, 20))
                instructor_name = cls.get('instructor_name') or cls.get('instructorName') or 'Unassigned'
                instructor_label = ctk.CTkLabel(inline_frame, text=f'Instructor: {instructor_name}', font=('Arial', 20), text_color=detail_color)
                instructor_label.pack(side='left', padx=(0, 20))
                timeout_label = ctk.CTkLabel(inline_frame, text=state['timeout_text'], font=('Arial', 18), text_color=timeout_color)
                timeout_label.pack(side='left', padx=(0, 20))
                action_button = ctk.CTkButton(inline_frame, text='', font=('Arial', 18, 'bold'), width=160, height=50)
                action_button.pack(side='right', padx=(10, 10))
                class_card_widgets[class_id] = {'status_label': class_desc_label, 'timeout_label': timeout_label, 'action_button': action_button, 'start_command': lambda c=cls: start_class_with_instructor_verification(c), 'view_command': lambda c=cls: view_ongoing_class(c)}
                apply_class_state_to_widgets(class_id, cls, state)
    except Exception as e:
        error_label = ctk.CTkLabel(root, text=f'Failed to load classes: {str(e)}', font=('Arial', 18))
        error_label.pack(pady=20)
    finally:
        if getattr(root, 'scanner_app', None) is None:
            schedule_classes_auto_refresh()

def end_class_session(cls, auto=False):
    """End a class session and mark absent students."""
    class_id = cls['id']
    class_code = cls['class_code']
    session_id = class_session_ids.get(class_id)
    if not auto:
        confirm = messagebox.askyesno('End Class', f"Are you sure you want to end {class_code}?\n\nAll students who haven't checked in will be marked as ABSENT.")
        if not confirm:
            return False
    try:
        instructor_binding = class_instructor_assignments.get(class_id)
        instructor_id_override = instructor_binding.get('id') if instructor_binding else None
        instructor_id = instructor_id_override
        if instructor_id is None:
            classes_response = requests.get(f'{SERVER_URL}/classes/api/list', headers=HEADERS, verify=False, timeout=10)
            if classes_response.status_code != 200:
                messagebox.showerror('Error', f'Could not fetch class list: {classes_response.status_code}')
                return False
            classes = classes_response.json()
            class_data = next((c for c in classes if int(c.get('id', 0)) == int(class_id)), None)
            if not class_data:
                messagebox.showerror('Error', 'Could not find class in the system.')
                return False
            instructor_id = class_data.get('instructorId')
        if not instructor_id:
            messagebox.showerror('Error', 'Could not determine instructor for this class.')
            return False
        checkout_data = {'instructor_id': instructor_id, 'class_id': class_id}
        if session_id:
            checkout_data['class_session_id'] = session_id
        checkout_data['auto'] = bool(auto)
        checkout_response = requests.post(f'{SERVER_URL}/api/checkout/instructor', json=checkout_data, headers=HEADERS, verify=False, timeout=10)
        if checkout_response.status_code == 200:
            result = checkout_response.json()
            absent_count = result.get('total_absent_students_marked', 0)
            title = 'Class Timed Out' if auto else 'Class Ended'
            if absent_count > 0:
                body = f"{class_code} {('timed out' if auto else 'ended')} successfully.\n{absent_count} absent student(s) marked."
            else:
                body = f"{class_code} {('timed out' if auto else 'ended')} successfully.\nNo absent students to mark."
            if auto and class_id not in _timeout_message_shown:
                try:
                    messagebox.showinfo(title, body)
                    _timeout_message_shown.add(class_id)
                except Exception:
                    pass
            elif not auto:
                try:
                    messagebox.showinfo(title, body)
                except Exception:
                    pass
        else:
            try:
                error_payload = checkout_response.json()
            except ValueError:
                error_payload = {}
            error_message = error_payload.get('error') or error_payload.get('message') or checkout_response.text or 'Unknown server response'
            messagebox.showerror('Error', f'Failed to end class: {error_message}')
    except Exception as e:
        messagebox.showerror('Error', f'Failed to end class: {str(e)}')
        return False
    return True

def end_class_session_and_reset(cls, auto=False):
    """End a class session, mark absences, and refresh the kiosk state."""
    result = end_class_session(cls, auto=auto)
    if result and cls['id'] in ongoing_classes:
        ongoing_classes.remove(cls['id'])
        class_session_ids.pop(cls['id'], None)
        class_rooms.pop(cls['id'], None)
        class_instructor_assignments.pop(cls['id'], None)
        locked_view_classes.discard(cls['id'])
        release_remote_view_lock(cls['id'])
        cancel_class_timeout(cls['id'])
        show_today_classes()
    if result:
        mark_class_recently_ended(cls['id'])
    persist_class_state()
    return result
root = ctk.CTk()
root.title('Facial Recognition Class Attendance System')
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
    root.overrideredirect(True)
except Exception:
    pass
show_today_classes()
root.mainloop()
