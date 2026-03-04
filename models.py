# app/models.py
from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
import uuid
from sqlalchemy.dialects.postgresql import JSONB

db = SQLAlchemy()

# =========================
# Core User Model
# =========================
class User(db.Model, UserMixin):
    __tablename__ = 'users'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # admin, teacher, student, parent
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime(timezone=True), default=datetime.now(timezone.utc))
    failed_login_attempts = db.Column(db.Integer, default=0)
    locked_until = db.Column(db.DateTime(timezone=True))
    last_login = db.Column(db.DateTime(timezone=True))

    # Profiles
    student_profile = db.relationship('Student', back_populates='user', uselist=False, cascade='all, delete-orphan')
    teacher_profile = db.relationship('Teacher', back_populates='user', uselist=False, cascade='all, delete-orphan')
    parent_profile = db.relationship('Parent', back_populates='user', uselist=False, cascade='all, delete-orphan')

    # Logs
    audit_logs = db.relationship('AuditLog', back_populates='user', cascade='all, delete-orphan')
    security_logs = db.relationship('SecurityLog', back_populates='user', cascade='all, delete-orphan')

    # Reports generated
    generated_reports = db.relationship('ReportCard', back_populates='generator', foreign_keys='ReportCard.generated_by')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def get_id(self):
        return str(self.id)

# =========================
# Academic Sessions & Terms
# =========================
class StudentPromotion(db.Model):
    __tablename__ = 'student_promotions'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    student_id = db.Column(db.String(36), db.ForeignKey('students.id'), nullable=False)
    from_class_id = db.Column(db.String(36), db.ForeignKey('classrooms.id'), nullable=False)
    to_class_id = db.Column(db.String(36), db.ForeignKey('classrooms.id'), nullable=False)
    academic_session_id = db.Column(db.String(36), db.ForeignKey('academic_sessions.id'), nullable=False)
    term = db.Column(db.Integer, nullable=False)
    promotion_type = db.Column(db.String(20), default='promotion')
    reason = db.Column(db.Text)
    promoted_by = db.Column(db.String(36), db.ForeignKey('users.id'))
    promoted_at = db.Column(db.DateTime(timezone=True), default=datetime.now(timezone.utc))
    
    # Relationships
    student = db.relationship('Student', back_populates='promotions')
    from_class = db.relationship('ClassRoom', foreign_keys=[from_class_id], back_populates='promotions_from')
    to_class = db.relationship('ClassRoom', foreign_keys=[to_class_id], back_populates='promotions_to')
    academic_session = db.relationship('AcademicSession', back_populates='promotions')
    promoter = db.relationship('User', foreign_keys=[promoted_by])

class AcademicSession(db.Model):
    __tablename__ = 'academic_sessions'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(50), unique=True, nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    is_active = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime(timezone=True), default=datetime.now(timezone.utc))

    terms = db.relationship(
        'AcademicTerm',
        back_populates='session',
        cascade='all, delete-orphan'
    )

    classrooms = db.relationship('ClassRoom', back_populates='academic_session', cascade='all, delete-orphan')

    promotions = db.relationship(
        'StudentPromotion',
        back_populates='academic_session',
        cascade='all, delete-orphan'
    )

class AcademicTerm(db.Model):
    __tablename__ = 'academic_terms'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = db.Column(db.String(36), db.ForeignKey('academic_sessions.id'), nullable=False)
    name = db.Column(db.String(50), nullable=False)
    term_number = db.Column(db.Integer, nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    is_active = db.Column(db.Boolean, default=False)

    # Assessment periods
    ca_start_date = db.Column(db.Date)
    ca_end_date = db.Column(db.Date)
    exam_start_date = db.Column(db.Date)
    exam_end_date = db.Column(db.Date)

    session = db.relationship('AcademicSession', back_populates='terms')
    subject_assignments = db.relationship('SubjectAssignment', back_populates='academic_term', cascade='all, delete-orphan')
    exams = db.relationship('Exam', back_populates='academic_term', cascade='all, delete-orphan')
    assessments = db.relationship('Assessment', back_populates='academic_term', cascade='all, delete-orphan')

    __table_args__ = (
        db.UniqueConstraint('session_id', 'term_number', name='unique_term_per_session'),
        db.UniqueConstraint('session_id', 'name', name='unique_term_name_per_session'),
    )

# =========================
# Parent & Student
# =========================
class Parent(db.Model):
    __tablename__ = 'parents'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), unique=True)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    email = db.Column(db.String(120))
    address = db.Column(db.Text)
    occupation = db.Column(db.String(100))

    user = db.relationship('User', back_populates='parent_profile')
    student_links = db.relationship('StudentParent', back_populates='parent', cascade='all, delete-orphan')
    notifications = db.relationship('ParentNotification', back_populates='parent', cascade='all, delete-orphan')

class StudentParent(db.Model):
    __tablename__ = 'student_parents'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    student_id = db.Column(db.String(36), db.ForeignKey('students.id'), nullable=False)
    parent_id = db.Column(db.String(36), db.ForeignKey('parents.id'), nullable=False)
    relationship = db.Column(db.String(50))
    is_primary = db.Column(db.Boolean, default=False)

    student = db.relationship('Student', back_populates='parent_links')
    parent = db.relationship('Parent', back_populates='student_links')

    __table_args__ = (
        db.UniqueConstraint('student_id', 'parent_id', name='unique_student_parent'),
    )

