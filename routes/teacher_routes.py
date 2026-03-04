# app/routes/teacher_routes.py
from flask import Blueprint, render_template, request, jsonify, flash, send_file, redirect, url_for, current_app, make_response
from werkzeug.utils import secure_filename
import os
from flask_login import login_required, current_user
from models import (
    db, User, Teacher, Student, Subject, SubjectAssignment, Assessment, 
    StudentAssessment, DomainEvaluation, TeacherComment, FormTeacherComment, 
    ExamResult, ClassRoom, AcademicSession, AcademicTerm, QuestionBank, 
    Exam, ExamQuestion, ExamSession, StudentParent, Parent, Attendance,
    AuditLog, LearningMaterial, StudentMaterialDownload, ExamQuestionAnalysis,
    StudentPerformanceAnalysis, TeacherReport, ExamResponse, AssessmentScoreMapping
)
import mimetypes
from utils.decorators import teacher_required
from datetime import datetime, timezone, timedelta, date
import pandas as pd
from io import BytesIO

from services.ai_analysis_service import AIAnalysisService
import json

teacher_bp = Blueprint('teacher', __name__, url_prefix='/teacher')

# =========================
# Teacher Dashboard Routes
# =========================
@teacher_bp.route('/dashboard')
@login_required
@teacher_required
def dashboard():
    """Teacher dashboard"""
    teacher = Teacher.query.filter_by(user_id=current_user.id).first_or_404()
    
    # Get current academic term
    current_term = AcademicTerm.query.filter_by(is_active=True).first()
    active_session = AcademicSession.query.filter_by(is_active=True).first()
    
    # Get assigned subjects for current term
    assigned_subjects = []
    if current_term:
        assignments = SubjectAssignment.query.filter_by(
            teacher_id=teacher.id,
            academic_term_id=current_term.id,
            is_active=True
        ).all()
        
        for assignment in assignments:
            subject = Subject.query.get(assignment.subject_id)
            classroom = ClassRoom.query.get(assignment.class_id)
            if subject and classroom:
                # Get student count for this class
                student_count = Student.query.filter_by(
                    current_class_id=classroom.id,
                    is_active=True,
                    academic_status='active'
                ).count()
                
                assigned_subjects.append({
                    'subject': subject,
                    'classroom': classroom,
                    'assignment': assignment,
                    'student_count': student_count
                })
    
    # Get form class if form teacher
    form_class = None
    if teacher.form_class_id:
        form_class = ClassRoom.query.get(teacher.form_class_id)
    
    # Get recent exams
    recent_exams = Exam.query.filter_by(
        teacher_id=teacher.id
    ).order_by(Exam.created_at.desc()).limit(5).all()
    
    # Get upcoming exams (scheduled for next 7 days)
    upcoming_exams = []
    if current_term:
        upcoming_exams = Exam.query.filter(
            Exam.teacher_id == teacher.id,
            Exam.academic_term_id == current_term.id,
            Exam.scheduled_start >= datetime.now(timezone.utc),
            Exam.scheduled_start <= datetime.now(timezone.utc) + timedelta(days=7)
        ).order_by(Exam.scheduled_start).all()
    
    stats = {
        'assigned_subjects': len(assigned_subjects),
        'form_class': form_class.name if form_class else 'Not Assigned',
        'students_count': len(form_class.class_students) if form_class else 0,
        'recent_exams': len(recent_exams),
        'upcoming_exams': len(upcoming_exams),
        'current_term': current_term.name if current_term else 'No Active Term',
        'active_session': active_session.name if active_session else 'No Active Session'
    }
    
    # Get current datetime for the template
    current_datetime = datetime.now()
    
    return render_template('teacher/dashboard.html', 
                         teacher=teacher, 
                         stats=stats, 
                         assigned_subjects=assigned_subjects,
                         form_class=form_class,
                         recent_exams=recent_exams,
                         upcoming_exams=upcoming_exams,
                         current_term=current_term,
                         now=current_datetime)  # Add this line

@teacher_bp.route('/dashboard/stats')
@login_required
@teacher_required
def dashboard_stats():
    """Get dashboard statistics for AJAX requests"""
    try:
        teacher = Teacher.query.filter_by(user_id=current_user.id).first_or_404()
        current_term = AcademicTerm.query.filter_by(is_active=True).first()
        active_session = AcademicSession.query.filter_by(is_active=True).first()
        
        # Get assigned subjects count
        assigned_subjects = 0
        if current_term:
            assigned_subjects = SubjectAssignment.query.filter_by(
                teacher_id=teacher.id,
                academic_term_id=current_term.id,
                is_active=True
            ).count()
        
        # Get form class students count
        students_count = 0
        if teacher.form_class_id:
            students_count = Student.query.filter_by(
                current_class_id=teacher.form_class_id,
                is_active=True,
                academic_status='active'
            ).count()
        
        # Get recent exams count
        recent_exams = Exam.query.filter_by(
            teacher_id=teacher.id
        ).count()
        
        # Get upcoming exams count
        upcoming_exams = 0
        if current_term:
            upcoming_exams = Exam.query.filter(
                Exam.teacher_id == teacher.id,
                Exam.academic_term_id == current_term.id,
                Exam.scheduled_start >= datetime.now(timezone.utc),
                Exam.scheduled_start <= datetime.now(timezone.utc) + timedelta(days=7)
            ).count()
        
        stats = {
            'assigned_subjects': assigned_subjects,
            'students_count': students_count,
            'recent_exams': recent_exams,
            'upcoming_exams': upcoming_exams,
            'current_term': current_term.name if current_term else 'No Active Term',
            'active_session': active_session.name if active_session else 'No Active Session'
        }
        
        return jsonify({
            'success': True,
            'stats': stats
        })
    
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400

@teacher_bp.route('/preview-exam/<exam_id>')
@login_required
@teacher_required
def preview_exam(exam_id):
    """Preview exam as a student would see it"""
    try:
        teacher = Teacher.query.filter_by(user_id=current_user.id).first_or_404()
        exam = Exam.query.get_or_404(exam_id)
        
        # Verify the exam belongs to this teacher
        if exam.teacher_id != teacher.id:
            flash('You are not authorized to preview this exam.', 'danger')
            return redirect(url_for('teacher.exams'))
        
        flash('Exam preview feature coming soon!', 'info')
        return redirect(url_for('teacher.exam_detail', exam_id=exam_id))
        
    except Exception as e:
        flash(f'Error previewing exam: {str(e)}', 'danger')
        return redirect(url_for('teacher.exam_detail', exam_id=exam_id))

@teacher_bp.route('/exam-results/<exam_id>')
@login_required
@teacher_required
def exam_results(exam_id):
    """View detailed exam results with filtering"""
    try:
        teacher = Teacher.query.filter_by(user_id=current_user.id).first_or_404()
        exam = Exam.query.get_or_404(exam_id)
        
        # Verify the exam belongs to this teacher
        if exam.teacher_id != teacher.id:
            flash('You are not authorized to view these results.', 'danger')
            return redirect(url_for('teacher.exams'))
        
        # Get filter parameters
        status_filter = request.args.get('status', 'all')
        search_query = request.args.get('search', '').strip()
        
        # Build query for exam sessions
        query = ExamSession.query.filter_by(exam_id=exam_id)
        
        # Apply status filter
        if status_filter != 'all':
            query = query.filter_by(status=status_filter)
        
        # Get all sessions with student data
        exam_sessions = query.join(Student).order_by(Student.last_name, Student.first_name).all()
        
        # Get exam questions to calculate total marks
        exam_questions = ExamQuestion.query.filter_by(exam_id=exam_id).all()
        total_exam_marks = sum([eq.marks or eq.question.marks for eq in exam_questions if eq.question])
        
        # Calculate results for each session
        results = []
        total_sessions = 0
        completed_sessions = 0
        total_percentage = 0
        pass_count = 0
        
        for session in exam_sessions:
            # Skip if search query doesn't match student name
            student = session.student
            if search_query:
                full_name = f"{student.first_name} {student.last_name}".lower()
                admission = student.admission_number.lower()
                if search_query.lower() not in full_name and search_query.lower() not in admission:
                    continue
            
            # Get all responses for this session
            responses = ExamResponse.query.filter_by(exam_session_id=session.id).all()
            
            # Calculate score
            total_marks = 0
            obtained_marks = 0
            
            for response in responses:
                # Get the exam question to know the marks
                exam_question = ExamQuestion.query.get(response.exam_question_id)
                question = QuestionBank.query.get(response.question_bank_id)
                
                if exam_question and question:
                    marks = exam_question.marks or question.marks
                    total_marks += marks
                    
                    # Check if answer is correct
                    if response.is_correct:
                        obtained_marks += marks
                    elif response.is_correct is None and response.answer and response.answer.strip():
                        # For subjective questions, give partial credit for non-empty answers
                        obtained_marks += marks * 0.5
            
            # If no responses found, use total_exam_marks
            if total_marks == 0 and total_exam_marks > 0:
                total_marks = total_exam_marks
            
            percentage = (obtained_marks / total_marks * 100) if total_marks > 0 else 0
            
            # Determine grade
            grade = calculate_grade(percentage)
            
            # Check if passed (assuming 40% is pass mark)
            passed = percentage >= 40
            
            # Update statistics
            total_sessions += 1
            if session.status == 'completed':
                completed_sessions += 1
                total_percentage += percentage
                if passed:
                    pass_count += 1
            
            results.append({
                'student': student,
                'session': session,
                'total_marks': total_marks,
                'obtained_marks': obtained_marks,
                'percentage': percentage,
                'grade': grade,
                'passed': passed
            })
        
        # Calculate overall statistics
        average_percentage = (total_percentage / completed_sessions) if completed_sessions > 0 else 0
        pass_rate = (pass_count / completed_sessions * 100) if completed_sessions > 0 else 0
        
        # Sort results by percentage (highest first)
        results.sort(key=lambda x: x['percentage'], reverse=True)
        
        # Add rank
        for i, result in enumerate(results):
            result['rank'] = i + 1
        
        return render_template('teacher/exam_results.html',
                             teacher=teacher,
                             exam=exam,
                             results=results,
                             total_sessions=total_sessions,
                             completed_sessions=completed_sessions,
                             average_percentage=average_percentage,
                             pass_rate=pass_rate,
                             status_filter=status_filter,
                             search_query=search_query,
                             total_exam_marks=total_exam_marks)
        
    except Exception as e:
        flash(f'Error loading exam results: {str(e)}', 'danger')
        return redirect(url_for('teacher.exam_detail', exam_id=exam_id))
    
def calculate_grade(percentage):
    """Calculate grade based on percentage"""
    if percentage >= 75:
        return 'A'
    elif percentage >= 70:
        return 'B'
    elif percentage >= 60:
        return 'C'
    elif percentage >= 50:
        return 'D'
    elif percentage >= 40:
        return 'E'
    else:
        return 'F'
        
@teacher_bp.route('/my-subjects')
@login_required
@teacher_required
def my_subjects():
    """View assigned subjects"""
    teacher = Teacher.query.filter_by(user_id=current_user.id).first_or_404()
    
    # Get current term
    current_term = AcademicTerm.query.filter_by(is_active=True).first()
    if not current_term:
        flash('No active academic term!', 'warning')
        return redirect(url_for('teacher.dashboard'))
    
    # Get subject assignments for current term
    assignments = SubjectAssignment.query.filter_by(
        teacher_id=teacher.id,
        academic_term_id=current_term.id,
        is_active=True
    ).all()
    
    subjects_data = []
    for assignment in assignments:
        subject = Subject.query.get(assignment.subject_id)
        classroom = ClassRoom.query.get(assignment.class_id)
        if subject and classroom:
            # Get student count for this class
            student_count = Student.query.filter_by(
                current_class_id=classroom.id,
                is_active=True,
                academic_status='active'
            ).count()
            
            subjects_data.append({
                'subject': subject,
                'classroom': classroom,
                'assignment': assignment,
                'student_count': student_count
            })
    
    return render_template('teacher/subjects.html', 
                         teacher=teacher,  # Add this line
                         subjects_data=subjects_data,
                         current_term=current_term)

@teacher_bp.route('/enter-scores/<subject_id>/<class_id>')
@login_required
@teacher_required
def enter_scores(subject_id, class_id):
    """Enter assessment scores for a subject in specific class - UPDATED FOR JSON STORAGE"""
    teacher = Teacher.query.filter_by(user_id=current_user.id).first_or_404()
    subject = Subject.query.get_or_404(subject_id)
    classroom = ClassRoom.query.get_or_404(class_id)
    
    # Verify teacher is assigned to this subject and class
    current_term = AcademicTerm.query.filter_by(is_active=True).first()
    if not current_term:
        flash('No active academic term!', 'danger')
        return redirect(url_for('teacher.my_subjects'))
    
    assignment = SubjectAssignment.query.filter_by(
        teacher_id=teacher.id,
        subject_id=subject_id,
        class_id=class_id,
        academic_term_id=current_term.id,
        is_active=True
    ).first()
    
    if not assignment:
        flash('You are not assigned to teach this subject in this class!', 'danger')
        return redirect(url_for('teacher.my_subjects'))
    
    # Get assessments for this term (shared across all subjects)
    assessments = Assessment.query.filter_by(
        academic_term_id=current_term.id,
        is_active=True
    ).order_by(Assessment.order).all()
    
    # Get students in the class
    students = Student.query.filter_by(
        current_class_id=class_id,
        is_active=True,
        academic_status='active'
    ).order_by(Student.admission_number).all()
    
    # Get existing StudentAssessment records for all students in this class, subject, and term
    student_assessments = StudentAssessment.query.filter(
        StudentAssessment.student_id.in_([s.id for s in students]),
        StudentAssessment.subject_id == subject_id,
        StudentAssessment.class_id == class_id,
        StudentAssessment.term_id == current_term.id
    ).all()
    
    # Create a dictionary for quick lookup
    assessment_dict = {sa.student_id: sa for sa in student_assessments}
    
    # Prepare the data structure for the template
    student_scores = {}
    student_averages = {}
    entered_scores_count = 0
    total_possible_scores = len(students) * len(assessments)
    
    for student in students:
        student_scores[student.id] = {}
        
        # Get the StudentAssessment record for this student if it exists
        student_assessment = assessment_dict.get(student.id)
        scores = student_assessment.assessment_scores if student_assessment else {}
        
        # Calculate student total if we have scores
        student_total = 0
        score_count = 0
        
        for assessment in assessments:
            score = scores.get(str(assessment.id))
            if score is not None:
                score_value = float(score)
                student_total += score_value
                score_count += 1
                entered_scores_count += 1
                
                student_scores[student.id][assessment.id] = {
                    'score': score_value,
                    'entered_at': student_assessment.entered_at if student_assessment else None,
                    'entered_by': student_assessment.entered_by if student_assessment else None,
                    'is_approved': student_assessment.is_approved if student_assessment else False
                }
            else:
                student_scores[student.id][assessment.id] = {
                    'score': None,
                    'entered_at': None,
                    'entered_by': None,
                    'is_approved': False
                }
        
        # Calculate student average if we have scores
        if score_count > 0:
            student_averages[student.id] = {
                'total': student_total,
                'average': student_total / score_count if score_count > 0 else 0,
                'count': score_count
            }
    
    # Calculate completion percentage
    completion_percentage = 0
    if total_possible_scores > 0:
        completion_percentage = (entered_scores_count / total_possible_scores) * 100
    
    # Calculate overall class statistics
    class_stats = {
        'total_students': len(students),
        'total_assessments': len(assessments),
        'entered_scores': entered_scores_count,
        'completion_percentage': round(completion_percentage, 1),
        'average_scores_per_assessment': {},
        'overall_average': 0
    }
    
    # Calculate average for each assessment
    for assessment in assessments:
        total_score = 0
        count = 0
        
        for student in students:
            score_data = student_scores[student.id][assessment.id]
            if score_data['score'] is not None:
                total_score += score_data['score']
                count += 1
        
        avg_score = total_score / count if count > 0 else 0
        
        class_stats['average_scores_per_assessment'][assessment.id] = {
            'name': assessment.assessment_type,
            'average': round(avg_score, 1),
            'max_score': assessment.max_score,
            'weight': assessment.weight
        }
    
    # Calculate overall average across all assessments
    all_scores = []
    for student in students:
        for assessment in assessments:
            score = student_scores[student.id][assessment.id]['score']
            if score is not None:
                all_scores.append(score)
    
    if all_scores:
        class_stats['overall_average'] = sum(all_scores) / len(all_scores)
    
    return render_template('teacher/enter_scores.html',
                         teacher=teacher,
                         subject=subject,
                         classroom=classroom,
                         assessments=assessments,
                         students=students,
                         student_scores=student_scores,
                         student_averages=student_averages,
                         current_term=current_term,
                         entered_scores_count=entered_scores_count,
                         total_possible_scores=total_possible_scores,
                         completion_percentage=completion_percentage,
                         class_stats=class_stats)

# =========================
# Question Bank Routes
# =========================

