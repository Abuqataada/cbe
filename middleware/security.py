# app/middleware/security.py
from flask import request, session, abort, current_app
from functools import wraps
import logging
from datetime import datetime, timezone, timedelta
from utils.security import SecurityManager

logger = logging.getLogger(__name__)

def generate_2fa_code():
    """Generate 2FA secret (alias for SecurityManager method)"""
    return SecurityManager.generate_2fa_secret()

def verify_2fa_code(secret, code):
    """Verify 2FA code (alias for SecurityManager method)"""
    return SecurityManager.verify_2fa_code(secret, code)

def check_password_strength(password):
    """Check password strength (alias for SecurityManager method)"""
    return SecurityManager.check_password_strength(password)

def admin_required(f):
    """Decorator to require admin role"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        from ..models import User
        from flask_login import current_user
        
        if not current_user.is_authenticated:
            logger.warning(f"Unauthenticated access attempt to {request.path}")
            abort(401)
        
        if current_user.role != 'admin':
            logger.warning(f"Non-admin access attempt by {current_user.username} to {request.path}")
            abort(403)
        
        return f(*args, **kwargs)
    return decorated_function

def teacher_required(f):
    """Decorator to require teacher role"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        from ..models import User
        from flask_login import current_user
        
        if not current_user.is_authenticated:
            abort(401)
        
        if current_user.role not in ['teacher', 'admin']:
            abort(403)
        
        return f(*args, **kwargs)
    return decorated_function

def student_required(f):
    """Decorator to require student role"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        from ..models import User
        from flask_login import current_user
        
        if not current_user.is_authenticated:
            abort(401)
        
        if current_user.role not in ['student', 'admin']:
            abort(403)
        
        return f(*args, **kwargs)
    return decorated_function

def rate_limit_by_ip(limit="5 per minute"):
    """Rate limiting decorator by IP address"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            from flask_limiter.util import get_remote_address
            
            ip = get_remote_address()
            key = f"rate_limit:{request.endpoint}:{ip}"
            
            # Simple in-memory rate limiting (use Redis in production)
            if not hasattr(current_app, 'rate_limit_store'):
                current_app.rate_limit_store = {}
            
            now = datetime.now(timezone.utc)
            window_start = now - timedelta(minutes=1)
            
            # Clean old entries
            current_app.rate_limit_store = {
                k: v for k, v in current_app.rate_limit_store.items() 
                if v['timestamp'] > window_start
            }
            
            # Check rate
            if key in current_app.rate_limit_store:
                current_app.rate_limit_store[key]['count'] += 1
                if current_app.rate_limit_store[key]['count'] > 5:
                    logger.warning(f"Rate limit exceeded for IP {ip} on {request.path}")
                    abort(429)
            else:
                current_app.rate_limit_store[key] = {
                    'count': 1,
                    'timestamp': now
                }
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def validate_csrf_token():
    """Validate CSRF token for POST requests"""
    if request.method in ['POST', 'PUT', 'DELETE', 'PATCH']:
        token = request.form.get('csrf_token') or request.headers.get('X-CSRF-Token')
        
        if not token or token != session.get('csrf_token'):
            logger.warning(f"CSRF validation failed for {request.path}")
            abort(403)
    
    return True

def sanitize_filename(filename):
    """Sanitize filename to prevent path traversal"""
    import os
    from werkzeug.utils import secure_filename
    
    # Use werkzeug's secure_filename
    safe_name = secure_filename(filename)
    
    # Additional checks
    if '..' in safe_name or safe_name.startswith('/') or safe_name.startswith('\\'):
        return None
    
    return safe_name

def check_file_upload(file):
    """Check uploaded file for security"""
    if not file:
        return False, "No file provided"
    
    # Check file size
    max_size = current_app.config.get('MAX_CONTENT_LENGTH', 16 * 1024 * 1024)
    file.seek(0, 2)  # Seek to end
    size = file.tell()
    file.seek(0)  # Reset pointer
    
    if size > max_size:
        return False, f"File too large. Maximum size is {max_size // (1024*1024)}MB"
    
    # Check file extension
    allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'doc', 'docx', 'xls', 'xlsx'}
    filename = file.filename.lower()
    
    if '.' not in filename:
        return False, "No file extension"
    
    extension = filename.rsplit('.', 1)[1]
    if extension not in allowed_extensions:
        return False, f"File type .{extension} not allowed"
    
    # Check file signature
    file_content = file.read(512)  # Read first 512 bytes
    file.seek(0)
    
    is_valid, mime_type = SecurityManager.check_file_signature(
        file_content,
        allowed_types={'image/jpeg', 'image/png', 'application/pdf'}
    )
    
    if not is_valid:
        return False, "Invalid file signature"
    
    return True, "File validated"

def log_security_event(event_type, user_id=None, details=None):
    """Log security events"""
    from ..models import SecurityLog
    
    try:
        security_log = SecurityLog(
            event_type=event_type,
            user_id=user_id,
            ip_address=request.remote_addr,
            user_agent=request.user_agent.string,
            details=details or {}
        )
        
        from extensions import db
        db.session.add(security_log)
        db.session.commit()
        
        logger.info(f"Security event logged: {event_type} for user {user_id}")
    except Exception as e:
        logger.error(f"Failed to log security event: {e}")

def require_2fa(f):
    """Decorator to require 2FA for sensitive operations"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        from flask_login import current_user
        
        if not current_user.is_authenticated:
            abort(401)
        
        # Check if 2FA is required but not verified in this session
        if current_user.two_factor_enabled and not session.get('2fa_verified', False):
            # Store intended destination
            session['next'] = request.url
            abort(403, description="2FA verification required")
        
        return f(*args, **kwargs)
    return decorated_function