class Student(db.Model):
    __tablename__ = 'students'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), unique=True)
    admission_number = db.Column(db.String(20), unique=True, nullable=False)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    middle_name = db.Column(db.String(50))
    date_of_birth = db.Column(db.Date)
    gender = db.Column(db.String(10))
    address = db.Column(db.Text)
    photo = db.Column(db.String(255))
    
    # Parent information (direct fields for simplicity)
    parent_name = db.Column(db.String(100))
    parent_phone = db.Column(db.String(20))
    parent_email = db.Column(db.String(120))
    parent_occupation = db.Column(db.String(100))
    
    current_class_id = db.Column(db.String(36), db.ForeignKey('classrooms.id'))
    enrollment_date = db.Column(db.Date, default=datetime.now(timezone.utc))
    is_active = db.Column(db.Boolean, default=True)
    academic_status = db.Column(db.String(20), default='active')

    user = db.relationship('User', back_populates='student_profile')
    classroom = db.relationship('ClassRoom', back_populates='class_students', foreign_keys=[current_class_id])
    parent_links = db.relationship('StudentParent', back_populates='student', cascade='all, delete-orphan')
    assessments = db.relationship('StudentAssessment', back_populates='student', cascade='all, delete-orphan')
    domain_evaluations = db.relationship('DomainEvaluation', back_populates='student', cascade='all, delete-orphan')
    exam_results = db.relationship('ExamResult', back_populates='student', cascade='all, delete-orphan')
    promotions = db.relationship('StudentPromotion', back_populates='student', cascade='all, delete-orphan')
    attendance_records = db.relationship('Attendance', back_populates='student', cascade='all, delete-orphan')
    exam_sessions = db.relationship('ExamSession', back_populates='student', cascade='all, delete-orphan')
    teacher_comments = db.relationship('TeacherComment', back_populates='student', cascade='all, delete-orphan')
    form_teacher_comments = db.relationship('FormTeacherComment', back_populates='student', cascade='all, delete-orphan')
    principal_remarks = db.relationship('PrincipalRemark', back_populates='student', cascade='all, delete-orphan')
    report_cards = db.relationship('ReportCard', back_populates='student', cascade='all, delete-orphan')
    notifications = db.relationship('ParentNotification', back_populates='student', cascade='all, delete-orphan')


# =========================
# Classroom
# =========================
class ClassRoom(db.Model):
    __tablename__ = 'classrooms'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    academic_session_id = db.Column(db.String(36), db.ForeignKey('academic_sessions.id'))
    name = db.Column(db.String(50), nullable=False)
    level = db.Column(db.String(50))  # Nursery, Primary, Secondary, etc.
    section = db.Column(db.String(10))  # A, B, C, etc.
    max_students = db.Column(db.Integer, default=40)
    room_number = db.Column(db.String(20))
    form_teacher_id = db.Column(db.String(36), db.ForeignKey('teachers.id'))

    # Relationships
    academic_session = db.relationship('AcademicSession', back_populates='classrooms')
    subject_assignments = db.relationship('SubjectAssignment', back_populates='classroom', cascade='all, delete-orphan')
    class_students = db.relationship('Student', back_populates='classroom', foreign_keys='Student.current_class_id', cascade='all, delete-orphan')
    exams = db.relationship('Exam', back_populates='classroom', cascade='all, delete-orphan')
    attendance_records = db.relationship('Attendance', back_populates='classroom', cascade='all, delete-orphan')
    promotions_from = db.relationship('StudentPromotion', back_populates='from_class', foreign_keys='StudentPromotion.from_class_id', cascade='all, delete-orphan')
    promotions_to = db.relationship('StudentPromotion', back_populates='to_class', foreign_keys='StudentPromotion.to_class_id', cascade='all, delete-orphan')

# =========================
# Subjects & Assignments
# =========================
class Subject(db.Model):
    __tablename__ = 'subjects'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(100), nullable=False)
    code = db.Column(db.String(20), unique=True, nullable=False)
    description = db.Column(db.Text)
    category = db.Column(db.String(50))  # Core, Elective
    is_active = db.Column(db.Boolean, default=True)
    assessment_structure = db.Column(JSONB)  # Add these fields for grading
    pass_mark = db.Column(db.Float, default=40.0)
    max_mark = db.Column(db.Float, default=100.0)

    subject_assignments = db.relationship('SubjectAssignment', back_populates='subject', cascade='all, delete-orphan')
    question_banks = db.relationship('QuestionBank', back_populates='subject', cascade='all, delete-orphan')
    exams = db.relationship('Exam', back_populates='subject', cascade='all, delete-orphan')
    exam_results = db.relationship('ExamResult', back_populates='subject', cascade='all, delete-orphan')
    teacher_comments = db.relationship('TeacherComment', back_populates='subject', cascade='all, delete-orphan')

class SubjectAssignment(db.Model):
    __tablename__ = 'subject_assignments'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    teacher_id = db.Column(db.String(36), db.ForeignKey('teachers.id'), nullable=False)
    subject_id = db.Column(db.String(36), db.ForeignKey('subjects.id'), nullable=False)
    class_id = db.Column(db.String(36), db.ForeignKey('classrooms.id'), nullable=False)
    academic_term_id = db.Column(db.String(36), db.ForeignKey('academic_terms.id'), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime(timezone=True), default=datetime.now(timezone.utc))

    teacher = db.relationship('Teacher', back_populates='subject_assignments')
    subject = db.relationship('Subject', back_populates='subject_assignments')
    classroom = db.relationship('ClassRoom', back_populates='subject_assignments')
    academic_term = db.relationship('AcademicTerm', back_populates='subject_assignments')

    __table_args__ = (db.UniqueConstraint('teacher_id', 'subject_id', 'class_id', 'academic_term_id',name='unique_subject_assignment'),)

