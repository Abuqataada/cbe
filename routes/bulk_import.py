# app/routes/bulk_import.py
from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, send_file
from flask_login import login_required, current_user
import pandas as pd
from io import BytesIO
from datetime import datetime, timezone
from models import (
    db, User, Student, Teacher, ClassRoom, Subject, SubjectAssignment,
    AcademicSession, AcademicTerm, Assessment, StudentAssessment, Parent,
    StudentParent, AuditLog
)
from utils.decorators import admin_required, teacher_required
from middleware.security import sanitize_filename
import os
import json

bulk_bp = Blueprint('bulk', __name__, url_prefix='/bulk')

@bulk_bp.route('/dashboard')
@login_required
@admin_required
def dashboard():
    """Bulk import dashboard"""
    return render_template('bulk/dashboard.html')

@bulk_bp.route('/import-students', methods=['GET', 'POST'])
@login_required
@admin_required
def import_students():
    """Import students in bulk"""
    # Get active academic session
    active_session = AcademicSession.query.filter_by(is_active=True).first()
    if not active_session:
        flash('No active academic session. Please create one first.', 'danger')
        return redirect(url_for('bulk.dashboard'))
    
    classes = ClassRoom.query.filter_by(academic_session_id=active_session.id).all()
    
    if request.method == 'POST':
        try:
            if 'file' not in request.files:
                flash('No file selected', 'danger')
                return render_template('bulk/import_students.html', classes=classes)
            
            file = request.files['file']
            if file.filename == '':
                flash('No file selected', 'danger')
                return render_template('bulk/import_students.html', classes=classes)
            
            # Validate file
            filename = sanitize_filename(file.filename)
            if not (filename.endswith('.xlsx') or filename.endswith('.csv')):
                flash('Please upload Excel (.xlsx) or CSV (.csv) file', 'danger')
                return render_template('bulk/import_students.html', classes=classes)
            
            file_type = 'excel' if filename.endswith('.xlsx') else 'csv'
            class_id = request.form.get('class_id')
            
            # Read file
            if file_type == 'excel':
                df = pd.read_excel(file)
            else:
                df = pd.read_csv(file)
            
            # Process each row
            success_count = 0
            failed_count = 0
            errors = []
            
            for index, row in df.iterrows():
                try:
                    # Generate username from admission number
                    admission_number = str(row.get('admission_number', '')).strip()
                    if not admission_number:
                        errors.append(f"Row {index+2}: Missing admission number")
                        failed_count += 1
                        continue
                    
                    # Create user account
                    user = User(
                        username=admission_number,
                        email=row.get('email', f'{admission_number}@school.edu'),
                        role='student',
                        created_by=current_user.id,
                        is_active=True
                    )
                    user.set_password(admission_number)  # Default password
                    db.session.add(user)
                    db.session.flush()  # Get user ID
                    
                    # Parse date of birth
                    dob = None
                    if pd.notna(row.get('date_of_birth')):
                        try:
                            dob = pd.to_datetime(row['date_of_birth']).date()
                        except:
                            dob = None
                    
                    # Parse enrollment date
                    enrollment_date = datetime.now(timezone.utc).date()
                    if pd.notna(row.get('enrollment_date')):
                        try:
                            enrollment_date = pd.to_datetime(row['enrollment_date']).date()
                        except:
                            pass
                    
                    # Create student
                    student = Student(
                        user_id=user.id,
                        admission_number=admission_number,
                        first_name=str(row.get('first_name', '')).strip(),
                        last_name=str(row.get('last_name', '')).strip(),
                        middle_name=str(row.get('middle_name', '')).strip() if pd.notna(row.get('middle_name')) else None,
                        date_of_birth=dob,
                        gender=str(row.get('gender', '')).strip(),
                        address=str(row.get('address', '')).strip() if pd.notna(row.get('address')) else None,
                        parent_name=str(row.get('parent_name', '')).strip() if pd.notna(row.get('parent_name')) else None,
                        parent_phone=str(row.get('parent_phone', '')).strip() if pd.notna(row.get('parent_phone')) else None,
                        parent_email=str(row.get('parent_email', '')).strip() if pd.notna(row.get('parent_email')) else None,
                        current_class_id=int(class_id) if class_id else None,
                        enrollment_date=enrollment_date,
                        academic_status='active',
                        is_active=True
                    )
                    db.session.add(student)
                    
                    # Log action
                    audit_log = AuditLog(
                        user_id=current_user.id,
                        action='BULK_IMPORT_STUDENT',
                        table_name='students',
                        record_id=student.id,
                        ip_address=request.remote_addr
                    )
                    db.session.add(audit_log)
                    
                    success_count += 1
                    
                except Exception as e:
                    errors.append(f"Row {index+2}: {str(e)}")
                    failed_count += 1
                    db.session.rollback()
            
            db.session.commit()
            
            flash(f'Import completed: {success_count} successful, {failed_count} failed', 
                  'success' if failed_count == 0 else 'warning')
            
            if errors:
                request.session['import_errors'] = errors[:50]
            
            return redirect(url_for('bulk.import_results'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Import failed: {str(e)}', 'danger')
    
    return render_template('bulk/import_students.html', classes=classes)

@bulk_bp.route('/import-teachers', methods=['GET', 'POST'])
@login_required
@admin_required
def import_teachers():
    """Import teachers in bulk"""
    if request.method == 'POST':
        try:
            if 'file' not in request.files:
                flash('No file selected', 'danger')
                return render_template('bulk/import_teachers.html')
            
            file = request.files['file']
            if file.filename == '':
                flash('No file selected', 'danger')
                return render_template('bulk/import_teachers.html')
            
            filename = sanitize_filename(file.filename)
            if not (filename.endswith('.xlsx') or filename.endswith('.csv')):
                flash('Please upload Excel (.xlsx) or CSV (.csv) file', 'danger')
                return render_template('bulk/import_teachers.html')
            
            file_type = 'excel' if filename.endswith('.xlsx') else 'csv'
            
            # Read file
            if file_type == 'excel':
                df = pd.read_excel(file)
            else:
                df = pd.read_csv(file)
            
            success_count = 0
            failed_count = 0
            errors = []
            
            for index, row in df.iterrows():
                try:
                    staff_id = str(row.get('staff_id', '')).strip()
                    if not staff_id:
                        errors.append(f"Row {index+2}: Missing staff ID")
                        failed_count += 1
                        continue
                    
                    # Create user account
                    email = str(row.get('email', f'{staff_id}@school.edu')).strip()
                    user = User(
                        username=staff_id,
                        email=email,
                        role='teacher',
                        created_by=current_user.id,
                        is_active=True
                    )
                    user.set_password(staff_id)  # Default password
                    db.session.add(user)
                    db.session.flush()
                    
                    # Create teacher
                    teacher = Teacher(
                        user_id=user.id,
                        staff_id=staff_id,
                        first_name=str(row.get('first_name', '')).strip(),
                        last_name=str(row.get('last_name', '')).strip(),
                        qualification=str(row.get('qualification', '')).strip() if pd.notna(row.get('qualification')) else None,
                        specialization=str(row.get('specialization', '')).strip() if pd.notna(row.get('specialization')) else None,
                        phone=str(row.get('phone', '')).strip() if pd.notna(row.get('phone')) else None,
                        email=email,
                        form_class_id=int(row['form_class_id']) if pd.notna(row.get('form_class_id')) else None
                    )
                    db.session.add(teacher)
                    
                    # Log action
                    audit_log = AuditLog(
                        user_id=current_user.id,
                        action='BULK_IMPORT_TEACHER',
                        table_name='teachers',
                        record_id=teacher.id,
                        ip_address=request.remote_addr
                    )
                    db.session.add(audit_log)
                    
                    success_count += 1
                    
                except Exception as e:
                    errors.append(f"Row {index+2}: {str(e)}")
                    failed_count += 1
                    db.session.rollback()
            
            db.session.commit()
            
            flash(f'Import completed: {success_count} successful, {failed_count} failed',
                  'success' if failed_count == 0 else 'warning')
            
            if errors:
                request.session['import_errors'] = errors[:50]
            
            return redirect(url_for('bulk.import_results'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Import failed: {str(e)}', 'danger')
    
    return render_template('bulk/import_teachers.html')

@bulk_bp.route('/import-scores', methods=['GET', 'POST'])
@login_required
@teacher_required
def import_scores():
    """Import assessment scores in bulk"""
    teacher = current_user.teacher_profile
    
    if request.method == 'POST':
        try:
            subject_id = request.form.get('subject_id')
            assessment_id = request.form.get('assessment_id')
            
            if not subject_id or not assessment_id:
                flash('Please select subject and assessment', 'danger')
                return redirect(url_for('bulk.import_scores'))
            
            if 'file' not in request.files:
                flash('No file selected', 'danger')
                return redirect(url_for('bulk.import_scores'))
            
            file = request.files['file']
            if file.filename == '':
                flash('No file selected', 'danger')
                return redirect(url_for('bulk.import_scores'))
            
            filename = sanitize_filename(file.filename)
            if not (filename.endswith('.xlsx') or filename.endswith('.csv')):
                flash('Please upload Excel (.xlsx) or CSV (.csv) file', 'danger')
                return redirect(url_for('bulk.import_scores'))
            
            file_type = 'excel' if filename.endswith('.xlsx') else 'csv'
            
            # Read file
            if file_type == 'excel':
                df = pd.read_excel(file)
            else:
                df = pd.read_csv(file)
            
            success_count = 0
            failed_count = 0
            errors = []
            
            # Verify assessment exists
            assessment = Assessment.query.get(assessment_id)
            if not assessment:
                flash('Invalid assessment selected', 'danger')
                return redirect(url_for('bulk.import_scores'))
            
            for index, row in df.iterrows():
                try:
                    admission_number = str(row.get('admission_number', '')).strip()
                    if not admission_number:
                        errors.append(f"Row {index+2}: Missing admission number")
                        failed_count += 1
                        continue
                    
                    # Find student
                    student = Student.query.filter_by(admission_number=admission_number).first()
                    if not student:
                        errors.append(f"Row {index+2}: Student not found: {admission_number}")
                        failed_count += 1
                        continue
                    
                    # Get score
                    score_value = row.get('score')
                    if pd.isna(score_value):
                        errors.append(f"Row {index+2}: Missing score")
                        failed_count += 1
                        continue
                    
                    try:
                        score = float(score_value)
                        if score < 0 or score > assessment.max_score:
                            errors.append(f"Row {index+2}: Score {score} out of range (0-{assessment.max_score})")
                            failed_count += 1
                            continue
                    except ValueError:
                        errors.append(f"Row {index+2}: Invalid score format: {score_value}")
                        failed_count += 1
                        continue
                    
                    # Check if score exists
                    student_assessment = StudentAssessment.query.filter_by(
                        student_id=student.id,
                        assessment_id=assessment_id
                    ).first()
                    
                    if student_assessment:
                        # Update existing
                        student_assessment.score = score
                        student_assessment.entered_by = teacher.id
                        student_assessment.is_approved = False
                    else:
                        # Create new
                        student_assessment = StudentAssessment(
                            student_id=student.id,
                            assessment_id=assessment_id,
                            score=score,
                            entered_by=teacher.id
                        )
                        db.session.add(student_assessment)
                    
                    success_count += 1
                    
                except Exception as e:
                    errors.append(f"Row {index+2}: {str(e)}")
                    failed_count += 1
            
            db.session.commit()
            
            flash(f'Scores imported: {success_count} successful, {failed_count} failed',
                  'success' if failed_count == 0 else 'warning')
            
            if errors:
                request.session['import_errors'] = errors[:50]
            
            return redirect(url_for('bulk.import_results'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Import failed: {str(e)}', 'danger')
    
    # Get teacher's subjects for current term
    current_term = AcademicTerm.query.filter_by(is_active=True).first()
    if current_term:
        assignments = SubjectAssignment.query.filter_by(
            teacher_id=teacher.id,
            academic_term_id=current_term.id,
            is_active=True
        ).all()
        subjects = [Subject.query.get(a.subject_id) for a in assignments if Subject.query.get(a.subject_id)]
    else:
        subjects = []
    
    return render_template('bulk/import_scores.html', subjects=subjects)

@bulk_bp.route('/import-classes', methods=['GET', 'POST'])
@login_required
@admin_required
def import_classes():
    """Import classes in bulk"""
    # Get active academic session
    active_session = AcademicSession.query.filter_by(is_active=True).first()
    if not active_session:
        flash('No active academic session. Please create one first.', 'danger')
        return redirect(url_for('bulk.dashboard'))
    
    if request.method == 'POST':
        try:
            if 'file' not in request.files:
                flash('No file selected', 'danger')
                return render_template('bulk/import_classes.html')
            
            file = request.files['file']
            if file.filename == '':
                flash('No file selected', 'danger')
                return render_template('bulk/import_classes.html')
            
            filename = sanitize_filename(file.filename)
            if not (filename.endswith('.xlsx') or filename.endswith('.csv')):
                flash('Please upload Excel (.xlsx) or CSV (.csv) file', 'danger')
                return render_template('bulk/import_classes.html')
            
            file_type = 'excel' if filename.endswith('.xlsx') else 'csv'
            
            # Read file
            if file_type == 'excel':
                df = pd.read_excel(file)
            else:
                df = pd.read_csv(file)
            
            success_count = 0
            failed_count = 0
            errors = []
            
            for index, row in df.iterrows():
                try:
                    name = str(row.get('name', '')).strip()
                    if not name:
                        errors.append(f"Row {index+2}: Missing class name")
                        failed_count += 1
                        continue
                    
                    level = str(row.get('level', '')).strip()
                    if not level:
                        errors.append(f"Row {index+2}: Missing level")
                        failed_count += 1
                        continue
                    
                    # Check if class already exists in this session
                    existing = ClassRoom.query.filter_by(
                        academic_session_id=active_session.id,
                        name=name
                    ).first()
                    
                    if existing:
                        errors.append(f"Row {index+2}: Class '{name}' already exists")
                        failed_count += 1
                        continue
                    
                    # Get form teacher ID if provided
                    form_teacher_id = None
                    if pd.notna(row.get('form_teacher_staff_id')):
                        staff_id = str(row['form_teacher_staff_id']).strip()
                        teacher = Teacher.query.filter_by(staff_id=staff_id).first()
                        if teacher:
                            form_teacher_id = teacher.id
                        else:
                            errors.append(f"Row {index+2}: Form teacher not found: {staff_id}")
                    
                    # Create class
                    classroom = ClassRoom(
                        academic_session_id=active_session.id,
                        name=name,
                        level=level,
                        section=str(row.get('section', '')).strip() if pd.notna(row.get('section')) else None,
                        max_students=int(row.get('max_students', 40)),
                        room_number=str(row.get('room_number', '')).strip() if pd.notna(row.get('room_number')) else None,
                        form_teacher_id=form_teacher_id
                    )
                    db.session.add(classroom)
                    
                    # Log action
                    audit_log = AuditLog(
                        user_id=current_user.id,
                        action='BULK_IMPORT_CLASS',
                        table_name='classrooms',
                        record_id=classroom.id,
                        ip_address=request.remote_addr
                    )
                    db.session.add(audit_log)
                    
                    success_count += 1
                    
                except Exception as e:
                    errors.append(f"Row {index+2}: {str(e)}")
                    failed_count += 1
            
            db.session.commit()
            
            flash(f'Import completed: {success_count} successful, {failed_count} failed',
                  'success' if failed_count == 0 else 'warning')
            
            if errors:
                request.session['import_errors'] = errors[:50]
            
            return redirect(url_for('bulk.import_results'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Import failed: {str(e)}', 'danger')
    
    return render_template('bulk/import_classes.html')

@bulk_bp.route('/download-template/<template_type>')
@login_required
def download_template(template_type):
    """Download import template"""
    if template_type not in ['students', 'teachers', 'scores', 'classes', 'subjects', 'subject_assignments']:
        flash('Invalid template type', 'danger')
        return redirect(url_for('bulk.dashboard'))
    
    # Define columns based on template type
    if template_type == 'students':
        columns = [
            'admission_number', 'first_name', 'last_name', 'middle_name',
            'date_of_birth', 'gender', 'address', 'parent_name',
            'parent_phone', 'parent_email', 'class_id', 'enrollment_date', 'email'
        ]
        sample_data = [
            ['ARN/2023/001', 'John', 'Doe', 'Michael', '2010-05-15', 'Male',
             '123 Main St', 'Jane Doe', '08012345678', 'parent@email.com', '1', '2023-09-01', 'john.doe@school.edu']
        ]
        descriptions = [
            'Unique student admission number (Required)',
            'Student first name (Required)',
            'Student last name (Required)',
            'Student middle name (Optional)',
            'Date of birth (YYYY-MM-DD) (Optional)',
            'Gender: Male or Female (Optional)',
            'Home address (Optional)',
            "Parent/Guardian's name (Optional)",
            "Parent/Guardian's phone (Optional)",
            "Parent/Guardian's email (Optional)",
            'ID of class (numeric) (Required)',
            'Date enrolled (YYYY-MM-DD) (Optional)',
            'Email address (Optional)'
        ]
    
    elif template_type == 'teachers':
        columns = [
            'staff_id', 'first_name', 'last_name', 'email',
            'qualification', 'specialization', 'phone', 'form_class_id'
        ]
        sample_data = [
            ['STAFF001', 'Sarah', 'Johnson', 's.johnson@school.edu',
             'M.Ed', 'Mathematics', '08087654321', '1']
        ]
        descriptions = [
            'Unique staff ID (Required)',
            'First name (Required)',
            'Last name (Required)',
            'Email address (Required)',
            'Educational qualification (Optional)',
            'Teaching specialization (Optional)',
            'Phone number (Optional)',
            'Form class ID if form teacher (Optional)'
        ]
    
    elif template_type == 'scores':
        columns = ['admission_number', 'score']
        sample_data = [['ARN/2023/001', '85.5'], ['ARN/2023/002', '92.0']]
        descriptions = [
            'Student admission number (Required)',
            'Score (0-100) (Required)'
        ]
    
    elif template_type == 'classes':
        columns = ['name', 'level', 'section', 'max_students', 'room_number', 'form_teacher_staff_id']
        sample_data = [['JSS 1A', 'JSS 1', 'A', '40', 'Room 101', 'STAFF001']]
        descriptions = [
            'Class name (Required)',
            'Level e.g., JSS 1, SSS 3 (Required)',
            'Section e.g., A, B, C (Optional)',
            'Maximum students (Optional, default: 40)',
            'Room number (Optional)',
            'Form teacher staff ID (Optional)'
        ]
    
    elif template_type == 'subjects':
        columns = ['code', 'name', 'category', 'description', 'pass_mark', 'max_mark']
        sample_data = [['MATH101', 'Mathematics', 'Core', 'Basic Mathematics', '40', '100']]
        descriptions = [
            'Subject code (Required)',
            'Subject name (Required)',
            'Category: Core, Elective, etc. (Optional)',
            'Description (Optional)',
            'Pass mark (Optional, default: 40)',
            'Maximum mark (Optional, default: 100)'
        ]
    
    elif template_type == 'subject_assignments':
        columns = ['teacher_staff_id', 'subject_code', 'class_name', 'term_name']
        sample_data = [['STAFF001', 'MATH101', 'JSS 1A', 'Autumn']]
        descriptions = [
            'Teacher staff ID (Required)',
            'Subject code (Required)',
            'Class name (Required)',
            'Term name: Autumn, Spring, Summer (Required)'
        ]
    
    # Create DataFrame
    df_template = pd.DataFrame(sample_data, columns=columns)
    
    # Create instructions DataFrame
    df_instructions = pd.DataFrame({
        'Column': columns,
        'Description': descriptions,
        'Required': ['Yes' if 'Required' in desc else 'No' for desc in descriptions],
        'Example': sample_data[0] if sample_data else ['' for _ in columns]
    })
    
    # Create Excel file in memory
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_template.to_excel(writer, sheet_name='Template', index=False)
        df_instructions.to_excel(writer, sheet_name='Instructions', index=False)
    
    output.seek(0)
    
    filename = f'{template_type}_import_template.xlsx'
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=filename
    )

@bulk_bp.route('/import-results')
@login_required
def import_results():
    """Show import results"""
    errors = request.session.pop('import_errors', []) if hasattr(request, 'session') else []
    warnings = request.session.pop('import_warnings', []) if hasattr(request, 'session') else []
    
    return render_template('bulk/import_results.html', errors=errors, warnings=warnings)

@bulk_bp.route('/validate-file', methods=['POST'])
@login_required
def validate_file():
    """Validate import file before processing"""
    try:
        if 'file' not in request.files:
            return jsonify({'valid': False, 'message': 'No file selected'})
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'valid': False, 'message': 'No file selected'})
        
        filename = sanitize_filename(file.filename)
        if not (filename.endswith('.xlsx') or filename.endswith('.csv')):
            return jsonify({'valid': False, 'message': 'Invalid file format'})
        
        # Read and validate file structure
        file_content = file.read()
        file.seek(0)  # Reset file pointer
        
        try:
            if filename.endswith('.xlsx'):
                df = pd.read_excel(BytesIO(file_content), nrows=5)  # Read first 5 rows
            else:
                df = pd.read_csv(BytesIO(file_content), nrows=5)
            
            # Basic validation
            if df.empty:
                return jsonify({'valid': False, 'message': 'File is empty'})
            
            if len(df.columns) < 2:
                return jsonify({'valid': False, 'message': 'File has insufficient columns'})
            
            # Count rows (excluding header)
            total_rows = len(df)
            
            return jsonify({
                'valid': True,
                'message': f'File validated: {total_rows} rows found',
                'columns': list(df.columns),
                'sample': df.head(3).to_dict('records')
            })
            
        except Exception as e:
            return jsonify({'valid': False, 'message': f'Error reading file: {str(e)}'})
    
    except Exception as e:
        return jsonify({'valid': False, 'message': f'Validation error: {str(e)}'})