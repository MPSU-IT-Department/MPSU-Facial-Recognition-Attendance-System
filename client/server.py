import os

# Centralized server configuration for the kiosk apps.
SERVER_URL = os.environ.get('FRCAS_SERVER_URL', 'http://127.0.0.1:5000')
API_KEY = os.environ.get('FRCAS_API_KEY', 'frcas-local-api-key')
HEADERS = {'X-API-Key': API_KEY}
JSON_HEADERS = {**HEADERS, 'Content-Type': 'application/json'}