# =========================
# Question Bank
# =========================
class QuestionBank(db.Model):
    __tablename__ = 'question_banks'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    subject_id = db.Column(db.String(36), db.ForeignKey('subjects.id'), nullable=False)
    teacher_id = db.Column(db.String(36), db.ForeignKey('teachers.id'), nullable=False)
    question_text = db.Column(db.Text, nullable=False)
    question_type = db.Column(db.String(20), nullable=False)
    difficulty = db.Column(db.String(20), default='medium')
    marks = db.Column(db.Float, default=1.0)
    options = db.Column(JSONB)
    correct_answer = db.Column(db.Text)
    explanation = db.Column(db.Text)
    topics = db.Column(JSONB)
    
    # Add these image fields
    question_image = db.Column(db.String(500))  # Path to question image
    question_image_alt = db.Column(db.String(200))  # Alt text for accessibility
    
    created_by = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=True)
    approved_by = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=True)
    is_approved = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime(timezone=True), default=datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime(timezone=True), default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))
    usage_count = db.Column(db.Integer, default=0)
    last_used = db.Column(db.DateTime(timezone=True))

    subject = db.relationship('Subject', back_populates='question_banks')
    teacher = db.relationship('Teacher', back_populates='question_banks', foreign_keys=[teacher_id])
    creator = db.relationship('User', foreign_keys=[created_by], backref='created_questions')
    approver = db.relationship('User', foreign_keys=[approved_by], backref='approved_questions')
    exam_questions = db.relationship('ExamQuestion', back_populates='question', cascade='all, delete-orphan')
    
# =========================
# Teacher
# =========================
class Teacher(db.Model):
    __tablename__ = 'teachers'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), unique=True)
    staff_id = db.Column(db.String(20), unique=True, nullable=False)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(120))
    phone = db.Column(db.String(20))
    qualification = db.Column(db.String(100))
    specialization = db.Column(db.String(100))
    address = db.Column(db.Text)
    form_class_id = db.Column(db.String(36), db.ForeignKey('classrooms.id'))
    created_at = db.Column(db.DateTime(timezone=True), default=datetime.now(timezone.utc))

    @property
    def form_class(self):
        """Get the form class object"""
        if self.form_class_id:
            return db.session.get(ClassRoom, self.form_class_id)
        return None
    
    # Relationships
    user = db.relationship('User', back_populates='teacher_profile')
    student_assessments = db.relationship('StudentAssessment', back_populates='teacher', cascade='all, delete-orphan')
    
    # Explicitly specify which foreign key to use
    form_class_assignment = db.relationship('ClassRoom',
                                            foreign_keys=[form_class_id],
                                            backref='form_teacher',  # Use backref to avoid bidirectional issues
                                            uselist=False  # One-to-one relationship
                                            )
    
    subject_assignments = db.relationship('SubjectAssignment', back_populates='teacher', cascade='all, delete-orphan')
    exams = db.relationship('Exam', back_populates='teacher', cascade='all, delete-orphan')
    exam_sessions = db.relationship('ExamSession', back_populates='teacher', cascade='all, delete-orphan')
    question_banks = db.relationship('QuestionBank', back_populates='teacher', cascade='all, delete-orphan')
    attendance_records = db.relationship('Attendance', back_populates='teacher', cascade='all, delete-orphan')
    student_assessments = db.relationship('StudentAssessment', back_populates='teacher', cascade='all, delete-orphan')
    exam_results_entered = db.relationship('ExamResult', back_populates='teacher', cascade='all, delete-orphan')
    domain_evaluations = db.relationship('DomainEvaluation', back_populates='teacher', cascade='all, delete-orphan')
    teacher_comments = db.relationship('TeacherComment', back_populates='teacher', cascade='all, delete-orphan')
    form_teacher_comments = db.relationship('FormTeacherComment', back_populates='form_teacher', cascade='all, delete-orphan')


# =========================
# Exams & Questions
# =========================
class Exam(db.Model):
    __tablename__ = 'exams'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(200), nullable=False)
    subject_id = db.Column(db.String(36), db.ForeignKey('subjects.id'), nullable=False)
    teacher_id = db.Column(db.String(36), db.ForeignKey('teachers.id'), nullable=False)
    class_id = db.Column(db.String(36), db.ForeignKey('classrooms.id'), nullable=False)
    academic_term_id = db.Column(db.String(36), db.ForeignKey('academic_terms.id'), nullable=False)
    duration_minutes = db.Column(db.Integer, nullable=False)
    total_marks = db.Column(db.Float, nullable=False)
    
    # Add these missing fields
    pass_mark = db.Column(db.Float, default=0.0)
    instructions = db.Column(db.Text)
    scheduled_start = db.Column(db.DateTime(timezone=True))
    scheduled_end = db.Column(db.DateTime(timezone=True))
    status = db.Column(db.String(20), default='draft')  # draft, scheduled, active, completed
    is_randomized = db.Column(db.Boolean, default=False)
    shuffle_questions = db.Column(db.Boolean, default=False)
    shuffle_options = db.Column(db.Boolean, default=False)
    access_code = db.Column(db.String(50))
    allow_back_navigation = db.Column(db.Boolean, default=True)
    show_results_immediately = db.Column(db.Boolean, default=True)
    
    created_at = db.Column(db.DateTime(timezone=True), default=datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime(timezone=True), default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))

    # Relationships
    teacher = db.relationship('Teacher', back_populates='exams')
    subject = db.relationship('Subject', back_populates='exams')
    classroom = db.relationship('ClassRoom', back_populates='exams')
    academic_term = db.relationship('AcademicTerm', back_populates='exams')
    exam_questions = db.relationship('ExamQuestion', back_populates='exam', cascade='all, delete-orphan')
    exam_sessions = db.relationship('ExamSession', back_populates='exam', cascade='all, delete-orphan')