@teacher_bp.route('/question-bank')
@login_required
@teacher_required
def question_bank():
    """Manage question bank"""
    teacher = Teacher.query.filter_by(user_id=current_user.id).first_or_404()
    
    # Get subjects assigned to teacher in current term
    current_term = AcademicTerm.query.filter_by(is_active=True).first()
    assigned_subjects = []
    
    if current_term:
        assignments = SubjectAssignment.query.filter_by(
            teacher_id=teacher.id,
            academic_term_id=current_term.id,
            is_active=True
        ).all()
        
        # Group by subject
        subject_dict = {}
        for assignment in assignments:
            subject = Subject.query.get(assignment.subject_id)
            classroom = ClassRoom.query.get(assignment.class_id)
            
            if subject:
                if subject.id not in subject_dict:
                    subject_dict[subject.id] = {
                        'subject': subject,
                        'classes': [],
                        'question_count': QuestionBank.query.filter_by(
                            subject_id=subject.id,
                            teacher_id=teacher.id
                        ).count()
                    }
                if classroom:
                    subject_dict[subject.id]['classes'].append(classroom)
        
        assigned_subjects = list(subject_dict.values())
    
    # Get all questions with filters
    subject_filter = request.args.get('subject')
    question_type_filter = request.args.get('type')
    difficulty_filter = request.args.get('difficulty')
    search_query = request.args.get('search', '')
    
    query = QuestionBank.query.filter_by(teacher_id=teacher.id)
    
    if subject_filter and subject_filter != 'all':
        query = query.filter_by(subject_id=subject_filter)
    
    if question_type_filter and question_type_filter != 'all':
        query = query.filter_by(question_type=question_type_filter)
    
    if difficulty_filter and difficulty_filter != 'all':
        query = query.filter_by(difficulty=difficulty_filter)
    
    if search_query:
        query = query.filter(
            db.or_(
                QuestionBank.question_text.ilike(f'%{search_query}%'),
                QuestionBank.explanation.ilike(f'%{search_query}%')
            )
        )
    
    questions = query.order_by(QuestionBank.created_at.desc()).all()
    
    # Get all subjects for filter dropdown
    teacher_subjects = Subject.query.join(SubjectAssignment).filter(
        SubjectAssignment.teacher_id == teacher.id,
        SubjectAssignment.is_active == True
    ).distinct().all()
    
    return render_template('teacher/question_bank.html',
                         teacher=teacher,
                         assigned_subjects=assigned_subjects,
                         questions=questions,
                         subjects=teacher_subjects,
                         current_term=current_term)

@teacher_bp.route('/question-bank/add', methods=['GET', 'POST'])
@login_required
@teacher_required
def add_question():
    """Add a new question to the question bank"""
    teacher = Teacher.query.filter_by(user_id=current_user.id).first_or_404()
    
    # Get subjects assigned to teacher
    current_term = AcademicTerm.query.filter_by(is_active=True).first()
    assigned_subjects = []
    
    if current_term:
        assignments = SubjectAssignment.query.filter_by(
            teacher_id=teacher.id,
            academic_term_id=current_term.id,
            is_active=True
        ).all()
        
        for assignment in assignments:
            subject = Subject.query.get(assignment.subject_id)
            classroom = ClassRoom.query.get(assignment.class_id)
            
            if subject and subject.id not in [s['subject'].id for s in assigned_subjects]:
                assigned_subjects.append({
                    'subject': subject,
                    'classroom': classroom
                })
    
    if request.method == 'POST':
        try:
            subject_id = request.form.get('subject_id')
            question_text = request.form.get('question_text')
            question_type = request.form.get('question_type')
            difficulty = request.form.get('difficulty')
            marks = request.form.get('marks', 1.0)
            explanation = request.form.get('explanation')
            topics = request.form.get('topics', '')
            
            # Validate required fields
            if not all([subject_id, question_text, question_type]):
                flash('Please fill in all required fields', 'danger')
                return redirect(url_for('teacher.add_question'))
            
            # Handle question image upload
            question_image = None
            question_image_filename = None
            if 'question_image' in request.files:
                image_file = request.files['question_image']
                if image_file and image_file.filename != '':
                    # Secure the filename
                    filename = secure_filename(image_file.filename)
                    # Create unique filename
                    unique_filename = f"question_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{filename}"
                    
                    # Create uploads directory if it doesn't exist
                    upload_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'questions')
                    os.makedirs(upload_dir, exist_ok=True)
                    
                    # Save the file
                    filepath = os.path.join(upload_dir, unique_filename)
                    image_file.save(filepath)
                    question_image = f"/static/uploads/questions/{unique_filename}"
                    question_image_filename = unique_filename
            
            # Create question object
            question = QuestionBank(
                subject_id=subject_id,
                teacher_id=teacher.id,
                question_text=question_text,
                question_type=question_type,
                difficulty=difficulty,
                marks=float(marks),
                explanation=explanation,
                created_by=current_user.id,
                is_approved=False,
                question_image=question_image
            )
            
            # Handle question type specific fields
            if question_type in ['multiple_choice', 'true_false']:
                options = []
                correct_answer = None
                
                if question_type == 'multiple_choice':
                    option_count = int(request.form.get('option_count', 4))
                    
                    # Handle option images
                    option_images = {}
                    for i in range(1, 6):  # Max 5 options
                        image_key = f'option_image_{i}'
                        if image_key in request.files:
                            image_file = request.files[image_key]
                            if image_file and image_file.filename != '':
                                filename = secure_filename(image_file.filename)
                                unique_filename = f"option_{i}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{filename}"
                                
                                upload_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'options')
                                os.makedirs(upload_dir, exist_ok=True)
                                
                                filepath = os.path.join(upload_dir, unique_filename)
                                image_file.save(filepath)
                                option_images[str(i)] = f"/static/uploads/options/{unique_filename}"
                    
                    for i in range(1, option_count + 1):
                        option_text = request.form.get(f'option_{i}')
                        if option_text:
                            is_correct = request.form.get(f'correct_option') == str(i)
                            option_data = {
                                'text': option_text,
                                'is_correct': is_correct
                            }
                            
                            # Add image if exists for this option
                            if str(i) in option_images:
                                option_data['image'] = option_images[str(i)]
                            
                            options.append(option_data)
                            if is_correct:
                                correct_answer = option_text
                
                elif question_type == 'true_false':
                    options = [
                        {'text': 'True', 'is_correct': False},
                        {'text': 'False', 'is_correct': False}
                    ]
                    correct_answer = request.form.get('correct_tf')
                    if correct_answer == 'true':
                        options[0]['is_correct'] = True
                        correct_answer = 'True'
                    else:
                        options[1]['is_correct'] = True
                        correct_answer = 'False'
                
                question.options = options
                question.correct_answer = correct_answer
            
            elif question_type == 'short_answer':
                correct_answer = request.form.get('short_answer')
                question.correct_answer = correct_answer
            
            elif question_type == 'essay':
                # Essay questions don't have a single correct answer
                question.correct_answer = None
            
            # Handle topics
            if topics:
                topic_list = [t.strip() for t in topics.split(',')]
                question.topics = topic_list
            
            db.session.add(question)
            
            # Log action
            audit_log = AuditLog(
                user_id=current_user.id,
                action='ADD_QUESTION',
                table_name='question_banks',
                record_id=question.id,
                details={
                    'subject_id': subject_id,
                    'question_type': question_type,
                    'difficulty': difficulty,
                    'has_image': question_image is not None
                },
                ip_address=request.remote_addr
            )
            db.session.add(audit_log)
            
            db.session.commit()
            
            flash('Question added successfully!', 'success')
            return redirect(url_for('teacher.question_bank'))
        
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding question: {str(e)}', 'danger')
            return redirect(url_for('teacher.add_question'))
    
    return render_template('teacher/add_question.html',
                         teacher=teacher,
                         assigned_subjects=assigned_subjects)

@teacher_bp.route('/question-bank/edit/<question_id>', methods=['GET', 'POST'])
@login_required
@teacher_required
def edit_question(question_id):
    """Edit a question in the question bank"""
    teacher = Teacher.query.filter_by(user_id=current_user.id).first_or_404()
    question = QuestionBank.query.get_or_404(question_id)
    
    # Verify ownership
    if question.teacher_id != teacher.id:
        flash('You do not have permission to edit this question', 'danger')
        return redirect(url_for('teacher.question_bank'))
    
    # Get subjects assigned to teacher
    current_term = AcademicTerm.query.filter_by(is_active=True).first()
    assigned_subjects = []
    
    if current_term:
        assignments = SubjectAssignment.query.filter_by(
            teacher_id=teacher.id,
            academic_term_id=current_term.id,
            is_active=True
        ).all()
        
        for assignment in assignments:
            subject = Subject.query.get(assignment.subject_id)
            if subject and subject.id not in [s['subject'].id for s in assigned_subjects]:
                assigned_subjects.append({
                    'subject': subject
                })
    
    if request.method == 'POST':
        try:
            # Update basic fields
            question.question_text = request.form.get('question_text')
            question.difficulty = request.form.get('difficulty')
            question.marks = float(request.form.get('marks', 1.0))
            question.explanation = request.form.get('explanation')
            
            # Handle topics
            topics = request.form.get('topics', '')
            if topics:
                question.topics = [t.strip() for t in topics.split(',') if t.strip()]
            else:
                question.topics = []
            
            # Handle question image upload
            if 'question_image' in request.files:
                image_file = request.files['question_image']
                if image_file and image_file.filename != '':
                    # Secure the filename
                    filename = secure_filename(image_file.filename)
                    # Create unique filename
                    unique_filename = f"question_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{filename}"
                    
                    # Create uploads directory if it doesn't exist
                    upload_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'questions')
                    os.makedirs(upload_dir, exist_ok=True)
                    
                    # Save the file
                    filepath = os.path.join(upload_dir, unique_filename)
                    image_file.save(filepath)
                    question.question_image = f"/static/uploads/questions/{unique_filename}"
                elif request.form.get('remove_question_image') == 'true':
                    # Remove existing image if requested
                    question.question_image = None
            
            # Handle question type specific fields
            if question.question_type in ['multiple_choice', 'true_false']:
                if question.question_type == 'multiple_choice':
                    options = []
                    correct_answer = None
                    option_count = int(request.form.get('option_count', len(question.options or [])))
                    
                    # Handle option images
                    option_images = {}
                    for i in range(1, 6):  # Max 5 options
                        image_key = f'option_image_{i}'
                        if image_key in request.files:
                            image_file = request.files[image_key]
                            if image_file and image_file.filename != '':
                                filename = secure_filename(image_file.filename)
                                unique_filename = f"option_{i}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{filename}"
                                
                                upload_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'options')
                                os.makedirs(upload_dir, exist_ok=True)
                                
                                filepath = os.path.join(upload_dir, unique_filename)
                                image_file.save(filepath)
                                option_images[str(i)] = f"/static/uploads/options/{unique_filename}"
                        elif request.form.get(f'remove_option_image_{i}') == 'true':
                            # Mark image for removal
                            option_images[str(i)] = None
                    
                    for i in range(1, option_count + 1):
                        option_text = request.form.get(f'option_{i}')
                        if option_text:
                            is_correct = request.form.get(f'correct_option') == str(i)
                            option_data = {
                                'text': option_text,
                                'is_correct': is_correct
                            }
                            
                            # Handle option images
                            if str(i) in option_images:
                                if option_images[str(i)] is None:
                                    # Remove existing image
                                    option_data['image'] = None
                                else:
                                    # Add new image
                                    option_data['image'] = option_images[str(i)]
                            elif question.options and i-1 < len(question.options) and 'image' in question.options[i-1]:
                                # Keep existing image
                                option_data['image'] = question.options[i-1]['image']
                            
                            options.append(option_data)
                            if is_correct:
                                correct_answer = option_text
                    
                    question.options = options
                    question.correct_answer = correct_answer
                
                elif question.question_type == 'true_false':
                    correct_answer = request.form.get('correct_tf')
                    if correct_answer == 'true':
                        question.options = [
                            {'text': 'True', 'is_correct': True},
                            {'text': 'False', 'is_correct': False}
                        ]
                        question.correct_answer = 'True'
                    else:
                        question.options = [
                            {'text': 'True', 'is_correct': False},
                            {'text': 'False', 'is_correct': True}
                        ]
                        question.correct_answer = 'False'
            
            elif question.question_type == 'short_answer':
                question.correct_answer = request.form.get('short_answer')
            
            question.updated_at = datetime.now(timezone.utc)
            
            # Log action
            audit_log = AuditLog(
                user_id=current_user.id,
                action='EDIT_QUESTION',
                table_name='question_banks',
                record_id=question_id,
                details={
                    'subject_id': question.subject_id,
                    'question_type': question.question_type,
                    'difficulty': question.difficulty
                },
                ip_address=request.remote_addr
            )
            db.session.add(audit_log)
            
            db.session.commit()
            
            flash('Question updated successfully!', 'success')
            return redirect(url_for('teacher.question_bank'))
        
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating question: {str(e)}', 'danger')
    
    # Prepare existing data for template
    existing_options = question.options or []
    
    return render_template('teacher/edit_question.html',
                         teacher=teacher,
                         question=question,
                         assigned_subjects=assigned_subjects,
                         existing_options=existing_options)

@teacher_bp.route('/question-bank/delete/<question_id>', methods=['POST'])
@login_required
@teacher_required
def delete_question(question_id):
    """Delete a question from the question bank"""
    try:
        teacher = Teacher.query.filter_by(user_id=current_user.id).first_or_404()
        question = QuestionBank.query.get_or_404(question_id)
        
        # Verify ownership
        if question.teacher_id != teacher.id:
            return jsonify({'success': False, 'message': 'Permission denied'}), 403
        
        # Check if question is used in any exam
        exam_questions = ExamQuestion.query.filter_by(question_bank_id=question_id).first()
        if exam_questions:
            return jsonify({
                'success': False, 
                'message': 'Cannot delete question that is used in an exam'
            }), 400
        
        # Delete associated images
        deleted_images = []
        
        # Delete question image if exists
        if question.question_image:
            try:
                # Extract filename from path
                image_path = question.question_image
                if image_path.startswith('/static/'):
                    # Convert to filesystem path
                    relative_path = image_path[len('/static/'):]
                    full_path = os.path.join(current_app.root_path, 'static', relative_path)
                    
                    if os.path.exists(full_path):
                        os.remove(full_path)
                        deleted_images.append(f'Question image: {os.path.basename(full_path)}')
            except Exception as img_error:
                # Log but don't fail the deletion
                print(f"Error deleting question image: {img_error}")
        
        # Delete option images for multiple choice questions
        if question.question_type == 'multiple_choice' and question.options:
            for i, option in enumerate(question.options):
                if 'image' in option and option['image']:
                    try:
                        image_path = option['image']
                        if image_path.startswith('/static/'):
                            relative_path = image_path[len('/static/'):]
                            full_path = os.path.join(current_app.root_path, 'static', relative_path)
                            
                            if os.path.exists(full_path):
                                os.remove(full_path)
                                deleted_images.append(f'Option {i+1} image: {os.path.basename(full_path)}')
                    except Exception as img_error:
                        print(f"Error deleting option image: {img_error}")
        
        # Log action before deletion
        audit_log = AuditLog(
            user_id=current_user.id,
            action='DELETE_QUESTION',
            table_name='question_banks',
            record_id=question_id,
            old_values={
                'subject_id': question.subject_id,
                'question_text': question.question_text[:100] + '...' if len(question.question_text) > 100 else question.question_text,
                'question_type': question.question_type,
                'had_images': len(deleted_images) > 0,
                'deleted_images': deleted_images if deleted_images else None
            },
            ip_address=request.remote_addr
        )
        db.session.add(audit_log)
        
        # Delete the question
        db.session.delete(question)
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': 'Question deleted successfully',
            'deleted_images': len(deleted_images)
        })
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400
    
