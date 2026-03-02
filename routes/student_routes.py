# app/routes/student_routes.py
from flask import Blueprint, render_template, request, jsonify, send_file, abort, flash, redirect, url_for, session, current_app, make_response
from werkzeug.utils import secure_filename
from flask_login import login_required, current_user
from models import (
    db, User, Student, Subject, ExamResult, ReportCard, ClassRoom, 
    AcademicTerm, Exam, ExamSession, ExamResponse, Attendance, AuditLog, QuestionBank, ExamQuestion, LearningMaterial, SubjectAssignment, StudentMaterialDownload
)
from utils.decorators import student_required
import os
from datetime import datetime, timezone, timedelta
import json
import random

student_bp = Blueprint('student', __name__, url_prefix='/student')

@student_bp.route('/dashboard')
@login_required
@student_required
def dashboard():
    """Student dashboard with minimal data"""
    student = Student.query.filter_by(user_id=current_user.id).first()
    
    if not student:
        flash('Student profile not found.', 'danger')
        return redirect(url_for('auth.student_logout'))
    
    # Get ONLY ACTIVE exams for the student's class
    available_exams = Exam.query.filter_by(
        class_id=student.current_class_id,
        status='active'  # Only show active exams
    ).order_by(
        Exam.created_at.desc()
    ).limit(6).all()
    
    # Get basic stats
    total_exams_taken = ExamResult.query.filter_by(
        student_id=student.id
    ).count()
    
    # Calculate average score
    avg_result = db.session.query(
        db.func.avg(ExamResult.total_score)
    ).filter(
        ExamResult.student_id == student.id
    ).scalar()
    
    average_score = float(avg_result) if avg_result else 0
    
    return render_template('student/dashboard.html',
                          student=student,
                          available_exams=available_exams,
                          total_exams_taken=total_exams_taken,
                          average_score=average_score)


@student_bp.route('/exams-dashboard')
@login_required
@student_required
def exams_dashboard():
    """Comprehensive exams dashboard showing ALL exam types"""
    student = Student.query.filter_by(user_id=current_user.id).first()
    
    if not student:
        flash('Student profile not found.', 'danger')
        return redirect(url_for('auth.student_logout'))
    
    # Get all exams for the student's class, grouped by status
    all_exams = Exam.query.filter_by(
        class_id=student.current_class_id
    ).order_by(
        Exam.scheduled_start.desc() if Exam.scheduled_start else Exam.created_at.desc()
    ).all()
    
    session = ExamSession.query.filter_by(
        student_id=student.id
    ).order_by(
        ExamSession.created_at.desc()
    ).first()

    # Group exams by status
    active_exams = [e for e in all_exams if e.status == 'active']
    scheduled_exams = [e for e in all_exams if e.status == 'scheduled']
    completed_exams = [e for e in all_exams if e.status == 'completed']
    draft_exams = [e for e in all_exams if e.status == 'draft']
    
    # Get exams that student has taken
    taken_exam_ids = [r.exam_id for r in ExamSession.query.filter_by(
        student_id=student.id
    ).with_entities(ExamSession.exam_id).all()]
    
    return render_template('student/exams_dashboard.html',
                          student=student,
                          session=session,
                          active_exams=active_exams,
                          scheduled_exams=scheduled_exams,
                          completed_exams=completed_exams,
                          taken_exam_ids=taken_exam_ids)

@student_bp.route('/available-exams')
@login_required
@student_required
def available_exams():
    """View all available exams"""
    student = Student.query.filter_by(user_id=current_user.id).first()
    
    if not student:
        flash('Student profile not found.', 'danger')
        return redirect(url_for('auth.student_logout'))
    
    # Get all exams for the student's class
    exams = Exam.query.filter_by(
        class_id=student.current_class_id
    ).order_by(
        Exam.scheduled_start.desc() if Exam.scheduled_start else Exam.created_at.desc()
    ).all()
    
    # Group exams by status
    active_exams = [e for e in exams if e.status == 'active']
    scheduled_exams = [e for e in exams if e.status == 'scheduled']
    completed_exams = [e for e in exams if e.status == 'completed']
    
    return render_template('student/exams.html',
                          student=student,
                          active_exams=active_exams,
                          scheduled_exams=scheduled_exams,
                          completed_exams=completed_exams)

