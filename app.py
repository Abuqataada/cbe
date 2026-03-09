import os
import logging
import click
from logging.handlers import RotatingFileHandler
from flask import Flask, app, request, render_template, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from config import config
from models import db, User

from datetime import datetime

TRIAL_EXPIRY = datetime(2026, 3, 20)


from flask_talisman import Talisman

# Add CSP headers
csp = {
    'default-src': ["'self'"],
    'style-src': [
        "'self'",
        "'unsafe-inline'",
        "https://cdn.jsdelivr.net",
        "https://cdnjs.cloudflare.com",
        "https://fonts.googleapis.com"
    ],
    'font-src': [
        "'self'",
        "https://cdn.jsdelivr.net",
        "https://cdnjs.cloudflare.com",
        "https://fonts.gstatic.com"
    ],
    'script-src': [
        "'self'",
        "'unsafe-inline'",
        "https://cdn.jsdelivr.net",
        "https://cdnjs.cloudflare.com"
    ],
    'img-src': ["'self'", "data:", "https:", "res.cloudinary.com"],
    'connect-src': ["'self'", "https://api.cloudinary.com", "https://res.cloudinary.com"],
}


login_manager = LoginManager()
migrate = Migrate()
limiter = Limiter(key_func=get_remote_address, default_limits=["200 per day", "50 per hour"])

