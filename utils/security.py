# app/utils/security.py
import re
import secrets
import string
import hashlib
import base64
import pyotp
import qrcode
from io import BytesIO
from datetime import datetime, timezone, timedelta
from flask import current_app
import logging

logger = logging.getLogger(__name__)

class SecurityManager:
    """Security utilities manager"""
    
    @staticmethod
    def check_password_strength(password):
        """
        Check password strength
        Returns: dict with 'is_strong' and 'message'
        """
        if len(password) < 8:
            return {
                'is_strong': False,
                'message': 'Password must be at least 8 characters long'
            }
        
        checks = {
            'uppercase': bool(re.search(r'[A-Z]', password)),
            'lowercase': bool(re.search(r'[a-z]', password)),
            'digits': bool(re.search(r'\d', password)),
            'special': bool(re.search(r'[!@#$%^&*(),.?":{}|<>]', password))
        }
        
        # Count how many requirements are met
        score = sum(checks.values())
        
        if score >= 3:
            return {'is_strong': True, 'message': 'Password is strong'}
        else:
            missing = []
            if not checks['uppercase']:
                missing.append('uppercase letter')
            if not checks['lowercase']:
                missing.append('lowercase letter')
            if not checks['digits']:
                missing.append('digit')
            if not checks['special']:
                missing.append('special character')
            
            return {
                'is_strong': False,
                'message': f'Password should include at least 3 of: {", ".join(missing)}'
            }
    
    @staticmethod
    def generate_secure_password(length=12):
        """Generate a secure random password"""
        alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
        return ''.join(secrets.choice(alphabet) for _ in range(length))
    
    @staticmethod
    def hash_token(token):
        """Hash a token for storage"""
        return hashlib.sha256(token.encode()).hexdigest()
    
    @staticmethod
    def verify_token(stored_hash, provided_token):
        """Verify a token against its hash"""
        return stored_hash == hashlib.sha256(provided_token.encode()).hexdigest()
    
    @staticmethod
    def generate_2fa_secret():
        """Generate a new 2FA secret"""
        return pyotp.random_base32()
    
    @staticmethod
    def generate_2fa_uri(secret, username, issuer_name="Arndale Academy"):
        """Generate 2FA URI for QR code"""
        return pyotp.totp.TOTP(secret).provisioning_uri(
            name=username,
            issuer_name=issuer_name
        )
    
    @staticmethod
    def verify_2fa_code(secret, code):
        """Verify 2FA code"""
        if not secret or not code:
            return False
        try:
            totp = pyotp.TOTP(secret)
            return totp.verify(code, valid_window=1)  # Allow 30 seconds before/after
        except:
            return False
    
    @staticmethod
    def generate_2fa_qr_code(secret, username):
        """Generate QR code for 2FA setup"""
        try:
            # Generate provisioning URI
            uri = SecurityManager.generate_2fa_uri(secret, username)
            
            # Create QR code
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(uri)
            qr.make(fit=True)
            
            # Create image
            img = qr.make_image(fill_color="black", back_color="white")
            
            # Convert to base64
            buffered = BytesIO()
            img.save(buffered, format="PNG")
            img_str = base64.b64encode(buffered.getvalue()).decode()
            
            return f"data:image/png;base64,{img_str}"
        except Exception as e:
            logger.error(f"Error generating QR code: {e}")
            return None
    
    @staticmethod
    def generate_reset_token():
        """Generate a password reset token"""
        return secrets.token_urlsafe(32)
    
    @staticmethod
    def generate_session_token():
        """Generate a session token"""
        return secrets.token_hex(32)
    
    @staticmethod
    def sanitize_input(input_str):
        """Sanitize user input"""
        if not input_str:
            return ""
        
        # Remove potentially dangerous characters
        sanitized = re.sub(r'[<>"\']', '', str(input_str))
        
        # Trim whitespace
        sanitized = sanitized.strip()
        
        return sanitized
    
    @staticmethod
    def validate_email(email):
        """Validate email format"""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))
    
    @staticmethod
    def validate_username(username):
        """Validate username format"""
        pattern = r'^[a-zA-Z0-9_]{3,30}$'
        return bool(re.match(pattern, username))
    
    @staticmethod
    def generate_csrf_token():
        """Generate CSRF token"""
        return secrets.token_hex(32)
    
    @staticmethod
    def calculate_password_entropy(password):
        """Calculate password entropy (bits)"""
        if not password:
            return 0
        
        # Determine character set size
        charset_size = 0
        if any(c.islower() for c in password):
            charset_size += 26
        if any(c.isupper() for c in password):
            charset_size += 26
        if any(c.isdigit() for c in password):
            charset_size += 10
        if any(c in string.punctuation for c in password):
            charset_size += 32
        
        # If no character sets detected, assume lowercase
        if charset_size == 0:
            charset_size = 26
        
        # Calculate entropy
        entropy = len(password) * (charset_size ** 0.5)
        return round(entropy, 2)
    
    @staticmethod
    def is_password_common(password):
        """Check if password is in common passwords list"""
        common_passwords = {
            'password', '123456', '12345678', '1234', 'qwerty',
            '12345', 'dragon', 'football', 'monkey', 'letmein',
            '111111', 'baseball', 'iloveyou', 'trustno1', 'sunshine'
        }
        return password.lower() in common_passwords
    
    @staticmethod
    def validate_ip_address(ip):
        """Validate IP address format"""
        ipv4_pattern = r'^(\d{1,3}\.){3}\d{1,3}$'
        ipv6_pattern = r'^([0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}$'
        
        if re.match(ipv4_pattern, ip):
            # Validate IPv4 octets
            octets = ip.split('.')
            for octet in octets:
                if not 0 <= int(octet) <= 255:
                    return False
            return True
        elif re.match(ipv6_pattern, ip):
            return True
        return False
    
    @staticmethod
    def generate_file_hash(file_content):
        """Generate SHA256 hash of file content"""
        return hashlib.sha256(file_content).hexdigest()
    
    @staticmethod
    def check_file_signature(file_content, allowed_types=None):
        """Check file signature for common file types"""
        if allowed_types is None:
            allowed_types = {'image/jpeg', 'image/png', 'application/pdf'}
        
        # Common file signatures
        signatures = {
            b'\xff\xd8\xff': 'image/jpeg',
            b'\x89PNG\r\n\x1a\n': 'image/png',
            b'%PDF': 'application/pdf',
            b'PK\x03\x04': 'application/zip',
            b'GIF87a': 'image/gif',
            b'GIF89a': 'image/gif'
        }
        
        for sig, mime_type in signatures.items():
            if file_content.startswith(sig):
                if mime_type in allowed_types:
                    return True, mime_type
                else:
                    return False, mime_type
        
        return False, None

# Singleton instance (created when needed)
security_manager = SecurityManager()