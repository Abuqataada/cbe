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
    
    # Session
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)
    SESSION_COOKIE_NAME = 'arndale_session'
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SECURE = False  # Will be overridden in production if HTTPS
    SESSION_COOKIE_SAMESITE = 'Lax'
    REMEMBER_COOKIE_SECURE = False
    
    # File uploads - Default to local (will be overridden in production)
    STORAGE_TYPE = 'local'  # 'local' or 'cloudinary'
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'svg', 'pdf', 'doc', 'docx'}
    UPLOAD_FOLDER = str(BASE_DIR / 'uploads')
    REPORT_FOLDER = str(BASE_DIR / 'reports')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
    
    # Cloudinary configuration (will be used when STORAGE_TYPE='cloudinary')
    CLOUDINARY_CLOUD_NAME = os.environ.get('CLOUDINARY_CLOUD_NAME')
    CLOUDINARY_API_KEY = os.environ.get('CLOUDINARY_API_KEY')
    CLOUDINARY_API_SECRET = os.environ.get('CLOUDINARY_API_SECRET')
    CLOUDINARY_FOLDER = 'arndale-cbt'  # Base folder in Cloudinary
    
    # Rate limiting
    RATELIMIT_ENABLED = True
    RATELIMIT_STORAGE_URI = os.environ.get('RATELIMIT_STORAGE_URI', "memory://")
    RATELIMIT_STRATEGY = 'fixed-window'
    RATELIMIT_DEFAULT = ["1000 per day", "200 per hour", "50 per minute"]
    RATELIMIT_HEADERS_ENABLED = True
    
    # Application settings
    DEBUG = False
    TESTING = False
    PORT = int(os.environ.get('PORT', 5000))
    HOST = '0.0.0.0'
    
    # Admin credentials
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
        'require_special': False,
        'expiry_days': 90,
    }
    
    # Exam settings
    EXAM_DEFAULT_DURATION = 60
    EXAM_MAX_DURATION = 180
    EXAM_ALLOW_LATE_SUBMISSION = False
    EXAM_RANDOMIZE_QUESTIONS = True
    EXAM_SHOW_RESULTS_IMMEDIATELY = False
    
    # Network settings
    ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', '*').split(',')
    SERVER_NAME = os.environ.get('SERVER_NAME')
    
    # Logging
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    LOG_FILE = str(BASE_DIR / 'logs' / 'server.log')
    LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    # Backup settings
    BACKUP_ENABLED = True
    BACKUP_FOLDER = str(BASE_DIR / 'backups')
    BACKUP_SCHEDULE = 'daily'
    KEEP_BACKUPS = 7
    
    # Performance
    JSONIFY_PRETTYPRINT_REGULAR = False
    TEMPLATES_AUTO_RELOAD = False
    SEND_FILE_MAX_AGE_DEFAULT = 31536000


class DevelopmentConfig(Config):
    """Development configuration - local file storage"""
    DEBUG = True
    TEMPLATES_AUTO_RELOAD = True
    SQLALCHEMY_ECHO = False
    
    # Use local storage in development
    STORAGE_TYPE = 'local'
    SESSION_COOKIE_SECURE = False
    REMEMBER_COOKIE_SECURE = False
    
    # Development rate limits (higher)
    RATELIMIT_DEFAULT = ["5000 per day", "1000 per hour"]


class ProductionConfig(Config):
    """Production configuration for Vercel - cloud storage"""
    DEBUG = False
    TESTING = False
    
    # Use Cloudinary in production
    STORAGE_TYPE = os.environ.get('STORAGE_TYPE', 'cloudinary')
    
    # Production security (HTTPS)
    SESSION_COOKIE_SECURE = True
    REMEMBER_COOKIE_SECURE = True
    SESSION_COOKIE_SAMESITE = 'Strict'
    
    # Database
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    
    # Production rate limits (stricter)
    RATELIMIT_DEFAULT = ["500 per day", "100 per hour", "20 per minute"]
    
    # Production logging
    LOG_LEVEL = 'WARNING'
    
    # Production backup settings
    BACKUP_ENABLED = True
    KEEP_BACKUPS = 30


class VercelConfig(ProductionConfig):
    """Vercel-specific production configuration"""
    
    # Force Cloudinary for Vercel
    STORAGE_TYPE = 'cloudinary'
    
    # Vercel environment settings
    SERVER_NAME = os.environ.get('VERCEL_URL')
    PREFERRED_URL_SCHEME = 'https'
    
    # Vercel doesn't have persistent storage for uploads
    UPLOAD_FOLDER = '/tmp/uploads'  # Temporary folder, files will be deleted
    REPORT_FOLDER = '/tmp/reports'
    
    # Rate limiting with Redis (if available)
    REDIS_URL = os.environ.get('REDIS_URL')
    if REDIS_URL:
        RATELIMIT_STORAGE_URI = REDIS_URL


class TestingConfig(Config):
    """Testing configuration"""
    TESTING = True
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    STORAGE_TYPE = 'local'
    WTF_CSRF_ENABLED = False
    SESSION_COOKIE_SECURE = False


# Configuration dictionary
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'vercel': VercelConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}

def init_directories():
    """Create necessary directories (only for local storage)"""
    storage_type = os.environ.get('STORAGE_TYPE', 'local')
    
    if storage_type == 'local':
        directories = [
            BASE_DIR / 'uploads',
            BASE_DIR / 'reports',
            BASE_DIR / 'database',
            BASE_DIR / 'logs',
            BASE_DIR / 'backups',
            BASE_DIR / 'static' / 'exports',
            BASE_DIR / 'static' / 'uploads' / 'questions',
            BASE_DIR / 'static' / 'uploads' / 'options',
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
        
        print(f"Local directories created in: {BASE_DIR}")
    else:
        print(f"Using cloud storage ({storage_type}), skipping local directory creation")

# Initialize directories when config is imported
init_directories()