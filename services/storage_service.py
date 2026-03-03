import os
from werkzeug.utils import secure_filename
from flask import current_app
import uuid
from datetime import datetime

class StorageService:
    """Unified storage service - handles both local and cloud storage"""
    
    @staticmethod
    def save_file(file, folder, filename=None, subfolder=None):
        """
        Save a file to either local storage or cloud storage based on config
        
        Args:
            file: File object
            folder: Base folder (e.g., 'questions', 'options', 'students')
            filename: Optional custom filename
            subfolder: Optional subfolder
        
        Returns:
            dict: {'success': bool, 'url': str, 'filename': str, 'public_id': str (for cloud)}
        """
        storage_type = current_app.config.get('STORAGE_TYPE', 'local')
        
        if storage_type == 'cloudinary':
            return StorageService._save_to_cloud(file, folder, filename, subfolder)
        else:
            return StorageService._save_to_local(file, folder, filename, subfolder)
    
    @staticmethod
    def _save_to_local(file, folder, filename=None, subfolder=None):
        """Save file to local filesystem"""
        try:
            # Generate filename if not provided
            if not filename:
                ext = os.path.splitext(file.filename)[1]
                filename = f"{uuid.uuid4().hex}{ext}"
            
            # Build path
            upload_path = current_app.config.get('UPLOAD_FOLDER', 'uploads')
            if subfolder:
                save_dir = os.path.join(upload_path, folder, subfolder)
            else:
                save_dir = os.path.join(upload_path, folder)
            
            # Create directory if it doesn't exist
            os.makedirs(save_dir, exist_ok=True)
            
            # Save file
            file_path = os.path.join(save_dir, secure_filename(filename))
            file.save(file_path)
            
            # Return relative URL for web access
            if subfolder:
                url = f"/uploads/{folder}/{subfolder}/{filename}"
            else:
                url = f"/uploads/{folder}/{filename}"
            
            return {
                'success': True,
                'url': url,
                'filename': filename,
                'path': file_path
            }
            
        except Exception as e:
            current_app.logger.error(f"Local storage error: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    @staticmethod
    def _save_to_cloud(file, folder, filename=None, subfolder=None):
        """Save file to Cloudinary"""
        try:
            from utils.cloudinary_helper import cloudinary_helper
            
            # Determine the folder structure
            cloud_folder = folder
            if subfolder:
                cloud_folder = f"{folder}/{subfolder}"
            
            # Upload to Cloudinary
            result = cloudinary_helper.upload_file(
                file,
                folder=cloud_folder,
                public_id=filename,
                resource_type='auto'
            )
            
            return result
            
        except Exception as e:
            current_app.logger.error(f"Cloud storage error: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    @staticmethod
    def delete_file(file_url, file_type='local'):
        """Delete a file from storage"""
        if file_type == 'cloudinary':
            from utils.cloudinary_helper import cloudinary_helper
            # Extract public_id from URL
            import re
            match = re.search(r'/([^/]+)\.(?:jpg|jpeg|png|gif|pdf|docx?)$', file_url)
            if match:
                public_id = match.group(1)
                return cloudinary_helper.delete_file(public_id)
        
        elif file_type == 'local':
            # Delete local file
            try:
                if os.path.exists(file_url):
                    os.remove(file_url)
                    return {'success': True}
            except Exception as e:
                current_app.logger.error(f"Local file delete error: {str(e)}")
        
        return {'success': False, 'error': 'File not found or invalid type'}

# Global instance
storage = StorageService()