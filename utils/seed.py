# app/utils/seed.py
from models import (
    db, User, AcademicSession, AcademicTerm, SystemConfiguration,
    GradeScale, SubjectCategory
)
from werkzeug.security import generate_password_hash
from datetime import datetime, timedelta, timezone

def create_default_finance_admin():
    """Create default finance admin user if not exists"""
    finance_admin = User.query.filter_by(username='finance_admin').first()
    if finance_admin:
        return False

    finance_admin = User(
        username='finance_admin',
        email='finance_admin@arndaleacademy.edu',
        role='finance_admin',
        is_active=True,
        created_at=datetime.now(timezone.utc)
    )
    finance_admin.set_password('finance123')  # Change this in production!

    db.session.add(finance_admin)
    db.session.commit()
    return True

def create_default_admin():
    """Create default admin user if not exists"""
    admin = User.query.filter_by(username='admin').first()
    if admin:
        return False
    
    admin = User(
        username='admin',
        email='admin@arndaleacademy.edu',
        role='admin',
        is_active=True,
        created_at=datetime.now(timezone.utc)
    )
    admin.set_password('admin123')  # Change this in production!
    
    db.session.add(admin)
    db.session.commit()
    return True

def create_default_academic_session():
    """Create default academic session if not exists"""
    session = AcademicSession.query.filter_by(is_active=True).first()
    if session:
        return False

    current_year = datetime.now().year
    session = AcademicSession(
        name=f"{current_year}/{current_year + 1}",
        start_date=datetime(current_year, 9, 1).date(),  # September 1st
        end_date=datetime(current_year + 1, 8, 31).date(),  # August 31st
        is_active=True
    )

    db.session.add(session)
    db.session.flush()  # ensures session.id is assigned before creating terms

    # Create terms for this session
    terms = [
        ('Autumn', 1, datetime(current_year, 9, 1), datetime(current_year, 12, 15)),
        ('Spring', 2, datetime(current_year, 1, 10), datetime(current_year, 4, 15)),
        ('Summer', 3, datetime(current_year, 4, 25), datetime(current_year, 7, 31))
    ]

    for name, term_number, start_date, end_date in terms:
        term = AcademicTerm(
            session_id=session.id,  # now session.id is valid
            name=name,
            term_number=term_number,
            start_date=start_date.date(),
            end_date=end_date.date(),
            is_active=(term_number == 1)  # Activate first term
        )
        db.session.add(term)

    db.session.commit()
    return True

def create_default_grade_scales():
    """Create default grade scales"""
    if GradeScale.query.count() > 0:
        return False
    
    grade_scales = [
        ('Excellent', 80, 100, 'A', 'Excellent', 5.0),
        ('Very Good', 70, 79, 'B', 'Very Good', 4.0),
        ('Good', 60, 69, 'C', 'Good', 3.0),
        ('Pass', 50, 59, 'D', 'Pass', 2.0),
        ('Fail', 0, 49, 'F', 'Fail', 0.0)
    ]
    
    for name, min_score, max_score, grade, remark, point in grade_scales:
        grade_scale = GradeScale(
            name=name,
            min_score=min_score,
            max_score=max_score,
            grade=grade,
            remark=remark,
            point=point,
            is_active=True
        )
        db.session.add(grade_scale)
    
    db.session.commit()
    return True

def create_default_subject_categories():
    """Create default subject categories"""
    if SubjectCategory.query.count() > 0:
        return False
    
    categories = [
        ('Core Subjects', 'Mandatory subjects for all students'),
        ('Electives', 'Optional subjects students can choose'),
        ('Languages', 'Language subjects'),
        ('Sciences', 'Science subjects'),
        ('Humanities', 'Humanities and social sciences'),
        ('Vocational', 'Vocational and technical subjects'),
        ('Extracurricular', 'Non-academic subjects')
    ]
    
    for name, description in categories:
        category = SubjectCategory(
            name=name,
            description=description,
            is_active=True
        )
        db.session.add(category)
    
    db.session.commit()
    return True

def create_default_system_config():
    """Create default system configuration"""
    configs = [
        ('school_name', 'Arndale Secondary School', 'School Name'),
        ('school_address', '123 Education Street, Knowledge City', 'School Address'),
        ('school_phone', '+234 123 456 7890', 'School Phone'),
        ('school_email', 'info@arndale.edu.ng', 'School Email'),
        ('academic_year_format', 'YYYY/YYYY', 'Academic Year Format'),
        ('default_password_policy', 'min_length:8,require_upper:true,require_lower:true,require_digits:true', 'Password Policy'),
        ('session_timeout', '30', 'Session timeout in minutes'),
        ('max_login_attempts', '5', 'Maximum login attempts before lock'),
        ('lockout_duration', '30', 'Lockout duration in minutes'),
        ('password_expiry_days', '90', 'Password expiry in days'),
        ('enable_2fa', 'false', 'Enable Two-Factor Authentication'),
        ('enable_captcha', 'true', 'Enable CAPTCHA for login'),
        ('report_card_template', 'default', 'Report card template'),
        ('attendance_marking', 'morning_afternoon', 'Attendance marking system'),
        ('grade_system', 'percentage', 'Grading system'),
        ('currency', 'NGN', 'Currency for fees'),
        ('timezone', 'Africa/Lagos', 'System timezone'),
        ('date_format', 'DD/MM/YYYY', 'Date format'),
        ('items_per_page', '20', 'Items per page in lists'),
        ('enable_parent_portal', 'true', 'Enable parent portal'),
        ('enable_sms_notifications', 'false', 'Enable SMS notifications'),
        ('enable_email_notifications', 'true', 'Enable email notifications'),
        ('exam_duration_default', '60', 'Default exam duration in minutes'),
        ('pass_mark_default', '40', 'Default pass mark percentage')
    ]
    
    for key, value, description in configs:
        existing = SystemConfiguration.query.filter_by(config_key=key).first()
        if not existing:
            config_item = SystemConfiguration(
                config_key=key,
                config_value=value,
                description=description,
                updated_by=1  # Admin user ID
            )
            db.session.add(config_item)
    
    db.session.commit()
    return True

def seed_all_data():
    """Seed all default data"""
    print("Seeding database...")
    
    create_default_admin()
    print("✓ Created default admin")
    
    create_default_academic_session()
    print("✓ Created default academic session and terms")
    
    create_default_grade_scales()
    print("✓ Created default grade scales")
    
    create_default_subject_categories()
    print("✓ Created default subject categories")
    
    create_default_system_config()
    print("✓ Created default system configuration")
    
    print("Database seeding completed!")