@student_bp.route('/results')
@login_required
@student_required
def results():
    """View exam results"""
    student = Student.query.filter_by(user_id=current_user.id).first()
    
    if not student:
        flash('Student profile not found.', 'danger')
        return redirect(url_for('auth.student_logout'))
    
    # Get exam results
    results = ExamResult.query.filter_by(
        student_id=student.id
    ).order_by(
        ExamResult.id.desc()
    ).all()
    
    return render_template('student/results.html',
                          student=student,
                          results=results)

# Exam Taking Functionality
@student_bp.route('/exams')
@login_required
@student_required
def exams():
    """View available exams"""
    student = Student.query.filter_by(user_id=current_user.id).first_or_404()
    
    if not student.current_class_id:
        flash('You are not assigned to any class!', 'warning')
        return redirect(url_for('student.dashboard'))
    
    current_term = AcademicTerm.query.filter_by(is_active=True).first()
    if not current_term:
        flash('No active academic term!', 'warning')
        return redirect(url_for('student.dashboard'))
    
    # Get published exams for student's class
    available_exams = Exam.query.filter(
        Exam.class_id == student.current_class_id,
        Exam.academic_term_id == current_term.id,
        Exam.status == 'published'
    ).order_by(Exam.scheduled_start).all()
    
    # Get exam sessions for the student
    exam_sessions = ExamSession.query.filter_by(
        student_id=student.id
    ).order_by(ExamSession.created_at.desc()).all()
    
    # Create a map of exam_id to exam_session
    exam_session_map = {session.exam_id: session for session in exam_sessions}
    
    return render_template('student/exams.html',
                         student=student,
                         available_exams=available_exams,
                         exam_session_map=exam_session_map,
                         current_term=current_term)

