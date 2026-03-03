import os
import cloudinary
import cloudinary.uploader
import cloudinary.api
from werkzeug.utils import secure_filename
import uuid
from flask import current_app

class CloudinaryHelper:
    """Helper class for Cloudinary operations"""
    
    def __init__(self, app=None):
        if app:
            self.init_app(app)
    
    def init_app(self, app):
        """Initialize Cloudinary with app config"""
        cloudinary.config(
            cloud_name=app.config.get('CLOUDINARY_CLOUD_NAME'),
            api_key=app.config.get('CLOUDINARY_API_KEY'),
            api_secret=app.config.get('CLOUDINARY_API_SECRET'),
            secure=True
        )
        self.folder = app.config.get('CLOUDINARY_FOLDER', 'arndale-cbt')
    
    def upload_file(self, file, folder=None, public_id=None, resource_type='auto'):
        """
        Upload a file to Cloudinary
        
        Args:
            file: File object or file path
            folder: Subfolder in Cloudinary
            public_id: Custom public_id (optional)
            resource_type: 'auto', 'image', 'video', 'raw'
        
        Returns:
            dict: Upload result with url, public_id, etc.
        """
        try:
            upload_folder = self.folder
            if folder:
                upload_folder = f"{self.folder}/{folder}"
            
            # Generate a unique public_id if not provided
            if not public_id:
                public_id = str(uuid.uuid4())
            
            # Upload the file
            result = cloudinary.uploader.upload(
                file,
                folder=upload_folder,
                public_id=public_id,
                resource_type=resource_type,
                overwrite=True
            )
            
            return {
                'success': True,
                'url': result['secure_url'],
                'public_id': result['public_id'],
                'format': result.get('format'),
                'size': result.get('bytes')
            }
            
        except Exception as e:
            current_app.logger.error(f"Cloudinary upload error: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def delete_file(self, public_id):
        """Delete a file from Cloudinary"""
        try:
            result = cloudinary.uploader.destroy(public_id)
            return {
                'success': result.get('result') == 'ok'
            }
        except Exception as e:
            current_app.logger.error(f"Cloudinary delete error: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_url(self, public_id, **options):
        """Generate a Cloudinary URL with transformations"""
        return cloudinary.CloudinaryImage(public_id).build_url(**options)
    
    def upload_question_image(self, file, question_id):
        """Upload a question image"""
        return self.upload_file(
            file,
            folder='questions',
            public_id=f"q_{question_id}",
            resource_type='image'
        )
    
    def upload_option_image(self, file, option_id):
        """Upload an option image"""
        return self.upload_file(
            file,
            folder='options',
            public_id=f"opt_{option_id}",
            resource_type='image'
        )
    
    def upload_student_photo(self, file, student_id):
        """Upload a student photo"""
        return self.upload_file(
            file,
            folder='students',
            public_id=f"student_{student_id}",
            resource_type='image'
        )
    
    def upload_teacher_photo(self, file, teacher_id):
        """Upload a teacher photo"""
        return self.upload_file(
            file,
            folder='teachers',
            public_id=f"teacher_{teacher_id}",
            resource_type='image'
        )
    
    def upload_document(self, file, doc_type, doc_id):
        """Upload any document (PDF, DOC, etc.)"""
        return self.upload_file(
            file,
            folder='documents',
            public_id=f"{doc_type}_{doc_id}",
            resource_type='raw'
        )

# Global instance
cloudinary_helper = CloudinaryHelper()