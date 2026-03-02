# app/utils/email_service.py
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import current_app, render_template
import logging
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

class EmailService:
    """Email service for sending notifications"""
    
    def __init__(self):
        # Don't initialize config here - get it when needed
        pass
    
    def _get_config(self):
        """Get email configuration from current_app context"""
        return {
            'smtp_server': current_app.config.get('SMTP_SERVER', 'smtp.gmail.com'),
            'smtp_port': current_app.config.get('SMTP_PORT', 587),
            'smtp_username': current_app.config.get('SMTP_USERNAME'),
            'smtp_password': current_app.config.get('SMTP_PASSWORD'),
            'from_email': current_app.config.get('FROM_EMAIL', 'noreply@arndale.edu.ng'),
            'use_tls': current_app.config.get('SMTP_USE_TLS', True),
            'app_url': current_app.config.get('APP_URL', 'http://localhost:5000'),
            'support_email': current_app.config.get('SUPPORT_EMAIL', 'support@arndale.edu.ng')
        }
    
    def send_email(self, to_email, subject, html_content, text_content=None):
        """Send email"""
        try:
            config = self._get_config()
            
            # Check if SMTP is configured
            if not config['smtp_username'] or not config['smtp_password']:
                logger.warning("SMTP not configured. Email not sent.")
                return False
            
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = config['from_email']
            msg['To'] = to_email
            
            # Create text/plain version
            if text_content:
                part1 = MIMEText(text_content, 'plain')
                msg.attach(part1)
            
            # Create HTML version
            part2 = MIMEText(html_content, 'html')
            msg.attach(part2)
            
            # Send email
            with smtplib.SMTP(config['smtp_server'], config['smtp_port']) as server:
                if config['use_tls']:
                    server.starttls()
                server.login(config['smtp_username'], config['smtp_password'])
                server.send_message(msg)
            
            logger.info(f"Email sent to {to_email}: {subject}")
            return True
            
        except smtplib.SMTPAuthenticationError as e:
            logger.error(f"SMTP authentication failed: {e}")
            return False
        except smtplib.SMTPException as e:
            logger.error(f"SMTP error sending email to {to_email}: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {e}")
            return False
    
    def send_welcome_email(self, to_email, username, password):
        """Send welcome email to new users"""
        subject = "Welcome to Arndale Academy CBT System"
        config = self._get_config()
        
        html_content = render_template(
            'emails/welcome.html',
            username=username,
            password=password,
            login_url=config['app_url']
        )
        
        text_content = f"""
        Welcome to Arndale Academy CBT System!
        
        Your account has been created:
        Username: {username}
        Password: {password}
        
        Please login at: {config['app_url']}
        
        For security reasons, please change your password after first login.
        
        Best regards,
        Arndale Academy Admin Team
        """
        
        return self.send_email(to_email, subject, html_content, text_content)
    
    def send_password_reset_email(self, to_email, reset_token):
        """Send password reset email"""
        config = self._get_config()
        reset_url = f"{config['app_url']}/reset-password/{reset_token}"
        
        subject = "Password Reset Request - Arndale Academy"
        
        html_content = render_template(
            'emails/password_reset.html',
            reset_url=reset_url,
            expiry_hours=1
        )
        
        text_content = f"""
        You have requested to reset your password for Arndale Academy CBT System.
        
        To reset your password, click the following link:
        {reset_url}
        
        This link will expire in 1 hour.
        
        If you did not request this password reset, please ignore this email.
        
        Best regards,
        Arndale Academy Admin Team
        """
        
        return self.send_email(to_email, subject, html_content, text_content)
    
    def send_login_notification(self, to_email, username, ip_address, user_agent, timestamp):
        """Send login notification email"""
        subject = "New Login Alert - Arndale Academy"
        config = self._get_config()
        
        html_content = render_template(
            'emails/login_notification.html',
            username=username,
            ip_address=ip_address,
            user_agent=user_agent,
            timestamp=timestamp,
            support_email=config['support_email']
        )
        
        text_content = f"""
        New login detected on your Arndale Academy account:
        
        Username: {username}
        IP Address: {ip_address}
        User Agent: {user_agent}
        Time: {timestamp}
        
        If this was you, no action is required.
        If you did not log in, please change your password immediately and contact support.
        
        Support Email: {config['support_email']}
        
        Best regards,
        Arndale Academy Security Team
        """
        
        return self.send_email(to_email, subject, html_content, text_content)
    
    def send_bulk_import_report(self, to_email, import_type, results, timestamp):
        """Send bulk import report"""
        subject = f"Bulk Import Report - {import_type.capitalize()}"
        
        html_content = render_template(
            'emails/import_report.html',
            import_type=import_type,
            results=results,
            timestamp=timestamp
        )
        
        text_content = f"""
        Bulk Import Report - {import_type.capitalize()}
        
        Import completed at: {timestamp}
        
        Results:
        - Total records: {results.get('total', 0)}
        - Successful: {results.get('success', 0)}
        - Failed: {results.get('failed', 0)}
        - Warnings: {len(results.get('warnings', []))}
        
        {'Errors:' if results.get('errors') else 'No errors'}
        {chr(10).join(results.get('errors', [])[:10])}
        {'... (more errors)' if len(results.get('errors', [])) > 10 else ''}
        
        Best regards,
        Arndale Academy System
        """
        
        return self.send_email(to_email, subject, html_content, text_content)
    
    def send_report_card_notification(self, to_email, student_name, term, academic_year):
        """Send report card notification"""
        subject = f"Report Card Available - {student_name}"
        config = self._get_config()
        
        html_content = render_template(
            'emails/report_card.html',
            student_name=student_name,
            term=term,
            academic_year=academic_year,
            portal_url=f"{config['app_url']}/student/report-cards"
        )
        
        text_content = f"""
        Dear Parent/Guardian,
        
        The report card for {student_name} for Term {term}, {academic_year} is now available.
        
        Please log in to the student portal to view and download the report card:
        {config['app_url']}/student/report-cards
        
        Best regards,
        Arndale Academy
        """
        
        return self.send_email(to_email, subject, html_content, text_content)

# Don't create instance at module level - create factory function instead
def get_email_service():
    """Factory function to get email service instance"""
    return EmailService()

# Convenience functions that create service instance when called
def send_password_reset_email(to_email, reset_token):
    service = EmailService()
    return service.send_password_reset_email(to_email, reset_token)

def send_welcome_email(to_email, username, password):
    service = EmailService()
    return service.send_welcome_email(to_email, username, password)

def send_bulk_import_report(to_email, import_type, results, timestamp):
    service = EmailService()
    return service.send_bulk_import_report(to_email, import_type, results, timestamp)

def send_login_notification(to_email, username, ip_address, user_agent, timestamp):
    service = EmailService()
    return service.send_login_notification(to_email, username, ip_address, user_agent, timestamp)

def send_report_card_notification(to_email, student_name, term, academic_year):
    service = EmailService()
    return service.send_report_card_notification(to_email, student_name, term, academic_year)