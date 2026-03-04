import os
import logging
import click
from logging.handlers import RotatingFileHandler
from flask import Flask, request, render_template, redirect, url_for, flash
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
    
    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    limiter.init_app(app)
    
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

# In app.py, add this route to see all endpoints
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