@student_bp.route('/take-exam/<exam_id>')
@login_required
@student_required
def take_exam(exam_id):
    """Start taking an exam"""
    student = Student.query.filter_by(user_id=current_user.id).first()
    
    if not student:
        flash('Student profile not found.', 'danger')
        return redirect(url_for('auth.student_logout'))
    
    exam = Exam.query.get_or_404(exam_id)
    
    # Check if student belongs to the exam's class
    if exam.class_id != student.current_class_id:
        flash('You are not authorized to take this exam.', 'danger')
        return redirect(url_for('student.dashboard'))
    
    # Check if exam is active
    if exam.status != 'active':
        flash('This exam is not currently available.', 'danger')
        return redirect(url_for('student.exams_dashboard'))
    
    # Check access code if required
    if exam.access_code:
        # You might want to check if student has entered the access code
        # For now, we'll assume they have access
        pass
    
    # Check if student has already taken this exam
    existing_session = ExamSession.query.filter_by(
        student_id=student.id,
        exam_id=exam_id
    ).first()
    
    if existing_session and existing_session.status == 'completed':
        flash('You have already completed this exam.', 'info')
        return redirect(url_for('student.view_exam_result', exam_id=exam_id))
    
    # Create or get exam session
    if not existing_session:
        exam_session = ExamSession(
            exam_id=exam_id,
            student_id=student.id,
            teacher_id=exam.teacher_id,
            start_time=datetime.now(timezone.utc),
            status='in_progress'
        )
        db.session.add(exam_session)
        db.session.commit()
        session_id = exam_session.id
    else:
        exam_session = existing_session
        session_id = exam_session.id
        # Update status if needed
        if exam_session.status != 'in_progress':
            exam_session.status = 'in_progress'
            db.session.commit()
    
    # Get exam questions
    exam_questions = ExamQuestion.query.filter_by(
        exam_id=exam_id
    ).order_by(ExamQuestion.order).all()
    
    questions = []
    for eq in exam_questions:
        question = QuestionBank.query.get(eq.question_bank_id)
        if question:
            # Handle options - ensure it's properly formatted
            options = []
            original_options = []  # Store original options with their indices
            
            if question.options:
                try:
                    # If options is already a list/dict, use it directly
                    if isinstance(question.options, (list, dict)):
                        options_data = question.options
                    # If it's a string, try to parse it
                    elif isinstance(question.options, str):
                        options_data = json.loads(question.options)
                    
                    # Create structured options with original indices
                    for idx, opt in enumerate(options_data):
                        option_dict = {
                            'id': idx,  # Original position/index
                            'text': opt.get('text', ''),
                            'is_correct': opt.get('is_correct', False),
                            'image': opt.get('image')  # Keep image if exists
                        }
                        options.append(option_dict)
                        
                except Exception as e:
                    print(f"Error parsing options for question {question.id}: {e}")
                    options = []
            
            # Store original options (unshuffled)
            original_options = options.copy()
            
            # Apply shuffle_options setting if it's a multiple choice question
            shuffled_options = []
            if (exam.shuffle_options and 
                question.question_type in ['multiple_choice', 'true_false'] and 
                options):
                # Create a copy to shuffle
                shuffled_options = options.copy()
                random.shuffle(shuffled_options)
                
                # Track the new positions for correct answer
                correct_option_index = None
                for i, opt in enumerate(shuffled_options):
                    if opt.get('is_correct'):
                        correct_option_index = i
                        break
            else:
                shuffled_options = options
            
            # Get the correct answer text
            correct_answer = question.correct_answer
            
            # If it's a multiple choice, find the correct option text
            if question.question_type == 'multiple_choice':
                for opt in original_options:
                    if opt.get('is_correct'):
                        correct_answer = opt.get('text', '')
                        break
            
            # Build question data with proper formatting
            question_data = {
                'exam_question': {
                    'id': eq.id,
                    'order': eq.order,
                    'marks': eq.marks
                },
                'question': {
                    'id': question.id,
                    'question_text': question.question_text,
                    'question_type': question.question_type,
                    'question_image': question.question_image,
                    'question_image_alt': question.question_image_alt,
                    'options': shuffled_options,  # Use shuffled version
                    'original_options': original_options,  # Store original for verification
                    'correct_answer': correct_answer,
                    'explanation': question.explanation,
                    'marks': question.marks,
                    'difficulty': question.difficulty,
                    'topics': question.topics if question.topics else []
                },
                'marks': eq.marks or question.marks,
                'original_order': eq.order  # Keep original order for reference
            }
            questions.append(question_data)
    
    # Apply exam randomization/shuffle settings for questions
    if exam.is_randomized or exam.shuffle_questions:
        # Create a shuffled copy but track the original indices
        for i, q in enumerate(questions):
            q['display_index'] = i  # Store original index
            
        # Shuffle the questions
        shuffled_questions = questions.copy()
        random.shuffle(shuffled_questions)
        
        # Update the display order
        for i, q in enumerate(shuffled_questions):
            q['current_display_position'] = i + 1  # 1-based for user display
    else:
        shuffled_questions = questions
        # Set display positions
        for i, q in enumerate(shuffled_questions):
            q['display_index'] = i
            q['current_display_position'] = i + 1
    
    # Store the question order in session for later verification
    session['exam_question_order'] = {
        'exam_id': exam_id,
        'questions': [
            {
                'question_id': q['question']['id'],
                'original_index': q['display_index'],
                'display_position': q['current_display_position']
            }
            for q in shuffled_questions
        ]
    }
    
    return render_template('student/take_exam.html',
                         student=student,
                         exam=exam,
                         exam_session=exam_session,
                         questions=shuffled_questions,
                         original_questions=questions,   # Keep original for reference if needed
                         can_go_back=exam.allow_back_navigation,
                         show_results_immediately=exam.show_results_immediately)