def create_app(config_name='default'):
    """Application factory"""
    app = Flask(__name__, static_folder='static', template_folder='templates')
    
    # Load configuration
    app.config.from_object(config[config_name])
    
    from utils.cloudinary_helper import cloudinary_helper

    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    limiter.init_app(app)
    cloudinary_helper.init_app(app)
    
    # Configure login manager
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'
    login_manager.login_message_category = 'info'
    
    @login_manager.user_loader
    def load_user(user_id):
        """Load a user by ID (from session)"""
        return User.query.get(user_id)
    
    def setup_security(app):
        # Only enable Talisman if HTTPS is configured
        if app.config.get('PREFERRED_URL_SCHEME') == 'https':
            from flask_talisman import Talisman
            Talisman(app, content_security_policy=csp, force_https=False)
        else:
            # Add basic security headers without HTTPS enforcement
            @app.after_request
            def add_security_headers(response):
                response.headers['X-Content-Type-Options'] = 'nosniff'
                response.headers['X-Frame-Options'] = 'SAMEORIGIN'
                response.headers['X-XSS-Protection'] = '1; mode=block'
                response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
                return response

    setup_security(app)
    
    # Setup logging - only if not in serverless environment
    if not app.debug and not os.environ.get('VERCEL_ENV'):
        if not os.path.exists('logs'):
            os.mkdir('logs')
        file_handler = RotatingFileHandler(
            'logs/school_management.log', maxBytes=10240, backupCount=10
        )
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        ))
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)
        app.logger.setLevel(logging.INFO)
        app.logger.info('School Management System startup')
    
    # Create directories ONLY if using local storage and NOT in serverless
    storage_type = app.config.get('STORAGE_TYPE', 'local')
    is_serverless = os.environ.get('VERCEL_ENV') is not None
    
    if storage_type == 'local' and not is_serverless:
        # Only create directories for local storage and non-serverless environments
        os.makedirs(app.config.get('UPLOAD_FOLDER', 'uploads'), exist_ok=True)
        os.makedirs(app.config.get('REPORT_FOLDER', 'reports'), exist_ok=True)
        os.makedirs('logs', exist_ok=True)
        app.logger.info(f"Created local directories for {storage_type} storage")
    else:
        # For serverless or cloud storage, skip directory creation
        app.logger.info(f"Skipping directory creation - Storage: {storage_type}, Serverless: {is_serverless}")
    
    # Register blueprints
    from routes.auth import auth_bp
    from routes.admin_routes import admin_bp
    from routes.teacher_routes import teacher_bp
    from routes.student_routes import student_bp
    from routes.bulk_import import bulk_bp
    from routes.report_routes import report_bp
    from routes.finance_routes import finance_bp
    
    app.register_blueprint(report_bp, url_prefix='/reports')
    app.register_blueprint(finance_bp, url_prefix='/finance')
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(teacher_bp)
    app.register_blueprint(student_bp)
    app.register_blueprint(bulk_bp)
    
    # Error handlers
    from routes.errors import register_error_handlers
    register_error_handlers(app)
    
    # CLI commands
    @app.cli.command('init-db')
    def init_db_command():
        """Initialize the database."""
        with app.app_context():
            db.create_all()
        print('Initialized the database.')

    @app.cli.command('seed-data')
    def seed_data_command():
        """Seed the database with initial data."""
        from utils.seed import seed_all_data
        with app.app_context():
            seed_all_data()
        print('Database seeded successfully.')

    @app.cli.command('create-admin')
    @click.option('--username', prompt=True, help='Admin username')
    @click.option('--email', prompt=True, help='Admin email')
    @click.option('--password', prompt=True, hide_input=True, confirmation_prompt=True, help='Admin password')
    def create_admin_command(username, email, password):
        """Create an admin user."""
        from models import User
        from werkzeug.security import generate_password_hash
        with app.app_context():
            if User.query.filter_by(username=username).first():
                print(f"User '{username}' already exists.")
                return
            if User.query.filter_by(email=email).first():
                print(f"Email '{email}' already exists.")
                return
            admin = User(username=username, email=email, role='admin', is_active=True)
            admin.set_password(password)
            db.session.add(admin)
            db.session.commit()
            print(f"Admin user '{username}' created successfully.")

    # Inject context
    @app.context_processor
    def inject_user():
        from flask_login import current_user
        return dict(current_user=current_user)
    
    @app.context_processor
    def inject_config():
        from models import SystemConfiguration
        configs = {}
        with app.app_context():
            try:
                for item in SystemConfiguration.query.all():
                    configs[item.config_key] = item.config_value
            except Exception:
                pass
        return dict(config=configs)
    
    # Request hooks
    @app.before_request
    def before_request():
        pass
    
    @app.after_request
    def after_request(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        if request.endpoint and not request.endpoint.startswith('static'):
            app.logger.info(f"{request.remote_addr} - {request.method} {request.path} - {response.status}")
        return response
    
    # Create tables and seed default data - only if not in serverless or using persistent DB
    with app.app_context():
        try:
            db.create_all()
            # Only call seed functions here
            from utils.seed import create_default_finance_admin, create_default_admin, create_default_academic_session
            create_default_admin()
            create_default_finance_admin()
            create_default_academic_session()
        except Exception as e:
            app.logger.error(f"Database initialization error: {str(e)}")
    
    return app

# Create app instance
app = create_app(os.getenv('FLASK_ENV') or 'default')

with app.app_context():
    # Create tables and seed default data - only if not in serverless or using persistent DB
    db.create_all()
    # Only call seed functions here
    from utils.seed import create_default_finance_admin, create_default_admin, create_default_academic_session
    create_default_admin()
    create_default_finance_admin()
    create_default_academic_session()

def create_upload_directories():
    """Create necessary upload directories"""
    directories = [
        'static/uploads/questions',
        'static/uploads/options'
    ]
    
    for directory in directories:
        os.makedirs(os.path.join(app.root_path, directory), exist_ok=True)

@app.before_request
def check_trial_expiry():

    # Allow expired page itself
    if request.endpoint == "expired":
        return None

    # Allow static files
    if request.endpoint == "static":
        return None

    if datetime.now() > TRIAL_EXPIRY:
        return redirect(url_for("expired"))


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/administrator')
def admin_index():
    return render_template('admin_index.html')

@app.route('/finance_admin')
def finance_admin_index():
    return render_template('finance_index.html')

@app.route('/staff')
def staff_index():
    return render_template('staff_index.html')

@app.route('/expired')
def expired():
    return render_template('expired.html')   


STUDENTS_INFO = {
    "class_id": "737ae9a7-bf8d-4ae0-a3d0-1d42c7187d46",
    "students": [
    {
      "address": None,
      "created_at": "2026-03-05T07:03:26.038194",
      "dob": "2015-02-01",
      "email": "miracle.imoh@arndaleacademy.com",
      "first_name": "Miracle  ",
      "full_name": "Miracle   Imoh",
      "gender": "female",
      "id": "d4635a92-8815-49da-add5-45ded31a13c0",
      "last_name": "Imoh",
      "medical_info": None,
      "middle_name": "Sylvester",
      "parent_email": None,
      "parent_name": "Sylvester Imoh",
      "parent_phone": "08036687581",
      "parent_relationship": None,
      "previous_school": None,
      "remarks": None,
      "updated_at": "2026-03-05T07:03:26.038221"
    },
    {
      "address": None,
      "created_at": "2026-03-05T07:11:51.243847",
      "dob": "2015-09-06",
      "email": "zahra.yakubu@arndaleacademy.com",
      "first_name": "Zahra",
      "full_name": "Zahra Yakubu",
      "gender": "female",
      "id": "91701bbc-67ef-4057-a5e6-cc11bdd82424",
      "last_name": "Yakubu",
      "medical_info": None,
      "middle_name": "Alfa",
      "parent_email": None,
      "parent_name": "Yakubu Alfa",
      "parent_phone": "08162282100",
      "parent_relationship": "Father",
      "previous_school": None,
      "remarks": None,
      "updated_at": "2026-03-05T07:11:51.243877"
    },
    {
      "address": None,
      "created_at": "2026-03-05T07:11:51.243847",
      "dob": "2014-12-18",
      "email": "nathan.reng@arndaleacademy.com",
      "first_name": "Nathan",
      "full_name": "Nathan Reng",
      "gender": "male",
      "id": "30e061da-053d-4225-9869-bbf53f6e8579",
      "last_name": "Reng",
      "medical_info": None,
      "middle_name": None,
      "parent_email": None,
      "parent_name": "Reng Gyang",
      "parent_phone": "07082440359",
      "parent_relationship": None,
      "previous_school": None,
      "remarks": None,
      "updated_at": "2026-03-05T07:11:51.243877"
    },
    {
      "address": None,
      "created_at": "2026-03-05T07:29:52.379267",
      "dob": "2015-01-24",
      "email": "khalil.abdulkadir@arndaleacademy.com",
      "first_name": "Khalil",
      "full_name": "Khalil Abdulkadir",
      "gender": "male",
      "id": "bd175ced-7d68-4a93-98c7-158f28d5b8f2",
      "last_name": "Abdulkadir",
      "medical_info": None,
      "middle_name": None,
      "parent_email": None,
      "parent_name": "Abdulkadir Halilu",
      "parent_phone": "08035865999",
      "parent_relationship": None,
      "previous_school": None,
      "remarks": None,
      "updated_at": "2026-03-05T07:29:52.379290"
    },
    {
      "address": None,
      "created_at": "2026-03-05T07:29:52.379267",
      "dob": "2013-01-13",
      "email": "joseph.essien@arndaleacademy.com",
      "first_name": "Joseph",
      "full_name": "Joseph Essien",
      "gender": "male",
      "id": "6a4cd06f-9fee-43e7-9644-e82dc2dbfc33",
      "last_name": "Essien",
      "medical_info": None,
      "middle_name": None,
      "parent_email": None,
      "parent_name": "Essien Joseph",
      "parent_phone": "09034812771",
      "parent_relationship": None,
      "previous_school": None,
      "remarks": None,
      "updated_at": "2026-03-05T07:29:52.379290"
    },
    {
      "address": None,
      "created_at": "2026-03-05T07:41:24.494424",
      "dob": "2014-06-24",
      "email": "abdullahi.ibrahim@arndaleacademy.com",
      "first_name": "Abdullahi",
      "full_name": "Abdullahi Ibrahim",
      "gender": "male",
      "id": "56b94773-8a09-4036-8ee7-ce5f0a2b1c70",
      "last_name": "Ibrahim",
      "medical_info": None,
      "middle_name": None,
      "parent_email": None,
      "parent_name": "Dogo Ibrahim",
      "parent_phone": "08039808663",
      "parent_relationship": None,
      "previous_school": None,
      "remarks": None,
      "updated_at": "2026-03-05T07:41:24.494450"
    },
    {
      "address": None,
      "created_at": "2026-03-05T07:49:22.354593",
      "dob": "2015-06-12",
      "email": "geogewill.temple@arndaleacademy.com",
      "first_name": "Geogewill ",
      "full_name": "Geogewill  Temple",
      "gender": "female",
      "id": "5089dee9-d25f-4f8b-bdbf-5ab36b277eb3",
      "last_name": "Temple",
      "medical_info": None,
      "middle_name": "Success",
      "parent_email": None,
      "parent_name": "Geogewill Temple",
      "parent_phone": "07060290349",
      "parent_relationship": None,
      "previous_school": None,
      "remarks": None,
      "updated_at": "2026-03-05T07:49:22.354622"
    },
    {
      "address": None,
      "created_at": "2026-03-05T07:58:26.760650",
      "dob": "2014-03-16",
      "email": "tanze.kaiyah@arndaleacademy.com",
      "first_name": "Tanze ",
      "full_name": "Tanze  Kaiyah",
      "gender": "female",
      "id": "aac5a677-3889-45a9-bb06-15cce443961d",
      "last_name": "Kaiyah",
      "medical_info": None,
      "middle_name": "Oprite",
      "parent_email": None,
      "parent_name": "Tanze Kaiyah",
      "parent_phone": "08060067079",
      "parent_relationship": None,
      "previous_school": None,
      "remarks": None,
      "updated_at": "2026-03-05T07:58:26.760674"
    },
    {
      "address": None,
      "created_at": "2026-03-05T08:08:34.374375",
      "dob": "2014-09-17",
      "email": "abubakar musbahu.muabahu@arndaleacademy.com",
      "first_name": "Abubakar Musbahu",
      "full_name": "Abubakar Musbahu Muabahu",
      "gender": "male",
      "id": "b19c13f9-e757-4079-ba3b-79594fed8e07",
      "last_name": "Muabahu",
      "medical_info": None,
      "middle_name": None,
      "parent_email": None,
      "parent_name": "Garba Musbahu",
      "parent_phone": "07031725065",
      "parent_relationship": None,
      "previous_school": None,
      "remarks": None,
      "updated_at": "2026-03-05T08:08:34.374416"
    },
    {
      "address": None,
      "created_at": "2026-03-05T08:16:11.525879",
      "dob": "2014-09-15",
      "email": "khadija.shehu@arndaleacademy.com",
      "first_name": "Khadija",
      "full_name": "Khadija Shehu",
      "gender": "female",
      "id": "12a3c57e-2800-441a-8725-bbe718182d0d",
      "last_name": "Shehu",
      "medical_info": None,
      "middle_name": None,
      "parent_email": None,
      "parent_name": "Ahmed Shehu",
      "parent_phone": "08066674881",
      "parent_relationship": None,
      "previous_school": None,
      "remarks": None,
      "updated_at": "2026-03-05T08:16:11.525907"
    },
    {
      "address": None,
      "created_at": "2026-03-05T08:23:17.878038",
      "dob": "2012-09-30",
      "email": "ahmed.usman@arndaleacademy.com",
      "first_name": "Ahmed",
      "full_name": "Ahmed Usman",
      "gender": "male",
      "id": "c31e1a77-b270-4b7e-8ed4-4f2f3f04cd8c",
      "last_name": "Usman",
      "medical_info": None,
      "middle_name": "Bilbob",
      "parent_email": None,
      "parent_name": "Usman Ahmed Bilbob",
      "parent_phone": "07031361073",
      "parent_relationship": None,
      "previous_school": None,
      "remarks": None,
      "updated_at": "2026-03-05T08:23:17.878065"
    },
    {
      "address": None,
      "created_at": "2026-03-05T08:27:25.916603",
      "dob": "2015-06-09",
      "email": "michael.george@arndaleacademy.com",
      "first_name": "Michael",
      "full_name": "Michael George",
      "gender": "male",
      "id": "28da111f-a878-4510-9ac2-e3ac6a70818d",
      "last_name": "George",
      "medical_info": None,
      "middle_name": None,
      "parent_email": None,
      "parent_name": "Mondi Sunday",
      "parent_phone": "07060452930",
      "parent_relationship": None,
      "previous_school": None,
      "remarks": None,
      "updated_at": "2026-03-05T08:27:25.916630"
    },
    {
      "address": None,
      "created_at": "2026-03-05T08:27:25.916603",
      "dob": "2014-01-02",
      "email": "aisha.idrs@arndaleacademy.com",
      "first_name": "Aisha",
      "full_name": "Aisha Idrs",
      "gender": "female",
      "id": "d3019332-b399-4ac4-84ad-a0fa5345f125",
      "last_name": "Idrs",
      "medical_info": None,
      "middle_name": "Muhammed",
      "parent_email": None,
      "parent_name": "Idris Muhammad",
      "parent_phone": "08037386434",
      "parent_relationship": None,
      "previous_school": None,
      "remarks": None,
      "updated_at": "2026-03-05T08:27:25.916630"
    },
    {
      "address": None,
      "created_at": "2026-03-05T09:01:54.475389",
      "dob": "2013-01-18",
      "email": "muhammed.bashir@arndaleacademy.com",
      "first_name": "Muhammed ",
      "full_name": "Muhammed  Bashir",
      "gender": "female",
      "id": "62748573-c9d5-4d56-9ac3-8b3e5385662d",
      "last_name": "Bashir",
      "medical_info": None,
      "middle_name": None,
      "parent_email": None,
      "parent_name": "Bashir Yar'Adua",
      "parent_phone": "08036193694",
      "parent_relationship": None,
      "previous_school": None,
      "remarks": None,
      "updated_at": "2026-03-05T09:01:54.475416"
    },
    {
      "address": None,
      "created_at": "2026-03-05T09:01:54.475389",
      "dob": "2014-04-04",
      "email": "imisi.onobulu@arndaleacademy.com",
      "first_name": "Imisi",
      "full_name": "Imisi Onobulu",
      "gender": "female",
      "id": "116feeb7-f461-46cc-a692-3637ddec3aae",
      "last_name": "Onobulu",
      "medical_info": None,
      "middle_name": "Oluwa",
      "parent_email": None,
      "parent_name": "Onubulu Onobulu",
      "parent_phone": "08080894714",
      "parent_relationship": None,
      "previous_school": None,
      "remarks": None,
      "updated_at": "2026-03-05T09:01:54.475416"
    },
    {
      "address": None,
      "created_at": "2026-03-05T09:01:54.475389",
      "dob": "2015-10-24",
      "email": "ahmed.shehu@arndaleacademy.com",
      "first_name": "Ahmed",
      "full_name": "Ahmed Shehu",
      "gender": "male",
      "id": "bcd7f914-1ab9-4a5a-9478-94ad4b8577d0",
      "last_name": "Shehu",
      "medical_info": None,
      "middle_name": None,
      "parent_email": None,
      "parent_name": "Ahmed Shehu",
      "parent_phone": "08066674881",
      "parent_relationship": None,
      "previous_school": None,
      "remarks": None,
      "updated_at": "2026-03-05T09:01:54.475416"
    },
    {
      "address": None,
      "created_at": "2026-03-05T09:01:54.475389",
      "dob": "2013-12-21",
      "email": "abdulhamid.abba@arndaleacademy.com",
      "first_name": "Abdulhamid",
      "full_name": "Abdulhamid Abba",
      "gender": "male",
      "id": "431807e8-0d14-49b0-9169-f648f6fc3e54",
      "last_name": "Abba",
      "medical_info": None,
      "middle_name": None,
      "parent_email": None,
      "parent_name": "Ibrahim Abba",
      "parent_phone": "08038448914",
      "parent_relationship": None,
      "previous_school": None,
      "remarks": None,
      "updated_at": "2026-03-05T09:01:54.475416"
    },
    {
      "address": None,
      "created_at": "2026-03-05T09:01:54.475389",
      "dob": "2014-01-10",
      "email": "abdullahi.ibrahim1@arndaleacademy.com",
      "first_name": "Abdullahi",
      "full_name": "Abdullahi Ibrahim",
      "gender": "male",
      "id": "8d78d5d2-6d2d-4a83-afa0-4cefee22718b",
      "last_name": "Ibrahim",
      "medical_info": None,
      "middle_name": "Umar",
      "parent_email": None,
      "parent_name": "Ibrahim Umar",
      "parent_phone": "07038391823",
      "parent_relationship": None,
      "previous_school": None,
      "remarks": None,
      "updated_at": "2026-03-05T09:01:54.475416"
    },
    {
      "address": None,
      "created_at": "2026-03-05T09:01:54.475389",
      "dob": "2015-02-16",
      "email": "humphrey.kamara@arndaleacademy.com",
      "first_name": "Humphrey",
      "full_name": "Humphrey Kamara",
      "gender": "female",
      "id": "ae01299a-7f18-49c2-bbce-de8f70accbe3",
      "last_name": "Kamara",
      "medical_info": None,
      "middle_name": None,
      "parent_email": None,
      "parent_name": "Humphrey Kamara",
      "parent_phone": "07037710911",
      "parent_relationship": None,
      "previous_school": None,
      "remarks": None,
      "updated_at": "2026-03-05T09:01:54.475416"
    },
    {
      "address": None,
      "created_at": "2026-03-07T08:55:23.945539",
      "dob": "2014-06-24",
      "email": "abdullahi.ibrahim fogo@arndaleacademy.com",
      "first_name": "ABDULLAHI ",
      "full_name": "ABDULLAHI  IBRAHIM FOGO",
      "gender": "male",
      "id": "feeb606f-5c4c-4810-8d6a-61661e6144dd",
      "last_name": "IBRAHIM FOGO",
      "medical_info": None,
      "middle_name": None,
      "parent_email": None,
      "parent_name": "DOGO IBRAHIM ",
      "parent_phone": "08039808663",
      "parent_relationship": None,
      "previous_school": None,
      "remarks": None,
      "updated_at": "2026-03-07T08:55:23.945565"
    },
    {
      "address": None,
      "created_at": "2026-03-07T08:55:23.945539",
      "dob": "2013-12-21",
      "email": "abdulhamid.ibrahim abba@arndaleacademy.com",
      "first_name": "ABDULHAMID ",
      "full_name": "ABDULHAMID  IBRAHIM ABBA",
      "gender": "male",
      "id": "a55aaa45-2c20-41f1-96d8-1dcd1a3f2529",
      "last_name": "IBRAHIM ABBA",
      "medical_info": None,
      "middle_name": None,
      "parent_email": None,
      "parent_name": "IBRAHIM ABBA",
      "parent_phone": "08038448914",
      "parent_relationship": "FATHER",
      "previous_school": None,
      "remarks": None,
      "updated_at": "2026-03-07T08:55:23.945565"
    },
    {
      "address": None,
      "created_at": "2026-03-07T08:55:23.945539",
      "dob": "2014-07-01",
      "email": "abubakar.musbahu garba@arndaleacademy.com",
      "first_name": "ABUBAKAR ",
      "full_name": "ABUBAKAR  MUSBAHU GARBA",
      "gender": "male",
      "id": "d4bd3df3-95c2-43b5-9498-bebf5b1c8a57",
      "last_name": "MUSBAHU GARBA",
      "medical_info": None,
      "middle_name": None,
      "parent_email": None,
      "parent_name": "GARBA MUSBAHU ",
      "parent_phone": "08031725065",
      "parent_relationship": "FATHER ",
      "previous_school": None,
      "remarks": None,
      "updated_at": "2026-03-07T08:55:23.945565"
    },
    {
      "address": None,
      "created_at": "2026-03-07T08:55:23.945539",
      "dob": "2015-06-09",
      "email": "alfa.zahra yakubu@arndaleacademy.com",
      "first_name": "ALFA",
      "full_name": "ALFA ZAHRA YAKUBU",
      "gender": "female",
      "id": "287b355c-e091-4801-a966-aac7ba5e6ba7",
      "last_name": "ZAHRA YAKUBU ",
      "medical_info": None,
      "middle_name": None,
      "parent_email": None,
      "parent_name": "YAKUBU ALFA",
      "parent_phone": "08162282100",
      "parent_relationship": "FATHER ",
      "previous_school": None,
      "remarks": None,
      "updated_at": "2026-03-07T08:55:23.945565"
    },
    {
      "address": None,
      "created_at": "2026-03-07T08:55:23.945539",
      "dob": "2015-06-12",
      "email": "amarachi.geogewill success@arndaleacademy.com",
      "first_name": "AMARACHI ",
      "full_name": "AMARACHI  GEOGEWILL SUCCESS",
      "gender": "female",
      "id": "a5252184-107a-43eb-a60c-d5a0127986fa",
      "last_name": "GEOGEWILL SUCCESS ",
      "medical_info": None,
      "middle_name": None,
      "parent_email": None,
      "parent_name": "GEORGEWILL TEMPLE ",
      "parent_phone": "07060290349",
      "parent_relationship": None,
      "previous_school": None,
      "remarks": None,
      "updated_at": "2026-03-07T08:55:23.945565"
    },
    {
      "address": None,
      "created_at": "2026-03-07T08:55:23.945539",
      "dob": "2015-09-15",
      "email": "ahmed.khadija@arndaleacademy.com",
      "first_name": "AHMED ",
      "full_name": "AHMED  KHADIJA",
      "gender": "female",
      "id": "4d159f14-23d1-4465-aaa7-78d7644af9ee",
      "last_name": "KHADIJA ",
      "medical_info": None,
      "middle_name": None,
      "parent_email": None,
      "parent_name": "AHMED SHEHU ",
      "parent_phone": "08066674881",
      "parent_relationship": None,
      "previous_school": None,
      "remarks": None,
      "updated_at": "2026-03-07T08:55:23.945565"
    },
    {
      "address": None,
      "created_at": "2026-03-07T08:55:23.945539",
      "dob": "2015-10-24",
      "email": "ahmed.shehu1@arndaleacademy.com",
      "first_name": "AHMED ",
      "full_name": "AHMED  SHEHU",
      "gender": "male",
      "id": "27ea7473-9a4c-454f-a0d3-134009a7617a",
      "last_name": "SHEHU ",
      "medical_info": None,
      "middle_name": None,
      "parent_email": None,
      "parent_name": "AHMED SHEHU ",
      "parent_phone": "08066674881",
      "parent_relationship": "FATHER ",
      "previous_school": None,
      "remarks": None,
      "updated_at": "2026-03-07T08:55:23.945565"
    },
    {
      "address": None,
      "created_at": "2026-03-07T08:55:23.945539",
      "dob": "2015-01-24",
      "email": "abdulkadir.khalil@arndaleacademy.com",
      "first_name": "ABDULKADIR ",
      "full_name": "ABDULKADIR  KHALIL",
      "gender": "male",
      "id": "5a0a58a7-ecf1-4749-827c-431fc0b7ee5f",
      "last_name": "KHALIL",
      "medical_info": None,
      "middle_name": None,
      "parent_email": None,
      "parent_name": "ABDULKADIR HAMZA",
      "parent_phone": "08035865999",
      "parent_relationship": None,
      "previous_school": None,
      "remarks": None,
      "updated_at": "2026-03-07T08:55:23.945565"
    },
    {
      "address": None,
      "created_at": "2026-03-07T08:55:23.945539",
      "dob": "2014-11-02",
      "email": "aisha.idris muhammed@arndaleacademy.com",
      "first_name": "AISHA",
      "full_name": "AISHA IDRIS MUHAMMED",
      "gender": "female",
      "id": "c768e8b7-665e-4bbb-80e9-2b479c409bda",
      "last_name": "IDRIS MUHAMMED",
      "medical_info": None,
      "middle_name": None,
      "parent_email": None,
      "parent_name": "IDRIS MUHAMMED ",
      "parent_phone": "08037386434",
      "parent_relationship": None,
      "previous_school": None,
      "remarks": None,
      "updated_at": "2026-03-07T08:55:23.945565"
    },
    {
      "address": None,
      "created_at": "2026-03-07T08:55:23.945539",
      "dob": "2015-02-06",
      "email": "kamara.himphrey@arndaleacademy.com",
      "first_name": "KAMARA ",
      "full_name": "KAMARA  HIMPHREY",
      "gender": "female",
      "id": "121e1e9b-e7f9-4845-bf4b-c001ae1c5b5f",
      "last_name": "HIMPHREY",
      "medical_info": None,
      "middle_name": None,
      "parent_email": None,
      "parent_name": "HUMPHREY ELORA",
      "parent_phone": "07037710911",
      "parent_relationship": "FATHER ",
      "previous_school": None,
      "remarks": None,
      "updated_at": "2026-03-07T08:55:23.945565"
    },
    {
      "address": None,
      "created_at": "2026-03-07T08:55:23.945539",
      "dob": "2015-06-09",
      "email": "michael.george chukudina@arndaleacademy.com",
      "first_name": "MICHAEL ",
      "full_name": "MICHAEL  GEORGE CHUKUDINA",
      "gender": "male",
      "id": "ba41144e-c592-4068-993a-7e82d4c934e8",
      "last_name": "GEORGE CHUKUDINA",
      "medical_info": None,
      "middle_name": None,
      "parent_email": None,
      "parent_name": "MONDAY SUNDAY ",
      "parent_phone": "07060452930",
      "parent_relationship": "FATHER ",
      "previous_school": None,
      "remarks": None,
      "updated_at": "2026-03-07T08:55:23.945565"
    },
    {
      "address": None,
      "created_at": "2026-03-07T08:55:23.945539",
      "dob": "2014-12-18",
      "email": "nathan.reng1@arndaleacademy.com",
      "first_name": "NATHAN ",
      "full_name": "NATHAN  RENG",
      "gender": "male",
      "id": "3a7e3011-f244-481e-ac3f-d9be9210873a",
      "last_name": "RENG ",
      "medical_info": None,
      "middle_name": None,
      "parent_email": None,
      "parent_name": "RENG GYANG",
      "parent_phone": "07082440359",
      "parent_relationship": "FATHER ",
      "previous_school": None,
      "remarks": None,
      "updated_at": "2026-03-07T08:55:23.945565"
    },
    {
      "address": None,
      "created_at": "2026-03-07T08:55:23.945539",
      "dob": "2014-04-04",
      "email": "imisioluwa.onobolu@arndaleacademy.com",
      "first_name": "IMISIOLUWA",
      "full_name": "IMISIOLUWA ONOBOLU",
      "gender": "female",
      "id": "0ba91d8d-cc8b-48e4-90c7-a8fb6aef5f35",
      "last_name": "ONOBOLU",
      "medical_info": None,
      "middle_name": None,
      "parent_email": None,
      "parent_name": "MR ONOBOLU ",
      "parent_phone": "08080894714",
      "parent_relationship": "FATHER ",
      "previous_school": None,
      "remarks": None,
      "updated_at": "2026-03-07T08:55:23.945565"
    },
    {
      "address": None,
      "created_at": "2026-03-07T08:55:23.945539",
      "dob": "2014-03-16",
      "email": "kaiyah.oprite janze@arndaleacademy.com",
      "first_name": "KAIYAH",
      "full_name": "KAIYAH OPRITE JANZE",
      "gender": "female",
      "id": "b3d78105-3b44-4b74-b5c2-7b43d1b67725",
      "last_name": "OPRITE JANZE",
      "medical_info": None,
      "middle_name": None,
      "parent_email": None,
      "parent_name": "MRS JANZE",
      "parent_phone": "080600 7079",
      "parent_relationship": None,
      "previous_school": None,
      "remarks": None,
      "updated_at": "2026-03-07T08:55:23.945565"
    },
    {
      "address": None,
      "created_at": "2026-03-07T08:55:23.945539",
      "dob": "2015-02-01",
      "email": "miracle.sylvester imoh@arndaleacademy.com",
      "first_name": "MIRACLE ",
      "full_name": "MIRACLE  SYLVESTER IMOH",
      "gender": "female",
      "id": "dd8bd44f-6d27-498f-a7f5-4e0668939873",
      "last_name": "SYLVESTER IMOH",
      "medical_info": None,
      "middle_name": None,
      "parent_email": None,
      "parent_name": "SYLVESTER IMOH ",
      "parent_phone": "0803668758",
      "parent_relationship": None,
      "previous_school": None,
      "remarks": None,
      "updated_at": "2026-03-07T08:55:23.945565"
    },
    {
      "address": None,
      "created_at": "2026-03-07T08:55:23.945539",
      "dob": "2013-01-18",
      "email": "muhammad.bashir@arndaleacademy.com",
      "first_name": "MUHAMMAD ",
      "full_name": "MUHAMMAD  BASHIR",
      "gender": "male",
      "id": "b5c06179-776c-43e6-acfd-b1a8556b46f9",
      "last_name": "BASHIR ",
      "medical_info": None,
      "middle_name": None,
      "parent_email": None,
      "parent_name": "BASHIR  'YAR ADUA",
      "parent_phone": "08036193694",
      "parent_relationship": "FATHER ",
      "previous_school": None,
      "remarks": None,
      "updated_at": "2026-03-07T08:55:23.945565"
    },
    {
      "address": None,
      "created_at": "2026-03-07T08:55:23.945539",
      "dob": "2013-01-13",
      "email": "joseph.essien1@arndaleacademy.com",
      "first_name": "JOSEPH ",
      "full_name": "JOSEPH  ESSIEN",
      "gender": "male",
      "id": "5a5829ae-c666-40d1-827d-e1d010194900",
      "last_name": "ESSIEN ",
      "medical_info": None,
      "middle_name": None,
      "parent_email": None,
      "parent_name": "MR ESSIEN ",
      "parent_phone": "09034812771",
      "parent_relationship": "FATHER ",
      "previous_school": None,
      "remarks": None,
      "updated_at": "2026-03-07T08:55:23.945565"
    }
  ],
  "success": True,
}


import re
from datetime import datetime, timezone
from flask import jsonify, request
from sqlalchemy import func, text
from sqlalchemy.exc import IntegrityError

ADMISSION_PREFIX = "AAHS"
ADMISSION_PAD = 5
DEFAULT_DOMAIN = "arndaleacademy.com"

# Put this in env in production (recommended)
IMPORT_TOKEN = "RUN_ONCE_2030"  # change this

def _parse_next_adm(latest: str | None) -> int:
    if not latest:
        return 1
    m = re.match(rf"^{ADMISSION_PREFIX}(\d+)$", latest)
    return int(m.group(1)) + 1 if m else 1

def _fmt_adm(n: int) -> str:
    return f"{ADMISSION_PREFIX}{n:0{ADMISSION_PAD}d}"

def _clean(s):
    if s is None:
        return None
    if isinstance(s, str):
        s = s.strip()
        return s if s else None
    return s


@app.route("/students/import-constant", methods=["GET"])
def import_students_from_constant():
    # ✅ token guard
    token = request.args.get("token")
    if token != IMPORT_TOKEN:
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    class_id = STUDENTS_INFO["class_id"]
    students = STUDENTS_INFO.get("students", [])

    classroom = db.session.get(ClassRoom, class_id)
    if not classroom:
        return jsonify({"success": False, "message": "Class not found", "class_id": class_id}), 404

    active_session = AcademicSession.query.filter_by(is_active=True).first()
    if not active_session:
        return jsonify({"success": False, "message": "No active academic session"}), 400

    created, skipped, errors = [], [], []

    try:
        # ✅ Postgres-safe lock for this import transaction (no FOR UPDATE on MAX)
        db.session.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": 737001})

        latest_adm = (
            db.session.query(func.max(Student.admission_number))
            .filter(Student.admission_number.like(f"{ADMISSION_PREFIX}%"))
            .scalar()
        )
        next_num = _parse_next_adm(latest_adm)

        for i, s in enumerate(students, start=1):
            try:
                first_name = _clean(s.get("first_name"))
                last_name = _clean(s.get("last_name"))
                middle_name = _clean(s.get("middle_name"))
                gender = _clean((s.get("gender") or "").lower())
                address = _clean(s.get("address"))

                parent_name = _clean(s.get("parent_name"))
                parent_phone = _clean(s.get("parent_phone"))
                parent_email = _clean(s.get("parent_email"))

                if not first_name or not last_name:
                    skipped.append({"index": i, "reason": "Missing first_name/last_name"})
                    continue

                # DOB
                dob = None
                dob_str = _clean(s.get("dob"))
                if dob_str:
                    try:
                        dob = datetime.strptime(dob_str, "%Y-%m-%d").date()
                    except ValueError:
                        dob = None

                # Generate admission number and ensure it's not taken
                # (extra safety if you ever re-run)
                while True:
                    admission_number = _fmt_adm(next_num)
                    next_num += 1
                    if not Student.query.filter_by(admission_number=admission_number).first():
                        break

                # Email
                email = _clean(s.get("email")) or f"{admission_number.lower()}@{DEFAULT_DOMAIN}"

                # If email exists already, skip
                if User.query.filter_by(email=email).first():
                    skipped.append({"index": i, "reason": "Email already exists", "email": email})
                    continue

                # If username exists already, skip (because username is unique)
                if User.query.filter_by(username=admission_number).first():
                    skipped.append({"index": i, "reason": "Username already exists", "username": admission_number})
                    continue

                user = User(
                    username=admission_number,
                    email=email,
                    role="student",
                    is_active=True,
                    created_at=datetime.now(timezone.utc),
                )
                user.set_password(admission_number)
                user.password_changed_at = datetime.now(timezone.utc)
                db.session.add(user)
                db.session.flush()

                student = Student(
                    user_id=user.id,
                    admission_number=admission_number,
                    first_name=first_name,
                    last_name=last_name,
                    middle_name=middle_name,
                    date_of_birth=dob,
                    gender=gender,
                    address=address,
                    parent_name=parent_name,
                    parent_phone=parent_phone,
                    parent_email=parent_email,
                    current_class_id=class_id,
                    enrollment_date=datetime.now(timezone.utc).date(),
                    academic_status="active",
                    is_active=True,
                )
                db.session.add(student)
                db.session.flush()

                created.append({
                    "index": i,
                    "student_id": student.id,
                    "user_id": user.id,
                    "admission_number": admission_number,
                    "name": f"{first_name} {last_name}",
                })

            except IntegrityError as ie:
                db.session.rollback()
                errors.append({"index": i, "error": "IntegrityError", "details": str(ie)})
                continue
            except Exception as e:
                db.session.rollback()
                errors.append({"index": i, "error": str(e)})
                continue

        db.session.add(AuditLog(
            user_id="a40a5fea-579a-4387-b0ab-59219ff1f8ee",
            action="IMPORT_STUDENTS_CONSTANT",
            table_name="students",
            new_values={
                "class_id": class_id,
                "created": len(created),
                "skipped": len(skipped),
                "errors": len(errors),
            },
            ip_address=request.remote_addr,
        ))

        db.session.commit()

        return jsonify({
            "success": True,
            "message": "Import complete. Delete/disable this route now.",
            "class_id": class_id,
            "created_count": len(created),
            "skipped_count": len(skipped),
            "error_count": len(errors),
            "created": created,
            "skipped": skipped,
            "errors": errors,
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": str(e)}), 500   

# See all endpoints
@app.route('/debug/routes')
def list_routes():
    import urllib.parse
    output = []
    for rule in app.url_map.iter_rules():
        methods = ','.join(rule.methods)
        line = urllib.parse.unquote(f"{rule.endpoint:50s} {methods:20s} {rule}")
        output.append(line)
    
    return "<br>".join(sorted(output))





# Import models for Flask-Migrate (do not run queries here)
from models import (
    User, Student, Teacher, Parent, ClassRoom, Subject,
    AcademicSession, AcademicTerm, SubjectAssignment, Assessment,
    StudentAssessment, QuestionBank, Exam, ExamQuestion, ExamSession,
    ExamResponse, StudentPromotion, Attendance, DomainEvaluation,
    TeacherComment, FormTeacherComment, PrincipalRemark, ReportCard,
    ParentNotification, SystemConfiguration, AuditLog, LoginAttempt,
    SecurityLog, GradeScale, SubjectCategory
)


if __name__ == '__main__':
    app.run(
        host='0.0.0.0',
        debug=app.config.get('DEBUG', False),
        port=int(app.config.get('PORT', 5000))
    )