class ExamQuestion(db.Model):
    __tablename__ = 'exam_questions'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    exam_id = db.Column(db.String(36), db.ForeignKey('exams.id'), nullable=False)
    question_bank_id = db.Column(db.String(36), db.ForeignKey('question_banks.id'), nullable=False)
    order = db.Column(db.Integer)
    marks = db.Column(db.Float)

    exam = db.relationship('Exam', back_populates='exam_questions')
    question = db.relationship('QuestionBank', back_populates='exam_questions')
    responses = db.relationship('ExamResponse', back_populates='exam_question', cascade='all, delete-orphan')

class ExamSession(db.Model):
    __tablename__ = 'exam_sessions'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    exam_id = db.Column(db.String(36), db.ForeignKey('exams.id'), nullable=False)
    student_id = db.Column(db.String(36), db.ForeignKey('students.id'), nullable=False)
    teacher_id = db.Column(db.String(36), db.ForeignKey('teachers.id'), nullable=False)
    start_time = db.Column(db.DateTime(timezone=True))
    end_time = db.Column(db.DateTime(timezone=True))
    status = db.Column(db.String(20), default='scheduled')
    created_at = db.Column(db.DateTime(timezone=True), default=datetime.now(timezone.utc))

    exam = db.relationship('Exam', back_populates='exam_sessions')
    student = db.relationship('Student', back_populates='exam_sessions')
    teacher = db.relationship('Teacher', back_populates='exam_sessions')
    responses = db.relationship('ExamResponse', back_populates='exam_session', cascade='all, delete-orphan')

class ExamResponse(db.Model):
    __tablename__ = 'exam_responses'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    exam_session_id = db.Column(db.String(36), db.ForeignKey('exam_sessions.id'), nullable=False)
    exam_question_id = db.Column(db.String(36), db.ForeignKey('exam_questions.id'), nullable=False)
    question_bank_id = db.Column(db.String(36), db.ForeignKey('question_banks.id'), nullable=False)
    
    # Answer fields
    answer = db.Column(db.Text)
    selected_option_index = db.Column(db.Integer)  # Index of selected option for multiple choice
    original_option_index = db.Column(db.Integer)  # Original index for shuffled options
    
    # Grading fields
    is_correct = db.Column(db.Boolean)  # True/False/None (None = needs manual grading)
    marks_awarded = db.Column(db.Float, default=0.0)
    correct_answer = db.Column(db.Text)  # Store the correct answer for reference
    
    # Timing fields
    timestamp = db.Column(db.DateTime(timezone=True), default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))
    save_type = db.Column(db.String(20), default='manual')  # 'manual', 'auto', 'final'
    response_time = db.Column(db.DateTime(timezone=True))  # When the response was made
    
    # Relationships
    exam_session = db.relationship('ExamSession', back_populates='responses')
    exam_question = db.relationship('ExamQuestion', back_populates='responses')
    question = db.relationship('QuestionBank', foreign_keys=[question_bank_id])

# =========================
# Assessments & Scores
# =========================
class Assessment(db.Model):
    __tablename__ = 'assessments'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    academic_term_id = db.Column(db.String(36), db.ForeignKey('academic_terms.id'), nullable=False)
    assessment_type = db.Column(db.String(50), nullable=False)  # Test, Assignment, Exam, etc.
    weight = db.Column(db.Float, default=1.0)
    max_score = db.Column(db.Float, default=100.0)
    order = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)

    academic_term = db.relationship('AcademicTerm', back_populates='assessments')
    #student_scores = db.relationship('StudentAssessment', back_populates='assessment', cascade='all, delete-orphan')

    __table_args__ = (
        db.UniqueConstraint('academic_term_id', 'assessment_type', name='unique_term_assessment_type'),
    )