@student_bp.route('/save-answer', methods=['POST'])
@login_required
@student_required
def save_answer():
    """Save student's answer - UPDATED for shuffled questions"""
    try:
        data = request.get_json()
        print(f"DEBUG - Received data in /save-answer: {data}")
        
        if not data:
            print("DEBUG - No data provided")
            return jsonify({'success': False, 'message': 'No data provided'}), 400
        
        student = Student.query.filter_by(user_id=current_user.id).first()
        print(f"DEBUG - Student found: {student}")
        
        if not student:
            return jsonify({'success': False, 'message': 'Student not found'}), 400
        
        # Get exam session
        session_id = data.get('sessionId')
        print(f"DEBUG - Looking for session ID: {session_id}")
        
        exam_session = ExamSession.query.filter_by(
            id=session_id,
            student_id=student.id
        ).first()
        
        print(f"DEBUG - Exam session found: {exam_session}")
        
        if not exam_session:
            return jsonify({'success': False, 'message': 'Exam session not found'}), 400
        
        # NEW: Get the question ID directly instead of using index
        question_id = data.get('questionId')
        print(f"DEBUG - Question ID: {question_id}")
        
        if not question_id:
            return jsonify({'success': False, 'message': 'Question ID required'}), 400
        
        # Find the ExamQuestion record for this question in this exam
        exam_question = ExamQuestion.query.filter_by(
            exam_id=exam_session.exam_id,
            question_bank_id=question_id
        ).first()
        
        print(f"DEBUG - Exam question found: {exam_question}")
        
        if not exam_question:
            return jsonify({'success': False, 'message': 'Question not found in exam'}), 400
        
        # Get the answer and additional metadata
        answer = data.get('answer')
        selected_option_index = data.get('selectedOptionIndex')  # For multiple choice
        original_option_index = data.get('originalOptionIndex')  # Original position if shuffled
        
        print(f"DEBUG - Answer data: answer={answer}, selectedOptionIndex={selected_option_index}, originalOptionIndex={original_option_index}")
        
        # Save or update response
        response = ExamResponse.query.filter_by(
            exam_session_id=exam_session.id,
            exam_question_id=exam_question.id
        ).first()
        
        print(f"DEBUG - Existing response found: {response}")
        
        save_type = data.get('saveType', 'manual')
        
        if response:
            response.answer = str(answer) if answer is not None else None
            response.selected_option_index = selected_option_index
            response.original_option_index = original_option_index
            response.timestamp = datetime.now(timezone.utc)
            response.save_type = save_type
            print(f"DEBUG - Updated response")
        else:
            response = ExamResponse(
                exam_session_id=exam_session.id,
                exam_question_id=exam_question.id,
                question_bank_id=question_id,  # Added this field
                answer=str(answer) if answer is not None else None,
                selected_option_index=selected_option_index,
                original_option_index=original_option_index,
                timestamp=datetime.now(timezone.utc),
                save_type=save_type
            )
            db.session.add(response)
            print(f"DEBUG - Created new response")
        
        db.session.commit()
        print(f"DEBUG - Committed to database, response ID: {response.id}")
        
        return jsonify({
            'success': True, 
            'message': 'Answer saved', 
            'timestamp': response.timestamp.isoformat(),
            'responseId': response.id
        })
        
    except Exception as e:
        db.session.rollback()
        import traceback
        print(f"ERROR in save_answer: {str(e)}")
        print(traceback.format_exc())
        return jsonify({'success': False, 'message': str(e)}), 400
        
@student_bp.route('/log-tab-switch', methods=['POST'])
@login_required
@student_required
def log_tab_switch():
    """Log tab switching during exam"""
    try:
        data = request.get_json()
        
        # Log to audit trail
        audit_log = AuditLog(
            user_id=current_user.id,
            action='TAB_SWITCH',
            details={
                'exam_id': data.get('examId'),
                'session_id': data.get('sessionId'),
                'switch_count': data.get('switchCount'),
                'timestamp': datetime.now(timezone.utc).isoformat()
            },
            ip_address=request.remote_addr
        )
        db.session.add(audit_log)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Tab switch logged'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400


