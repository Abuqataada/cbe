from flask import Blueprint, render_template, jsonify, request, flash, redirect, url_for, current_app, make_response, send_file
from flask_login import login_required, current_user
from datetime import datetime, timezone
import os
import tempfile
import json
import traceback

from services.pdf_report_service import PDFReportService
from models import (SystemConfiguration, db, Student, Teacher, ClassRoom, AcademicSession,
                    AcademicTerm, StudentAssessment, Subject, TeacherComment, FormTeacherComment,
                    PrincipalRemark, DomainEvaluation, ReportCard, SubjectAssignment, GradeScale)  # Added GradeScale

report_bp = Blueprint('report', __name__)

@report_bp.route('/generate_report_card/<student_id>/<term_id>')
@login_required
def generate_report_card(student_id, term_id):
    """Generate a report card PDF for a specific student and term"""
    try:
        print(f"Generating report card for student: {student_id}, term: {term_id}")
        print(f"Current user: {current_user.id}, role: {current_user.role}")
        
        # Get current user
        if not current_user.is_authenticated:
            flash('You must be logged in to generate reports', 'danger')
            return redirect(url_for('auth.login'))
        
        # Check if user is teacher or admin
        if current_user.role not in ['teacher', 'admin']:
            flash('You do not have permission to generate report cards', 'danger')
            return redirect(url_for('dashboard'))
        
        # Get student
        student = Student.query.get_or_404(student_id)
        print(f"Student found: {student.first_name} {student.last_name}")
        
        # Get academic term
        term = AcademicTerm.query.get_or_404(term_id)
        session = term.session
        print(f"Term found: {term.name}, Session: {session.name}")
        
        # Get student's class
        classroom = ClassRoom.query.get(student.current_class_id)
        print(f"Classroom: {classroom.name if classroom else 'None'}")
        
        # Get teacher if user is teacher
        teacher = None
        if current_user.role == 'teacher':
            teacher = Teacher.query.filter_by(user_id=current_user.id).first()
            if not teacher:
                flash('Teacher profile not found', 'danger')
                return redirect(url_for('teacher.dashboard'))
            print(f"Teacher found: {teacher.first_name} {teacher.last_name}")
        
        # Get form teacher (if any)
        form_teacher = None
        if classroom and classroom.form_teacher_id:
            form_teacher = Teacher.query.get(classroom.form_teacher_id)
        
        # Get all subjects for the class (you'll need to populate this)
        # For now, create sample data matching your example
        academic_data = _get_sample_academic_data()
        
        # Get comments from database
        form_comment = FormTeacherComment.query.filter_by(
            student_id=student_id,
            term=term.term_number,
            academic_year=session.name
        ).first()
        
        principal_remark = PrincipalRemark.query.filter_by(
            student_id=student_id,
            term=term.term_number,
            academic_year=session.name
        ).first()

        # FIXED: Extract signature path from JSON dictionary
        principal_signature = SystemConfiguration.query.filter_by(config_key='principal_signature').first()
        principal_signature_image = None
        if principal_signature and principal_signature.config_value:
            # config_value is a JSON/dict, so extract the path
            signature_data = principal_signature.config_value
            if isinstance(signature_data, dict) and 'signature_path' in signature_data:
                signature_path = signature_data['signature_path']
                # Remove leading slash if present
                if signature_path.startswith('/'):
                    signature_path = signature_path[1:]
                
                # Build full path
                principal_signature_path = os.path.join(
                    current_app.root_path, 
                    'static', 
                    signature_path
                )
                
                # Check if file exists
                if os.path.exists(principal_signature_path):
                    principal_signature_image = principal_signature_path
                    print(f"Found principal signature at: {principal_signature_image}")
                else:
                    print(f"Warning: Principal signature file not found at: {principal_signature_path}")
            else:
                print(f"Warning: Invalid principal signature data format: {signature_data}")

        # FIXED: Extract resumption date from JSON dictionary
        resumption_date_config = SystemConfiguration.query.filter_by(config_key='resumption_date').first()
        next_term_date = 'To Be Announced'
        if resumption_date_config and resumption_date_config.config_value:
            # config_value is a JSON/dict, so extract the date
            date_data = resumption_date_config.config_value
            if isinstance(date_data, dict) and 'date' in date_data:
                next_term_date = date_data['date']
                print(f"Found resumption date: {next_term_date}")
            else:
                print(f"Warning: Invalid resumption date data format: {date_data}")
        
        # If no comments in DB, use sample comments
        if not form_comment and not principal_remark:
            comments = _get_sample_comments()
        else:
            comments = {
                'form_tutor_comment': form_comment.comment if form_comment else '',
                'principal_remark': principal_remark.remark if principal_remark else ''
            }
        
        # Prepare school information
        school_info = {
            'name': 'ARNDALE ACADEMY',
            'address': 'Plot 647 CADASTAL ZONE CO7 Karmo, Abuja',
            'phone': '08166656369',
            'logo_path': os.path.join(current_app.root_path, 'static', 'images', 'logo.jpg')
        }
        
        # Check if logo exists, if not use placeholder
        if not os.path.exists(school_info['logo_path']):
            school_info['logo_path'] = None
        
        # Prepare student data
        student_data = {
            'full_name': f"{student.first_name} {student.last_name}",
            'admission_number': student.admission_number,
            'class': classroom.name if classroom else '',
            'year': classroom.level if classroom else '',
            'form_group': classroom.name if classroom else '',
            'form_tutor': form_teacher.first_name + ' ' + form_teacher.last_name if form_teacher else 'Not Assigned'
        }

        print("Form tutor:", student_data['form_tutor'])
        
        # Prepare term data
        term_data = {
            'academic_year': session.name,
            'term_number': term.term_number,
            'term_name': term.name,
            'next_term_resumption_date': next_term_date,
            'principal_signature': principal_signature_image  # Now this is the full file path
        }
        
        # ===== NEW: Get grade scales from database =====
        grade_scales = []
        try:
            # Get all active grade scales
            grade_scale_records = GradeScale.query.filter_by(is_active=True).all()
            
            # Convert to dictionary format for PDF service
            for scale in grade_scale_records:
                grade_scales.append({
                    'id': scale.id,
                    'name': scale.name,
                    'min_score': float(scale.min_score),
                    'max_score': float(scale.max_score),
                    'grade': scale.grade,
                    'remark': scale.remark if scale.remark else '',
                    'point': float(scale.point) if scale.point else 0.0,
                    'is_active': scale.is_active
                })
            
            print(f"Retrieved {len(grade_scales)} active grade scales from database")
            
            # If no grade scales found, use default ones
            if not grade_scales:
                print("No grade scales found in database, using defaults")
                grade_scales = _get_default_grade_scales()
                
        except Exception as e:
            print(f"Error retrieving grade scales: {e}")
            print("Using default grade scales")
            grade_scales = _get_default_grade_scales()
        
        print(f"Generating PDF with data...")
        
        # Generate PDF - NOW WITH grade_scales parameter
        pdf_service = PDFReportService(current_app.root_path)
        pdf_bytes = pdf_service.generate_report_card(
            student_data=student_data,
            term_data=term_data,
            academic_data=academic_data,
            comments=comments,
            school_info=school_info,
            grade_scales=grade_scales  # Added this parameter
        )
        
        print(f"PDF generated successfully")
        
        # Save report card to database (optional)
        try:
            report_card = ReportCard(
                student_id=student_id,
                term=term.term_number,
                academic_year=session.name,
                file_path=f"reports/{student_id}_{term_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                generated_by=current_user.id,
                is_published=True,
                published_at=datetime.now(timezone.utc),
                report_data={
                    'student_info': student_data,
                    'term_info': term_data,
                    'academic_performance': academic_data,
                    'comments': comments,
                    'grade_scales_used': grade_scales  # Save grade scales used
                }
            )
            db.session.add(report_card)
            db.session.commit()
            print(f"Report saved to database with ID: {report_card.id}")
        except Exception as db_error:
            print(f"Warning: Could not save to database: {db_error}")
            # Continue even if DB save fails
        
        # Create response
        response = make_response(pdf_bytes)
        response.headers['Content-Type'] = 'application/pdf'
        filename = f"{student.first_name}_{student.last_name}_Term{term.term_number}_Report_{datetime.now().strftime('%Y%m%d')}.pdf"
        response.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        return response
        
    except Exception as e:
        error_msg = f'Error generating report card: {str(e)}'
        print(error_msg)
        print(traceback.format_exc())
        flash(error_msg, 'danger')
        
        # Redirect to appropriate page based on user role
        if current_user.role == 'teacher':
            return redirect(url_for('teacher.student_details', student_id=student_id))
        elif current_user.role == 'admin':
            return redirect(url_for('admin.view_student_profile', student_id=student_id))
        else:
            return redirect(url_for('dashboard'))


