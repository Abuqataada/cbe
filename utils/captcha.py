# app/utils/captcha.py
import random
import string
import hashlib
import time
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import base64
import json
import hmac

class CaptchaGenerator:
    """Generate and verify CAPTCHA images"""
    
    def __init__(self, width=200, height=80, length=6):
        self.width = width
        self.height = height
        self.length = length
        self.font_size = 40
        self.noise_level = 3
        
    def generate(self, captcha_id=None):
        """Generate a CAPTCHA image and text"""
        if not captcha_id:
            captcha_id = hashlib.sha256(str(time.time()).encode()).hexdigest()[:16]
        
        # Generate random text
        chars = string.ascii_uppercase + string.digits
        # Exclude confusing characters
        exclude_chars = {'0', 'O', '1', 'I', 'L'}
        chars = ''.join(c for c in chars if c not in exclude_chars)
        text = ''.join(random.choice(chars) for _ in range(self.length))
        
        # Create image
        image = Image.new('RGB', (self.width, self.height), color=(255, 255, 255))
        draw = ImageDraw.Draw(image)
        
        # Try to load font, fallback to default
        try:
            font = ImageFont.truetype("arial.ttf", self.font_size)
        except IOError:
            font = ImageFont.load_default()
        
        # Draw text with random positioning and rotation
        for i, char in enumerate(text):
            # Random color
            color = (
                random.randint(0, 100),
                random.randint(0, 100),
                random.randint(0, 100)
            )
            
            # Random position
            x = 20 + i * 30 + random.randint(-5, 5)
            y = 10 + random.randint(-10, 10)
            
            # Random rotation
            angle = random.randint(-15, 15)
            
            # Draw character
            char_image = Image.new('RGBA', (30, 50), (255, 255, 255, 0))
            char_draw = ImageDraw.Draw(char_image)
            char_draw.text((0, 0), char, fill=color, font=font)
            char_image = char_image.rotate(angle, expand=1)
            
            image.paste(char_image, (int(x), int(y)), char_image)
        
        # Add noise
        self._add_noise(image)
        
        # Add lines
        self._add_lines(draw)
        
        # Apply blur
        image = image.filter(ImageFilter.GaussianBlur(radius=0.5))
        
        # Convert to base64
        buffered = BytesIO()
        image.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode()
        
        # Store CAPTCHA hash (not plain text)
        captcha_hash = hashlib.sha256(text.encode()).hexdigest()
        
        return {
            'id': captcha_id,
            'image': f"data:image/png;base64,{img_str}",
            'hash': captcha_hash,
            'expires': time.time() + 300  # 5 minutes
        }
    
    def _add_noise(self, image):
        """Add random noise to image"""
        pixels = image.load()
        
        for i in range(image.width):
            for j in range(image.height):
                if random.random() < 0.05:  # 5% noise
                    pixels[i, j] = (
                        random.randint(0, 255),
                        random.randint(0, 255),
                        random.randint(0, 255)
                    )
    
    def _add_lines(self, draw):
        """Add random lines to image"""
        for _ in range(5):
            x1 = random.randint(0, self.width)
            y1 = random.randint(0, self.height)
            x2 = random.randint(0, self.width)
            y2 = random.randint(0, self.height)
            
            color = (
                random.randint(0, 200),
                random.randint(0, 200),
                random.randint(0, 200)
            )
            
            draw.line([(x1, y1), (x2, y2)], fill=color, width=2)
    
    @staticmethod
    def verify(captcha_id, user_input, stored_hash):
        """Verify CAPTCHA input"""
        if not captcha_id or not user_input or not stored_hash:
            return False
        
        # Case insensitive comparison
        user_input = user_input.upper().strip()
        
        # Remove confusing characters
        user_input = user_input.replace('0', 'O').replace('1', 'I').replace('L', 'I')
        
        # Calculate hash of user input
        user_hash = hashlib.sha256(user_input.encode()).hexdigest()
        
        return hmac.compare_digest(user_hash, stored_hash)

# Global CAPTCHA store (use Redis in production)
_captcha_store = {}

def generate_captcha():
    """Generate a new CAPTCHA"""
    generator = CaptchaGenerator()
    captcha_data = generator.generate()
    
    # Store in memory (replace with Redis in production)
    _captcha_store[captcha_data['id']] = {
        'hash': captcha_data['hash'],
        'expires': captcha_data['expires']
    }
    
    # Cleanup expired CAPTCHAs
    cleanup_captchas()
    
    return {
        'id': captcha_data['id'],
        'image': captcha_data['image']
    }

def verify_captcha(captcha_id, user_input):
    """Verify CAPTCHA"""
    if captcha_id not in _captcha_store:
        return False
    
    captcha_data = _captcha_store[captcha_id]
    
    # Check expiry
    if time.time() > captcha_data['expires']:
        del _captcha_store[captcha_id]
        return False
    
    # Verify
    generator = CaptchaGenerator()
    is_valid = generator.verify(captcha_id, user_input, captcha_data['hash'])
    
    # Remove after verification (one-time use)
    if captcha_id in _captcha_store:
        del _captcha_store[captcha_id]
    
    return is_valid

def cleanup_captchas():
    """Cleanup expired CAPTCHAs"""
    current_time = time.time()
    expired_ids = [
        captcha_id for captcha_id, data in _captcha_store.items()
        if current_time > data['expires']
    ]
    
    for captcha_id in expired_ids:
        del _captcha_store[captcha_id]