@student_bp.route('/submit-exam', methods=['POST'])
@login_required
@student_required
def submit_exam():
    """Submit completed exam - UPDATED for shuffled questions"""
    try:
        data = request.get_json()
        
        student = Student.query.filter_by(user_id=current_user.id).first()
        if not student:
            return jsonify({'success': False, 'message': 'Student not found'}), 400
        
        # Get exam session
        exam_session = ExamSession.query.filter_by(
            id=data.get('sessionId'),
            student_id=student.id
        ).first()
        
        if not exam_session:
            return jsonify({'success': False, 'message': 'Exam session not found'}), 400
        
        # Get exam
        exam = Exam.query.get(exam_session.exam_id)
        if not exam:
            return jsonify({'success': False, 'message': 'Exam not found'}), 400
        
        # Update exam session
        exam_session.status = 'completed'
        exam.status = 'completed'  # Mark exam as completed
        exam_session.end_time = datetime.now(timezone.utc)
        
        # Process answers
        answers = data.get('answers', {})  # {questionId: answerData}
        option_mappings = data.get('optionMappings', {})  # {questionId: {shuffledIndex: originalIndex}}
        
        total_score = 0
        total_possible = 0
        
        # Get all exam questions
        exam_questions = ExamQuestion.query.filter_by(
            exam_id=exam_session.exam_id
        ).all()
        
        for eq in exam_questions:
            question = QuestionBank.query.get(eq.question_bank_id)
            if not question:
                continue
            
            # Get marks for this question
            question_marks = eq.marks if eq.marks else question.marks
            total_possible += question_marks
            
            # Check if we have an answer for this question
            question_id = str(question.id)
            answer_data = answers.get(question_id)
            
            is_correct = None
            selected_answer = None
            selected_option_index = None
            original_option_index = None
            correct_answer_text = question.correct_answer
            
            if answer_data:
                selected_answer = answer_data.get('answer')
                selected_option_index = answer_data.get('selectedOptionIndex')
                original_option_index = answer_data.get('originalOptionIndex')
                
                # Determine correctness based on question type
                if question.question_type in ['multiple_choice', 'true_false']:
                    # Get option mapping if shuffled
                    mapping = option_mappings.get(question_id, {})
                    
                    if selected_option_index is not None:
                        # Convert selected index to original index if shuffled
                        original_index = mapping.get(str(selected_option_index), selected_option_index)
                        
                        # Check if this original index is correct
                        if question.options and 0 <= original_index < len(question.options):
                            original_option = question.options[original_index]
                            is_correct = original_option.get('is_correct', False)
                            
                            # Get the correct answer text
                            for opt in question.options:
                                if opt.get('is_correct'):
                                    correct_answer_text = opt.get('text', '')
                                    break
                            
                            # If correct, add to score
                            if is_correct:
                                total_score += question_marks
                    
                elif question.question_type == 'short_answer':
                    # Compare answer text
                    correct_answer_lower = (question.correct_answer or '').strip().lower()
                    selected_answer_lower = (selected_answer or '').strip().lower()
                    is_correct = correct_answer_lower == selected_answer_lower
                    
                    if is_correct:
                        total_score += question_marks
                
                elif question.question_type == 'essay':
                    # Essay requires manual grading
                    is_correct = None  # Mark for manual review
            
            # Save or update response
            response = ExamResponse.query.filter_by(
                exam_session_id=exam_session.id,
                exam_question_id=eq.id
            ).first()
            
            if response:
                response.answer = str(selected_answer) if selected_answer is not None else None
                response.selected_option_index = selected_option_index
                response.original_option_index = original_option_index
                response.is_correct = is_correct
                response.marks_awarded = question_marks if is_correct else 0
                response.correct_answer = correct_answer_text
                response.timestamp = datetime.now(timezone.utc)
                response.response_time = datetime.now(timezone.utc)
            else:
                response = ExamResponse(
                    exam_session_id=exam_session.id,
                    exam_question_id=eq.id,
                    question_bank_id=question.id,
                    answer=str(selected_answer) if selected_answer is not None else None,
                    selected_option_index=selected_option_index,
                    original_option_index=original_option_index,
                    is_correct=is_correct,
                    marks_awarded=question_marks if is_correct else 0,
                    correct_answer=correct_answer_text,
                    timestamp=datetime.now(timezone.utc),
                    response_time=datetime.now(timezone.utc)
                )
                db.session.add(response)
        
        # Calculate percentage
        percentage = (total_score / total_possible * 100) if total_possible > 0 else 0
        
        # Create exam result (if you have an ExamResult model)
        # If you don't have this model yet, you might need to create it
        try:
            result = ExamResult(
                exam_session_id=exam_session.id,
                student_id=student.id,
                exam_id=exam_session.exam_id,
                score=total_score,
                total_possible=total_possible,
                percentage=percentage,
                passed=percentage >= exam.pass_mark,
                submitted_at=datetime.now(timezone.utc)
            )
            db.session.add(result)
        except:
            # If ExamResult model doesn't exist, just log it
            print(f"Exam result for session {exam_session.id}: Score={total_score}/{total_possible}")
        
        # Log submission
        audit_log = AuditLog(
            user_id=current_user.id,
            action='SUBMIT_EXAM',
            details={
                'exam_id': exam_session.exam_id,
                'session_id': exam_session.id,
                'score': total_score,
                'total_possible': total_possible,
                'percentage': percentage,
                'duration': data.get('duration'),
                'tab_switches': data.get('tabSwitches'),
                'reason': data.get('reason')
            },
            ip_address=request.remote_addr
        )
        db.session.add(audit_log)
        
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': 'Exam submitted successfully',
            'score': total_score,
            'total_possible': total_possible,
            'percentage': percentage,
            'passed': percentage >= exam.pass_mark
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"Error submitting exam: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)}), 400    