def _get_default_grade_scales():
    """Return default grade scales if none in database"""
    return [
        {'grade': 'A*', 'min_score': 90.0, 'max_score': 100.0, 'remark': 'Excellent', 'point': 5.0, 'is_active': True},
        {'grade': 'A', 'min_score': 80.0, 'max_score': 89.0, 'remark': 'Very Good', 'point': 4.0, 'is_active': True},
        {'grade': 'B', 'min_score': 70.0, 'max_score': 79.0, 'remark': 'Good', 'point': 3.0, 'is_active': True},
        {'grade': 'C', 'min_score': 60.0, 'max_score': 69.0, 'remark': 'Credit', 'point': 2.0, 'is_active': True},
        {'grade': 'D', 'min_score': 50.0, 'max_score': 59.0, 'remark': 'Pass', 'point': 1.0, 'is_active': True},
        {'grade': 'F', 'min_score': 0.0, 'max_score': 49.0, 'remark': 'Fail', 'point': 0.0, 'is_active': True},
    ]


def _get_sample_academic_data():
    """Return sample academic data for testing"""
    return [
        {
            'subject_name': 'Mathematics',
            'teacher_name': 'Mr. Johnson',
            'ca1_score': 18.0,
            'ca2_score': 17.0,
            'project_score': 9.0,
            'exam_score': 45.0,
            'total_score': 89.0,
            'grade': 'A',
            'class_average': 75.5,
            'effort': '1',
            'comment': 'Shows excellent understanding of mathematical concepts.'
        },
        {
            'subject_name': 'English Language',
            'teacher_name': 'Mrs. Smith',
            'ca1_score': 16.0,
            'ca2_score': 15.0,
            'project_score': 8.0,
            'exam_score': 42.0,
            'total_score': 81.0,
            'grade': 'A',
            'class_average': 70.2,
            'effort': '1',
            'comment': 'Strong writing skills and good comprehension.'
        },
        {
            'subject_name': 'Physics',
            'teacher_name': 'Dr. Brown',
            'ca1_score': 14.0,
            'ca2_score': 13.0,
            'project_score': 7.0,
            'exam_score': 38.0,
            'total_score': 72.0,
            'grade': 'B',
            'class_average': 65.8,
            'effort': '2',
            'comment': 'Good practical skills but needs to improve theory.'
        }
    ]