class StudentAssessment(db.Model):
    __tablename__ = 'student_assessments'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    student_id = db.Column(db.String(36), db.ForeignKey('students.id'), nullable=False)
    subject_id = db.Column(db.String(36), db.ForeignKey('subjects.id'), nullable=False)
    class_id = db.Column(db.String(36), db.ForeignKey('classrooms.id'), nullable=False)
    term_id = db.Column(db.String(36), db.ForeignKey('academic_terms.id'), nullable=False)
    
    # CHANGED: Store all assessment scores in JSON format
    assessment_scores = db.Column(JSONB, nullable=False, default=dict)  # Format: {assessment_id: score_value}
    
    # Add a total score field for easy access
    total_score = db.Column(db.Float, default=0.0)
    average_score = db.Column(db.Float, default=0.0)
    
    # Metadata
    entered_by = db.Column(db.String(36), db.ForeignKey('teachers.id'))
    entered_at = db.Column(db.DateTime(timezone=True), default=datetime.now(timezone.utc))
    is_approved = db.Column(db.Boolean, default=False)
    approved_by = db.Column(db.String(36), db.ForeignKey('users.id'))
    approved_at = db.Column(db.DateTime(timezone=True))
    updated_at = db.Column(db.DateTime(timezone=True), default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))

    # Relationships
    student = db.relationship('Student', back_populates='assessments')
    subject = db.relationship('Subject')
    classroom = db.relationship('ClassRoom')
    teacher = db.relationship('Teacher', back_populates='student_assessments', foreign_keys=[entered_by])
    approver = db.relationship('User', foreign_keys=[approved_by])

    def get_score_for_assessment(self, assessment_id):
        """Get score for a specific assessment"""
        return self.assessment_scores.get(str(assessment_id))
    
    def set_score_for_assessment(self, assessment_id, score):
        """Set score for a specific assessment and update totals"""
        self.assessment_scores[str(assessment_id)] = float(score)
        self.update_totals()
        self.updated_at = datetime.now(timezone.utc)
    
    def update_totals(self):
        """Update total and average scores"""
        scores = list(self.assessment_scores.values())
        self.total_score = sum(scores)
        self.average_score = sum(scores) / len(scores) if scores else 0.0
    
    def get_assessment_scores_list(self):
        """Convert assessment_scores dict to list format for frontend"""
        return [
            {
                'assessment_id': assessment_id,
                'score': score
            }
            for assessment_id, score in self.assessment_scores.items()
        ]
    
    # Add relationship to assessment for easy querying (optional)
    #assessment_relations = db.relationship('Assessment', 
    #                                     secondary='assessment_score_mappings',
    #                                     backref='student_assessment_records')

    __table_args__ = (
        db.UniqueConstraint('student_id', 'subject_id', 'class_id', 'term_id',
                           name='unique_student_assessment_record'),
    )

class AssessmentScoreMapping(db.Model):
    __tablename__ = 'assessment_score_mappings'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    student_assessment_id = db.Column(db.String(36), db.ForeignKey('student_assessments.id'), nullable=False)
    assessment_id = db.Column(db.String(36), db.ForeignKey('assessments.id'), nullable=False)
    
    # Individual score for this assessment
    score = db.Column(db.Float, nullable=False)
    
    # Metadata
    created_at = db.Column(db.DateTime(timezone=True), default=datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime(timezone=True), default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))
    
    __table_args__ = (
        db.UniqueConstraint('student_assessment_id', 'assessment_id', 
                           name='unique_assessment_score_mapping'),
    )
   
# =========================
# Exam Results & Evaluations
# =========================
class ExamResult(db.Model):
    __tablename__ = 'exam_results'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # Existing fields
    student_id = db.Column(db.String(36), db.ForeignKey('students.id'), nullable=False)
    subject_id = db.Column(db.String(36), db.ForeignKey('subjects.id'), nullable=False)
    term = db.Column(db.Integer, nullable=False)
    academic_year = db.Column(db.String(20), nullable=False)
    exam_score = db.Column(db.Float, nullable=False)
    ca_score = db.Column(db.Float)
    total_score = db.Column(db.Float)
    grade = db.Column(db.String(5))
    remark = db.Column(db.String(100))
    position_in_class = db.Column(db.Integer)
    entered_by = db.Column(db.String(36), db.ForeignKey('teachers.id'))
    is_locked = db.Column(db.Boolean, default=False)
    
    # NEW: Add exam session reference
    exam_session_id = db.Column(db.String(36), db.ForeignKey('exam_sessions.id'))
    
    # Optional: Add exam-specific fields if needed
    exam_id = db.Column(db.String(36), db.ForeignKey('exams.id'))
    percentage = db.Column(db.Float)
    passed = db.Column(db.Boolean, default=False)
    submitted_at = db.Column(db.DateTime(timezone=True), default=datetime.now(timezone.utc))
    
    # Relationships
    student = db.relationship('Student', back_populates='exam_results')
    subject = db.relationship('Subject', back_populates='exam_results')
    teacher = db.relationship('Teacher', back_populates='exam_results_entered')
    
    # NEW: Relationship with exam session
    exam_session = db.relationship('ExamSession', backref='exam_result')
    exam = db.relationship('Exam', backref='exam_results')

class Attendance(db.Model):
    __tablename__ = 'attendance'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    student_id = db.Column(db.String(36), db.ForeignKey('students.id'), nullable=False)
    classroom_id = db.Column(db.String(36), db.ForeignKey('classrooms.id'), nullable=False)
    teacher_id = db.Column(db.String(36), db.ForeignKey('teachers.id'), nullable=False)
    
    # ADD THESE REQUIRED FIELDS
    date = db.Column(db.Date, nullable=False, default=datetime.now(timezone.utc).date())
    status = db.Column(db.String(20), nullable=False, default='present')  # present, absent, late, excused
    session = db.Column(db.String(20))  # morning, afternoon, full_day
    remark = db.Column(db.String(200))  # Optional: Reason for absence/lateness
    
    # Timestamps
    recorded_at = db.Column(db.DateTime(timezone=True), default=datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime(timezone=True), default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))
    
    # Relationships
    student = db.relationship('Student', back_populates='attendance_records')
    classroom = db.relationship('ClassRoom', back_populates='attendance_records')
    teacher = db.relationship('Teacher', back_populates='attendance_records')