def calculate_exam_score(session_id):
    """Calculate exam score (simplified version)"""
    responses = ExamResponse.query.filter_by(exam_session_id=session_id).all()
    total_score = 0
    
    for response in responses:
        exam_question = ExamQuestion.query.get(response.exam_question_id)
        question = QuestionBank.query.get(exam_question.question_bank_id)
        
        if question and response.answer:
            if question.question_type == 'multiple_choice':
                # Find correct option
                correct_option = next((opt for opt in question.options if opt.get('is_correct')), None)
                if correct_option and response.answer == correct_option.get('text'):
                    total_score += exam_question.marks or question.marks
            elif question.question_type == 'true_false':
                if response.answer.lower() == question.correct_answer.lower():
                    total_score += exam_question.marks or question.marks
            elif question.question_type in ['short_answer', 'essay']:
                # For now, give partial credit for non-empty answers
                if response.answer.strip():
                    total_score += (exam_question.marks or question.marks) * 0.5
    
    return total_score

@student_bp.route('/exam/<session_id>/result')
@login_required
@student_required
def view_exam_result(session_id):  # Changed parameter name
    """View specific exam result"""
    # Get the exam session
    exam_session = ExamSession.query.get_or_404(session_id)
    
    print(f"DEBUG - Session ID: {session_id}")
    print(f"DEBUG - Exam session: {exam_session}")
    
    student = Student.query.filter_by(user_id=current_user.id).first_or_404()
    print(f"DEBUG - Student: {student}")
    print(f"DEBUG - Exam session student ID: {exam_session.student_id}")
    
    # Verify ownership
    if exam_session.student_id != student.id:
        abort(403)
    
    # Get the exam from the session
    exam_id = exam_session.exam_id
    exam = Exam.query.get_or_404(exam_id)
    
    # Only show results if exam is configured to show immediately
    if not exam.show_results_immediately:
        flash('Results are not available yet!', 'warning')
        return redirect(url_for('student.exams'))

    # Get exam questions with their related QuestionBank data
    exam_questions = ExamQuestion.query.filter_by(exam_id=exam_id).all()
    
    print(f"DEBUG - Found {len(exam_questions)} exam questions")
    
    # Prepare detailed questions data
    questions_data = []
    for eq in exam_questions:
        question = QuestionBank.query.get(eq.question_bank_id)
        if question:
            questions_data.append({
                'exam_question': eq,
                'question': question,
                'marks': eq.marks or question.marks,
                'options': question.options if question.options else [],
                'correct_answer': question.correct_answer,
                'explanation': question.explanation
            })
    
    # Get responses for this session
    responses = ExamResponse.query.filter_by(exam_session_id=exam_session.id).all()
    
    print(f"DEBUG - Found {len(responses)} responses")
    
    # Create a map of exam_question_id to response for easy lookup
    response_map = {}
    for response in responses:
        response_map[response.exam_question_id] = response
    
    # Calculate score
    total_marks = 0
    obtained_marks = 0
    
    for eq in exam_questions:
        question = QuestionBank.query.get(eq.question_bank_id)
        if question:
            marks = eq.marks or question.marks
            total_marks += marks
            
            # Find response for this question
            response = response_map.get(eq.id)
            if response and response.answer:
                # Check if the response is correct
                if question.question_type == 'multiple_choice':
                    # Get the correct option
                    if question.options:
                        # Find correct option
                        correct_option = None
                        for opt in question.options:
                            if isinstance(opt, dict) and opt.get('is_correct'):
                                correct_option = opt.get('text')
                                break
                        
                        if correct_option and response.answer == correct_option:
                            obtained_marks += marks
                        elif question.correct_answer and response.answer == question.correct_answer:
                            obtained_marks += marks
                elif question.question_type == 'true_false':
                    if response.answer.lower() == (question.correct_answer or '').lower():
                        obtained_marks += marks
                elif question.question_type in ['short_answer', 'essay']:
                    # For now, give partial credit for non-empty answers
                    if response.answer.strip():
                        obtained_marks += marks * 0.5
    
    percentage = (obtained_marks / total_marks * 100) if total_marks > 0 else 0
    
    # Determine grade based on percentage
    grade = calculate_grade(percentage)
    
    print(f"DEBUG - Score: {obtained_marks}/{total_marks}, Percentage: {percentage}, Grade: {grade}")
    
    return render_template('student/exam_result.html',
                         student=student,
                         exam=exam,
                         exam_session=exam_session,
                         questions_data=questions_data,
                         responses=responses,
                         response_map=response_map,
                         total_marks=total_marks,
                         obtained_marks=obtained_marks,
                         percentage=percentage,
                         grade=grade)

