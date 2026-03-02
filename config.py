import os
from datetime import timedelta
from pathlib import Path

# Get base directory
BASE_DIR = Path(__file__).parent.absolute()

class Config:
    """Base configuration"""
    # Security
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'arndale-cbt-2024-lan-secret-key-change-in-production'
    
    # Database
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or f'sqlite:///{BASE_DIR}/database/arndale_cbt.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_recycle': 299,
        'pool_pre_ping': True,
    }
    
    # Session (LAN specific - no HTTPS)
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)
    SESSION_COOKIE_NAME = 'arndale_session'
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SECURE = False  # No HTTPS in LAN
    SESSION_COOKIE_SAMESITE = 'Lax'
    REMEMBER_COOKIE_SECURE = False  # No HTTPS in LAN
    
    # File uploads
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'svg'}
    UPLOAD_FOLDER = str(BASE_DIR / 'uploads')
    REPORT_FOLDER = str(BASE_DIR / 'reports')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
    
    # Rate limiting (in-memory for LAN)
    RATELIMIT_ENABLED = True
    RATELIMIT_STORAGE_URI = "memory://" # Simple for LAN
    RATELIMIT_STRATEGY = 'fixed-window'
    RATELIMIT_DEFAULT = ["1000 per day", "200 per hour", "50 per minute"]
    RATELIMIT_HEADERS_ENABLED = True
    
    # Application settings
    DEBUG = False
    TESTING = False
    PORT = 5000
    HOST = '0.0.0.0'  # Listen on all interfaces
    
    # Admin credentials (CHANGE THESE IN PRODUCTION!)
    ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME') or 'admin'
    ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD') or 'admin123'
    ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL') or 'admin@arndaleacademy.edu'

    FINANCE_ADMIN_USERNAME = os.environ.get('FINANCE_ADMIN_USERNAME') or 'finance_admin'
    FINANCE_ADMIN_PASSWORD = os.environ.get('FINANCE_ADMIN_PASSWORD') or 'finance123'
    FINANCE_ADMIN_EMAIL = os.environ.get('FINANCE_ADMIN_EMAIL') or 'finance_admin@arndaleacademy.edu'
    
    # Grading & Assessment
    ASSESSMENT_TYPES = ['Test 1', 'Test 2', 'Assignment', 'Practical', 'Project Work', 'Mid-Term Test']
    DOMAIN_TYPES = ['Affective', 'Psychomotor', 'Behavioural & Social']
    DEFAULT_GRADING_SYSTEM = {
        'A': (85, 100),
        'B': (60, 84),
        'C': (50, 59),
        'D': (45, 49),
        'E': (40, 44),
        'F': (0, 39)
    }
    
    # Security settings
    PASSWORD_POLICY = {
        'min_length': 8,
        'require_uppercase': True,
        'require_lowercase': True,
        'require_numbers': True,
        'require_special': False,  # Keep simple for students
        'expiry_days': 90,  # Password expires after 90 days
    }
    
    # Exam settings
    EXAM_DEFAULT_DURATION = 60  # minutes
    EXAM_MAX_DURATION = 180  # 3 hours maximum
    EXAM_ALLOW_LATE_SUBMISSION = False
    EXAM_RANDOMIZE_QUESTIONS = True
    EXAM_SHOW_RESULTS_IMMEDIATELY = False
    
    # Network settings (LAN specific)
    ALLOWED_HOSTS = ['*']  # Accept connections from any IP in LAN
    SERVER_NAME = None  # Don't set for LAN
    
    # Logging
    LOG_LEVEL = 'INFO'
    LOG_FILE = str(BASE_DIR / 'logs' / 'server.log')
    LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    # Backup settings
    BACKUP_ENABLED = True
    BACKUP_FOLDER = str(BASE_DIR / 'backups')
    BACKUP_SCHEDULE = 'daily'  # daily, weekly, monthly
    KEEP_BACKUPS = 7  # Keep last 7 backups
    
    # Performance
    JSONIFY_PRETTYPRINT_REGULAR = False  # Disable for production
    TEMPLATES_AUTO_RELOAD = False  # Disable for production
    SEND_FILE_MAX_AGE_DEFAULT = 31536000  # 1 year cache for static files

class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    TEMPLATES_AUTO_RELOAD = True
    SQLALCHEMY_ECHO = False  # Set to True for SQL debugging
    
    # Development security (relaxed)
    SESSION_COOKIE_SECURE = False
    REMEMBER_COOKIE_SECURE = False
    
    # Development rate limits (higher)
    RATELIMIT_DEFAULT = ["5000 per day", "1000 per hour"]

class ProductionConfig(Config):
    """Production configuration for LAN deployment"""
    DEBUG = False
    TESTING = False
    
    # LAN-specific settings (NO HTTPS)
    PREFERRED_URL_SCHEME = 'http'  # Force HTTP scheme
    SESSION_COOKIE_SECURE = False  # Allow cookies over HTTP
    REMEMBER_COOKIE_SECURE = False
    
    # Disable HTTPS redirects
    FORCE_HTTPS = False
    
    # Database
    SQLALCHEMY_DATABASE_URI = 'sqlite:///database/arndale_cbt.db'
    
    # Network settings
    SERVER_NAME = None  # Don't set for LAN
    
    # Security (relaxed for LAN)
    SECURITY_SSL_REDIRECT = False
    
    """Production configuration for LAN deployment"""
    DEBUG = False
    TESTING = False
    
    # Production security (strict)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Strict'  # Changed to Strict for production
    
    # Production database (SQLite is fine for LAN, but PostgreSQL is better)
    SQLALCHEMY_DATABASE_URI = f'sqlite:///{BASE_DIR}/database/arndale_cbt_prod.db'
    
    # Production rate limits (stricter)
    RATELIMIT_DEFAULT = ["500 per day", "100 per hour", "20 per minute"]
    
    # Production logging
    LOG_LEVEL = 'WARNING'  # Only warnings and errors
    
    # Production backup settings
    BACKUP_ENABLED = True
    KEEP_BACKUPS = 30  # Keep 30 days of backups

class TestingConfig(Config):
    """Testing configuration"""
    TESTING = True
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False
    SESSION_COOKIE_SECURE = False

# Configuration dictionary
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}

def init_directories():
    """Create necessary directories"""
    directories = [
        BASE_DIR / 'uploads',
        BASE_DIR / 'reports',
        BASE_DIR / 'database',
        BASE_DIR / 'logs',
        BASE_DIR / 'backups',
        BASE_DIR / 'static' / 'exports',
    ]
    
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)
    
    print(f"Directories created in: {BASE_DIR}")

# Initialize directories when config is imported
init_directories()