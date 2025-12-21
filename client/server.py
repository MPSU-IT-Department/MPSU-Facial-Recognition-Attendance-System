import os

# Centralized server configuration for the kiosk apps.
SERVER_URL = os.environ.get('FRCAS_SERVER_URL', 'https://192.168.1.18:5000')
API_KEY = os.environ.get('FRCAS_API_KEY', 'FrC4sS3cUr3K3y2024!@#$%^&*()')
HEADERS = {'X-API-Key': API_KEY}
JSON_HEADERS = {**HEADERS, 'Content-Type': 'application/json'}