def calculate_grade(percentage):
    """Calculate grade based on percentage"""
    if percentage >= 80:
        return 'A', 'Excellent'
    elif percentage >= 70:
        return 'B', 'Very Good'
    elif percentage >= 60:
        return 'C', 'Good'
    elif percentage >= 50:
        return 'D', 'Pass'
    elif percentage >= 40:
        return 'E', 'Fair'
    else:
        return 'F', 'Fail'
    
@student_bp.route('/exam-results/<exam_session_id>')
@login_required
@student_required 
def exam_results(exam_session_id):
    """View individual exam results"""
    exam_session = ExamSession.query.get_or_404(exam_session_id)
    student = Student.query.filter_by(user_id=current_user.id).first_or_404()
    
    # Verify ownership
    if exam_session.student_id != student.id:
        abort(403)
    
    # Only show results if exam is configured to show immediately or has been graded
    if exam_session.exam.show_results_immediately and exam_session.status != 'graded':
        flash('Results are not available yet!', 'warning')
        return redirect(url_for('student.exams'))
    
    # Get exam and responses
    exam = exam_session.exam
    responses = ExamResponse.query.filter_by(
        exam_session_id=exam_session_id
    ).all()
    
    return render_template('student/exam_results.html',
                         student=student,
                         exam_session=exam_session,
                         exam=exam,
                         responses=responses)

# Basic profile management
@student_bp.route('/profile')
@login_required
@student_required
def profile():
    """View and update student profile"""
    student = Student.query.filter_by(user_id=current_user.id).first()
    
    if not student:
        flash('Student profile not found.', 'danger')
        return redirect(url_for('auth.student_logout'))
    
    # Get attendance summary
    attendance_summary = db.session.query(
        Attendance.status,
        db.func.count(Attendance.id).label('count')
    ).filter(
        Attendance.student_id == student.id
    ).group_by(
        Attendance.status
    ).all()
    
    return render_template('student/profile.html',
                          student=student,
                          attendance_summary=attendance_summary)


@student_bp.route('/e-library')
@login_required
@student_required
def e_library():
    """Student e-library - view learning materials"""
    student = Student.query.filter_by(user_id=current_user.id).first_or_404()
    
    if not student.current_class_id:
        flash('You are not assigned to any class!', 'warning')
        return redirect(url_for('student.dashboard'))
    
    # Get search and filter parameters
    search_query = request.args.get('search', '')
    subject_filter = request.args.get('subject', 'all')
    material_type_filter = request.args.get('type', 'all')
    
    # Build query
    query = LearningMaterial.query.filter(
        LearningMaterial.is_published == True,
        db.or_(
            LearningMaterial.accessible_to == 'all',
            db.and_(
                LearningMaterial.accessible_to == 'subject',
                LearningMaterial.subject_id.in_(
                    db.session.query(Subject.id).join(SubjectAssignment).filter(
                        SubjectAssignment.class_id == student.current_class_id
                    )
                )
            ),
            db.and_(
                LearningMaterial.accessible_to == 'class',
                LearningMaterial.class_id == student.current_class_id
            )
        )
    )
    
    # Apply filters
    if search_query:
        query = query.filter(
            db.or_(
                LearningMaterial.title.ilike(f'%{search_query}%'),
                LearningMaterial.description.ilike(f'%{search_query}%'),
                LearningMaterial.tags.contains([search_query])
            )
        )
    
    if subject_filter != 'all':
        query = query.filter(LearningMaterial.subject_id == subject_filter)
    
    if material_type_filter != 'all':
        query = query.filter(LearningMaterial.material_type == material_type_filter)
    
    # Get materials
    materials = query.order_by(
        LearningMaterial.is_featured.desc(),
        LearningMaterial.created_at.desc()
    ).all()
    
    # Get all subjects with materials
    subjects = Subject.query.join(LearningMaterial).filter(
        LearningMaterial.is_published == True,
        db.or_(
            LearningMaterial.accessible_to == 'all',
            db.and_(
                LearningMaterial.accessible_to == 'subject',
                LearningMaterial.subject_id.in_(
                    db.session.query(Subject.id).join(SubjectAssignment).filter(
                        SubjectAssignment.class_id == student.current_class_id
                    )
                )
            ),
            db.and_(
                LearningMaterial.accessible_to == 'class',
                LearningMaterial.class_id == student.current_class_id
            )
        )
    ).distinct().all()
    
    # Track view
    for material in materials:
        material.view_count = (material.view_count or 0) + 1
    
    db.session.commit()
    
    return render_template('student/e_library.html',
                         student=student,
                         materials=materials,
                         subjects=subjects,
                         search_query=search_query,
                         subject_filter=subject_filter,
                         material_type_filter=material_type_filter)

