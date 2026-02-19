import argparse
from getpass import getpass
from datetime import datetime
from app import create_app
from extensions import db
from models.user import User

def parse_args():
    p = argparse.ArgumentParser(description='Create or update an admin user')
    p.add_argument('--username', '-u', required=True, help='Username for the admin account')
    p.add_argument('--email', '-e', required=False, help='Email address')
    p.add_argument('--password', '-p', required=False, help='Password (will prompt if omitted)')
    p.add_argument('--first-name', required=False, help='First name')
    p.add_argument('--last-name', required=False, help='Last name')
    return p.parse_args()

def main():
    args = parse_args()
    password = args.password or getpass('Password: ')
    app = create_app()
    with app.app_context():
        user = User.query.filter_by(username=args.username).first()
        if user:
            user.email = args.email or user.email
            user.first_name = args.first_name or user.first_name
            user.last_name = args.last_name or user.last_name
            user.role = 'admin'
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
        else:
            user = User(username=args.username, email=args.email, first_name=args.first_name or '', last_name=args.last_name or '', role='admin')
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
if __name__ == '__main__':
    main()
