# app/routes/errors.py
from flask import render_template, jsonify, request
import traceback

def register_error_handlers(app):
    """Register error handlers for the application"""
    
    @app.errorhandler(400)
    def bad_request_error(error):
        if request.is_json or request.accept_mimetypes.accept_json:
            return jsonify({
                'error': 'Bad Request',
                'message': str(error),
                'code': 400
            }), 400
        return render_template('errors/400.html'), 400
    
    @app.errorhandler(401)
    def unauthorized_error(error):
        if request.is_json or request.accept_mimetypes.accept_json:
            return jsonify({
                'error': 'Unauthorized',
                'message': 'Please log in to access this resource',
                'code': 401
            }), 401
        return render_template('errors/401.html'), 401
    
    @app.errorhandler(403)
    def forbidden_error(error):
        if request.is_json or request.accept_mimetypes.accept_json:
            return jsonify({
                'error': 'Forbidden',
                'message': 'You do not have permission to access this resource',
                'code': 403
            }), 403
        return render_template('errors/403.html'), 403
    
    @app.errorhandler(404)
    def not_found_error(error):
        if request.is_json or request.accept_mimetypes.accept_json:
            return jsonify({
                'error': 'Not Found',
                'message': 'The requested resource was not found',
                'code': 404
            }), 404
        return render_template('errors/404.html'), 404
    
    @app.errorhandler(405)
    def method_not_allowed_error(error):
        if request.is_json or request.accept_mimetypes.accept_json:
            return jsonify({
                'error': 'Method Not Allowed',
                'message': str(error),
                'code': 405
            }), 405
        return render_template('errors/405.html'), 405
    
    @app.errorhandler(413)
    def payload_too_large_error(error):
        if request.is_json or request.accept_mimetypes.accept_json:
            return jsonify({
                'error': 'Payload Too Large',
                'message': 'File size exceeds maximum allowed',
                'code': 413
            }), 413
        return render_template('errors/413.html'), 413
    
    @app.errorhandler(429)
    def ratelimit_error(error):
        if request.is_json or request.accept_mimetypes.accept_json:
            return jsonify({
                'error': 'Too Many Requests',
                'message': 'Rate limit exceeded',
                'code': 429
            }), 429
        return render_template('errors/429.html'), 429
    
    @app.errorhandler(500)
    def internal_error(error):
        app.logger.error(f'500 Error: {str(error)}')
        app.logger.error(traceback.format_exc())
        
        if request.is_json or request.accept_mimetypes.accept_json:
            return jsonify({
                'error': 'Internal Server Error',
                'message': 'An unexpected error occurred',
                'code': 500
            }), 500
        return render_template('errors/500.html'), 500
    
    @app.errorhandler(Exception)
    def handle_exception(error):
        app.logger.error(f'Unhandled Exception: {str(error)}')
        app.logger.error(traceback.format_exc())
        
        if request.is_json or request.accept_mimetypes.accept_json:
            return jsonify({
                'error': 'Internal Server Error',
                'message': 'An unexpected error occurred',
                'code': 500
            }), 500
        return render_template('errors/500.html'), 500