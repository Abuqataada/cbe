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
    "class_id": "fdd21d62-85a9-424e-a2e7-33552be11d9c",
    "students": [
    {
      "address": None,
      "created_at": "2026-03-02T08:51:13.649415",
      "dob": "2009-08-12",
      "email": "bernice.abba@arndaleacademy.com",
      "first_name": "BERNICE",
      "full_name": "BERNICE ABBA",
      "gender": "female",
      "id": "393e2c40-c5e9-44c8-b3c3-8e595082c58a",
      "last_name": "ABBA",
      "medical_info": None,
      "middle_name": None,
      "parent_email": None,
      "parent_name": "MR/MRS ABBA",
      "parent_phone": "09056999083",
      "parent_relationship": None,
      "previous_school": None,
      "remarks": None,
      "updated_at": "2026-03-02T08:51:13.649444"
    },
    {
      "address": None,
      "created_at": "2026-03-02T08:51:13.649415",
      "dob": "2009-06-11",
      "email": "maryam.abba@arndaleacademy.com",
      "first_name": "MARYAM",
      "full_name": "MARYAM ABBA",
      "gender": "female",
      "id": "108d07e3-121c-4ce2-a7e0-fd60a58b1386",
      "last_name": "ABBA",
      "medical_info": None,
      "middle_name": "IBRAHIM",
      "parent_email": None,
      "parent_name": "MR/MRS ABBA",
      "parent_phone": "08038448914",
      "parent_relationship": None,
      "previous_school": None,
      "remarks": None,
      "updated_at": "2026-03-02T08:51:13.649444"
    },
    {
      "address": None,
      "created_at": "2026-03-02T08:51:13.649415",
      "dob": "2010-09-05",
      "email": "yusuf.abner@arndaleacademy.com",
      "first_name": "YUSUF",
      "full_name": "YUSUF ABNER",
      "gender": "male",
      "id": "ab61e6b2-a5c2-410e-ad45-621d84cd3764",
      "last_name": "ABNER",
      "medical_info": None,
      "middle_name": None,
      "parent_email": None,
      "parent_name": "MR/MRS ABNER",
      "parent_phone": "08167459508",
      "parent_relationship": None,
      "previous_school": None,
      "remarks": None,
      "updated_at": "2026-03-02T08:51:13.649444"
    },
    {
      "address": None,
      "created_at": "2026-03-02T08:51:13.649415",
      "dob": "2009-09-29",
      "email": "somtochukwu.akuneaziri@arndaleacademy.com",
      "first_name": "SOMTOCHUKWU",
      "full_name": "SOMTOCHUKWU AKUNEAZIRI",
      "gender": "female",
      "id": "ea77e243-c0c3-4a26-85ca-6941c0ef8cb9",
      "last_name": "AKUNEAZIRI",
      "medical_info": None,
      "middle_name": None,
      "parent_email": None,
      "parent_name": "MR/MRS AKUNEAZIRI",
      "parent_phone": "08032054934",
      "parent_relationship": None,
      "previous_school": None,
      "remarks": None,
      "updated_at": "2026-03-02T08:51:13.649444"
    },
    {
      "address": None,
      "created_at": "2026-03-02T08:51:13.649415",
      "dob": "2008-07-10",
      "email": "alaric.kollomi@arndaleacademy.com",
      "first_name": "ALARIC",
      "full_name": "ALARIC KOLLOMI",
      "gender": "male",
      "id": "fbb6927c-78ea-48a9-9d74-cc1288497011",
      "last_name": "KOLLOMI",
      "medical_info": None,
      "middle_name": None,
      "parent_email": None,
      "parent_name": "MR/MRS KOLLOMI",
      "parent_phone": "08120065261",
      "parent_relationship": None,
      "previous_school": None,
      "remarks": None,
      "updated_at": "2026-03-02T08:51:13.649444"
    },
    {
      "address": None,
      "created_at": "2026-03-02T08:51:13.649415",
      "dob": "2008-10-14",
      "email": "farouk.ali@arndaleacademy.com",
      "first_name": "FAROUK",
      "full_name": "FAROUK ALI",
      "gender": "male",
      "id": "95f304b0-2dcc-4e3f-9ecc-7028c8469516",
      "last_name": "ALI",
      "medical_info": None,
      "middle_name": "UMAR",
      "parent_email": None,
      "parent_name": "DR/MRS UMAR",
      "parent_phone": "07036162222",
      "parent_relationship": None,
      "previous_school": None,
      "remarks": None,
      "updated_at": "2026-03-02T08:51:13.649444"
    },
    {
      "address": None,
      "created_at": "2026-03-02T08:51:13.649415",
      "dob": "2009-03-03",
      "email": "maryam.aminu@arndaleacademy.com",
      "first_name": "MARYAM",
      "full_name": "MARYAM AMINU",
      "gender": "female",
      "id": "5fc9a519-8e70-45a6-8851-a8db91487843",
      "last_name": "AMINU",
      "medical_info": None,
      "middle_name": "MARYAM",
      "parent_email": None,
      "parent_name": "MR/MRS JAMILA MUHA'D",
      "parent_phone": "08066795028",
      "parent_relationship": None,
      "previous_school": None,
      "remarks": None,
      "updated_at": "2026-03-02T08:51:13.649444"
    },
    {
      "address": None,
      "created_at": "2026-03-02T08:51:13.649415",
      "dob": "2009-05-05",
      "email": "muhammed.bilya@arndaleacademy.com",
      "first_name": "MUHAMMED",
      "full_name": "MUHAMMED BILYA",
      "gender": "male",
      "id": "7cfa1915-7400-4c84-83f7-9185f4f4dcf8",
      "last_name": "BILYA",
      "medical_info": None,
      "middle_name": "AUWAL",
      "parent_email": None,
      "parent_name": "MR/MRS BILYA",
      "parent_phone": "08067501111",
      "parent_relationship": None,
      "previous_school": None,
      "remarks": None,
      "updated_at": "2026-03-02T08:51:13.649444"
    },
    {
      "address": None,
      "created_at": "2026-03-02T08:51:13.649415",
      "dob": "2011-04-11",
      "email": "gabriella.ezeadikwa@arndaleacademy.com",
      "first_name": "GABRIELLA",
      "full_name": "GABRIELLA EZEADIKWA",
      "gender": "female",
      "id": "94a6cca2-ac9e-4605-8a9e-a6c349a4af75",
      "last_name": "EZEADIKWA",
      "medical_info": None,
      "middle_name": None,
      "parent_email": None,
      "parent_name": "DR/MRS EZEADIKWA",
      "parent_phone": "08039377729",
      "parent_relationship": None,
      "previous_school": None,
      "remarks": None,
      "updated_at": "2026-03-02T08:51:13.649444"
    },
    {
      "address": None,
      "created_at": "2026-03-02T08:51:13.649415",
      "dob": "2010-03-27",
      "email": "fatimah-zeenah.abdulmalik@arndaleacademy.com",
      "first_name": "FATIMAH-ZEENAH",
      "full_name": "FATIMAH-ZEENAH ABDULMALIK",
      "gender": "female",
      "id": "31640b37-e385-47cd-a6b2-506946928203",
      "last_name": "ABDULMALIK",
      "medical_info": None,
      "middle_name": None,
      "parent_email": None,
      "parent_name": "MR/MRS ABDULMALIK",
      "parent_phone": "07035744711",
      "parent_relationship": None,
      "previous_school": None,
      "remarks": None,
      "updated_at": "2026-03-02T08:51:13.649444"
    },
    {
      "address": None,
      "created_at": "2026-03-02T08:51:13.649415",
      "dob": "2010-04-13",
      "email": "ifiemi.tekenah@arndaleacademy.com",
      "first_name": "IFIEMI",
      "full_name": "IFIEMI TEKENAH",
      "gender": "male",
      "id": "eaa729bb-ee3d-4e56-b6b5-af9585c53e15",
      "last_name": "TEKENAH",
      "medical_info": None,
      "middle_name": "KURUMIOYE",
      "parent_email": None,
      "parent_name": "MR/MRS KURUMIOYE",
      "parent_phone": "08165112033",
      "parent_relationship": None,
      "previous_school": None,
      "remarks": None,
      "updated_at": "2026-03-02T08:51:13.649444"
    },
    {
      "address": None,
      "created_at": "2026-03-02T08:51:13.649415",
      "dob": "2009-03-26",
      "email": "abdul-mannan.jimoh@arndaleacademy.com",
      "first_name": "ABDUL-MANNAN",
      "full_name": "ABDUL-MANNAN JIMOH",
      "gender": "male",
      "id": "503d0f36-e5d1-4313-8e90-b1529a210062",
      "last_name": "JIMOH",
      "medical_info": None,
      "middle_name": None,
      "parent_email": None,
      "parent_name": "MR/MRS SIKIRU JIMOH",
      "parent_phone": "08030714489",
      "parent_relationship": None,
      "previous_school": None,
      "remarks": None,
      "updated_at": "2026-03-02T08:51:13.649444"
    },
    {
      "address": None,
      "created_at": "2026-03-02T08:51:13.649415",
      "dob": "2009-10-22",
      "email": "shalom.kassim@arndaleacademy.com",
      "first_name": "SHALOM",
      "full_name": "SHALOM KASSIM",
      "gender": "female",
      "id": "edd31905-cf24-488b-aa69-1e7066f3085b",
      "last_name": "KASSIM",
      "medical_info": None,
      "middle_name": "OLUWATUMILARA",
      "parent_email": None,
      "parent_name": "MR/MRS AHMED",
      "parent_phone": "080364368819",
      "parent_relationship": None,
      "previous_school": None,
      "remarks": None,
      "updated_at": "2026-03-02T08:51:13.649444"
    },
    {
      "address": None,
      "created_at": "2026-03-02T08:51:13.649415",
      "dob": "2010-06-02",
      "email": "stephanie.mbaegbu@arndaleacademy.com",
      "first_name": "STEPHANIE",
      "full_name": "STEPHANIE MBAEGBU",
      "gender": "female",
      "id": "a761e1d1-2d6e-4f1a-8476-519d5620d3f2",
      "last_name": "MBAEGBU",
      "medical_info": None,
      "middle_name": None,
      "parent_email": None,
      "parent_name": "MR/MRS EZIRIM",
      "parent_phone": "08037884524",
      "parent_relationship": None,
      "previous_school": None,
      "remarks": None,
      "updated_at": "2026-03-02T08:51:13.649444"
    },
    {
      "address": None,
      "created_at": "2026-03-02T08:51:13.649415",
      "dob": "2009-06-30",
      "email": "miracle.obenwa@arndaleacademy.com",
      "first_name": "MIRACLE",
      "full_name": "MIRACLE OBENWA",
      "gender": "female",
      "id": "5a4851f5-a1a2-4cf9-b686-0d83bac5fe83",
      "last_name": "OBENWA",
      "medical_info": None,
      "middle_name": "S",
      "parent_email": None,
      "parent_name": "DR LILIAN HELEN",
      "parent_phone": "08035631071",
      "parent_relationship": None,
      "previous_school": None,
      "remarks": None,
      "updated_at": "2026-03-02T08:51:13.649444"
    },
    {
      "address": None,
      "created_at": "2026-03-02T08:51:13.649415",
      "dob": "2009-06-23",
      "email": "elvis.samuel@arndaleacademy.com",
      "first_name": "ELVIS",
      "full_name": "ELVIS SAMUEL",
      "gender": "male",
      "id": "ed2c4eee-3468-4853-b0d9-a7232741610e",
      "last_name": "SAMUEL",
      "medical_info": None,
      "middle_name": "N",
      "parent_email": None,
      "parent_name": "MR/MRS SAMUEL",
      "parent_phone": "08065335568",
      "parent_relationship": None,
      "previous_school": None,
      "remarks": None,
      "updated_at": "2026-03-02T08:51:13.649444"
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
IMPORT_TOKEN = "RUN_ONCE_2029"  # change this

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