@teacher_bp.route('/question-bank/bulk-upload', methods=['GET', 'POST'])
@login_required
@teacher_required
def bulk_upload_questions():
    """Bulk upload questions via Excel/CSV"""
    teacher = Teacher.query.filter_by(user_id=current_user.id).first_or_404()
    
    if request.method == 'POST':
        try:
            if 'file' not in request.files:
                flash('No file uploaded', 'danger')
                return redirect(url_for('teacher.bulk_upload_questions'))
            
            file = request.files['file']
            if file.filename == '':
                flash('No file selected', 'danger')
                return redirect(url_for('teacher.bulk_upload_questions'))
            
            if file and file.filename.endswith(('.xlsx', '.xls', '.csv')):
                # Read file
                if file.filename.endswith('.csv'):
                    df = pd.read_csv(file)
                else:
                    df = pd.read_excel(file)
                
                required_columns = ['subject_code', 'question_text', 'question_type', 'difficulty']
                missing_columns = [col for col in required_columns if col not in df.columns]
                
                if missing_columns:
                    flash(f'Missing required columns: {", ".join(missing_columns)}', 'danger')
                    return redirect(url_for('teacher.bulk_upload_questions'))
                
                success_count = 0
                error_count = 0
                errors = []
                
                for index, row in df.iterrows():
                    try:
                        # Get subject by code
                        subject = Subject.query.filter_by(code=row['subject_code']).first()
                        if not subject:
                            errors.append(f"Row {index+2}: Subject with code '{row['subject_code']}' not found")
                            error_count += 1
                            continue
                        
                        # Create question
                        question = QuestionBank(
                            subject_id=subject.id,
                            teacher_id=teacher.id,
                            question_text=str(row['question_text']).strip(),
                            question_type=row['question_type'],
                            difficulty=row.get('difficulty', 'medium'),
                            marks=float(row.get('marks', 1.0)),
                            explanation=str(row.get('explanation', '')).strip(),
                            created_by=current_user.id,
                            is_approved=False
                        )
                        
                        # Handle question type specific fields
                        if row['question_type'] == 'multiple_choice':
                            options = []
                            correct_option = row.get('correct_option', 1)
                            
                            for i in range(1, 5):
                                option_text = row.get(f'option_{i}')
                                if pd.notna(option_text):
                                    options.append({
                                        'text': str(option_text).strip(),
                                        'is_correct': i == int(correct_option)
                                    })
                            
                            question.options = options
                            if options:
                                correct_option_index = int(correct_option) - 1
                                if 0 <= correct_option_index < len(options):
                                    question.correct_answer = options[correct_option_index]['text']
                        
                        elif row['question_type'] == 'true_false':
                            correct_answer = str(row.get('correct_answer', 'True')).strip()
                            question.correct_answer = correct_answer
                            question.options = [
                                {'text': 'True', 'is_correct': correct_answer.lower() == 'true'},
                                {'text': 'False', 'is_correct': correct_answer.lower() == 'false'}
                            ]
                        
                        elif row['question_type'] == 'short_answer':
                            correct_answer = str(row.get('correct_answer', '')).strip()
                            question.correct_answer = correct_answer
                        
                        # Handle topics
                        topics = str(row.get('topics', '')).strip()
                        if topics:
                            topic_list = [t.strip() for t in topics.split(',')]
                            question.topics = topic_list
                        
                        db.session.add(question)
                        success_count += 1
                        
                    except Exception as e:
                        errors.append(f"Row {index+2}: {str(e)}")
                        error_count += 1
                
                # Log bulk upload
                audit_log = AuditLog(
                    user_id=current_user.id,
                    action='BULK_UPLOAD_QUESTIONS',
                    table_name='question_banks',
                    details={
                        'success_count': success_count,
                        'error_count': error_count,
                        'filename': file.filename
                    },
                    ip_address=request.remote_addr
                )
                db.session.add(audit_log)
                
                db.session.commit()
                
                if errors:
                    flash(f'Uploaded {success_count} questions with {error_count} errors', 'warning')
                else:
                    flash(f'Successfully uploaded {success_count} questions', 'success')
                
                return render_template('teacher/bulk_upload_result.html',
                                     teacher=teacher,
                                     success_count=success_count,
                                     error_count=error_count,
                                     errors=errors)
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error processing file: {str(e)}', 'danger')
            return redirect(url_for('teacher.bulk_upload_questions'))
    
    # GET request - show upload form
    return render_template('teacher/bulk_upload.html', teacher=teacher)

@teacher_bp.route('/question-bank/download-template')
@login_required
@teacher_required
def download_question_template():
    """Download Excel template for bulk question upload"""
    # Create DataFrame template
    df = pd.DataFrame(columns=[
        'subject_code', 
        'question_text', 
        'question_type', 
        'difficulty',
        'marks',
        'option_1',
        'option_2',
        'option_3',
        'option_4',
        'correct_option',
        'correct_answer',
        'explanation (optional)',
        'topics (optional, comma-separated)'
    ])
    
    # Add example rows
    examples = [
        {
            'subject_code': 'MATH101',
            'question_text': 'What is 2 + 2?',
            'question_type': 'multiple_choice',
            'difficulty': 'medium',
            'marks': 1.0,
            'option_1': '3',
            'option_2': '4',
            'option_3': '5',
            'option_4': '6',
            'correct_option': 2,
            'correct_answer': '',
            'explanation': 'Basic addition',
            'topics': 'addition,basic math'
        },
        {
            'subject_code': 'ENG101',
            'question_text': 'The sky is blue. True or False?',
            'question_type': 'true_false',
            'difficulty': 'medium',
            'marks': 1.0,
            'option_1': '',
            'option_2': '',
            'option_3': '',
            'option_4': '',
            'correct_option': '',
            'correct_answer': 'True',
            'explanation': 'The sky appears blue due to Rayleigh scattering',
            'topics': 'science,colors'
        }
    ]
    
    for example in examples:
        df = pd.concat([df, pd.DataFrame([example])], ignore_index=True)
    
    # Create Excel file in memory
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Template', index=False)
        
        # Add instructions sheet
        instructions_df = pd.DataFrame({
            'Column': [
                'subject_code', 
                'question_text', 
                'question_type', 
                'difficulty',
                'marks',
                'option_1 to option_4',
                'correct_option',
                'correct_answer',
                'explanation',
                'topics'
            ],
            'Description': [
                'Subject code (must exist in system)',
                'The question text',
                'multiple_choice, true_false, short_answer, or essay',
                'easy, medium, or hard',
                'Marks for this question (default: 1.0)',
                'Options for multiple choice questions',
                'For multiple choice: correct option number (1-4)',
                'For true_false/short_answer: correct answer',
                'Optional explanation',
                'Comma-separated topics'
            ],
            'Required': [
                'Yes',
                'Yes',
                'Yes',
                'No (default: medium)',
                'No (default: 1.0)',
                'Only for multiple_choice',
                'For multiple_choice and true_false/short_answer',
                'For true_false/short_answer',
                'No',
                'No'
            ]
        })
        instructions_df.to_excel(writer, sheet_name='Instructions', index=False)
    
    output.seek(0)
    
    filename = 'question_upload_template.xlsx'
    return send_file(output,
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                     as_attachment=True,
                     download_name=filename)

@teacher_bp.route('/question-bank/stats')
@login_required
@teacher_required
def question_bank_stats():
    """Get question bank statistics"""
    try:
        teacher = Teacher.query.filter_by(user_id=current_user.id).first_or_404()
        
        # Get total questions
        total_questions = QuestionBank.query.filter_by(teacher_id=teacher.id).count()
        
        # Get questions by type
        questions_by_type = db.session.query(
            QuestionBank.question_type,
            db.func.count(QuestionBank.id).label('count')
        ).filter_by(teacher_id=teacher.id).group_by(QuestionBank.question_type).all()
        
        # Get questions by difficulty
        questions_by_difficulty = db.session.query(
            QuestionBank.difficulty,
            db.func.count(QuestionBank.id).label('count')
        ).filter_by(teacher_id=teacher.id).group_by(QuestionBank.difficulty).all()
        
        # Get questions by subject
        questions_by_subject = db.session.query(
            Subject.name,
            db.func.count(QuestionBank.id).label('count')
        ).join(QuestionBank, Subject.id == QuestionBank.subject_id
        ).filter(QuestionBank.teacher_id == teacher.id
        ).group_by(Subject.name).all()
        
        # Get approval status
        approved_count = QuestionBank.query.filter_by(
            teacher_id=teacher.id,
            is_approved=True
        ).count()
        
        pending_count = total_questions - approved_count
        
        stats = {
            'total_questions': total_questions,
            'approved_count': approved_count,
            'pending_count': pending_count,
            'questions_by_type': dict(questions_by_type),
            'questions_by_difficulty': dict(questions_by_difficulty),
            'questions_by_subject': dict(questions_by_subject),
            'approval_rate': (approved_count / total_questions * 100) if total_questions > 0 else 0
        }
        
        return jsonify({
            'success': True,
            'stats': stats
        })
    
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400

@teacher_bp.route('/question-bank/request-approval/<question_id>', methods=['POST'])
@login_required
@teacher_required
def request_question_approval(question_id):
    """Request approval for a question"""
    try:
        teacher = Teacher.query.filter_by(user_id=current_user.id).first_or_404()
        question = QuestionBank.query.get_or_404(question_id)
        
        # Verify ownership
        if question.teacher_id != teacher.id:
            return jsonify({'success': False, 'message': 'Permission denied'}), 403
        
        # Check if already approved
        if question.is_approved:
            return jsonify({'success': False, 'message': 'Question is already approved'}), 400
        
        # In a real system, you might send a notification to admin here
        # For now, we'll just log the request
        
        audit_log = AuditLog(
            user_id=current_user.id,
            action='REQUEST_APPROVAL',
            table_name='question_banks',
            record_id=question_id,
            details={
                'subject_id': question.subject_id,
                'question_type': question.question_type,
                'teacher_id': teacher.id
            },
            ip_address=request.remote_addr
        )
        db.session.add(audit_log)
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': 'Approval request submitted successfully'
        })
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400


@teacher_bp.route('/exams')
@login_required
@teacher_required
def exams():
    """Manage exams"""
    teacher = Teacher.query.filter_by(user_id=current_user.id).first_or_404()
    current_term = AcademicTerm.query.filter_by(is_active=True).first()
    
    if not current_term:
        flash('No active academic term!', 'warning')
        return redirect(url_for('teacher.dashboard'))
    
    # Get exams created by teacher for current term
    exams_list = Exam.query.filter_by(
        teacher_id=teacher.id,
        academic_term_id=current_term.id
    ).order_by(Exam.created_at.desc()).all()
    
    # Get subject assignments
    assignments = SubjectAssignment.query.filter_by(
        teacher_id=teacher.id,
        academic_term_id=current_term.id,
        is_active=True
    ).all()
    
    assigned_classes = []
    for assignment in assignments:
        subject = Subject.query.get(assignment.subject_id)
        classroom = ClassRoom.query.get(assignment.class_id)
        if subject and classroom:
            # Get question count for this subject
            question_count = QuestionBank.query.filter_by(
                subject_id=subject.id,
                teacher_id=teacher.id
            ).count()
            
            assigned_classes.append({
                'subject': subject,
                'classroom': classroom,
                'assignment': assignment,
                'question_count': question_count
            })
    
    # Group exams by status
    exam_stats = {
        'draft': 0,
        'scheduled': 0,
        'active': 0,
        'completed': 0,
        'total': len(exams_list)
    }
    
    for exam in exams_list:
        if exam.status in exam_stats:
            exam_stats[exam.status] += 1
    
    return render_template('teacher/exams.html',
                         teacher=teacher,
                         exams=exams_list,
                         assigned_classes=assigned_classes,
                         current_term=current_term,
                         exam_stats=exam_stats)

@teacher_bp.route('/exams/create', methods=['POST'])
@login_required
@teacher_required
def create_exam():
    """Create a new exam"""
    try:
        teacher = Teacher.query.filter_by(user_id=current_user.id).first_or_404()
        current_term = AcademicTerm.query.filter_by(is_active=True).first()
        
        if not current_term:
            return jsonify({'success': False, 'message': 'No active academic term'}), 400
        
        print(f"Form data received: {request.form}")  # Debug log
        print(f"Request method: {request.method}")    # Debug log
        
        # Get form data - using new field names
        exam_name = request.form.get('exam_name')
        exam_type = request.form.get('exam_type')
        
        # Get subject and class from the combined selection or hidden fields
        subject_id = request.form.get('subject_id')
        class_id = request.form.get('class_id')
        
        # If using combined selection field (backward compatibility)
        if not subject_id or not class_id:
            subject_selection = request.form.get('subject_selection')
            if subject_selection and '_' in subject_selection:
                subject_id, class_id = subject_selection.split('_')
        
        duration = request.form.get('duration')
        total_marks = float(request.form.get('total_marks'))
        instructions = request.form.get('instructions')
        
        print(f"Parsed values - Name: {exam_name}, Type: {exam_type}, Subject: {subject_id}, Class: {class_id}, Duration: {duration}, Marks: {total_marks}")
        
        # Validate required fields
        required_fields = {
            'exam_name': exam_name,
            'exam_type': exam_type,
            'subject_id': subject_id,
            'class_id': class_id,
            'duration': duration,
            'total_marks': total_marks
        }
        
        missing_fields = [field for field, value in required_fields.items() if not value]
        if missing_fields:
            print(f"Missing fields: {missing_fields}")  # Debug log
            return jsonify({
                'success': False, 
                'message': f'Please fill in all required fields. Missing: {", ".join(missing_fields)}'
            }), 400
        
        # Verify teacher is assigned to this subject and class
        assignment = SubjectAssignment.query.filter_by(
            teacher_id=teacher.id,
            subject_id=subject_id,
            class_id=class_id,
            academic_term_id=current_term.id,
            is_active=True
        ).first()
        
        if not assignment:
            print(f"No assignment found for teacher {teacher.id}, subject {subject_id}, class {class_id}")  # Debug log
            return jsonify({
                'success': False, 
                'message': 'You are not assigned to teach this subject in this class'
            }), 400
        
        # Create exam
        exam = Exam(
            name=exam_name,
            subject_id=subject_id,
            teacher_id=teacher.id,
            class_id=class_id,
            academic_term_id=current_term.id,
            duration_minutes=duration,
            total_marks=total_marks,
            instructions=instructions,
            status='draft',
            pass_mark=total_marks * 0.4,  # Default 40% pass mark
            created_at=datetime.now(timezone.utc)
        )
        
        db.session.add(exam)
        
        # Log action
        audit_log = AuditLog(
            user_id=current_user.id,
            action='CREATE_EXAM',
            table_name='exams',
            record_id=exam.id,
            details={
                'exam_name': exam_name,
                'subject_id': subject_id,
                'class_id': class_id,
                'exam_type': exam_type,
                'duration': duration,
                'total_marks': total_marks
            },
            ip_address=request.remote_addr
        )
        db.session.add(audit_log)
        
        db.session.commit()
        
        flash('Exam created successfully! You can now add questions.', 'success')
        
        return redirect(url_for('teacher.exams'))
        
    except Exception as e:
        db.session.rollback()
        print(f"Error creating exam: {str(e)}")  # Debug log
        import traceback
        traceback.print_exc()  # Print full traceback
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 400

@teacher_bp.route('/exams/delete/<exam_id>', methods=['POST'])
@login_required
@teacher_required
def delete_exam(exam_id):
    """Delete an exam"""
    try:
        teacher = Teacher.query.filter_by(user_id=current_user.id).first_or_404()
        exam = Exam.query.get_or_404(exam_id)
        
        # Verify ownership
        if exam.teacher_id != teacher.id:
            return jsonify({'success': False, 'message': 'Permission denied'}), 403
        
        # Check if exam has sessions
        exam_sessions = ExamSession.query.filter_by(exam_id=exam_id).first()
        if exam_sessions:
            return jsonify({
                'success': False, 
                'message': 'Cannot delete exam that has student sessions'
            }), 400
        
        # Log action before deletion
        audit_log = AuditLog(
            user_id=current_user.id,
            action='DELETE_EXAM',
            table_name='exams',
            record_id=exam_id,
            old_values={
                'exam_name': exam.name,
                'subject_id': exam.subject_id,
                'class_id': exam.class_id,
                'status': exam.status
            },
            ip_address=request.remote_addr
        )
        db.session.add(audit_log)
        
        db.session.delete(exam)
        db.session.commit()

        flash('Exam deleted successfully!', 'success')
        
        return redirect(url_for('teacher.exams'))
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400
    
@teacher_bp.route('/exams/view/<exam_id>')
@login_required
@teacher_required
def view_exam(exam_id):
    """View exam details"""
    teacher = Teacher.query.filter_by(user_id=current_user.id).first_or_404()
    exam = Exam.query.get_or_404(exam_id)
    
    # Verify ownership
    if exam.teacher_id != teacher.id:
        flash('You do not have permission to view this exam', 'danger')
        return redirect(url_for('teacher.exams'))
    
    # Get exam questions with details
    exam_questions = ExamQuestion.query.filter_by(exam_id=exam_id).order_by(ExamQuestion.order).all()
    
    questions = []
    for eq in exam_questions:
        question = QuestionBank.query.get(eq.question_bank_id)
        if question:
            questions.append({
                'exam_question': eq,
                'question': question,
                'marks': eq.marks or question.marks
            })
    
    # Get exam sessions
    exam_sessions = ExamSession.query.filter_by(exam_id=exam_id).all()
    
    # Get class students
    students = Student.query.filter_by(
        current_class_id=exam.class_id,
        is_active=True,
        academic_status='active'
    ).order_by(Student.admission_number).all()
    
    # Calculate statistics
    total_questions = len(questions)
    total_marks = sum(q['marks'] for q in questions) if questions else exam.total_marks
    
    return render_template('teacher/view_exam.html',
                         teacher=teacher,
                         exam=exam,
                         questions=questions,
                         exam_sessions=exam_sessions,
                         students=students,
                         total_questions=total_questions,
                         total_marks=total_marks)