class DomainEvaluation(db.Model):
    __tablename__ = 'domain_evaluations'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    student_id = db.Column(db.String(36), db.ForeignKey('students.id'), nullable=False)
    domain_type = db.Column(db.String(50), nullable=False)  # Affective, Psychomotor, Cognitive
    term = db.Column(db.Integer, nullable=False)
    academic_year = db.Column(db.String(20), nullable=False)
    evaluation_data = db.Column(JSONB)  # Add this field - store criteria ratings
    average_score = db.Column(db.Float)  # Add this field
    comments = db.Column(db.Text)
    total_criteria = db.Column(db.Integer)  # Add this field
    evaluated_criteria = db.Column(db.Integer)  # Add this field
    class_id = db.Column(db.String(36), db.ForeignKey('classrooms.id'))  # Add this field
    evaluated_by = db.Column(db.String(36), db.ForeignKey('teachers.id'))
    evaluated_at = db.Column(db.DateTime(timezone=True), default=datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime(timezone=True), default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))

    student = db.relationship('Student', back_populates='domain_evaluations')
    teacher = db.relationship('Teacher', back_populates='domain_evaluations')
    classroom = db.relationship('ClassRoom')  # Add this relationship

    __table_args__ = (
        db.UniqueConstraint('student_id', 'domain_type', 'term', 'academic_year', 
                           name='unique_domain_evaluation'),
    )

# =========================
# Comments, Report Cards & Notifications
# =========================
class TeacherComment(db.Model):
    __tablename__ = 'teacher_comments'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    student_id = db.Column(db.String(36), db.ForeignKey('students.id'), nullable=False)
    teacher_id = db.Column(db.String(36), db.ForeignKey('teachers.id'), nullable=False)
    subject_id = db.Column(db.String(36), db.ForeignKey('subjects.id'), nullable=False)
    term = db.Column(db.Integer, nullable=False)
    academic_year = db.Column(db.String(20), nullable=False)
    comment = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=datetime.now(timezone.utc))

    student = db.relationship('Student', back_populates='teacher_comments')
    teacher = db.relationship('Teacher', back_populates='teacher_comments')
    subject = db.relationship('Subject', back_populates='teacher_comments')

class FormTeacherComment(db.Model):
    __tablename__ = 'form_teacher_comments'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    student_id = db.Column(db.String(36), db.ForeignKey('students.id'), nullable=False)
    form_teacher_id = db.Column(db.String(36), db.ForeignKey('teachers.id'), nullable=False)
    term = db.Column(db.Integer, nullable=False)
    academic_year = db.Column(db.String(20), nullable=False)
    comment = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=datetime.now(timezone.utc))

    student = db.relationship('Student', back_populates='form_teacher_comments')
    form_teacher = db.relationship('Teacher', back_populates='form_teacher_comments')

class PrincipalRemark(db.Model):
    __tablename__ = 'principal_remarks'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    student_id = db.Column(db.String(36), db.ForeignKey('students.id'), nullable=False)
    term = db.Column(db.Integer, nullable=False)
    academic_year = db.Column(db.String(20), nullable=False)
    remark = db.Column(db.Text, nullable=False)
    signed_by = db.Column(db.String(100))
    created_at = db.Column(db.DateTime(timezone=True), default=datetime.now(timezone.utc))

    student = db.relationship('Student', back_populates='principal_remarks')

class ReportCard(db.Model):
    __tablename__ = 'report_cards'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    student_id = db.Column(db.String(36), db.ForeignKey('students.id'), nullable=False)
    term = db.Column(db.Integer, nullable=False)
    academic_year = db.Column(db.String(20), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)
    generated_at = db.Column(db.DateTime(timezone=True), default=datetime.now(timezone.utc))
    generated_by = db.Column(db.String(36), db.ForeignKey('users.id'))
    is_published = db.Column(db.Boolean, default=False)
    published_at = db.Column(db.DateTime(timezone=True))
    report_data = db.Column(JSONB)

    student = db.relationship('Student', back_populates='report_cards')
    generator = db.relationship('User', foreign_keys=[generated_by])

class ParentNotification(db.Model):
    __tablename__ = 'parent_notifications'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    parent_id = db.Column(db.String(36), db.ForeignKey('parents.id'), nullable=False)
    student_id = db.Column(db.String(36), db.ForeignKey('students.id'), nullable=False)
    notification_type = db.Column(db.String(50), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    is_sent = db.Column(db.Boolean, default=False)
    sent_via = db.Column(JSONB)
    created_at = db.Column(db.DateTime(timezone=True), default=datetime.now(timezone.utc))
    read_at = db.Column(db.DateTime(timezone=True))

    parent = db.relationship('Parent', back_populates='notifications')
    student = db.relationship('Student', back_populates='notifications')

# =========================
# System Config & Audit
# =========================
class SystemConfiguration(db.Model):
    __tablename__ = 'system_configuration'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    config_key = db.Column(db.String(100), unique=True, nullable=False)
    config_value = db.Column(JSONB, nullable=False)
    description = db.Column(db.Text)
    updated_at = db.Column(db.DateTime(timezone=True), default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))
    updated_by = db.Column(db.String(36), db.ForeignKey('users.id'))

    updater = db.relationship('User', foreign_keys=[updated_by])

    # Helper methods for specific configs
    @staticmethod
    def get_principal_signature():
        config = db.session.query(SystemConfiguration).filter_by(
            config_key='principal_signature'
        ).first()
        if config and config.config_value:
            return config.config_value.get('signature_path', '')
        return ''

    @staticmethod
    def get_resumption_date():
        config = db.session.query(SystemConfiguration).filter_by(
            config_key='resumption_date'
        ).first()
        if config and config.config_value:
            return config.config_value.get('date', '')
        return ''

    @staticmethod
    def update_principal_signature(signature_path, updated_by_user_id):
        config = db.session.query(SystemConfiguration).filter_by(
            config_key='principal_signature'
        ).first()
        
        if not config:
            config = SystemConfiguration(
                config_key='principal_signature',
                config_value={'signature_path': signature_path},
                description='Principal digital signature for report cards',
                updated_by=updated_by_user_id
            )
            db.session.add(config)
        else:
            config.config_value = {'signature_path': signature_path}
            config.updated_by = updated_by_user_id
        
        db.session.commit()
        return config

    @staticmethod
    def update_resumption_date(date_str, updated_by_user_id):
        config = db.session.query(SystemConfiguration).filter_by(
            config_key='resumption_date'
        ).first()
        
        if not config:
            config = SystemConfiguration(
                config_key='resumption_date',
                config_value={'date': date_str},
                description='Next term resumption date for report cards',
                updated_by=updated_by_user_id
            )
            db.session.add(config)
        else:
            config.config_value = {'date': date_str}
            config.updated_by = updated_by_user_id
        
        db.session.commit()
        return config
    
