# app/utils/security.py
import hashlib
import hmac
import base64
import secrets
import string
import re
import os
from datetime import datetime, timedelta
import pyotp
import qrcode
from io import BytesIO
import logging
from flask import current_app, request, redirect
from functools import wraps
import jwt

logger = logging.getLogger(__name__)

class SecurityManager:
    """Centralized security management"""
    
    @staticmethod
    def generate_2fa_secret():
        """Generate a new 2FA secret"""
        return pyotp.random_base32()
    
    @staticmethod
    def generate_2fa_uri(secret, username, issuer="Arndale Academy"):
        """Generate 2FA URI for QR code"""
        return pyotp.totp.TOTP(secret).provisioning_uri(
            name=username,
            issuer_name=issuer
        )
    
    @staticmethod
    def verify_2fa_token(secret, token):
        """Verify 2FA token"""
        totp = pyotp.TOTP(secret)
        return totp.verify(token, valid_window=1)  # Allow 30-second drift
    
    @staticmethod
    def generate_qr_code(uri):
        """Generate QR code from URI"""
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(uri)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        img_byte_arr = BytesIO()
        img.save(img_byte_arr, format='PNG')
        img_byte_arr.seek(0)
        
        return img_byte_arr
    
    @staticmethod
    def check_password_strength(password):
        """Check password strength"""
        result = {
            'is_strong': True,
            'score': 0,
            'message': '',
            'requirements': {}
        }
        
        # Length check
        min_length = current_app.config.get('PASSWORD_MIN_LENGTH', 8)
        result['requirements']['min_length'] = len(password) >= min_length
        
        # Upper case check
        result['requirements']['has_upper'] = bool(re.search(r'[A-Z]', password))
        
        # Lower case check
        result['requirements']['has_lower'] = bool(re.search(r'[a-z]', password))
        
        # Digit check
        result['requirements']['has_digit'] = bool(re.search(r'\d', password))
        
        # Special character check
        special_chars = r'[!@#$%^&*()\-_=+\[\]{}|;:,.<>?]'
        result['requirements']['has_special'] = bool(re.search(special_chars, password))
        
        # Common password check
        common_passwords = [
            'password', '123456', 'qwerty', 'admin', 'welcome',
            'password123', 'abc123', 'letmein', 'monkey', 'sunshine'
        ]
        result['requirements']['not_common'] = password.lower() not in common_passwords
        
        # Calculate score
        score = sum(result['requirements'].values())
        result['score'] = score
        
        # Determine strength
        if score >= 5:
            result['message'] = 'Strong password'
        elif score >= 4:
            result['message'] = 'Moderate password'
            result['is_strong'] = False
        else:
            result['message'] = 'Weak password'
            result['is_strong'] = False
        
        return result
    
    @staticmethod
    def hash_sensitive_data(data, salt=None):
        """Hash sensitive data"""
        if salt is None:
            salt = secrets.token_bytes(16)
        
        key = current_app.config.get('SECRET_KEY').encode()
        h = hmac.new(key, data.encode() + salt, hashlib.sha256)
        return base64.b64encode(h.digest() + salt).decode()
    
    @staticmethod
    def verify_hashed_data(data, hashed):
        """Verify hashed data"""
        try:
            decoded = base64.b64decode(hashed)
            salt = decoded[-16:]
            key = current_app.config.get('SECRET_KEY').encode()
            h = hmac.new(key, data.encode() + salt, hashlib.sha256)
            return hmac.compare_digest(h.digest(), decoded[:-16])
        except Exception:
            return False
    
    @staticmethod
    def generate_secure_token(length=32):
        """Generate cryptographically secure token"""
        return secrets.token_urlsafe(length)
    
    @staticmethod
    def sanitize_input(input_string):
        """Sanitize user input to prevent XSS"""
        if not input_string:
            return ''
        
        # Remove script tags and events
        sanitized = re.sub(r'<script.*?>.*?</script>', '', input_string, flags=re.IGNORECASE)
        sanitized = re.sub(r'on\w+=".*?"', '', sanitized, flags=re.IGNORECASE)
        sanitized = re.sub(r'on\w+=\'.*?\'', '', sanitized, flags=re.IGNORECASE)
        
        # Escape HTML special characters
        html_escape_table = {
            "&": "&amp;",
            '"': "&quot;",
            "'": "&#39;",
            ">": "&gt;",
            "<": "&lt;",
        }
        
        for char, escape in html_escape_table.items():
            sanitized = sanitized.replace(char, escape)
        
        return sanitized
    
    @staticmethod
    def validate_email(email):
        """Validate email format"""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))
    
    @staticmethod
    def validate_phone(phone):
        """Validate phone number format (Nigeria)"""
        pattern = r'^(\+234|0)[789][01]\d{8}$'
        return bool(re.match(pattern, phone))
    
    @staticmethod
    def generate_csrf_token():
        """Generate CSRF token"""
        return secrets.token_hex(32)
    
    @staticmethod
    def verify_csrf_token(token, session_token):
        """Verify CSRF token"""
        return hmac.compare_digest(token, session_token)
    
    @staticmethod
    def rate_limit_key():
        """Generate rate limiting key"""
        return f"{request.remote_addr}"

def require_https(f):
    """Decorator to require HTTPS"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not request.is_secure and current_app.env != 'development':
            if request.url.startswith('http://'):
                https_url = request.url.replace('http://', 'https://', 1)
                return redirect(https_url, code=301)
        return f(*args, **kwargs)
    return decorated_function

def validate_jwt_token(token):
    """Validate JWT token"""
    try:
        secret_key = current_app.config['SECRET_KEY']
        payload = jwt.decode(token, secret_key, algorithms=['HS256'])
        return payload
    except jwt.ExpiredSignatureError:
        logger.warning("JWT token expired")
        return None
    except jwt.InvalidTokenError:
        logger.warning("Invalid JWT token")
        return None

def generate_jwt_token(payload, expires_in=3600):
    """Generate JWT token"""
    secret_key = current_app.config['SECRET_KEY']
    payload['exp'] = datetime.utcnow() + timedelta(seconds=expires_in)
    payload['iat'] = datetime.utcnow()
    return jwt.encode(payload, secret_key, algorithm='HS256')

def sanitize_filename(filename):
    """Sanitize filename to prevent path traversal"""
    # Remove directory components
    filename = os.path.basename(filename)
    
    # Remove null bytes
    filename = filename.replace('\x00', '')
    
    # Limit length
    if len(filename) > 255:
        name, ext = os.path.splitext(filename)
        filename = name[:255 - len(ext)] + ext
    
    # Allow only safe characters
    safe_chars = r'[^A-Za-z0-9_.-]'
    filename = re.sub(safe_chars, '_', filename)
    
    return filename

def check_content_type(request, allowed_types=['application/json', 'multipart/form-data', 'application/x-www-form-urlencoded']):
    """Check content type of request"""
    content_type = request.headers.get('Content-Type', '').split(';')[0]
    return content_type in allowed_types

def generate_secure_filename(original_filename):
    """Generate secure random filename"""
    ext = original_filename.rsplit('.', 1)[1].lower() if '.' in original_filename else ''
    random_name = secrets.token_urlsafe(16)
    if ext:
        return f"{random_name}.{ext}"
    return random_name