@teacher_bp.route('/exams/edit/<exam_id>', methods=['GET', 'POST'])
@login_required
@teacher_required
def edit_exam(exam_id):
    """Edit an exam"""
    teacher = Teacher.query.filter_by(user_id=current_user.id).first_or_404()
    exam = Exam.query.get_or_404(exam_id)
    
    # Verify ownership
    if exam.teacher_id != teacher.id:
        flash('You do not have permission to edit this exam', 'danger')
        return redirect(url_for('teacher.exams'))
    
    if request.method == 'POST':
        try:
            # Update exam details
            exam.name = request.form.get('exam_name')
            exam.duration_minutes = int(request.form.get('duration', 60))
            exam.total_marks = float(request.form.get('total_marks', 100))
            exam.pass_mark = float(request.form.get('pass_mark', 40))
            exam.instructions = request.form.get('instructions')
            exam.access_code = request.form.get('access_code')
            
            # Settings
            exam.is_randomized = 'is_randomized' in request.form
            exam.shuffle_questions = 'shuffle_questions' in request.form
            exam.shuffle_options = 'shuffle_options' in request.form
            exam.allow_back_navigation = 'allow_back_navigation' in request.form
            exam.show_results_immediately = 'show_results_immediately' in request.form
            
            # Schedule
            scheduled_start = request.form.get('scheduled_start')
            scheduled_end = request.form.get('scheduled_end')
            
            if scheduled_start:
                exam.scheduled_start = datetime.fromisoformat(scheduled_start.replace('T', ' '))
            if scheduled_end:
                exam.scheduled_end = datetime.fromisoformat(scheduled_end.replace('T', ' '))
            
            exam.updated_at = datetime.now(timezone.utc)
            
            # Log action
            audit_log = AuditLog(
                user_id=current_user.id,
                action='UPDATE_EXAM',
                table_name='exams',
                record_id=exam_id,
                details={
                    'exam_name': exam.name,
                    'status': exam.status
                },
                ip_address=request.remote_addr
            )
            db.session.add(audit_log)
            
            db.session.commit()
            
            flash('Exam updated successfully!', 'success')
            return redirect(url_for('teacher.edit_exam', exam_id=exam_id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating exam: {str(e)}', 'danger')
    
    # GET request - show edit form
    # Get exam questions
    exam_questions = ExamQuestion.query.filter_by(exam_id=exam_id).order_by(ExamQuestion.order).all()
    
    questions = []
    questions_json = []  # New: JSON serializable version
    
    for eq in exam_questions:
        question = QuestionBank.query.get(eq.question_bank_id)
        if question:
            questions.append({
                'exam_question': eq,
                'question': question,
                'marks': eq.marks or question.marks
            })
            
            # Add to JSON serializable list
            questions_json.append({
                'question': {
                    'id': question.id,
                    'question_text': question.question_text,
                    'question_type': question.question_type,
                    'difficulty': question.difficulty,
                    'marks': question.marks,
                    'topics': question.topics or [] if hasattr(question, 'topics') else []
                },
                'marks': eq.marks or question.marks
            })
    
    # Get available questions from question bank
    available_questions = QuestionBank.query.filter_by(
        subject_id=exam.subject_id,
        teacher_id=teacher.id
    ).all()
    
    # Group questions by type and difficulty
    questions_by_type = {}
    questions_by_difficulty = {}
    
    for q in available_questions:
        # By type
        if q.question_type not in questions_by_type:
            questions_by_type[q.question_type] = []
        questions_by_type[q.question_type].append(q)
        
        # By difficulty
        if q.difficulty not in questions_by_difficulty:
            questions_by_difficulty[q.difficulty] = []
        questions_by_difficulty[q.difficulty].append(q)
    
    return render_template('teacher/edit_exam.html',
                         teacher=teacher,
                         exam=exam,
                         questions=questions,
                         questions_json=questions_json,  # Add this
                         available_questions=available_questions,
                         questions_by_type=questions_by_type,
                         questions_by_difficulty=questions_by_difficulty)

@teacher_bp.route('/exams/<exam_id>/add-questions', methods=['POST'])
@login_required
@teacher_required
def add_exam_questions(exam_id):
    """Add questions to an exam"""
    try:
        teacher = Teacher.query.filter_by(user_id=current_user.id).first_or_404()
        exam = Exam.query.get_or_404(exam_id)
        
        # Verify ownership
        if exam.teacher_id != teacher.id:
            return jsonify({'success': False, 'message': 'Permission denied'}), 403
        
        data = request.get_json()
        if not data or 'questions' not in data:
            return jsonify({'success': False, 'message': 'No questions provided'}), 400
        
        added_count = 0
        for question_data in data['questions']:
            question_id = question_data.get('id')
            marks = question_data.get('marks', 1.0)
            
            # Check if question already in exam
            existing = ExamQuestion.query.filter_by(
                exam_id=exam_id,
                question_bank_id=question_id
            ).first()
            
            if not existing:
                # Get the next order number
                max_order = db.session.query(db.func.max(ExamQuestion.order)).filter_by(exam_id=exam_id).scalar()
                next_order = (max_order or 0) + 1
                
                # Add question to exam
                exam_question = ExamQuestion(
                    exam_id=exam_id,
                    question_bank_id=question_id,
                    order=next_order,
                    marks=float(marks)
                )
                db.session.add(exam_question)
                added_count += 1
        
        # Log action
        audit_log = AuditLog(
            user_id=current_user.id,
            action='ADD_EXAM_QUESTIONS',
            table_name='exam_questions',
            record_id=exam_id,
            details={
                'exam_id': exam_id,
                'added_count': added_count
            },
            ip_address=request.remote_addr
        )
        db.session.add(audit_log)
        
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': f'{added_count} questions added to exam',
            'count': added_count
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400

@teacher_bp.route('/exams/<exam_id>/remove-question/<question_id>', methods=['POST'])
@login_required
@teacher_required
def remove_exam_question(exam_id, question_id):
    """Remove a question from an exam"""
    try:
        teacher = Teacher.query.filter_by(user_id=current_user.id).first_or_404()
        exam = Exam.query.get_or_404(exam_id)
        
        # Verify ownership
        if exam.teacher_id != teacher.id:
            return jsonify({'success': False, 'message': 'Permission denied'}), 403
        
        # Find and remove the exam question
        exam_question = ExamQuestion.query.filter_by(
            exam_id=exam_id,
            question_bank_id=question_id
        ).first()
        
        if not exam_question:
            return jsonify({'success': False, 'message': 'Question not found in exam'}), 404
        
        # Log action
        audit_log = AuditLog(
            user_id=current_user.id,
            action='REMOVE_EXAM_QUESTION',
            table_name='exam_questions',
            record_id=exam_question.id,
            details={
                'exam_id': exam_id,
                'question_id': question_id
            },
            ip_address=request.remote_addr
        )
        db.session.add(audit_log)
        
        db.session.delete(exam_question)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Question removed from exam'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400

@teacher_bp.route('/exams/<exam_id>/update-order', methods=['POST'])
@login_required
@teacher_required
def update_exam_question_order(exam_id):
    """Update question order and marks in an exam"""
    try:
        teacher = Teacher.query.filter_by(user_id=current_user.id).first_or_404()
        exam = Exam.query.get_or_404(exam_id)
        
        # Verify ownership
        if exam.teacher_id != teacher.id:
            return jsonify({'success': False, 'message': 'Permission denied'}), 403
        
        data = request.get_json()
        if not data or 'questions' not in data:
            return jsonify({'success': False, 'message': 'No questions provided'}), 400
        
        updated_count = 0
        for i, question_data in enumerate(data['questions']):
            question_id = question_data.get('id')
            marks = question_data.get('marks', 1.0)
            
            # Update exam question
            exam_question = ExamQuestion.query.filter_by(
                exam_id=exam_id,
                question_bank_id=question_id
            ).first()
            
            if exam_question:
                exam_question.order = i + 1
                exam_question.marks = float(marks)
                updated_count += 1
        
        # Log action
        audit_log = AuditLog(
            user_id=current_user.id,
            action='UPDATE_EXAM_ORDER',
            table_name='exam_questions',
            record_id=exam_id,
            details={
                'exam_id': exam_id,
                'updated_count': updated_count
            },
            ip_address=request.remote_addr
        )
        db.session.add(audit_log)
        
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': f'Updated {updated_count} questions',
            'count': updated_count
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400

@teacher_bp.route('/exams/publish/<exam_id>', methods=['POST'])
@login_required
@teacher_required
def publish_exam(exam_id):
    """Publish an exam"""
    try:
        teacher = Teacher.query.filter_by(user_id=current_user.id).first_or_404()
        exam = Exam.query.get_or_404(exam_id)
        
        # Verify ownership
        if exam.teacher_id != teacher.id:
            return jsonify({'success': False, 'message': 'Permission denied'}), 403
        
        # Check if exam has questions
        question_count = ExamQuestion.query.filter_by(exam_id=exam_id).count()
        if question_count == 0:
            return jsonify({'success': False, 'message': 'Exam must have at least one question'}), 400
        
        data = request.get_json()
        status = data.get('status', 'scheduled')
        
        exam.status = status
        exam.updated_at = datetime.now(timezone.utc)
        
        # Log action
        audit_log = AuditLog(
            user_id=current_user.id,
            action='PUBLISH_EXAM',
            table_name='exams',
            record_id=exam_id,
            details={
                'exam_id': exam_id,
                'new_status': status
            },
            ip_address=request.remote_addr
        )
        db.session.add(audit_log)
        
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': f'Exam published successfully as {status}'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400

@teacher_bp.route('/exams/activate/<exam_id>', methods=['POST'])
@login_required
@teacher_required
def activate_exam(exam_id):
    """Activate a scheduled exam (make it available to students)"""
    try:
        teacher = Teacher.query.filter_by(user_id=current_user.id).first_or_404()
        exam = Exam.query.get_or_404(exam_id)
        
        # Verify ownership
        if exam.teacher_id != teacher.id:
            return jsonify({'success': False, 'message': 'Permission denied'}), 403
        
        # Check if exam is scheduled
        if exam.status != 'scheduled':
            return jsonify({
                'success': False, 
                'message': f'Exam is {exam.status}, not scheduled'
            }), 400
        
        # Check if exam has questions
        question_count = ExamQuestion.query.filter_by(exam_id=exam_id).count()
        if question_count == 0:
            return jsonify({
                'success': False, 
                'message': 'Exam must have at least one question'
            }), 400
        
        # Check if scheduled time is in the past
        if exam.scheduled_start:
            # Make exam.scheduled_start timezone-aware
            if exam.scheduled_start.tzinfo is None:
                # If scheduled_start is naive, assume it's in UTC
                exam_scheduled_start = exam.scheduled_start.replace(tzinfo=timezone.utc)
            else:
                exam_scheduled_start = exam.scheduled_start
            
            current_time = datetime.now(timezone.utc)
            
            """if exam_scheduled_start > current_time:
                return jsonify({
                    'success': False, 
                    'message': f'Exam scheduled time has not arrived yet. It starts at {exam_scheduled_start.strftime("%Y-%m-%d %H:%M UTC")}'
                }), 400"""
        
        # Update exam status
        exam.status = 'active'
        exam.updated_at = datetime.now(timezone.utc)
        
        # Log action
        audit_log = AuditLog(
            user_id=current_user.id,
            action='ACTIVATE_EXAM',
            table_name='exams',
            record_id=exam_id,
            details={
                'exam_id': exam_id,
                'old_status': 'scheduled',
                'new_status': 'active'
            },
            ip_address=request.remote_addr
        )
        db.session.add(audit_log)
        
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': 'Exam activated successfully!',
            'exam_status': exam.status
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400
            

# Attendance Management
@teacher_bp.route('/attendance')
@login_required
@teacher_required
def attendance():
    """Attendance management dashboard"""
    teacher = Teacher.query.filter_by(user_id=current_user.id).first_or_404()
    
    # Get current term
    current_term = AcademicTerm.query.filter_by(is_active=True).first()
    if not current_term:
        flash('No active academic term!', 'warning')
        return redirect(url_for('teacher.dashboard'))
    
    # Check if teacher is a form teacher
    if not teacher.form_class_id:
        flash('You are not assigned as a form teacher!', 'warning')
        return redirect(url_for('teacher.dashboard'))
    
    # Get form class students
    students = Student.query.filter_by(
        current_class_id=teacher.form_class_id,
        is_active=True,
        academic_status='active'
    ).order_by(Student.first_name, Student.last_name).all()
    
    # Get today's date
    today = datetime.now(timezone.utc).date()
    
    # Get attendance for today
    today_attendance = Attendance.query.filter_by(
        classroom_id=teacher.form_class_id,
        date=today
    ).all()
    
    # Create a dictionary of today's attendance
    attendance_dict = {att.student_id: att for att in today_attendance}
    
    # Get attendance statistics for current month
    month_start = date(today.year, today.month, 1)
    month_end = date(today.year, today.month, 1) + timedelta(days=32)
    month_end = month_end.replace(day=1) - timedelta(days=1)
    
    # Get all attendance for current month
    month_attendance = Attendance.query.filter(
        Attendance.classroom_id == teacher.form_class_id,
        Attendance.date >= month_start,
        Attendance.date <= month_end
    ).all()
    
    # Calculate statistics
    total_school_days = get_school_days(month_start, month_end)
    attendance_stats = {}
    
    for student in students:
        student_attendance = [a for a in month_attendance if a.student_id == student.id]
        present_count = len([a for a in student_attendance if a.status in ['present', 'late']])
        absent_count = len([a for a in student_attendance if a.status == 'absent'])
        excused_count = len([a for a in student_attendance if a.status == 'excused'])
        
        attendance_stats[student.id] = {
            'present': present_count,
            'absent': absent_count,
            'excused': excused_count,
            'attendance_rate': round((present_count / total_school_days * 100), 1) if total_school_days > 0 else 0
        }
    
    return render_template('teacher/attendance.html',
                         teacher=teacher,
                         students=students,
                         current_term=current_term,
                         today=today,
                         today_attendance=attendance_dict,
                         attendance_stats=attendance_stats,
                         total_school_days=total_school_days)

def get_school_days(start_date, end_date):
    """Calculate number of school days between two dates (excluding weekends)"""
    school_days = 0
    current_date = start_date
    
    while current_date <= end_date:
        # Monday = 0, Sunday = 6
        if current_date.weekday() < 5:  # Monday to Friday
            school_days += 1
        current_date += timedelta(days=1)
    
    return school_days

@teacher_bp.route('/mark-attendance', methods=['POST'])
@login_required
@teacher_required
def mark_attendance():
    """Mark attendance for students"""
    try:
        teacher = Teacher.query.filter_by(user_id=current_user.id).first_or_404()
        
        if not teacher.form_class_id:
            return jsonify({'success': False, 'message': 'You are not a form teacher'}), 403
        
        data = request.get_json()
        date_str = data.get('date')
        attendance_data = data.get('attendance_data', [])
        
        if not date_str or not attendance_data:
            return jsonify({'success': False, 'message': 'Missing required data'}), 400
        
        try:
            attendance_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return jsonify({'success': False, 'message': 'Invalid date format'}), 400
        
        # Check if attendance is for future date
        if attendance_date > datetime.now(timezone.utc).date():
            return jsonify({'success': False, 'message': 'Cannot mark attendance for future dates'}), 400
        
        successful_saves = 0
        errors = []
        
        for item in attendance_data:
            student_id = item.get('student_id')
            status = item.get('status')
            session = item.get('session', 'full_day')
            remark = item.get('remark', '')
            
            if not student_id or not status:
                errors.append(f"Missing data for student")
                continue
            
            # Verify student is in teacher's form class
            student = Student.query.get(student_id)
            if not student:
                errors.append(f"Student {student_id} not found")
                continue
                
            if student.current_class_id != teacher.form_class_id:
                errors.append(f"Student {student.first_name} is not in your form class")
                continue
            
            # Check if attendance already exists for this date
            existing_attendance = Attendance.query.filter_by(
                student_id=student_id,
                classroom_id=teacher.form_class_id,
                date=attendance_date
            ).first()
            
            if existing_attendance:
                # Update existing attendance
                existing_attendance.status = status
                existing_attendance.session = session
                existing_attendance.remark = remark
                existing_attendance.teacher_id = teacher.id
                existing_attendance.updated_at = datetime.now(timezone.utc)
                action = 'UPDATE'
            else:
                # Create new attendance
                new_attendance = Attendance(
                    student_id=student_id,
                    classroom_id=teacher.form_class_id,
                    teacher_id=teacher.id,
                    date=attendance_date,
                    status=status,
                    session=session,
                    remark=remark,
                    recorded_at=datetime.now(timezone.utc)
                )
                db.session.add(new_attendance)
                action = 'CREATE'
            
            successful_saves += 1
        
        db.session.commit()
        
        # Log action
        audit_log = AuditLog(
            user_id=current_user.id,
            action='MARK_ATTENDANCE',
            table_name='attendance',
            record_id=f"{teacher.form_class_id}_{attendance_date}",
            new_values={
                'date': attendance_date.isoformat(),
                'students_marked': successful_saves,
                'errors': errors
            },
            details={'class': teacher.form_class.name},
            ip_address=request.remote_addr
        )
        db.session.add(audit_log)
        db.session.commit()
        
        message = f"Attendance marked for {successful_saves} students"
        if errors:
            message += f". Errors: {len(errors)}"
        
        return jsonify({
            'success': True, 
            'message': message,
            'saved_count': successful_saves,
            'errors': errors
        })
        
    except Exception as e:
        db.session.rollback()
        import traceback
        print(traceback.format_exc())
        return jsonify({'success': False, 'message': str(e)}), 500

@teacher_bp.route('/attendance-report')
@login_required
@teacher_required
def attendance_report():
    """Generate attendance reports"""
    teacher = Teacher.query.filter_by(user_id=current_user.id).first_or_404()
    
    if not teacher.form_class_id:
        flash('You are not assigned as a form teacher!', 'warning')
        return redirect(url_for('teacher.dashboard'))
    
    # Get current term
    current_term = AcademicTerm.query.filter_by(is_active=True).first()
    
    # Get date range parameters
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    
    # Default to current month if no dates provided
    today = datetime.now(timezone.utc).date()
    if not start_date_str:
        start_date = date(today.year, today.month, 1)
    else:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
    
    if not end_date_str:
        end_date = today
    else:
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
    
    # Get form class students
    students = Student.query.filter_by(
        current_class_id=teacher.form_class_id,
        is_active=True,
        academic_status='active'
    ).order_by(Student.first_name, Student.last_name).all()
    
    # Get attendance data for date range
    attendance_records = Attendance.query.filter(
        Attendance.classroom_id == teacher.form_class_id,
        Attendance.date >= start_date,
        Attendance.date <= end_date
    ).order_by(Attendance.date.desc()).all()
    
    # Calculate statistics
    total_school_days = get_school_days(start_date, end_date)
    
    # Group attendance by student
    student_attendance = []
    for student in students:
        student_records = [r for r in attendance_records if r.student_id == student.id]
        
        present_count = len([r for r in student_records if r.status in ['present', 'late']])
        absent_count = len([r for r in student_records if r.status == 'absent'])
        late_count = len([r for r in student_records if r.status == 'late'])
        excused_count = len([r for r in student_records if r.status == 'excused'])
        
        attendance_rate = round((present_count / total_school_days * 100), 1) if total_school_days > 0 else 0
        
        student_attendance.append({
            'student': student,
            'records': student_records,
            'present': present_count,
            'absent': absent_count,
            'late': late_count,
            'excused': excused_count,
            'attendance_rate': attendance_rate,
            'days_missed': absent_count
        })
    
    # Summary statistics
    total_students = len(students)
    total_present = sum(item['present'] for item in student_attendance)
    total_absent = sum(item['absent'] for item in student_attendance)
    average_attendance = round(sum(item['attendance_rate'] for item in student_attendance) / total_students, 1) if total_students > 0 else 0
    
    # Sort students by attendance rate (descending)
    student_attendance.sort(key=lambda x: x['attendance_rate'], reverse=True)
    
    return render_template('teacher/attendance_report.html',
                         teacher=teacher,
                         current_term=current_term,
                         start_date=start_date,
                         end_date=end_date,
                         today=today,
                         total_school_days=total_school_days,
                         student_attendance=student_attendance,
                         total_students=total_students,
                         total_present=total_present,
                         total_absent=total_absent,
                         average_attendance=average_attendance)

@teacher_bp.route('/export-attendance')
@login_required
@teacher_required
def export_attendance():
    """Export attendance data as CSV"""
    try:
        teacher = Teacher.query.filter_by(user_id=current_user.id).first_or_404()
        
        if not teacher.form_class_id:
            return jsonify({'success': False, 'message': 'You are not a form teacher'}), 403
        
        # Get date range parameters
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')
        
        # Default to current month
        today = datetime.now(timezone.utc).date()
        if not start_date_str:
            start_date = date(today.year, today.month, 1)
        else:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        
        if not end_date_str:
            end_date = today
        else:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        
        # Get attendance data
        attendance_records = Attendance.query.join(Student).filter(
            Attendance.classroom_id == teacher.form_class_id,
            Attendance.date >= start_date,
            Attendance.date <= end_date
        ).order_by(Attendance.date, Student.first_name).all()
        
        # Create CSV
        csv_data = []
        csv_data.append('Date,Student Name,Admission Number,Status,Session,Remark,Recorded At')
        
        for record in attendance_records:
            csv_data.append(f'"{record.date}","{record.student.first_name} {record.student.last_name}",'
                          f'"{record.student.admission_number}","{record.status}","{record.session or ""}",'
                          f'"{record.remark or ""}","{record.recorded_at}"')
        
        csv_content = '\n'.join(csv_data)
        
        # Create response
        response = make_response(csv_content)
        response.headers['Content-Disposition'] = f'attachment; filename=attendance_{teacher.form_class.name.replace(" ", "_")}_{start_date}_{end_date}.csv'
        response.headers['Content-Type'] = 'text/csv'
        
        return response
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@teacher_bp.route('/attendance-calendar')
@login_required
@teacher_required
def attendance_calendar():
    """View attendance calendar"""
    teacher = Teacher.query.filter_by(user_id=current_user.id).first_or_404()
    
    if not teacher.form_class_id:
        flash('You are not assigned as a form teacher!', 'warning')
        return redirect(url_for('teacher.dashboard'))
    
    # Get month and year parameters
    year = request.args.get('year', datetime.now().year, type=int)
    month = request.args.get('month', datetime.now().month, type=int)
    
    # Calculate previous and next months
    if month == 1:
        prev_year = year - 1
        prev_month = 12
    else:
        prev_year = year
        prev_month = month - 1
    
    if month == 12:
        next_year = year + 1
        next_month = 1
    else:
        next_year = year
        next_month = month + 1
    
    # Get attendance for the month
    month_start = date(year, month, 1)
    month_end = date(year, month, 1) + timedelta(days=32)
    month_end = month_end.replace(day=1) - timedelta(days=1)
    
    attendance_records = Attendance.query.filter(
        Attendance.classroom_id == teacher.form_class_id,
        Attendance.date >= month_start,
        Attendance.date <= month_end
    ).all()
    
    # Group by date
    daily_attendance = {}
    for record in attendance_records:
        date_str = record.date.isoformat()
        if date_str not in daily_attendance:
            daily_attendance[date_str] = {
                'present': 0,
                'absent': 0,
                'late': 0,
                'excused': 0,
                'total': 0
            }
        
        daily_attendance[date_str][record.status] += 1
        daily_attendance[date_str]['total'] += 1
    
    # Get current term
    current_term = AcademicTerm.query.filter_by(is_active=True).first()
    
    # Get total students
    total_students = len(teacher.form_class.class_students)
    
    # Calculate summary statistics
    total_present = sum(stats['present'] for stats in daily_attendance.values())
    total_absent = sum(stats['absent'] for stats in daily_attendance.values())
    total_late = sum(stats['late'] for stats in daily_attendance.values())
    total_excused = sum(stats['excused'] for stats in daily_attendance.values())
    
    return render_template('teacher/attendance_calendar.html',
                         teacher=teacher,
                         current_term=current_term,
                         year=year,
                         month=month,
                         daily_attendance=daily_attendance,
                         month_start=month_start,
                         month_end=month_end,
                         prev_year=prev_year,
                         prev_month=prev_month,
                         next_year=next_year,
                         next_month=next_month,
                         total_students=total_students,
                         today=datetime.now(timezone.utc).date(),
                         total_present=total_present,
                         total_absent=total_absent,
                         total_late=total_late,
                         total_excused=total_excused)

@teacher_bp.route('/get-attendance')
@login_required
@teacher_required
def get_attendance():
    """Get attendance for a specific date"""
    try:
        teacher = Teacher.query.filter_by(user_id=current_user.id).first_or_404()
        
        if not teacher.form_class_id:
            return jsonify({'success': False, 'message': 'You are not a form teacher'}), 403
        
        date_str = request.args.get('date')
        if not date_str:
            return jsonify({'success': False, 'message': 'Date is required'}), 400
        
        try:
            attendance_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return jsonify({'success': False, 'message': 'Invalid date format'}), 400
        
        # Get attendance for the date
        attendance_records = Attendance.query.filter_by(
            classroom_id=teacher.form_class_id,
            date=attendance_date
        ).all()
        
        attendance_data = []
        for record in attendance_records:
            attendance_data.append({
                'student_id': record.student_id,
                'status': record.status,
                'session': record.session,
                'remark': record.remark,
                'recorded_at': record.recorded_at.isoformat() if record.recorded_at else None
            })
        
        return jsonify({
            'success': True,
            'date': date_str,
            'attendance': attendance_data,
            'count': len(attendance_data)
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    
@teacher_bp.route('/download-template/<template_type>')
@login_required
@teacher_required
def download_template(template_type):
    """Download Excel template for bulk upload"""
    if template_type == 'scores':
        # Create DataFrame template for scores
        df = pd.DataFrame(columns=['Admission Number', 'Student Name', 'Assessment 1', 'Assessment 2', 'Assessment 3'])
        
    elif template_type == 'domain':
        # Create DataFrame template for domain evaluation
        df = pd.DataFrame(columns=['Admission Number', 'Student Name', 'Domain Type', 'Criteria', 'Rating (1-5)', 'Comments'])
    
    # Create Excel file in memory
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Template', index=False)
    
    output.seek(0)
    
    filename = f'{template_type}_template.xlsx'
    return send_file(output,
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                     as_attachment=True,
                     download_name=filename)

@teacher_bp.route('/exam-detail/<exam_id>')
@login_required
@teacher_required
def exam_detail(exam_id):
    """View exam details"""
    try:
        teacher = Teacher.query.filter_by(user_id=current_user.id).first_or_404()
        exam = Exam.query.get_or_404(exam_id)
        
        # Verify the exam belongs to this teacher
        if exam.teacher_id != teacher.id:
            flash('You are not authorized to view this exam.', 'danger')
            return redirect(url_for('teacher.exams'))
        
        # Get exam questions with their related QuestionBank data
        exam_questions = ExamQuestion.query.filter_by(exam_id=exam_id).all()
        
        # Get question details for each exam question
        questions_data = []
        for eq in exam_questions:
            question = QuestionBank.query.get(eq.question_bank_id)
            if question:
                questions_data.append({
                    'exam_question': eq,
                    'question': question,
                    'marks': eq.marks or question.marks
                })
        
        # Get exam sessions (students who have taken/are taking the exam)
        exam_sessions = ExamSession.query.filter_by(exam_id=exam_id).all()
        
        # Get session statistics
        total_students = Student.query.filter_by(
            current_class_id=exam.class_id,
            is_active=True,
            academic_status='active'
        ).count()
        
        session_stats = {
            'total_students': total_students,
            'started': len([s for s in exam_sessions if s.status == 'started']),
            'completed': len([s for s in exam_sessions if s.status == 'completed']),
            'scheduled': len([s for s in exam_sessions if s.status == 'scheduled'])
        }
        
        # Calculate average score if exams are completed
        average_score = 0
        completed_sessions = [s for s in exam_sessions if s.status == 'completed']
        if completed_sessions:
            total_score = 0
            for session in completed_sessions:
                # You would need to calculate actual score from responses
                # This is a placeholder - implement your scoring logic
                total_score += 0  # Placeholder
            average_score = total_score / len(completed_sessions) if completed_sessions else 0
        
        return render_template('teacher/exam_detail.html',
                             teacher=teacher,
                             exam=exam,
                             questions_data=questions_data,
                             exam_sessions=exam_sessions,
                             session_stats=session_stats,
                             average_score=average_score)
        
    except Exception as e:
        flash(f'Error loading exam details: {str(e)}', 'danger')
        return redirect(url_for('teacher.exams'))

@teacher_bp.route('/save-scores', methods=['POST'])
@login_required
@teacher_required
def save_scores():
    """Save assessment scores with term-based assessments - NEW JSON FORMAT"""
    try:
        data = request.get_json()
        subject_id = data.get('subject_id')
        class_id = data.get('class_id')
        academic_term_id = data.get('academic_term_id')
        scores_data = data.get('scores', [])
        
        print(f"Received data: subject_id={subject_id}, class_id={class_id}, academic_term_id={academic_term_id}, scores count={len(scores_data)}")
        
        if not subject_id or not class_id or not academic_term_id:
            return jsonify({'success': False, 'message': 'Missing required data'}), 400
        
        teacher = Teacher.query.filter_by(user_id=current_user.id).first_or_404()
        
        # Verify teacher is assigned to this subject and class
        assignment = SubjectAssignment.query.filter_by(
            teacher_id=teacher.id,
            subject_id=subject_id,
            class_id=class_id,
            academic_term_id=academic_term_id,
            is_active=True
        ).first()
        
        if not assignment:
            return jsonify({'success': False, 'message': 'You are not assigned to teach this subject in this class!'}), 403
        
        # Group scores by student
        student_scores_dict = {}
        for score_data in scores_data:
            student_id = score_data.get('student_id')
            assessment_id = score_data.get('assessment_id')
            score_value = score_data.get('score')
            
            if not all([student_id, assessment_id, score_value is not None]):
                print(f"Skipping invalid score data: {score_data}")
                continue
            
            if student_id not in student_scores_dict:
                student_scores_dict[student_id] = {}
            
            student_scores_dict[student_id][assessment_id] = float(score_value)
        
        print(f"Grouped scores for {len(student_scores_dict)} students")
        
        saved_count = 0
        # Process each student's scores
        for student_id, scores_dict in student_scores_dict.items():
            # Check if StudentAssessment record exists
            student_assessment = StudentAssessment.query.filter_by(
                student_id=student_id,
                subject_id=subject_id,
                class_id=class_id,
                term_id=academic_term_id
            ).first()
            
            if student_assessment:
                # Update existing record
                student_assessment.assessment_scores = scores_dict
                student_assessment.entered_by = teacher.id
                student_assessment.entered_at = datetime.now(timezone.utc)
                student_assessment.updated_at = datetime.now(timezone.utc)
                
                # Calculate total and average
                scores = list(scores_dict.values())
                student_assessment.total_score = sum(scores)
                student_assessment.average_score = sum(scores) / len(scores) if scores else 0.0
                
                print(f"Updated scores for student {student_id}: {scores_dict}")
            else:
                # Create new record
                student_assessment = StudentAssessment(
                    student_id=student_id,
                    subject_id=subject_id,
                    class_id=class_id,
                    term_id=academic_term_id,
                    assessment_scores=scores_dict,
                    entered_by=teacher.id,
                    entered_at=datetime.now(timezone.utc)
                )
                
                # Calculate total and average
                scores = list(scores_dict.values())
                student_assessment.total_score = sum(scores)
                student_assessment.average_score = sum(scores) / len(scores) if scores else 0.0
                
                db.session.add(student_assessment)
                print(f"Created new scores for student {student_id}: {scores_dict}")
            
            saved_count += 1
        
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': f'Successfully saved scores for {saved_count} students!',
            'saved_count': saved_count,
            'total_scores': sum(len(scores) for scores in student_scores_dict.values())
        })
        
    except Exception as e:
        db.session.rollback()
        import traceback
        print(f"Error in save_scores: {str(e)}")
        print(traceback.format_exc())
        return jsonify({'success': False, 'message': str(e)}), 400
    
# Form Teacher Comments Routes
@teacher_bp.route('/form-teacher/comments')
@login_required
@teacher_required
def form_teacher_comments():
    """Form teacher comments page - only for form teachers"""
    teacher = Teacher.query.filter_by(user_id=current_user.id).first_or_404()
    
    # Check if teacher is a form teacher
    if not teacher.form_class_id:
        flash('You are not assigned as a form teacher for any class.', 'warning')
        return redirect(url_for('teacher.dashboard'))
    
    # Get current term
    current_term = AcademicTerm.query.filter_by(is_active=True).first()
    if not current_term:
        flash('No active academic term found.', 'danger')
        return redirect(url_for('teacher.dashboard'))
    
    # Get teacher's form class
    form_class = ClassRoom.query.get_or_404(teacher.form_class_id)
    
    # Get students in the form class
    students = Student.query.filter_by(
        current_class_id=form_class.id,
        is_active=True,
        academic_status='active'
    ).order_by(Student.first_name, Student.last_name).all()
    
    # Get existing comments for this term
    existing_comments = {}
    for student in students:
        comment = FormTeacherComment.query.filter_by(
            student_id=student.id,
            form_teacher_id=teacher.id,
            academic_year=current_term.session.name,
            term=current_term.term_number
        ).first()
        
        if comment:
            existing_comments[student.id] = comment.comment
    
    return render_template('teacher/form_teacher_comments.html',
                         teacher=teacher,
                         form_class=form_class,
                         students=students,
                         current_term=current_term,
                         existing_comments=existing_comments)

@teacher_bp.route('/form-teacher/save-comment', methods=['POST'])
@login_required
@teacher_required
def save_form_teacher_comment():
    """Save form teacher comment for a student"""
    try:
        teacher = Teacher.query.filter_by(user_id=current_user.id).first_or_404()
        
        # Check if teacher is a form teacher
        if not teacher.form_class_id:
            return jsonify({'success': False, 'message': 'You are not a form teacher'}), 403
        
        # Log the request for debugging
        print(f"Save comment request from teacher {teacher.id}")
        print(f"Request data: {request.get_data()}")
        
        # Get JSON data
        if not request.is_json:
            print("Request is not JSON")
            return jsonify({'success': False, 'message': 'Request must be JSON'}), 400
        
        data = request.get_json()
        print(f"Parsed JSON data: {data}")
        
        if data is None:
            print("JSON data is None")
            return jsonify({'success': False, 'message': 'Invalid JSON data'}), 400
        
        student_id = data.get('student_id')
        comment_text = data.get('comment')
        
        print(f"Student ID: {student_id}, Comment: {comment_text[:50] if comment_text else 'None'}")
        
        if not student_id:
            print("Student ID is missing")
            return jsonify({'success': False, 'message': 'Student ID is required'}), 400
        
        if comment_text is None:
            print("Comment text is None")
            return jsonify({'success': False, 'message': 'Comment is required'}), 400
        
        # Verify student exists
        student = Student.query.get(student_id)
        if not student:
            print(f"Student with ID {student_id} not found")
            return jsonify({'success': False, 'message': 'Student not found'}), 404
            
        # Verify student is in teacher's form class
        if student.current_class_id != teacher.form_class_id:
            print(f"Student {student_id} not in teacher's form class {teacher.form_class_id}")
            return jsonify({'success': False, 'message': 'Student is not in your form class'}), 403
        
        # Get current term
        current_term = AcademicTerm.query.filter_by(is_active=True).first()
        if not current_term:
            print("No active academic term")
            return jsonify({'success': False, 'message': 'No active academic term'}), 400
        
        print(f"Current term: {current_term.name}, Term {current_term.term_number}")
        
        # Check if comment already exists
        existing_comment = FormTeacherComment.query.filter_by(
            student_id=student_id,
            form_teacher_id=teacher.id,
            academic_year=current_term.session.name,
            term=current_term.term_number
        ).first()
        
        if existing_comment:
            # Update existing comment
            existing_comment.comment = comment_text
            existing_comment.updated_at = datetime.now(timezone.utc)
            action = 'UPDATE'
            print(f"Updating existing comment for student {student_id}")
        else:
            # Create new comment
            new_comment = FormTeacherComment(
                student_id=student_id,
                form_teacher_id=teacher.id,
                academic_year=current_term.session.name,
                term=current_term.term_number,
                comment=comment_text,
                created_at=datetime.now(timezone.utc)
            )
            db.session.add(new_comment)
            action = 'CREATE'
            print(f"Creating new comment for student {student_id}")
        
        db.session.commit()
        print("Database commit successful")
        
        # Log action
        audit_log = AuditLog(
            user_id=current_user.id,
            action='SAVE_FORM_TEACHER_COMMENT',
            table_name='form_teacher_comments',
            record_id=student_id,
            new_values={'comment': comment_text[:100] + '...' if len(comment_text) > 100 else comment_text},
            ip_address=request.remote_addr
        )
        db.session.add(audit_log)
        db.session.commit()
        print("Audit log created")
        
        return jsonify({
            'success': True, 
            'message': 'Comment saved successfully!',
            'action': action
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"Error saving comment: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)}), 500
 
@teacher_bp.route('/form-teacher/get-comments')
@login_required
@teacher_required
def get_form_teacher_comments():
    """Get form teacher comments for export or viewing"""
    teacher = Teacher.query.filter_by(user_id=current_user.id).first_or_404()
    
    # Check if teacher is a form teacher
    if not teacher.form_class_id:
        return jsonify({'success': False, 'message': 'You are not a form teacher'}), 403
    
    # Get current term
    current_term = AcademicTerm.query.filter_by(is_active=True).first()
    if not current_term:
        return jsonify({'success': False, 'message': 'No active academic term'}), 400
    
    # Get all comments for teacher's form class
    comments = FormTeacherComment.query.join(Student).filter(
        FormTeacherComment.form_teacher_id == teacher.id,
        FormTeacherComment.academic_year == current_term.session.name,
        FormTeacherComment.term == current_term.term_number,
        Student.current_class_id == teacher.form_class_id
    ).all()
    
    comments_data = []
    for comment in comments:
        comments_data.append({
            'student_id': comment.student_id,
            'student_name': f"{comment.student.first_name} {comment.student.last_name}",
            'admission_number': comment.student.admission_number,
            'comment': comment.comment,
            'created_at': comment.created_at.isoformat()
        })
    
    return jsonify({'success': True, 'comments': comments_data})

@teacher_bp.route('/domain-evaluation')
@login_required
@teacher_required
def domain_evaluation():
    """Evaluate learning domains"""
    teacher = Teacher.query.filter_by(user_id=current_user.id).first_or_404()
    
    # Get current term
    current_term = AcademicTerm.query.filter_by(is_active=True).first()
    if not current_term:
        flash('No active academic term!', 'warning')
        return redirect(url_for('teacher.dashboard'))
    
    # Get form class students
    if not teacher.form_class_id:
        flash('You are not assigned as a form teacher!', 'warning')
        return redirect(url_for('teacher.dashboard'))
    
    students = Student.query.filter_by(
        current_class_id=teacher.form_class_id,
        is_active=True,
        academic_status='active'
    ).all()
    
    # Get existing evaluations
    existing_evaluations = {}
    for student in students:
        evaluations = DomainEvaluation.query.filter_by(
            student_id=student.id,
            term=current_term.term_number,
            academic_year=current_term.session.name,
            evaluated_by=teacher.id
        ).all()
        existing_evaluations[student.id] = {e.domain_type: e for e in evaluations}
    
    domain_types = ['Affective', 'Psychomotor', 'Cognitive']
    
    return render_template('teacher/domain_evaluation.html',
                         teacher=teacher,
                         students=students,
                         domain_types=domain_types,
                         existing_evaluations=existing_evaluations,
                         current_term=current_term)

@teacher_bp.route('/save-domain-evaluation', methods=['POST'])
@login_required
@teacher_required
def save_domain_evaluation():
    """Save domain evaluation for a student"""
    try:
        teacher = Teacher.query.filter_by(user_id=current_user.id).first_or_404()
        
        # Check if teacher is a form teacher
        if not teacher.form_class_id:
            return jsonify({'success': False, 'message': 'You are not a form teacher'}), 403
        
        data = request.get_json()
        student_id = data.get('student_id')
        domain_type = data.get('domain_type')
        evaluation_data = data.get('evaluation_data')
        average_score = data.get('average_score')
        comments = data.get('comments', '')
        total_criteria = data.get('total_criteria')
        evaluated_criteria = data.get('evaluated_criteria')
        
        print(f"DEBUG - Received data: {data}")  # Add debug logging
        
        if not all([student_id, domain_type, evaluation_data, average_score is not None]):
            return jsonify({'success': False, 'message': 'Required fields are missing'}), 400
        
        # Validate domain type
        valid_domains = ['Affective', 'Psychomotor', 'Cognitive']
        if domain_type not in valid_domains:
            return jsonify({'success': False, 'message': f'Invalid domain type: {domain_type}'}), 400
        
        # Verify student is in teacher's form class
        student = Student.query.get(student_id)
        if not student:
            return jsonify({'success': False, 'message': 'Student not found'}), 404
            
        if student.current_class_id != teacher.form_class_id:
            return jsonify({'success': False, 'message': 'Student is not in your form class'}), 403
        
        # Get current term
        current_term = AcademicTerm.query.filter_by(is_active=True).first()
        if not current_term:
            return jsonify({'success': False, 'message': 'No active academic term'}), 400
        
        # Check if evaluation already exists
        existing_eval = DomainEvaluation.query.filter_by(
            student_id=student_id,
            domain_type=domain_type,
            term=current_term.term_number,
            academic_year=current_term.session.name,
            evaluated_by=teacher.id
        ).first()
        
        print(f"DEBUG - Existing eval: {existing_eval}")  # Add debug logging
        
        if existing_eval:
            # Update existing evaluation
            existing_eval.evaluation_data = evaluation_data
            existing_eval.average_score = float(average_score)
            existing_eval.comments = comments
            existing_eval.total_criteria = total_criteria
            existing_eval.evaluated_criteria = evaluated_criteria
            existing_eval.updated_at = datetime.now(timezone.utc)
            existing_eval.class_id = teacher.form_class_id  # Ensure class_id is set
            action = 'UPDATE'
        else:
            # Create new evaluation
            new_eval = DomainEvaluation(
                student_id=student_id,
                domain_type=domain_type,
                evaluation_data=evaluation_data,
                average_score=float(average_score),
                comments=comments,
                total_criteria=total_criteria,
                evaluated_criteria=evaluated_criteria,
                term=current_term.term_number,
                academic_year=current_term.session.name,
                evaluated_by=teacher.id,
                class_id=teacher.form_class_id,
                evaluated_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc)
            )
            db.session.add(new_eval)
            action = 'CREATE'
        
        db.session.commit()
        
        # Log action
        audit_log = AuditLog(
            user_id=current_user.id,
            action='SAVE_DOMAIN_EVALUATION',
            table_name='domain_evaluations',
            record_id=f"{student_id}_{domain_type}",
            new_values={
                'domain_type': domain_type,
                'average_score': average_score,
                'criteria_evaluated': f'{evaluated_criteria}/{total_criteria}'
            },
            ip_address=request.remote_addr
        )
        db.session.add(audit_log)
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': f'{domain_type} domain evaluation saved successfully!',
            'action': action,
            'average_score': average_score
        })
        
    except Exception as e:
        db.session.rollback()
        import traceback
        print(traceback.format_exc())  # For debugging
        return jsonify({'success': False, 'message': str(e)}), 500
    
    
@teacher_bp.route('/export-domain-evaluations')
@login_required
@teacher_required
def export_domain_evaluations():
    """Get domain evaluations for export"""
    try:
        teacher = Teacher.query.filter_by(user_id=current_user.id).first_or_404()
        print(f"Export request by teacher ID: {teacher.id}")  # Debug log
        
        # Check if teacher is a form teacher
        if not teacher.form_class_id:
            return jsonify({'success': False, 'message': 'You are not a form teacher'}), 403
        
        print("Teacher is a form teacher")  # Debug log
        # Get current term
        current_term = AcademicTerm.query.filter_by(is_active=True).first()
        if not current_term:
            return jsonify({'success': False, 'message': 'No active academic term'}), 400
        
        print(f"Current term: {current_term.term_number}, Academic year: {current_term.session.name}")  # Debug log
        # Get all evaluations for teacher's form class
        evaluations = DomainEvaluation.query.join(Student).filter(
            DomainEvaluation.evaluated_by == teacher.id,
            DomainEvaluation.term == current_term.term_number,
            DomainEvaluation.academic_year == current_term.session.name,
            Student.current_class_id == teacher.form_class_id
        ).order_by(DomainEvaluation.domain_type, Student.first_name).all()
        
        print(f"Found {len(evaluations)} evaluations")  # Debug log
        evaluations_data = []
        for item in evaluations:
            evaluations_data.append({
                'student_id': item.student_id,
                'student_name': f"{item.student.first_name} {item.student.last_name}",
                'admission_number': item.student.admission_number,
                'domain_type': item.domain_type,
                'average_score': item.average_score,
                'comments': item.comments,
                'evaluation_data': item.evaluation_data,
                'evaluated_at': item.evaluated_at.isoformat(),
                'updated_at': item.updated_at.isoformat() if item.updated_at else None
            })
        
        print("Prepared evaluations data for export")  # Debug log
        return jsonify({
            'success': True, 
            'evaluations': evaluations_data,
            'form_class': teacher.form_class.name,
            'term': current_term.term_number,
            'academic_year': current_term.session.name,
            'teacher': teacher.user.username
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@teacher_bp.route('/get-domain-evaluations/<student_id>')
@login_required
@teacher_required
def get_domain_evaluations(student_id):
    """Get domain evaluations for a specific student"""
    try:
        teacher = Teacher.query.filter_by(user_id=current_user.id).first_or_404()
        
        # Check if teacher is a form teacher
        if not teacher.form_class_id:
            return jsonify({'success': False, 'message': 'You are not a form teacher'}), 403
        
        # Verify student is in teacher's form class
        student = Student.query.get(student_id)
        if not student:
            return jsonify({'success': False, 'message': 'Student not found'}), 404
            
        if student.current_class_id != teacher.form_class_id:
            return jsonify({'success': False, 'message': 'Student is not in your form class'}), 403
        
        # Get current term
        current_term = AcademicTerm.query.filter_by(is_active=True).first()
        if not current_term:
            return jsonify({'success': False, 'message': 'No active academic term'}), 400
        
        # Get all evaluations for this student
        evaluations = DomainEvaluation.query.filter_by(
            student_id=student_id,
            term=current_term.term_number,
            academic_year=current_term.session.name,
            evaluated_by=teacher.id
        ).all()
        
        evaluations_data = {}
        for eval in evaluations:
            evaluations_data[eval.domain_type] = {
                'evaluation_data': eval.evaluation_data,
                'average_score': eval.average_score,
                'comments': eval.comments,
                'created_at': eval.created_at.isoformat(),
                'updated_at': eval.updated_at.isoformat() if eval.updated_at else None
            }
        
        return jsonify({
            'success': True, 
            'evaluations': evaluations_data,
            'student_name': f"{student.first_name} {student.last_name}"
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    


# Subject Teacher Comments Routes
@teacher_bp.route('/enter-comments')
@login_required
@teacher_required
def enter_comments():
    """Enter teacher comments"""
    teacher = Teacher.query.filter_by(user_id=current_user.id).first_or_404()
    current_term = AcademicTerm.query.filter_by(is_active=True).first()
    
    if not current_term:
        flash('No active academic term!', 'warning')
        return redirect(url_for('teacher.dashboard'))
    
    # Get subject assignments for current term
    assignments = SubjectAssignment.query.filter_by(
        teacher_id=teacher.id,
        academic_term_id=current_term.id,
        is_active=True
    ).all()
    
    subject_students = {}
    for assignment in assignments:
        subject = Subject.query.get(assignment.subject_id)
        classroom = ClassRoom.query.get(assignment.class_id)
        
        if subject and classroom:
            students = Student.query.filter_by(
                current_class_id=classroom.id,
                is_active=True,
                academic_status='active'
            ).all()
            
            # Get existing comments
            for student in students:
                existing_comment = TeacherComment.query.filter_by(
                    student_id=student.id,
                    teacher_id=teacher.id,
                    subject_id=subject.id,
                    term=current_term.term_number,
                    academic_year=current_term.session.name
                ).first()
                
                student.existing_comment = existing_comment.comment if existing_comment else ''
            
            subject_students[subject.id] = {
                'subject': subject,
                'classroom': classroom,
                'students': students
            }
    
    return render_template('teacher/comments.html',
                           teacher=teacher,
                           subject_students=subject_students,
                           current_term=current_term)

@teacher_bp.route('/save-subject-comment', methods=['POST'])
@login_required
@teacher_required
def save_subject_comment():
    """Save subject teacher comment for a student"""
    try:
        teacher = Teacher.query.filter_by(user_id=current_user.id).first_or_404()
        
        data = request.get_json()
        student_id = data.get('student_id')
        subject_id = data.get('subject_id')
        comment_text = data.get('comment')
        
        if not all([student_id, subject_id, comment_text is not None]):
            return jsonify({'success': False, 'message': 'All fields are required'}), 400
        
        # Verify teacher is assigned to this subject
        current_term = AcademicTerm.query.filter_by(is_active=True).first()
        if not current_term:
            return jsonify({'success': False, 'message': 'No active academic term'}), 400
        
        assignment = SubjectAssignment.query.filter_by(
            teacher_id=teacher.id,
            subject_id=subject_id,
            academic_term_id=current_term.id,
            is_active=True
        ).first()
        
        if not assignment:
            return jsonify({'success': False, 'message': 'You are not assigned to teach this subject'}), 403
        
        # Verify student is in the assigned class
        student = Student.query.get(student_id)
        if not student:
            return jsonify({'success': False, 'message': 'Student not found'}), 404
            
        if student.current_class_id != assignment.class_id:
            return jsonify({'success': False, 'message': 'Student is not in your assigned class for this subject'}), 403
        
        # Check if comment already exists
        existing_comment = TeacherComment.query.filter_by(
            student_id=student_id,
            teacher_id=teacher.id,
            subject_id=subject_id,
            term=current_term.term_number,
            academic_year=current_term.session.name
        ).first()
        
        if existing_comment:
            # Update existing comment
            existing_comment.comment = comment_text
            existing_comment.updated_at = datetime.now(timezone.utc)
            action = 'UPDATE'
        else:
            # Create new comment
            new_comment = TeacherComment(
                student_id=student_id,
                teacher_id=teacher.id,
                subject_id=subject_id,
                term=current_term.term_number,
                academic_year=current_term.session.name,
                comment=comment_text
            )
            db.session.add(new_comment)
            action = 'CREATE'
        
        db.session.commit()
        
        # Log action
        audit_log = AuditLog(
            user_id=current_user.id,
            action='SAVE_SUBJECT_COMMENT',
            table_name='teacher_comments',
            record_id=f"{student_id}_{subject_id}",
            new_values={'comment': comment_text[:100] + '...' if len(comment_text) > 100 else comment_text},
            ip_address=request.remote_addr
        )
        db.session.add(audit_log)
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': 'Comment saved successfully!',
            'action': action
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

@teacher_bp.route('/get-subject-comments/<subject_id>')
@login_required
@teacher_required
def get_subject_comments(subject_id):
    """Get subject comments for export"""
    try:
        teacher = Teacher.query.filter_by(user_id=current_user.id).first_or_404()
        
        # Verify teacher is assigned to this subject
        current_term = AcademicTerm.query.filter_by(is_active=True).first()
        if not current_term:
            return jsonify({'success': False, 'message': 'No active academic term'}), 400
        
        assignment = SubjectAssignment.query.filter_by(
            teacher_id=teacher.id,
            subject_id=subject_id,
            academic_term_id=current_term.id,
            is_active=True
        ).first()
        
        if not assignment:
            return jsonify({'success': False, 'message': 'You are not assigned to teach this subject'}), 403
        
        # Get all comments for this subject
        comments = TeacherComment.query.join(Student).filter(
            TeacherComment.teacher_id == teacher.id,
            TeacherComment.subject_id == subject_id,
            TeacherComment.term == current_term.term_number,
            TeacherComment.academic_year == current_term.session.name,
            Student.current_class_id == assignment.class_id
        ).all()
        
        # Get subject and class info
        subject = Subject.query.get(subject_id)
        classroom = ClassRoom.query.get(assignment.class_id)
        
        comments_data = []
        for comment in comments:
            comments_data.append({
                'student_id': comment.student_id,
                'student_name': f"{comment.student.first_name} {comment.student.last_name}",
                'admission_number': comment.student.admission_number,
                'comment': comment.comment,
                'created_at': comment.created_at.isoformat(),
                'updated_at': comment.updated_at.isoformat() if comment.updated_at else None
            })
        
        return jsonify({
            'success': True, 
            'comments': comments_data,
            'subject': {
                'name': subject.name,
                'code': subject.code
            },
            'classroom': {
                'name': classroom.name,
                'level': classroom.level,
                'section': classroom.section
            },
            'term': current_term.term_number,
            'academic_year': current_term.session.name
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    

# =========================
# Learning Materials / Notes Routes
# =========================

@teacher_bp.route('/my-subjects/upload-notes')
@login_required
@teacher_required
def upload_notes():
    """Upload notes and learning materials"""
    teacher = Teacher.query.filter_by(user_id=current_user.id).first_or_404()
    
    # Get current term
    current_term = AcademicTerm.query.filter_by(is_active=True).first()
    if not current_term:
        flash('No active academic term!', 'warning')
        return redirect(url_for('teacher.dashboard'))
    
    # Get subject assignments for current term
    assignments = SubjectAssignment.query.filter_by(
        teacher_id=teacher.id,
        academic_term_id=current_term.id,
        is_active=True
    ).all()
    
    subject_classes = []
    for assignment in assignments:
        subject = Subject.query.get(assignment.subject_id)
        classroom = ClassRoom.query.get(assignment.class_id)
        
        if subject and classroom:
            # Count existing materials for this subject-class
            material_count = LearningMaterial.query.filter_by(
                subject_id=subject.id,
                class_id=classroom.id,
                teacher_id=teacher.id
            ).count()
            
            subject_classes.append({
                'subject': subject,
                'classroom': classroom,
                'assignment': assignment,
                'material_count': material_count
            })
    
    # Get all uploaded materials by this teacher
    all_materials = LearningMaterial.query.filter_by(
        teacher_id=teacher.id
    ).order_by(LearningMaterial.created_at.desc()).all()
    
    # Group materials by subject and class
    materials_by_subject = {}
    for material in all_materials:
        key = f"{material.subject_id}_{material.class_id}"
        if key not in materials_by_subject:
            subject = Subject.query.get(material.subject_id)
            classroom = ClassRoom.query.get(material.class_id)
            materials_by_subject[key] = {
                'subject': subject,
                'classroom': classroom,
                'materials': []
            }
        materials_by_subject[key]['materials'].append(material)
    print(subject_classes)
    return render_template('teacher/upload_notes.html',
                         teacher=teacher,
                         subject_classes=subject_classes,
                         materials_by_subject=materials_by_subject,
                         current_term=current_term)

@teacher_bp.route('/upload-material', methods=['POST'])
@login_required
@teacher_required
def upload_material():
    """Upload a learning material - simplified version"""
    try:
        teacher = Teacher.query.filter_by(user_id=current_user.id).first_or_404()
        
        # Get form data
        title = request.form.get('title')
        description = request.form.get('description')
        subject_id = request.form.get('subject_id')
        class_id = request.form.get('class_id')
        material_type = request.form.get('material_type', 'note')
        tags = request.form.get('tags', '')
        is_published = 'is_published' in request.form
        accessible_to = request.form.get('accessible_to', 'class')
        
        # Validate required fields
        if not all([title, subject_id, class_id]):
            flash('Please fill in all required fields', 'danger')
            return redirect(url_for('teacher.upload_notes'))
        
        # Verify teacher is assigned to this subject and class
        current_term = AcademicTerm.query.filter_by(is_active=True).first()
        if not current_term:
            flash('No active academic term!', 'danger')
            return redirect(url_for('teacher.upload_notes'))
        
        assignment = SubjectAssignment.query.filter_by(
            teacher_id=teacher.id,
            subject_id=subject_id,
            class_id=class_id,
            academic_term_id=current_term.id,
            is_active=True
        ).first()
        
        if not assignment:
            flash('You are not assigned to teach this subject in this class!', 'danger')
            return redirect(url_for('teacher.upload_notes'))
        
        # Handle file upload
        file_path = None
        file_type = None
        file_size = None
        content = request.form.get('content', '')
        external_link = request.form.get('external_link', '')
        
        if 'file' in request.files:
            file = request.files['file']
            if file and file.filename != '':
                # Get file extension
                filename = file.filename
                if '.' in filename:
                    file_extension = filename.rsplit('.', 1)[1].lower()
                else:
                    file_extension = ''
                
                # Define allowed extensions with their MIME types
                allowed_extensions = {
                    'pdf': 'application/pdf',
                    'doc': 'application/msword',
                    'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                    'ppt': 'application/vnd.ms-powerpoint',
                    'pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
                    'txt': 'text/plain',
                    'jpg': 'image/jpeg',
                    'jpeg': 'image/jpeg',
                    'png': 'image/png',
                    'mp4': 'video/mp4',
                    'mp3': 'audio/mpeg',
                    'zip': 'application/zip'
                }
                
                if file_extension not in allowed_extensions:
                    flash('File type not allowed. Allowed types: PDF, DOC, PPT, Images, Videos, MP3, ZIP', 'danger')
                    return redirect(url_for('teacher.upload_notes'))
                
                # Secure filename
                filename = secure_filename(file.filename)
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                unique_filename = f"{timestamp}_{filename}"
                
                # Create upload directory if it doesn't exist
                upload_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'materials')
                os.makedirs(upload_dir, exist_ok=True)
                
                # Save file
                filepath = os.path.join(upload_dir, unique_filename)
                file.save(filepath)
                
                # Get file size
                file_size = os.path.getsize(filepath)
                
                file_path = f"/static/uploads/materials/{unique_filename}"
                file_type = file_extension
        
        elif external_link:
            # For external links
            file_type = 'link'
        elif content:
            # For text content
            file_type = 'text'
        else:
            flash('Please provide either a file, content, or external link', 'danger')
            return redirect(url_for('teacher.upload_notes'))
        
        # Process tags
        tag_list = []
        if tags:
            tag_list = [tag.strip() for tag in tags.split(',') if tag.strip()]
        
        # Create material
        material = LearningMaterial(
            title=title,
            description=description,
            subject_id=subject_id,
            class_id=class_id,
            teacher_id=teacher.id,
            file_path=file_path,
            file_type=file_type,
            file_size=file_size,
            content=content,
            external_link=external_link,
            material_type=material_type,
            tags=tag_list,
            is_published=is_published,
            accessible_to=accessible_to,
            published_at=datetime.now(timezone.utc) if is_published else None
        )
        
        db.session.add(material)
        
        # Log action
        audit_log = AuditLog(
            user_id=current_user.id,
            action='UPLOAD_MATERIAL',
            table_name='learning_materials',
            record_id=material.id,
            details={
                'title': title,
                'subject_id': subject_id,
                'class_id': class_id,
                'material_type': material_type,
                'has_file': file_path is not None
            },
            ip_address=request.remote_addr
        )
        db.session.add(audit_log)
        
        db.session.commit()
        
        flash('Material uploaded successfully!', 'success')
        return redirect(url_for('teacher.upload_notes'))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error uploading material: {str(e)}', 'danger')
        return redirect(url_for('teacher.upload_notes'))
    
@teacher_bp.route('/edit-material/<material_id>', methods=['GET', 'POST'])
@login_required
@teacher_required
def edit_material(material_id):
    """Edit a learning material - fixed version without magic"""
    teacher = Teacher.query.filter_by(user_id=current_user.id).first_or_404()
    material = LearningMaterial.query.get_or_404(material_id)
    
    # Verify ownership
    if material.teacher_id != teacher.id:
        flash('You do not have permission to edit this material', 'danger')
        return redirect(url_for('teacher.upload_notes'))
    
    if request.method == 'POST':
        try:
            # Update material details
            material.title = request.form.get('title')
            material.description = request.form.get('description')
            material.material_type = request.form.get('material_type', 'note')
            material.tags = [tag.strip() for tag in request.form.get('tags', '').split(',') if tag.strip()]
            material.is_published = 'is_published' in request.form
            material.accessible_to = request.form.get('accessible_to', 'class')
            material.content = request.form.get('content', '')
            material.external_link = request.form.get('external_link', '')
            
            # Handle file replacement
            if 'file' in request.files:
                file = request.files['file']
                if file and file.filename != '':
                    # Validate file extension
                    allowed_extensions = {'pdf', 'doc', 'docx', 'ppt', 'pptx', 'txt', 
                                         'jpg', 'jpeg', 'png', 'mp4', 'mp3', 'zip'}
                    
                    # Get file extension
                    filename = file.filename
                    if '.' in filename:
                        file_extension = filename.rsplit('.', 1)[1].lower()
                    else:
                        file_extension = ''
                    
                    if file_extension not in allowed_extensions:
                        flash('File type not allowed. Allowed types: PDF, DOC, PPT, Images, Videos, MP3, ZIP', 'danger')
                        return redirect(url_for('teacher.edit_material', material_id=material_id))
                    
                    # Remove old file if exists
                    if material.file_path and material.file_path.startswith('/static/'):
                        old_path = os.path.join(current_app.root_path, 'static', 
                                              material.file_path[len('/static/'):])
                        if os.path.exists(old_path):
                            os.remove(old_path)
                    
                    # Upload new file
                    filename = secure_filename(file.filename)
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    unique_filename = f"{timestamp}_{filename}"
                    
                    upload_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'materials')
                    os.makedirs(upload_dir, exist_ok=True)
                    
                    filepath = os.path.join(upload_dir, unique_filename)
                    file.save(filepath)
                    
                    material.file_path = f"/static/uploads/materials/{unique_filename}"
                    material.file_size = os.path.getsize(filepath)
                    material.file_type = file_extension
            
            material.updated_at = datetime.now(timezone.utc)
            
            if material.is_published and not material.published_at:
                material.published_at = datetime.now(timezone.utc)
            
            # Log action
            audit_log = AuditLog(
                user_id=current_user.id,
                action='EDIT_MATERIAL',
                table_name='learning_materials',
                record_id=material_id,
                details={
                    'title': material.title,
                    'subject_id': material.subject_id,
                    'class_id': material.class_id,
                    'material_type': material.material_type
                },
                ip_address=request.remote_addr
            )
            db.session.add(audit_log)
            
            db.session.commit()
            
            flash('Material updated successfully!', 'success')
            return redirect(url_for('teacher.upload_notes'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating material: {str(e)}', 'danger')
    
    # GET request - show edit form
    # Get subject assignments for dropdown
    current_term = AcademicTerm.query.filter_by(is_active=True).first()
    assignments = []
    
    if current_term:
        assignments = SubjectAssignment.query.filter_by(
            teacher_id=teacher.id,
            academic_term_id=current_term.id,
            is_active=True
        ).all()
    
    subject_classes = []
    for assignment in assignments:
        subject = Subject.query.get(assignment.subject_id)
        classroom = ClassRoom.query.get(assignment.class_id)
        
        if subject and classroom:
            subject_classes.append({
                'subject': subject,
                'classroom': classroom
            })
    
    return render_template('teacher/edit_material.html',
                         teacher=teacher,
                         material=material,
                         subject_classes=subject_classes)

@teacher_bp.route('/delete-material/<material_id>', methods=['POST'])
@login_required
@teacher_required
def delete_material(material_id):
    """Delete a learning material"""
    try:
        teacher = Teacher.query.filter_by(user_id=current_user.id).first_or_404()
        material = LearningMaterial.query.get_or_404(material_id)
        
        # Verify ownership
        if material.teacher_id != teacher.id:
            return jsonify({'success': False, 'message': 'Permission denied'}), 403
        
        # Delete file if exists
        if material.file_path and material.file_path.startswith('/static/'):
            try:
                relative_path = material.file_path[len('/static/'):]
                full_path = os.path.join(current_app.root_path, 'static', relative_path)
                
                if os.path.exists(full_path):
                    os.remove(full_path)
            except Exception as e:
                print(f"Error deleting file: {e}")
        
        # Log action before deletion
        audit_log = AuditLog(
            user_id=current_user.id,
            action='DELETE_MATERIAL',
            table_name='learning_materials',
            record_id=material_id,
            old_values={
                'title': material.title,
                'subject_id': material.subject_id,
                'class_id': material.class_id,
                'material_type': material.material_type,
                'download_count': material.download_count
            },
            ip_address=request.remote_addr
        )
        db.session.add(audit_log)
        
        # Delete the material
        db.session.delete(material)
        db.session.commit()
        
        flash('Material deleted successfully!', 'success')
        return redirect(url_for('teacher.upload_notes'))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting material: {str(e)}', 'danger')
        return redirect(url_for('teacher.upload_notes'))

@teacher_bp.route('/toggle-material-publish/<material_id>', methods=['POST'])
@login_required
@teacher_required
def toggle_material_publish(material_id):
    """Toggle material publish status"""
    try:
        teacher = Teacher.query.filter_by(user_id=current_user.id).first_or_404()
        material = LearningMaterial.query.get_or_404(material_id)
        
        # Verify ownership
        if material.teacher_id != teacher.id:
            return jsonify({'success': False, 'message': 'Permission denied'}), 403
        
        material.is_published = not material.is_published
        
        if material.is_published and not material.published_at:
            material.published_at = datetime.now(timezone.utc)
        
        material.updated_at = datetime.now(timezone.utc)
        
        # Log action
        audit_log = AuditLog(
            user_id=current_user.id,
            action='TOGGLE_MATERIAL_PUBLISH',
            table_name='learning_materials',
            record_id=material_id,
            new_values={
                'is_published': material.is_published,
                'published_at': material.published_at
            },
            ip_address=request.remote_addr
        )
        db.session.add(audit_log)
        
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': 'Material status updated successfully',
            'is_published': material.is_published
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400

@teacher_bp.route('/material-downloads/<material_id>')
@login_required
@teacher_required
def material_downloads(material_id):
    """View download statistics for a material"""
    teacher = Teacher.query.filter_by(user_id=current_user.id).first_or_404()
    material = LearningMaterial.query.get_or_404(material_id)
    
    # Verify ownership
    if material.teacher_id != teacher.id:
        flash('You do not have permission to view this material', 'danger')
        return redirect(url_for('teacher.upload_notes'))
    
    # Get download history
    downloads = StudentMaterialDownload.query.filter_by(
        material_id=material_id
    ).order_by(StudentMaterialDownload.downloaded_at.desc()).all()
    
    # Get download statistics
    daily_downloads = {}
    for download in downloads:
        date_str = download.downloaded_at.strftime('%Y-%m-%d')
        if date_str not in daily_downloads:
            daily_downloads[date_str] = 0
        daily_downloads[date_str] += 1
    
    return render_template('teacher/material_downloads.html',
                         teacher=teacher,
                         material=material,
                         downloads=downloads,
                         daily_downloads=daily_downloads)



@teacher_bp.route('/reports')
@login_required
@teacher_required
def reports_dashboard():
    """Teacher reports dashboard"""
    teacher = Teacher.query.filter_by(user_id=current_user.id).first_or_404()
    
    # Get current term
    current_term = AcademicTerm.query.filter_by(is_active=True).first()
    if not current_term:
        flash('No active academic term!', 'warning')
        return redirect(url_for('teacher.dashboard'))
    
    # Get teacher's exams
    exams = Exam.query.filter_by(
        teacher_id=teacher.id,
        academic_term_id=current_term.id
    ).order_by(Exam.created_at.desc()).all()
    
    # Get teacher's reports
    generated_reports = TeacherReport.query.filter_by(
        teacher_id=teacher.id
    ).order_by(TeacherReport.generated_at.desc()).limit(5).all()
    
    # Get recent analyses
    recent_analyses = StudentPerformanceAnalysis.query.join(Exam).filter(
        Exam.teacher_id == teacher.id
    ).order_by(StudentPerformanceAnalysis.created_at.desc()).limit(5).all()
    
    # Count statistics
    total_exams = len(exams)
    total_reports = TeacherReport.query.filter_by(teacher_id=teacher.id).count()
    total_analyses = StudentPerformanceAnalysis.query.join(Exam).filter(
        Exam.teacher_id == teacher.id
    ).count()
    
    # Get classes with recent exams
    classes_with_exams = []
    for exam in exams[:5]:  # Limit to 5 most recent
        if exam.classroom and exam.subject:
            classes_with_exams.append({
                'exam': exam,
                'classroom': exam.classroom,
                'subject': exam.subject,
                'student_count': len(exam.classroom.class_students) if exam.classroom else 0
            })
    
    return render_template('teacher/reports_dashboard.html',
                         teacher=teacher,
                         current_term=current_term,
                         exams=exams,
                         generated_reports=generated_reports,
                         recent_analyses=recent_analyses,
                         total_exams=total_exams,
                         total_reports=total_reports,
                         total_analyses=total_analyses,
                         classes_with_exams=classes_with_exams)

@teacher_bp.route('/reports/exam/<exam_id>')
@login_required
@teacher_required
def exam_report(exam_id):
    """Generate exam performance report"""
    teacher = Teacher.query.filter_by(user_id=current_user.id).first_or_404()
    exam = Exam.query.get_or_404(exam_id)
    
    # Verify ownership
    if exam.teacher_id != teacher.id:
        flash('You do not have permission to view this exam report', 'danger')
        return redirect(url_for('teacher.reports_dashboard'))
    
    # Get exam sessions with responses
    exam_sessions = ExamSession.query.filter_by(exam_id=exam_id).all()
    
    # Get all students in the class
    students = Student.query.filter_by(
        current_class_id=exam.class_id,
        is_active=True,
        academic_status='active'
    ).order_by(Student.first_name, Student.last_name).all()
    
    # Get or create analyses
    ai_service = AIAnalysisService()
    student_performances = []
    
    for student in students:
        # Find exam session for this student
        session = next((s for s in exam_sessions if s.student_id == student.id), None)
        
        if session:
            # Get exam responses
            responses = ExamResponse.query.join(ExamQuestion).filter(
                ExamResponse.exam_session_id == session.id
            ).all()
            
            # Calculate score
            total_score = 0
            max_score = 0
            question_responses = []
            
            for response in responses:
                exam_question = ExamQuestion.query.get(response.exam_question_id)
                question = QuestionBank.query.get(exam_question.question_bank_id)
                
                if question and exam_question:
                    max_score += exam_question.marks or question.marks
                    
                    # Check if answer is correct (simplified - you might need more complex logic)
                    is_correct = False
                    if question.question_type in ['multiple_choice', 'true_false']:
                        is_correct = response.answer == question.correct_answer
                    # For other types, you might need different checking logic
                    
                    if is_correct:
                        total_score += exam_question.marks or question.marks
                    
                    question_responses.append({
                        'question_id': question.id,
                        'question_text': question.question_text[:100],
                        'question_type': question.question_type,
                        'marks': exam_question.marks or question.marks,
                        'student_answer': response.answer,
                        'correct_answer': question.correct_answer,
                        'is_correct': is_correct
                    })
            
            percentage = (total_score / max_score * 100) if max_score > 0 else 0
            
            # Get or create analysis
            analysis = StudentPerformanceAnalysis.query.filter_by(
                student_id=student.id,
                exam_id=exam_id,
                subject_id=exam.subject_id
            ).first()
            
            if not analysis:
                # Create new analysis
                analysis_data = ai_service.analyze_student_performance(
                    student_data={
                        'first_name': student.first_name,
                        'last_name': student.last_name,
                        'class_name': exam.classroom.name,
                        'score': total_score,
                        'percentage': percentage
                    },
                    exam_data={
                        'title': exam.name,
                        'subject_name': exam.subject.name,
                        'total_marks': exam.total_marks
                    },
                    question_responses=question_responses
                )
                
                analysis = StudentPerformanceAnalysis(
                    student_id=student.id,
                    exam_id=exam_id,
                    subject_id=exam.subject_id,
                    overall_score=percentage,
                    accuracy_rate=analysis_data.get('accuracy_rate', 0),
                    strengths=analysis_data.get('strengths', []),
                    weaknesses=analysis_data.get('weaknesses', []),
                    recommendations=analysis_data.get('recommendations', []),
                    ai_comment=analysis_data.get('ai_comment', ''),
                    analysis_method=analysis_data.get('analysis_method', 'rule_based'),
                    confidence_score=analysis_data.get('confidence_score', 0.5)
                )
                db.session.add(analysis)
                db.session.commit()
            
            student_performances.append({
                'student': student,
                'session': session,
                'score': total_score,
                'percentage': percentage,
                'analysis': analysis,  # This could be a model object or None
                'question_responses': question_responses
            })
        else:
            # No exam session for this student
            student_performances.append({
                'student': student,
                'session': None,
                'score': 0,
                'percentage': 0,
                'analysis': None,
                'question_responses': []
            })
    
    # Sort by score descending
    student_performances.sort(key=lambda x: x['percentage'], reverse=True)
    
    # Calculate class statistics
    valid_scores = [p['percentage'] for p in student_performances if p['session']]
    avg_score = sum(valid_scores) / len(valid_scores) if valid_scores else 0
    max_score = max(valid_scores) if valid_scores else 0
    min_score = min(valid_scores) if valid_scores else 0
    
    # Get question analysis
    all_responses = [p['question_responses'] for p in student_performances if p['question_responses']]
    question_analysis = ai_service.analyze_exam_questions(
        exam_data={'title': exam.name},
        all_responses=all_responses
    )
    
    # Generate class report
    class_report = ai_service.generate_class_report(
        class_data={
            'class_name': exam.classroom.name,
            'subject_name': exam.subject.name
        },
        student_performances=[p for p in student_performances if p['session']]
    )
    
    return render_template('teacher/exam_report.html',
                         teacher=teacher,
                         exam=exam,
                         student_performances=student_performances,
                         avg_score=round(avg_score, 2),
                         max_score=round(max_score, 2),
                         min_score=round(min_score, 2),
                         question_analysis=question_analysis,
                         class_report=class_report)

@teacher_bp.route('/reports/student/<student_id>/<exam_id>')
@login_required
@teacher_required
def student_report(student_id, exam_id):
    """Generate detailed student report"""
    teacher = Teacher.query.filter_by(user_id=current_user.id).first_or_404()
    student = Student.query.get_or_404(student_id)
    exam = Exam.query.get_or_404(exam_id)
    
    # Verify teacher has access to this student's data
    if exam.teacher_id != teacher.id:
        flash('You do not have permission to view this student report', 'danger')
        return redirect(url_for('teacher.reports_dashboard'))
    
    # Check if student is in the exam class
    if student.current_class_id != exam.class_id:
        flash('Student is not in this exam class', 'danger')
        return redirect(url_for('teacher.reports_dashboard'))
    
    # Get exam session
    session = ExamSession.query.filter_by(
        exam_id=exam_id,
        student_id=student_id
    ).first()
    
    if not session:
        flash('Student has not taken this exam', 'warning')
        return redirect(url_for('teacher.reports_dashboard'))
    
    # Get analysis
    analysis = StudentPerformanceAnalysis.query.filter_by(
        student_id=student_id,
        exam_id=exam_id,
        subject_id=exam.subject_id
    ).first()
    
    # Get detailed responses
    responses = ExamResponse.query.join(ExamQuestion).filter(
        ExamResponse.exam_session_id == session.id
    ).all()
    
    detailed_responses = []
    total_score = 0
    max_score = 0
    
    for response in responses:
        exam_question = ExamQuestion.query.get(response.exam_question_id)
        question = QuestionBank.query.get(exam_question.question_bank_id)
        
        if question and exam_question:
            max_score += exam_question.marks or question.marks
            
            # Check if answer is correct
            is_correct = False
            explanation = ""
            
            if question.question_type in ['multiple_choice', 'true_false']:
                is_correct = response.answer == question.correct_answer
                explanation = question.explanation or ""
            elif question.question_type == 'short_answer':
                # Simple matching for short answer (could be improved)
                is_correct = (response.answer or "").strip().lower() == (question.correct_answer or "").strip().lower()
                explanation = question.explanation or ""
            
            if is_correct:
                total_score += exam_question.marks or question.marks
            
            detailed_responses.append({
                'question': question,
                'exam_question': exam_question,
                'response': response,
                'is_correct': is_correct,
                'explanation': explanation,
                'marks_awarded': exam_question.marks if is_correct else 0
            })
    
    percentage = (total_score / max_score * 100) if max_score > 0 else 0
    
    # Get student's other performances in this subject
    other_exams = Exam.query.filter_by(
        subject_id=exam.subject_id,
        class_id=exam.class_id,
        teacher_id=teacher.id
    ).filter(Exam.id != exam_id).all()
    
    other_performances = []
    for other_exam in other_exams:
        other_analysis = StudentPerformanceAnalysis.query.filter_by(
            student_id=student_id,
            exam_id=other_exam.id,
            subject_id=exam.subject_id
        ).first()
        
        if other_analysis:
            other_performances.append({
                'exam': other_exam,
                'analysis': other_analysis,
                'date': other_exam.created_at
            })
    
    # Sort by date
    other_performances.sort(key=lambda x: x['date'], reverse=True)
    
    return render_template('teacher/student_report.html',
                         teacher=teacher,
                         student=student,
                         exam=exam,
                         analysis=analysis,
                         detailed_responses=detailed_responses,
                         total_score=total_score,
                         max_score=max_score,
                         percentage=round(percentage, 2),
                         other_performances=other_performances[:5])  # Last 5 exams

@teacher_bp.route('/reports/generate/<report_type>', methods=['POST'])
@login_required
@teacher_required
def generate_report(report_type):
    """Generate AI report"""
    try:
        teacher = Teacher.query.filter_by(user_id=current_user.id).first_or_404()
        
        data = request.get_json()
        exam_id = data.get('exam_id')
        subject_id = data.get('subject_id')
        class_id = data.get('class_id')
        
        ai_service = AIAnalysisService()
        
        if report_type == 'exam_analysis' and exam_id:
            exam = Exam.query.get_or_404(exam_id)
            
            # Check if report already exists
            existing_report = TeacherReport.query.filter_by(
                teacher_id=teacher.id,
                exam_id=exam_id,
                report_type='exam_analysis'
            ).first()
            
            if existing_report:
                return jsonify({
                    'success': True,
                    'message': 'Report already exists',
                    'report_id': existing_report.id
                })
            
            # Generate exam report (simplified - in reality, you'd gather more data)
            report = TeacherReport(
                teacher_id=teacher.id,
                exam_id=exam_id,
                subject_id=exam.subject_id,
                class_id=exam.class_id,
                report_type='exam_analysis',
                title=f'Analysis Report: {exam.name}',
                summary=f'AI-generated analysis of {exam.name} performance',
                is_ai_generated=True,
                ai_model='gpt-3.5-turbo' if ai_service.llm else 'rule_based',
                status='published'
            )
            
            db.session.add(report)
            db.session.commit()
            
            return jsonify({
                'success': True,
                'message': 'Exam analysis report generated successfully',
                'report_id': report.id
            })
        
        elif report_type == 'class_performance' and class_id and subject_id:
            # Generate class performance report
            classroom = ClassRoom.query.get_or_404(class_id)
            subject = Subject.query.get_or_404(subject_id)
            
            report = TeacherReport(
                teacher_id=teacher.id,
                subject_id=subject_id,
                class_id=class_id,
                report_type='class_performance',
                title=f'Class Performance Report: {subject.name} - {classroom.name}',
                summary=f'AI-generated performance analysis for {classroom.name} in {subject.name}',
                is_ai_generated=True,
                ai_model='gpt-3.5-turbo' if ai_service.llm else 'rule_based',
                status='published'
            )
            
            db.session.add(report)
            db.session.commit()
            
            return jsonify({
                'success': True,
                'message': 'Class performance report generated successfully',
                'report_id': report.id
            })
        
        else:
            return jsonify({
                'success': False,
                'message': 'Invalid report type or missing parameters'
            }), 400
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

@teacher_bp.route('/reports/view/<report_id>')
@login_required
@teacher_required
def view_report(report_id):
    """View generated report"""
    teacher = Teacher.query.filter_by(user_id=current_user.id).first_or_404()
    report = TeacherReport.query.get_or_404(report_id)
    
    # Verify ownership
    if report.teacher_id != teacher.id:
        flash('You do not have permission to view this report', 'danger')
        return redirect(url_for('teacher.reports_dashboard'))
    
    return render_template('teacher/view_report.html',
                         teacher=teacher,
                         report=report)

@teacher_bp.route('/reports/analyze-all/<exam_id>', methods=['POST'])
@login_required
@teacher_required
def analyze_all_students(exam_id):
    """Run AI analysis for all students in an exam"""
    try:
        teacher = Teacher.query.filter_by(user_id=current_user.id).first_or_404()
        exam = Exam.query.get_or_404(exam_id)
        
        # Verify ownership
        if exam.teacher_id != teacher.id:
            return jsonify({'success': False, 'message': 'Permission denied'}), 403
        
        ai_service = AIAnalysisService()
        
        # Get all students who took the exam
        exam_sessions = ExamSession.query.filter_by(exam_id=exam_id).all()
        
        analyzed_count = 0
        errors = []
        
        for session in exam_sessions:
            try:
                student = Student.query.get(session.student_id)
                if not student:
                    continue
                
                # Check if analysis already exists
                existing = StudentPerformanceAnalysis.query.filter_by(
                    student_id=student.id,
                    exam_id=exam_id,
                    subject_id=exam.subject_id
                ).first()
                
                if existing:
                    analyzed_count += 1
                    continue
                
                # Get exam responses
                responses = ExamResponse.query.join(ExamQuestion).filter(
                    ExamResponse.exam_session_id == session.id
                ).all()
                
                # Calculate score and prepare data
                total_score = 0
                max_score = 0
                question_responses = []
                
                for response in responses:
                    exam_question = ExamQuestion.query.get(response.exam_question_id)
                    question = QuestionBank.query.get(exam_question.question_bank_id)
                    
                    if question and exam_question:
                        max_score += exam_question.marks or question.marks
                        
                        # Check if answer is correct
                        is_correct = False
                        if question.question_type in ['multiple_choice', 'true_false']:
                            is_correct = response.answer == question.correct_answer
                        
                        if is_correct:
                            total_score += exam_question.marks or question.marks
                        
                        question_responses.append({
                            'question_id': question.id,
                            'question_text': question.question_text[:100],
                            'question_type': question.question_type,
                            'marks': exam_question.marks or question.marks,
                            'student_answer': response.answer,
                            'correct_answer': question.correct_answer,
                            'is_correct': is_correct
                        })
                
                percentage = (total_score / max_score * 100) if max_score > 0 else 0
                
                # Run AI analysis
                analysis_data = ai_service.analyze_student_performance(
                    student_data={
                        'first_name': student.first_name,
                        'last_name': student.last_name,
                        'class_name': exam.classroom.name,
                        'score': total_score,
                        'percentage': percentage
                    },
                    exam_data={
                        'title': exam.name,
                        'subject_name': exam.subject.name,
                        'total_marks': exam.total_marks
                    },
                    question_responses=question_responses
                )
                
                # Create analysis record
                analysis = StudentPerformanceAnalysis(
                    student_id=student.id,
                    exam_id=exam_id,
                    subject_id=exam.subject_id,
                    overall_score=percentage,
                    accuracy_rate=analysis_data.get('accuracy_rate', 0),
                    strengths=analysis_data.get('strengths', []),
                    weaknesses=analysis_data.get('weaknesses', []),
                    recommendations=analysis_data.get('recommendations', []),
                    ai_comment=analysis_data.get('ai_comment', ''),
                    analysis_method=analysis_data.get('analysis_method', 'rule_based'),
                    confidence_score=analysis_data.get('confidence_score', 0.5)
                )
                db.session.add(analysis)
                analyzed_count += 1
                
            except Exception as e:
                errors.append(f"Student {student.id if student else 'unknown'}: {str(e)}")
        
        db.session.commit()
        
        message = f"Analyzed {analyzed_count} students"
        if errors:
            message += f" with {len(errors)} errors"
        
        return jsonify({
            'success': True,
            'message': message,
            'analyzed_count': analyzed_count,
            'errors': errors
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    