class AuditLog(db.Model):
    __tablename__ = 'audit_logs'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'))
    action = db.Column(db.String(100), nullable=False)
    table_name = db.Column(db.String(100))
    record_id = db.Column(db.String(36))
    old_values = db.Column(JSONB)
    new_values = db.Column(JSONB)
    details = db.Column(JSONB)  # Add this field
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.Text)
    timestamp = db.Column(db.DateTime(timezone=True), default=datetime.now(timezone.utc))

    user = db.relationship('User', back_populates='audit_logs')

class LoginAttempt(db.Model):
    __tablename__ = 'login_attempts'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    username = db.Column(db.String(80))
    ip_address = db.Column(db.String(45))
    successful = db.Column(db.Boolean, default=False)
    user_agent = db.Column(db.Text)
    timestamp = db.Column(db.DateTime(timezone=True), default=datetime.now(timezone.utc))

    __table_args__ = (
        db.Index('idx_login_ip_time', 'ip_address', 'timestamp'),
        db.Index('idx_login_username_time', 'username', 'timestamp'),
    )

class SecurityLog(db.Model):
    __tablename__ = 'security_logs'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    event_type = db.Column(db.String(50), nullable=False)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'))
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.Text)
    details = db.Column(JSONB)
    timestamp = db.Column(db.DateTime(timezone=True), default=datetime.now(timezone.utc))

    user = db.relationship('User', back_populates='security_logs')

# =========================
# Reference Tables
# =========================
class GradeScale(db.Model):
    __tablename__ = 'grade_scales'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(50), nullable=False)
    min_score = db.Column(db.Float, nullable=False)
    max_score = db.Column(db.Float, nullable=False)
    grade = db.Column(db.String(5), nullable=False)
    remark = db.Column(db.String(100))
    point = db.Column(db.Float)
    is_active = db.Column(db.Boolean, default=True)

    __table_args__ = (
        db.UniqueConstraint('name', 'min_score', 'max_score', name='unique_grade_range'),
    )

class SubjectCategory(db.Model):
    __tablename__ = 'subject_categories'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(50), unique=True, nullable=False)
    description = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)


# =========================
# E-Library / Learning Materials
# =========================
class LearningMaterial(db.Model):
    __tablename__ = 'learning_materials'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    
    # Subject and Class information
    subject_id = db.Column(db.String(36), db.ForeignKey('subjects.id'), nullable=False)
    class_id = db.Column(db.String(36), db.ForeignKey('classrooms.id'), nullable=False)
    
    # Upload information
    teacher_id = db.Column(db.String(36), db.ForeignKey('teachers.id'), nullable=False)
    file_path = db.Column(db.String(500))  # For file uploads
    file_type = db.Column(db.String(50))   # pdf, doc, ppt, video, etc.
    file_size = db.Column(db.Integer)      # In bytes
    
    # For notes/links without files
    content = db.Column(db.Text)           # HTML content for notes
    external_link = db.Column(db.String(500))  # Link to external resource
    
    # Metadata
    material_type = db.Column(db.String(50), default='note')  # note, assignment, video, link, etc.
    tags = db.Column(JSONB)  # Array of tags for filtering
    is_published = db.Column(db.Boolean, default=True)
    is_featured = db.Column(db.Boolean, default=False)
    
    # Access control
    accessible_to = db.Column(db.String(20), default='class')  # class, subject, all
    
    # Stats
    download_count = db.Column(db.Integer, default=0)
    view_count = db.Column(db.Integer, default=0)
    
    # Timestamps
    created_at = db.Column(db.DateTime(timezone=True), default=datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime(timezone=True), default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))
    published_at = db.Column(db.DateTime(timezone=True))
    
    # Relationships
    subject = db.relationship('Subject', backref='learning_materials')
    classroom = db.relationship('ClassRoom', backref='learning_materials')
    teacher = db.relationship('Teacher', backref='uploaded_materials')
    
    # Student downloads tracking
    student_downloads = db.relationship('StudentMaterialDownload', 
                                       back_populates='material', 
                                       cascade='all, delete-orphan')