def _get_sample_comments():
    """Return sample comments for testing"""
    return {
        'form_tutor_comment': 'Filippo has shown remarkable improvement this term. He is a diligent student who participates actively in class discussions and submits assignments on time. He works well with peers and shows leadership qualities.',
        'principal_remark': 'Outstanding performance this term. Filippo demonstrates excellent academic ability and good character. We are proud of his achievements and encourage him to maintain this high standard.'
    }

@report_bp.route('/download_report/<report_id>')
@login_required
def download_report(report_id):
    """Download a previously generated report"""
    try:
        report = ReportCard.query.get_or_404(report_id)
        
        # Check permissions
        if current_user.role not in ['teacher', 'admin']:
            flash('You do not have permission to download reports', 'danger')
            return redirect(url_for('dashboard'))
        
        # Check if teacher owns this student (for teacher role)
        if current_user.role == 'teacher':
            teacher = Teacher.query.filter_by(user_id=current_user.id).first()
            if not teacher:
                flash('Teacher profile not found', 'danger')
                return redirect(url_for('teacher.dashboard'))
            
            # Check if teacher teaches this student's class
            student = Student.query.get(report.student_id)
            if not student or not student.current_class_id:
                flash('Student or class not found', 'danger')
                return redirect(url_for('teacher.dashboard'))
            
            # Verify teacher is assigned to this class (you might need to adjust this based on your models)
            class_assignment = SubjectAssignment.query.filter_by(
                teacher_id=teacher.id,
                class_id=student.current_class_id
            ).first()
            
            if not class_assignment:
                flash('You do not have permission to download this report', 'danger')
                return redirect(url_for('teacher.dashboard'))
        
        # Construct file path
        file_path = os.path.join(
            current_app.root_path,
            'static',
            report.file_path
        )
        
        # Check if file exists
        if not os.path.exists(file_path):
            # Try to find the file in uploads
            file_path = os.path.join(
                current_app.root_path,
                'uploads',
                report.file_path
            )
            
            if not os.path.exists(file_path):
                flash('Report file not found. Please regenerate the report.', 'danger')
                return redirect(request.referrer or url_for('dashboard'))
        
        return send_file(
            file_path,
            as_attachment=True,
            download_name=f"report_{report.student.first_name}_{report.student.last_name}_term{report.term}.pdf"
        )
        
    except Exception as e:
        flash(f'Error downloading report: {str(e)}', 'danger')
        return redirect(request.referrer or url_for('dashboard'))



