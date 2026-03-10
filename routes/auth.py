# app/routes/auth.py
from flask import Blueprint, render_template, redirect, url_for, flash, request, session, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash, generate_password_hash
import secrets
import string
from datetime import datetime, timedelta, timezone
from models import db, User, Student, Teacher, Parent, AuditLog, LoginAttempt, SecurityLog
from utils.email_service import send_password_reset_email, send_welcome_email
from middleware.security import generate_2fa_code, verify_2fa_code, check_password_strength
from utils.captcha import generate_captcha, verify_captcha
import re
from sqlalchemy import or_

auth_bp = Blueprint('auth', __name__)

# Password policy configuration
PASSWORD_POLICY = {
    'min_length': 8,
    'require_upper': True,
    'require_lower': True,
    'require_digits': True,
    'require_special': True,
    'max_age_days': 90  # Password expiry
}

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Login for admin, teachers, and parents (password required)"""
    if current_user.is_authenticated:
        return redirect(url_for('auth.redirect_by_role'))
    
    # Get role from query parameter or form
    requested_role = request.args.get('role') or request.form.get('role', '').strip().lower()
    
    # Remove student from allowed roles for this route
    allowed_roles = ['admin', 'finance_admin', 'teacher', 'parent']
    if requested_role == 'student':
        # Redirect to student login
        return redirect(url_for('auth.student_login'))
    
    # Role-specific template mapping (no student)
    role_templates = {
        'admin': 'admin/login.html',
        'finance_admin': 'finance_admin/login.html',
        'teacher': 'teacher/login.html',
        'parent': 'parent/login.html'
    }
    
    template = 'index.html'  # Generic fallback
    if requested_role in role_templates:
        template = role_templates[requested_role]
    
    if request.method == 'POST':
        print("Login POST data:", request.form)
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        role = request.form.get('role', '').strip().lower()
        
        # Check rate limiting
        ip_address = request.remote_addr
        now = datetime.now(timezone.utc)
        
        failed_attempts = LoginAttempt.query.filter_by(
            ip_address=ip_address,
            successful=False
        ).filter(
            LoginAttempt.timestamp >= now - timedelta(minutes=15)
        ).count()
        
        if failed_attempts >= 5:
            flash('Too many failed login attempts. Please try again later.', 'danger')
            return render_template(template, 
                                  role=role, 
                                  requested_role=requested_role,
                                  username=username)
        
        # Verify CAPTCHA if enabled
        if failed_attempts >= 3:
            captcha_input = request.form.get('captcha', '')
            captcha_id = request.form.get('captcha_id', '')
            if not verify_captcha(captcha_id, captcha_input):
                flash('Invalid CAPTCHA code. Please try again.', 'danger')
                return render_template(template, 
                                      show_captcha=True,
                                      role=role,
                                      requested_role=requested_role,
                                      username=username)
        
        # Find user (NO STUDENT LOGIC HERE)
        user = User.query.filter(
            User.is_active == True,
            or_(User.username == username, User.email == username)
        ).first()
        
        if user:
            # Validate role
            if role and user.role != role:
                flash(f'This account does not have {role} privileges.', 'danger')
                return render_template(template, 
                                      role=role,
                                      requested_role=requested_role,
                                      username=username)
            
            # Check if account is locked
            if user.locked_until and user.locked_until > now:
                remaining = (user.locked_until - now).seconds // 60
                flash(f'Account is locked. Please try again in {remaining} minutes.', 'danger')
                return render_template(template, 
                                      role=role,
                                      requested_role=requested_role,
                                      username=username)
            
            # Verify password
            if user.check_password(password):
                # Log successful login
                login_user(user)
                user.last_login = now
                user.failed_login_attempts = 0
                user.locked_until = None
                
                # Log audit trail
                audit_log = AuditLog(
                    user_id=user.id,
                    action='LOGIN',
                    ip_address=ip_address,
                    user_agent=request.user_agent.string
                )
                db.session.add(audit_log)
                
                # Security log
                security_log = SecurityLog(
                    user_id=user.id,
                    event_type='LOGIN_SUCCESS',
                    ip_address=ip_address,
                    user_agent=request.user_agent.string,
                    details={'username': username, 'role': user.role}
                )
                db.session.add(security_log)
                
                # Clear failed attempts
                LoginAttempt.query.filter_by(
                    ip_address=ip_address,
                    successful=False
                ).delete()
                
                db.session.commit()
                flash('Login successful!', 'success')
                return redirect(url_for('auth.redirect_by_role'))
            else:
                # Failed login
                user.failed_login_attempts = (user.failed_login_attempts or 0) + 1

                # Log failed attempt
                login_attempt = LoginAttempt(
                    username=username,
                    ip_address=ip_address,
                    successful=False,
                    user_agent=request.user_agent.string
                )
                db.session.add(login_attempt)
                
                security_log = SecurityLog(
                    user_id=user.id,
                    event_type='LOGIN_FAILED',
                    ip_address=ip_address,
                    user_agent=request.user_agent.string,
                    details={'username': username, 
                            'attempts': user.failed_login_attempts,
                            'role': role}
                )
                db.session.add(security_log)
                
                db.session.commit()
                flash('Invalid username or password.', 'danger')
        else:
            # Log failed attempt
            login_attempt = LoginAttempt(
                username=username,
                ip_address=ip_address,
                successful=False,
                user_agent=request.user_agent.string
            )
            db.session.add(login_attempt)
            
            security_log = SecurityLog(
                event_type='LOGIN_FAILED',
                ip_address=ip_address,
                user_agent=request.user_agent.string,
                details={'username': username, 
                        'reason': 'user_not_found',
                        'role': role}
            )
            db.session.add(security_log)
            
            db.session.commit()
            flash('Invalid username or password.', 'danger')
        
        return render_template(template, 
                              role=role,
                              requested_role=requested_role,
                              username=username)
    
    # GET request
    now = datetime.now(timezone.utc)
    show_captcha = LoginAttempt.query.filter_by(
        ip_address=request.remote_addr,
        successful=False
    ).filter(
        LoginAttempt.timestamp >= now - timedelta(minutes=15)
    ).count() >= 3
    
    captcha_data = None
    if show_captcha:
        captcha_data = generate_captcha()
        session['captcha_id'] = captcha_data['id']
    
    role_names = {
        'admin': 'Administrator',
        'teacher': 'Teacher',
        'parent': 'Parent'
    }
    
    display_role = role_names.get(requested_role, requested_role.capitalize() if requested_role else None)
    
    return render_template(template, 
                          role=requested_role,
                          requested_role=requested_role,
                          display_role=display_role,
                          show_captcha=show_captcha, 
                          captcha=captcha_data)

@auth_bp.route('/student-login', methods=['GET', 'POST'])
def student_login():
    """Student-only login using admission number (no password required)"""
    if current_user.is_authenticated and current_user.role == 'student':
        return redirect(url_for('student.dashboard'))  # Adjust to your student dashboard route
    
    if request.method == 'POST':
        admission_number = request.form.get('admission_number', '').strip()
        exam_code = request.form.get('exam_code', '').strip()  # Optional: for specific exams
        
        ip_address = request.remote_addr
        now = datetime.now(timezone.utc)
        
        # Check rate limiting for IP
        failed_attempts = LoginAttempt.query.filter_by(
            ip_address=ip_address,
            successful=False
        ).filter(
            LoginAttempt.timestamp >= now - timedelta(minutes=15)
        ).count()
        
        if failed_attempts >= 10:  # Higher limit for student-only login
            flash('Too many failed login attempts. Please contact your teacher.', 'danger')
            return render_template('student/login_simple.html')
        
        # Verify CAPTCHA if needed
        if failed_attempts >= 5:
            captcha_input = request.form.get('captcha', '')
            captcha_id = request.form.get('captcha_id', '')
            if not verify_captcha(captcha_id, captcha_input):
                flash('Invalid security code. Please try again.', 'danger')
                return render_template('student/login.html',
                                      show_captcha=True,
                                      admission_number=admission_number)
        
        # Find student by admission number
        student = Student.query.filter_by(
            admission_number=admission_number,
            is_active=True
        ).first()
        
        if not student:
            # Log failed attempt
            login_attempt = LoginAttempt(
                username=admission_number,
                ip_address=ip_address,
                successful=False,
                user_agent=request.user_agent.string
            )
            db.session.add(login_attempt)
            
            security_log = SecurityLog(
                event_type='STUDENT_LOGIN_FAILED',
                ip_address=ip_address,
                user_agent=request.user_agent.string,
                details={'admission_number': admission_number, 
                        'reason': 'student_not_found'}
            )
            db.session.add(security_log)
            
            db.session.commit()
            flash('Invalid admission number. Please check and try again.', 'danger')
            return render_template('student/login.html', admission_number=admission_number)
        
        # Get the associated user account
        user = User.query.filter_by(
            id=student.user_id,
            role='student',
            is_active=True
        ).first()
        
        if not user:
            flash('Student account is not properly configured. Please contact administrator.', 'danger')
            return render_template('student/login.html')
        
        # Check if student has active exams
        # You can add exam-specific logic here if needed
        
        # Log the student in
        login_user(user)
        user.last_login = now
        
        # Log successful login
        audit_log = AuditLog(
            user_id=user.id,
            action='STUDENT_LOGIN',
            ip_address=ip_address,
            user_agent=request.user_agent.string,
            details={'admission_number': admission_number, 'exam_code': exam_code}
        )
        db.session.add(audit_log)
        
        security_log = SecurityLog(
            user_id=user.id,
            event_type='STUDENT_LOGIN_SUCCESS',
            ip_address=ip_address,
            user_agent=request.user_agent.string,
            details={'admission_number': admission_number, 'student_id': student.id}
        )
        db.session.add(security_log)
        
        # Clear failed attempts for this IP
        LoginAttempt.query.filter_by(
            ip_address=ip_address,
            successful=False
        ).delete()
        
        db.session.commit()
        
        # Redirect based on exam code or to student dashboard
        if exam_code:
            # Redirect to specific exam
            return redirect(url_for('exam.take_exam', exam_code=exam_code))
        else:
            return redirect(url_for('student.dashboard'))  # Your student dashboard route
    
    # GET request - generate CAPTCHA if needed
    now = datetime.now(timezone.utc)
    show_captcha = LoginAttempt.query.filter_by(
        ip_address=request.remote_addr,
        successful=False
    ).filter(
        LoginAttempt.timestamp >= now - timedelta(minutes=15)
    ).count() >= 5
    
    captcha_data = None
    if show_captcha:
        captcha_data = generate_captcha()
        session['captcha_id'] = captcha_data['id']
    
    return render_template('student/login.html', 
                          show_captcha=show_captcha,
                          captcha=captcha_data)


@auth_bp.route('/student-logout')
@login_required
def student_logout():
    """Student-specific logout"""
    if current_user.role != 'student':
        return redirect(url_for('auth.logout'))
    
    # Log the logout
    audit_log = AuditLog(
        user_id=current_user.id,
        action='STUDENT_LOGOUT',
        ip_address=request.remote_addr,
        user_agent=request.user_agent.string
    )
    db.session.add(audit_log)
    db.session.commit()
    
    logout_user()
    flash('You have been logged out from the student portal.', 'success')
    return redirect(url_for('index'))

@auth_bp.route('/logout')
@login_required
def logout():
    """User logout with audit logging"""
    user_id = current_user.id
    username = current_user.username
    role = current_user.role

    if role == "teacher":
        temp = "staff_index"
    elif role == "admin":
        temp = "admin_index"
    elif role == "finance_admin":
        temp = "finance_admin_index"
    else:
        temp = "index"
    
    # Log audit trail before logout
    audit_log = AuditLog(
        user_id=user_id,
        action='LOGOUT',
        ip_address=request.remote_addr,
        user_agent=request.user_agent.string
    )
    db.session.add(audit_log)
    
    # Security log
    security_log = SecurityLog(
        user_id=user_id,
        event_type='LOGOUT',
        ip_address=request.remote_addr,
        user_agent=request.user_agent.string,
        details={'username': username, 'role': role}
    )
    db.session.add(security_log)
    
    db.session.commit()
    
    logout_user()
    flash('You have been logged out successfully.', 'success')
    return redirect(url_for(temp))

@auth_bp.route('/redirect')
@login_required
def redirect_by_role():
    """Redirect users based on their role"""
    role = current_user.role
    
    # Log role-based redirection
    audit_log = AuditLog(
        user_id=current_user.id,
        action='ROLE_REDIRECT',
        ip_address=request.remote_addr,
        user_agent=request.user_agent.string
    )
    db.session.add(audit_log)
    db.session.commit()
    
    # Redirect based on role
    if role == 'admin':
        return redirect(url_for('admin.dashboard'))
    elif role == 'finance_admin':
        return redirect(url_for('finance.finance_dashboard'))
    elif role == 'teacher':
        return redirect(url_for('teacher.dashboard'))
    elif role == 'student':
        return redirect(url_for('student.dashboard'))
    elif role == 'parent':
        return redirect(url_for('parent.dashboard'))
    else:
        flash('Invalid user role. Please contact administrator.', 'danger')
        return redirect(url_for('auth.logout'))
    
@auth_bp.route('/two-factor-verify', methods=['GET', 'POST'])
def two_factor_verify():
    """Two-factor authentication verification"""
    if 'pre_2fa_user_id' not in session:
        return redirect(url_for('auth.login'))
    
    user_id = session['pre_2fa_user_id']
    user = User.query.get(user_id)
    
    if not user or not user.is_active:
        session.pop('pre_2fa_user_id', None)
        session.pop('pre_2fa_remember', None)
        return redirect(url_for('auth.login'))
    
    if request.method == 'POST':
        token = request.form.get('token', '').strip()
        
        if verify_2fa_code(user.two_factor_secret, token):
            # Complete login
            login_user(user, remember=session.get('pre_2fa_remember', False))
            user.last_login = datetime.now(timezone.utc)
            user.failed_login_attempts = 0
            
            # Clear session
            session.pop('pre_2fa_user_id', None)
            session.pop('pre_2fa_remember', None)
            
            # Log audit trail
            audit_log = AuditLog(
                user_id=user.id,
                action='LOGIN_2FA',
                ip_address=request.remote_addr,
                user_agent=request.user_agent.string
            )
            db.session.add(audit_log)
            
            # Security log
            security_log = SecurityLog(
                user_id=user.id,
                event_type='2FA_SUCCESS',
                ip_address=request.remote_addr,
                user_agent=request.user_agent.string
            )
            db.session.add(security_log)
            
            db.session.commit()
            
            flash('Two-factor authentication successful!', 'success')
            return redirect(url_for('auth.redirect_by_role'))
        else:
            # Security log for failed 2FA
            security_log = SecurityLog(
                user_id=user.id,
                event_type='2FA_FAILED',
                ip_address=request.remote_addr,
                user_agent=request.user_agent.string
            )
            db.session.add(security_log)
            db.session.commit()
            
            flash('Invalid authentication code. Please try again.', 'danger')
    
    return render_template('auth/two_factor.html')

@auth_bp.route('/register', methods=['GET', 'POST'])
@login_required
def register():
    """Register new users (admin only)"""
    if current_user.role != 'admin':
        flash('Access denied.', 'danger')
        return redirect(url_for('auth.redirect_by_role'))
    
    from models import AcademicSession, ClassRoom  # Import here to avoid circular import
    
    if request.method == 'POST':
        try:
            username = request.form['username'].strip()
            email = request.form['email'].strip()
            role = request.form['role']
            password = request.form['password']
            
            # Validate inputs
            if not re.match(r'^[a-zA-Z0-9_]+$', username):
                flash('Username can only contain letters, numbers, and underscores.', 'danger')
                return render_template('auth/register.html')
            
            if not re.match(r'^[^@]+@[^@]+\.[^@]+$', email):
                flash('Invalid email address.', 'danger')
                return render_template('auth/register.html')
            
            # Check password strength
            strength_result = check_password_strength(password)
            if not strength_result['is_strong']:
                flash(f'Password is too weak: {strength_result["message"]}', 'danger')
                return render_template('auth/register.html')
            
            # Check if username or email exists
            if User.query.filter_by(username=username).first():
                flash('Username already exists.', 'danger')
                return render_template('auth/register.html')
            
            if User.query.filter_by(email=email).first():
                flash('Email already exists.', 'danger')
                return render_template('auth/register.html')
            
            # Create user
            user = User(
                username=username,
                email=email,
                role=role,
                created_by=current_user.id
            )
            user.set_password(password)
            user.password_changed_at = datetime.now(timezone.utc)
            
            db.session.add(user)
            db.session.flush()  # Get user ID without committing
            
            # Create profile based on role
            if role == 'student':
                # Get active academic session
                active_session = AcademicSession.query.filter_by(is_active=True).first()
                if not active_session:
                    flash('No active academic session. Please create one first.', 'danger')
                    db.session.rollback()
                    return render_template('auth/register.html')
                
                student = Student(
                    user_id=user.id,
                    admission_number=username,
                    first_name=request.form.get('first_name', ''),
                    last_name=request.form.get('last_name', ''),
                    current_class_id=request.form.get('class_id'),
                    enrollment_date=datetime.now(timezone.utc).date(),
                    academic_status='active'
                )
                db.session.add(student)
                
            elif role == 'teacher':
                teacher = Teacher(
                    user_id=user.id,
                    staff_id=username,
                    first_name=request.form.get('first_name', ''),
                    last_name=request.form.get('last_name', ''),
                    email=email,
                    phone=request.form.get('phone', '')
                )
                db.session.add(teacher)
                
            elif role == 'parent':
                parent = Parent(
                    user_id=user.id,
                    first_name=request.form.get('first_name', ''),
                    last_name=request.form.get('last_name', ''),
                    phone=request.form.get('phone', ''),
                    email=email
                )
                db.session.add(parent)
            
            # Log audit trail
            audit_log = AuditLog(
                user_id=current_user.id,
                action='CREATE_USER',
                table_name='users',
                record_id=user.id,
                new_values={'username': username, 'email': email, 'role': role},
                ip_address=request.remote_addr
            )
            db.session.add(audit_log)
            
            # Security log
            security_log = SecurityLog(
                user_id=current_user.id,
                event_type='USER_CREATED',
                ip_address=request.remote_addr,
                user_agent=request.user_agent.string,
                details={'new_user_id': user.id, 'role': role}
            )
            db.session.add(security_log)
            
            db.session.commit()
            
            # Send welcome email
            try:
                send_welcome_email(email, username, password)
            except Exception as e:
                print(f"Failed to send welcome email: {e}")
            
            flash(f'{role.capitalize()} account created successfully!', 'success')
            
            # Redirect based on created user role
            if role == 'admin':
                return redirect(url_for('admin.dashboard'))
            else:
                return redirect(url_for('admin.manage_users'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating account: {str(e)}', 'danger')
    
    # Get classes for student registration
    classes = ClassRoom.query.all()
    return render_template('auth/register.html', classes=classes)

@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    """Password reset request"""
    if current_user.is_authenticated:
        return redirect(url_for('auth.redirect_by_role'))
    
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        
        # Find user by email
        user = User.query.filter_by(email=email, is_active=True).first()
        
        if user:
            # Generate reset token
            reset_token = secrets.token_urlsafe(32)
            user.reset_token = reset_token
            user.reset_token_expiry = datetime.now(timezone.utc) + timedelta(hours=1)
            
            # Security log
            security_log = SecurityLog(
                user_id=user.id,
                event_type='PASSWORD_RESET_REQUEST',
                ip_address=request.remote_addr,
                user_agent=request.user_agent.string,
                details={'email': email}
            )
            db.session.add(security_log)
            
            db.session.commit()
            
            # Send reset email
            try:
                send_password_reset_email(user.email, reset_token)
                flash('Password reset instructions have been sent to your email.', 'success')
            except Exception as e:
                flash('Failed to send reset email. Please contact administrator.', 'danger')
        else:
            # Still show success to prevent email enumeration
            flash('If an account exists with that email, reset instructions have been sent.', 'success')
        
        return redirect(url_for('auth.login'))
    
    return render_template('auth/forgot_password.html')

@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    """Password reset with token"""
    if current_user.is_authenticated:
        return redirect(url_for('auth.redirect_by_role'))
    
    now = datetime.now(timezone.utc)
    user = User.query.filter_by(
        reset_token=token,
        is_active=True
    ).first()
    
    if not user or not user.reset_token_expiry or user.reset_token_expiry < now:
        flash('Invalid or expired reset token.', 'danger')
        return redirect(url_for('auth.forgot_password'))
    
    if request.method == 'POST':
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        
        if password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return render_template('auth/reset_password.html', token=token)
        
        # Check password strength
        strength_result = check_password_strength(password)
        if not strength_result['is_strong']:
            flash(f'Password is too weak: {strength_result["message"]}', 'danger')
            return render_template('auth/reset_password.html', token=token)
        
        # Check against previous passwords
        if user.previous_passwords:
            for old_hash in user.previous_passwords:
                if check_password_hash(old_hash, password):
                    flash('You cannot reuse a previous password.', 'danger')
                    return render_template('auth/reset_password.html', token=token)
        
        # Update password
        old_password_hash = user.password_hash
        user.set_password(password)
        user.password_changed_at = now
        user.reset_token = None
        user.reset_token_expiry = None
        user.failed_login_attempts = 0
        user.locked_until = None
        
        # Store old password hash
        if user.previous_passwords is None:
            user.previous_passwords = []
        user.previous_passwords.append(old_password_hash)
        
        # Keep only last 5 passwords
        if len(user.previous_passwords) > 5:
            user.previous_passwords = user.previous_passwords[-5:]
        
        # Log audit trail
        audit_log = AuditLog(
            user_id=user.id,
            action='PASSWORD_RESET',
            ip_address=request.remote_addr,
            user_agent=request.user_agent.string
        )
        db.session.add(audit_log)
        
        # Security log
        security_log = SecurityLog(
            user_id=user.id,
            event_type='PASSWORD_RESET_COMPLETE',
            ip_address=request.remote_addr,
            user_agent=request.user_agent.string
        )
        db.session.add(security_log)
        
        db.session.commit()
        
        flash('Password has been reset successfully. Please login with your new password.', 'success')
        return redirect(url_for('auth.login'))
    
    return render_template('auth/reset_password.html', token=token)

@auth_bp.route('/force-password-change', methods=['GET', 'POST'])
def force_password_change():
    """Force password change for expired passwords"""
    user_id = session.get('user_id_for_password_reset')
    if not user_id:
        return redirect(url_for('auth.login'))
    
    user = User.query.get(user_id)
    if not user or not user.is_active:
        session.pop('user_id_for_password_reset', None)
        return redirect(url_for('auth.login'))
    
    if request.method == 'POST':
        current_password = request.form['current_password']
        new_password = request.form['new_password']
        confirm_password = request.form['confirm_password']
        
        if not user.check_password(current_password):
            flash('Current password is incorrect.', 'danger')
            return render_template('auth/force_password_change.html')
        
        if new_password != confirm_password:
            flash('New passwords do not match.', 'danger')
            return render_template('auth/force_password_change.html')
        
        # Check password strength
        strength_result = check_password_strength(new_password)
        if not strength_result['is_strong']:
            flash(f'Password is too weak: {strength_result["message"]}', 'danger')
            return render_template('auth/force_password_change.html')
        
        # Prevent reuse of recent passwords
        if user.previous_passwords:
            for old_hash in user.previous_passwords:
                if check_password_hash(old_hash, new_password):
                    flash('You cannot reuse a recent password.', 'danger')
                    return render_template('auth/force_password_change.html')
        
        # Update password
        old_password_hash = user.password_hash
        user.set_password(new_password)
        user.password_changed_at = datetime.now(timezone.utc)
        
        # Store old password (hashed) to prevent reuse
        if user.previous_passwords is None:
            user.previous_passwords = []
        user.previous_passwords.append(old_password_hash)
        
        # Keep only last 5 passwords
        if len(user.previous_passwords) > 5:
            user.previous_passwords = user.previous_passwords[-5:]
        
        # Log audit trail
        audit_log = AuditLog(
            user_id=user.id,
            action='PASSWORD_CHANGE_FORCED',
            ip_address=request.remote_addr,
            user_agent=request.user_agent.string
        )
        db.session.add(audit_log)
        
        # Security log
        security_log = SecurityLog(
            user_id=user.id,
            event_type='PASSWORD_CHANGED',
            ip_address=request.remote_addr,
            user_agent=request.user_agent.string
        )
        db.session.add(security_log)
        
        db.session.commit()
        
        session.pop('user_id_for_password_reset', None)
        flash('Password updated successfully. Please login again.', 'success')
        return redirect(url_for('auth.login'))
    
    return render_template('auth/force_password_change.html')

@auth_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    """User profile management"""
    if request.method == 'POST':
        try:
            # Update email
            new_email = request.form.get('email', '').strip()
            if new_email and new_email != current_user.email:
                if User.query.filter_by(email=new_email).first():
                    flash('Email already in use.', 'danger')
                else:
                    old_email = current_user.email
                    current_user.email = new_email
                    
                    # Update teacher/parent email if applicable
                    if current_user.role == 'teacher' and current_user.teacher_profile:
                        current_user.teacher_profile.email = new_email
                    elif current_user.role == 'parent' and current_user.parent_profile:
                        current_user.parent_profile.email = new_email
                    
                    flash('Email updated successfully.', 'success')
            
            # Update 2FA settings
            if 'enable_2fa' in request.form:
                current_user.two_factor_enabled = True
                if not current_user.two_factor_secret:
                    from middleware.security import generate_2fa_secret
                    current_user.two_factor_secret = generate_2fa_secret()
                flash('Two-factor authentication enabled.', 'success')
            elif 'disable_2fa' in request.form:
                current_user.two_factor_enabled = False
                flash('Two-factor authentication disabled.', 'success')
            
            # Update login notifications
            if 'login_notifications' in request.form:
                current_user.login_notifications = True
            else:
                current_user.login_notifications = False
            
            db.session.commit()
            
            # Security log for profile update
            security_log = SecurityLog(
                user_id=current_user.id,
                event_type='PROFILE_UPDATED',
                ip_address=request.remote_addr,
                user_agent=request.user_agent.string
            )
            db.session.add(security_log)
            db.session.commit()
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating profile: {str(e)}', 'danger')
    
    return render_template('auth/profile.html')

@auth_bp.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    """Change password for authenticated users"""
    if request.method == 'POST':
        try:
            current_password = request.form['current_password']
            new_password = request.form['new_password']
            confirm_password = request.form['confirm_password']
            
            if not current_user.check_password(current_password):
                flash('Current password is incorrect.', 'danger')
                return render_template('auth/change_password.html')
            
            if new_password != confirm_password:
                flash('New passwords do not match.', 'danger')
                return render_template('auth/change_password.html')
            
            # Check password strength
            strength_result = check_password_strength(new_password)
            if not strength_result['is_strong']:
                flash(f'Password is too weak: {strength_result["message"]}', 'danger')
                return render_template('auth/change_password.html')
            
            # Prevent reuse of recent passwords
            if current_user.previous_passwords:
                for old_hash in current_user.previous_passwords:
                    if check_password_hash(old_hash, new_password):
                        flash('You cannot reuse a recent password.', 'danger')
                        return render_template('auth/change_password.html')
            
            # Update password
            old_password_hash = current_user.password_hash
            current_user.set_password(new_password)
            current_user.password_changed_at = datetime.now(timezone.utc)
            
            # Store old password hash
            if current_user.previous_passwords is None:
                current_user.previous_passwords = []
            current_user.previous_passwords.append(old_password_hash)
            
            # Keep only last 5 passwords
            if len(current_user.previous_passwords) > 5:
                current_user.previous_passwords = current_user.previous_passwords[-5:]
            
            # Security log
            security_log = SecurityLog(
                user_id=current_user.id,
                event_type='PASSWORD_CHANGED',
                ip_address=request.remote_addr,
                user_agent=request.user_agent.string
            )
            db.session.add(security_log)
            
            db.session.commit()
            
            flash('Password changed successfully!', 'success')
            return redirect(url_for('auth.profile'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error changing password: {str(e)}', 'danger')
    
    return render_template('auth/change_password.html')

# Error handlers
@auth_bp.errorhandler(401)
def unauthorized_error(error):
    flash('Please log in to access this page.', 'warning')
    return redirect(url_for('auth.login'))

@auth_bp.errorhandler(403)
def forbidden_error(error):
    flash('You do not have permission to access this page.', 'danger')
    return redirect(url_for('auth.redirect_by_role'))

@auth_bp.errorhandler(404)
def not_found_error(error):
    return render_template('errors/404.html'), 404

@auth_bp.errorhandler(429)
def ratelimit_error(error):
    flash('Too many requests. Please slow down.', 'warning')
    return redirect(url_for('auth.login'))

@auth_bp.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('errors/500.html'), 500