class StudentMaterialDownload(db.Model):
    __tablename__ = 'student_material_downloads'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    student_id = db.Column(db.String(36), db.ForeignKey('students.id'), nullable=False)
    material_id = db.Column(db.String(36), db.ForeignKey('learning_materials.id'), nullable=False)
    downloaded_at = db.Column(db.DateTime(timezone=True), default=datetime.now(timezone.utc))
    
    # Relationships
    student = db.relationship('Student', backref='downloaded_materials')
    material = db.relationship('LearningMaterial', back_populates='student_downloads')

    __table_args__ = (
        db.UniqueConstraint('student_id', 'material_id', name='unique_student_download'),
    )


# =========================
# AI Analysis & Reports
# =========================
class ExamQuestionAnalysis(db.Model):
    __tablename__ = 'exam_question_analysis'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    exam_id = db.Column(db.String(36), db.ForeignKey('exams.id'), nullable=False)
    question_bank_id = db.Column(db.String(36), db.ForeignKey('question_banks.id'), nullable=False)
    
    # Analysis data
    total_attempts = db.Column(db.Integer, default=0)
    correct_attempts = db.Column(db.Integer, default=0)
    incorrect_attempts = db.Column(db.Integer, default=0)
    average_time_spent = db.Column(db.Float)  # in seconds
    difficulty_rating = db.Column(db.Float)  # 1-10 scale
    common_mistakes = db.Column(JSONB)
    learning_gaps = db.Column(JSONB)
    
    # Timestamps
    analyzed_at = db.Column(db.DateTime(timezone=True), default=datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime(timezone=True), default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))
    
    # Relationships
    exam = db.relationship('Exam', backref='question_analyses')
    question = db.relationship('QuestionBank', backref='analyses')

class StudentPerformanceAnalysis(db.Model):
    __tablename__ = 'student_performance_analysis'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    student_id = db.Column(db.String(36), db.ForeignKey('students.id'), nullable=False)
    exam_id = db.Column(db.String(36), db.ForeignKey('exams.id'), nullable=False)
    subject_id = db.Column(db.String(36), db.ForeignKey('subjects.id'), nullable=False)
    
    # Performance metrics
    overall_score = db.Column(db.Float)
    percentile = db.Column(db.Float)
    time_management_score = db.Column(db.Float)  # 1-10 scale
    accuracy_rate = db.Column(db.Float)
    completion_rate = db.Column(db.Float)
    
    # AI-generated insights
    strengths = db.Column(JSONB)  # List of strengths
    weaknesses = db.Column(JSONB)  # List of weaknesses
    recommendations = db.Column(JSONB)  # List of recommendations
    ai_comment = db.Column(db.Text)  # AI-generated comment for student
    
    # Topic-level analysis
    topic_performance = db.Column(JSONB)  # {topic: score}
    question_type_performance = db.Column(JSONB)  # {type: score}
    
    # Metadata
    analysis_method = db.Column(db.String(50), default='ai')
    confidence_score = db.Column(db.Float)  # AI confidence in analysis
    is_reviewed = db.Column(db.Boolean, default=False)
    reviewed_by = db.Column(db.String(36), db.ForeignKey('teachers.id'))
    reviewed_at = db.Column(db.DateTime(timezone=True))
    
    # Timestamps
    created_at = db.Column(db.DateTime(timezone=True), default=datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime(timezone=True), default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))
    
    # Relationships
    student = db.relationship('Student', backref='performance_analyses')
    exam = db.relationship('Exam', backref='student_analyses')
    subject = db.relationship('Subject', backref='performance_analyses')
    reviewer = db.relationship('Teacher', foreign_keys=[reviewed_by])

class TeacherReport(db.Model):
    __tablename__ = 'teacher_reports'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    teacher_id = db.Column(db.String(36), db.ForeignKey('teachers.id'), nullable=False)
    exam_id = db.Column(db.String(36), db.ForeignKey('exams.id'))
    subject_id = db.Column(db.String(36), db.ForeignKey('subjects.id'))
    class_id = db.Column(db.String(36), db.ForeignKey('classrooms.id'))
    
    # Report content
    report_type = db.Column(db.String(50), nullable=False)  # exam_analysis, student_progress, class_performance
    title = db.Column(db.String(200), nullable=False)
    summary = db.Column(db.Text)
    insights = db.Column(JSONB)
    recommendations = db.Column(JSONB)
    
    # Data for charts and visualizations
    chart_data = db.Column(JSONB)
    statistics = db.Column(JSONB)
    
    # AI-generated content
    is_ai_generated = db.Column(db.Boolean, default=True)
    ai_model = db.Column(db.String(100))
    generation_prompt = db.Column(db.Text)
    
    # Report status
    status = db.Column(db.String(20), default='draft')  # draft, published, archived
    is_shared = db.Column(db.Boolean, default=False)
    shared_with = db.Column(JSONB)  # List of user IDs or roles
    
    # Timestamps
    generated_at = db.Column(db.DateTime(timezone=True), default=datetime.now(timezone.utc))
    published_at = db.Column(db.DateTime(timezone=True))
    archived_at = db.Column(db.DateTime(timezone=True))
    
    # Relationships
    teacher = db.relationship('Teacher', backref='reports')
    exam = db.relationship('Exam', backref='teacher_reports')
    subject = db.relationship('Subject', backref='teacher_reports')
    classroom = db.relationship('ClassRoom', backref='teacher_reports')


    