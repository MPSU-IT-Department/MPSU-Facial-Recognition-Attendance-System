"""
Flask Backend Launcher
Starts the Flask backend for FRCAS-ClassPass
"""
import sys
import os
import subprocess
from pathlib import Path
from dotenv import load_dotenv

def main():
    """Launch the Flask backend"""
    root_dir = Path(__file__).parent.absolute()
    load_dotenv(dotenv_path=root_dir / '.env')
    backend_dir = root_dir / 'backend'
    os.chdir(backend_dir)
    host = os.environ.get('FRCAS_HOST', '127.0.0.1')
    port = os.environ.get('FRCAS_PORT', '5000')
    use_https = os.environ.get('FRCAS_USE_HTTPS', 'false').strip().lower() in {'1', 'true', 'yes', 'on'}
    os.environ['FLASK_APP'] = 'app:create_app'
    os.environ['FLASK_ENV'] = 'development'
    os.environ['PYTHONPATH'] = str(backend_dir)
    os.environ['FLASK_RUN_HOST'] = host
    os.environ['FLASK_RUN_PORT'] = port
    try:
        python_exe = sys.executable
        command = [python_exe, '-m', 'flask', 'run', '--host', host, '--port', port]
        scheme = 'http'
        if use_https:
            cert_path = os.environ.get('FRCAS_SSL_CERT', 'cert.pem')
            key_path = os.environ.get('FRCAS_SSL_KEY', 'key.pem')
            if os.path.exists(cert_path) and os.path.exists(key_path):
                command.extend(['--cert', cert_path, '--key', key_path])
                scheme = 'https'
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError as e:
        sys.exit(e.returncode)
    except Exception as e:
        sys.exit(1)
if __name__ == '__main__':
    main()