@student_bp.route('/e-library/download/<material_id>')
@login_required
@student_required
def download_material(material_id):
    """Download a learning material"""
    try:
        student = Student.query.filter_by(user_id=current_user.id).first_or_404()
        material = LearningMaterial.query.get_or_404(material_id)
        
        # Check if material is accessible to student
        if not material.is_published:
            flash('This material is not available.', 'danger')
            return redirect(url_for('student.e_library'))
        
        # Check access rights
        has_access = False
        if material.accessible_to == 'all':
            has_access = True
        elif material.accessible_to == 'subject':
            # Check if student is in a class that has this subject
            assignments = SubjectAssignment.query.filter_by(
                subject_id=material.subject_id,
                class_id=student.current_class_id
            ).first()
            has_access = assignments is not None
        elif material.accessible_to == 'class':
            has_access = material.class_id == student.current_class_id
        
        if not has_access:
            flash('You do not have access to this material.', 'danger')
            return redirect(url_for('student.e_library'))
        
        # Update download count
        material.download_count = (material.download_count or 0) + 1
        
        # Track student download
        existing_download = StudentMaterialDownload.query.filter_by(
            student_id=student.id,
            material_id=material_id
        ).first()
        
        if not existing_download:
            download = StudentMaterialDownload(
                student_id=student.id,
                material_id=material_id
            )
            db.session.add(download)
        
        db.session.commit()
        
        # Serve file or content
        if material.file_path and material.file_path.startswith('/static/'):
            # Extract filename from path
            filename = material.file_path.split('/')[-1]
            # Get original filename from database or use title
            safe_title = secure_filename(material.title)
            extension = filename.split('.')[-1] if '.' in filename else ''
            
            if extension:
                download_name = f"{safe_title}.{extension}"
            else:
                download_name = safe_title
            
            # Get full path
            static_path = material.file_path[len('/static/'):]
            full_path = os.path.join(current_app.root_path, 'static', static_path)
            
            if os.path.exists(full_path):
                return send_file(full_path, as_attachment=True, download_name=download_name)
            else:
                flash('File not found on server.', 'danger')
                return redirect(url_for('student.e_library'))
        
        elif material.external_link:
            return redirect(material.external_link)
        
        elif material.content:
            # Create a text file with the content
            response = make_response(material.content)
            response.headers['Content-Type'] = 'text/plain'
            response.headers['Content-Disposition'] = f'attachment; filename="{secure_filename(material.title)}.txt"'
            return response
        
        else:
            flash('No content available for download.', 'danger')
            return redirect(url_for('student.e_library'))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error downloading material: {str(e)}', 'danger')
        return redirect(url_for('student.e_library'))

@student_bp.route('/e-library/view/<material_id>')
@login_required
@student_required
def view_material(material_id):
    """View material details"""
    student = Student.query.filter_by(user_id=current_user.id).first_or_404()
    material = LearningMaterial.query.get_or_404(material_id)
    
    # Check access (same as download)
    has_access = False
    if material.accessible_to == 'all':
        has_access = True
    elif material.accessible_to == 'subject':
        assignments = SubjectAssignment.query.filter_by(
            subject_id=material.subject_id,
            class_id=student.current_class_id
        ).first()
        has_access = assignments is not None
    elif material.accessible_to == 'class':
        has_access = material.class_id == student.current_class_id
    
    if not has_access or not material.is_published:
        flash('You do not have access to this material.', 'danger')
        return redirect(url_for('student.e_library'))
    
    # Get similar materials
    similar_materials = LearningMaterial.query.filter(
        LearningMaterial.is_published == True,
        LearningMaterial.subject_id == material.subject_id,
        LearningMaterial.id != material_id,
        db.or_(
            LearningMaterial.accessible_to == 'all',
            db.and_(
                LearningMaterial.accessible_to == 'subject',
                LearningMaterial.subject_id == material.subject_id
            ),
            db.and_(
                LearningMaterial.accessible_to == 'class',
                LearningMaterial.class_id == student.current_class_id
            )
        )
    ).order_by(LearningMaterial.created_at.desc()).limit(5).all()
    
    # Increment view count
    material.view_count = (material.view_count or 0) + 1
    db.session.commit()
    
    return render_template('student/view_material.html',
                         student=student,
                         material=material,
                         similar_materials=similar_materials)


