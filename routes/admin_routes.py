# app/routes/admin_routes.py
from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, send_file, abort, current_app, Response
import os
from werkzeug.utils import secure_filename
from flask_login import login_required, current_user
from datetime import datetime, timezone, date
from models import (
    db, User, Student, Teacher, Parent, ClassRoom, Subject, AcademicSession,
    AcademicTerm, SubjectAssignment, StudentAssessment, StudentParent, Assessment, SystemConfiguration, 
    AuditLog, GradeScale, SubjectCategory, QuestionBank, Exam, ExamQuestion,
    ExamSession, ExamResponse, ExamResult, StudentPromotion, Attendance, DomainEvaluation,
    TeacherComment, FormTeacherComment, PrincipalRemark, ReportCard,
    ParentNotification, AssessmentScoreMapping,TeacherReport, StudentPerformanceAnalysis,
    ExamQuestionAnalysis, StudentMaterialDownload, LearningMaterial, LoginAttempt, SecurityLog
)
from utils.decorators import admin_required
from config import Config
from datetime import datetime, timezone, date
import io
import csv
import traceback
import json

# For Excel export/import
try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False
    print("Warning: pandas not installed. Excel export/import will not work.")


admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

@admin_bp.context_processor
def utility_processor():
    def get_assessment_by_id(assessment_id):
        return Assessment.query.get(assessment_id)
    return dict(get_assessment_by_id=get_assessment_by_id)

@admin_bp.route('/dashboard')
@login_required
@admin_required
def dashboard():
    """Admin dashboard"""
    # Get active academic session
    active_session = AcademicSession.query.filter_by(is_active=True).first()
    
    stats = {
        'total_students': Student.query.filter_by(is_active=True, academic_status='active').count(),
        'total_teachers': Teacher.query.count(),
        'total_classes': ClassRoom.query.count(),
        'total_subjects': Subject.query.filter_by(is_active=True).count(),
        'active_session': active_session.name if active_session else 'No active session',
        'total_parents': Parent.query.count()
    }
    
    # Recent activities
    recent_logs = AuditLog.query.order_by(AuditLog.timestamp.desc()).limit(10).all()
    
    return render_template('admin/dashboard.html', stats=stats, recent_logs=recent_logs)

@admin_bp.route('/dashboard/stats')
@login_required
@admin_required
def dashboard_stats():
    """Get dashboard statistics for AJAX requests"""
    try:
        # Get active academic session
        active_session = None
        try:
            active_session = AcademicSession.query.filter_by(is_active=True).first()
        except Exception as e:
            print(f"Error fetching active session: {e}")
            active_session = None
        
        # Get student count
        total_students = 0
        try:
            total_students = Student.query.filter_by(is_active=True, academic_status='active').count()
        except Exception as e:
            print(f"Error fetching student count: {e}")
        
        # Get teacher count
        total_teachers = 0
        try:
            total_teachers = Teacher.query.count()
        except Exception as e:
            print(f"Error fetching teacher count: {e}")
        
        # Get class count
        total_classes = 0
        try:
            total_classes = ClassRoom.query.count()
        except Exception as e:
            print(f"Error fetching class count: {e}")
        
        # Get subject count
        total_subjects = 0
        try:
            total_subjects = Subject.query.filter_by(is_active=True).count()
        except Exception as e:
            print(f"Error fetching subject count: {e}")
        
        # Get parent count
        total_parents = 0
        try:
            total_parents = Parent.query.count()
        except Exception as e:
            print(f"Error fetching parent count: {e}")
        
        stats = {
            'total_students': total_students,
            'total_teachers': total_teachers,
            'total_classes': total_classes,
            'total_subjects': total_subjects,
            'active_session': active_session.name if active_session else 'No active session',
            'total_parents': total_parents,
            'pending_assessments': 0,  # Placeholder
            'upcoming_exams': 0,  # Placeholder
            'active_students_percentage': 95 if total_students > 0 else 0,
            'attendance_rate': 92  # Placeholder
        }
        
        return jsonify({
            'success': True,
            'stats': stats,
            'timestamp': datetime.now(timezone.utc).isoformat()
        })
    
    except Exception as e:
        print(f"Error in dashboard_stats: {e}")
        import traceback
        traceback.print_exc()
        
        # Return minimal stats on error
        return jsonify({
            'success': False,
            'message': str(e),
            'stats': {
                'total_students': 0,
                'total_teachers': 0,
                'total_classes': 0,
                'total_subjects': 0,
                'active_session': 'Error loading',
                'total_parents': 0,
                'pending_assessments': 0,
                'upcoming_exams': 0,
                'active_students_percentage': 0,
                'attendance_rate': 0
            }
        }), 400
    
# Dashboard Widget Data
@admin_bp.route('/dashboard/recent-activities')
@login_required
@admin_required
def recent_activities():
    """Get recent activities for dashboard"""
    try:
        recent_logs = AuditLog.query.order_by(AuditLog.timestamp.desc()).limit(10).all()
        
        activities = []
        for log in recent_logs:
            activities.append({
                'id': log.id,
                'action': log.action,
                'user': log.user.username if log.user else 'System',
                'timestamp': log.timestamp.strftime('%Y-%m-%d %H:%M'),
                'description': f"{log.action.replace('_', ' ').title()} by {log.user.username if log.user else 'System'}"
            })
        
        return jsonify({
            'success': True,
            'activities': activities
        })
    
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400


@admin_bp.route('/dashboard/class-distribution')
@login_required
@admin_required
def class_distribution():
    """Get class distribution data for charts"""
    try:
        classes = ClassRoom.query.all()
        
        distribution = []
        for classroom in classes:
            student_count = classroom.class_students.count()
            if student_count > 0:
                distribution.append({
                    'name': classroom.name,
                    'value': student_count,
                    'capacity': classroom.max_students if hasattr(classroom, 'max_students') else 40
                })
        
        return jsonify({
            'success': True,
            'distribution': distribution
        })
    
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400


@admin_bp.route('/dashboard/attendance-summary')
@login_required
@admin_required
def attendance_summary():
    """Get attendance summary for dashboard"""
    try:
        today = datetime.now(timezone.utc).date()
        
        # This is a simplified example - adjust based on your actual attendance model
        total_students = Student.query.filter_by(is_active=True, academic_status='active').count()
        
        # Mock data - replace with actual attendance queries
        summary = {
            'date': today.isoformat(),
            'total_students': total_students,
            'present': int(total_students * 0.92),
            'absent': int(total_students * 0.05),
            'late': int(total_students * 0.03),
            'attendance_rate': 92
        }
        
        return jsonify({
            'success': True,
            'summary': summary
        })
    
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400


# Quick Actions
@admin_bp.route('/dashboard/quick-actions', methods=['POST'])
@login_required
@admin_required
def quick_actions():
    """Handle quick actions from dashboard"""
    try:
        data = request.get_json()
        action = data.get('action')
        
        if action == 'add_student':
            # Quick add student logic
            return jsonify({
                'success': True,
                'message': 'Redirecting to add student form',
                'redirect': url_for('admin.manage_students')
            })
        
        elif action == 'add_teacher':
            return jsonify({
                'success': True,
                'message': 'Redirecting to add teacher form',
                'redirect': url_for('admin.manage_teachers')
            })
        
        elif action == 'schedule_exam':
            return jsonify({
                'success': True,
                'message': 'Redirecting to exam scheduling',
                'redirect': url_for('admin.manage_exams')
            })
        
        elif action == 'generate_reports':
            return jsonify({
                'success': True,
                'message': 'Redirecting to report generation',
                'redirect': url_for('admin.generate_reports')
            })
        
        else:
            return jsonify({
                'success': False,
                'message': 'Unknown action'
            }), 400
    
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400


# System Status
@admin_bp.route('/dashboard/system-status')
@login_required
@admin_required
def system_status():
    """Get system status information"""
    try:
        from datetime import datetime, timezone
        
        status = {
            'database': 'connected',
            'cache': 'running',
            'storage': 'available',
            'uptime': '99.9%',
            'last_backup': '2024-01-21 02:00:00',
            'active_users': User.query.filter_by(is_active=True).count(),
            'server_time': datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
        }
        
        return jsonify({
            'success': True,
            'status': status
        })
    
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400


# Notification Endpoints
@admin_bp.route('/notifications')
@login_required
@admin_required
def get_notifications():
    """Get notifications for admin"""
    try:
        # Mock notifications - replace with actual notification logic
        notifications = [
            {
                'id': 1,
                'type': 'warning',
                'title': 'System Backup Required',
                'message': 'System backup is due in 2 days',
                'timestamp': '2024-01-22 10:30:00',
                'read': False
            },
            {
                'id': 2,
                'type': 'info',
                'title': 'New Student Registration',
                'message': '5 new students registered today',
                'timestamp': '2024-01-22 09:15:00',
                'read': True
            },
            {
                'id': 3,
                'type': 'success',
                'title': 'Report Cards Generated',
                'message': 'Term 1 report cards have been generated successfully',
                'timestamp': '2024-01-21 16:45:00',
                'read': True
            }
        ]
        
        unread_count = len([n for n in notifications if not n['read']])
        
        return jsonify({
            'success': True,
            'notifications': notifications,
            'unread_count': unread_count
        })
    
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400


@admin_bp.route('/notifications/<notification_id>/read', methods=['POST'])
@login_required
@admin_required
def mark_notification_read(notification_id):
    """Mark notification as read"""
    try:
        # This would update the notification status in the database
        # For now, just return success
        
        return jsonify({
            'success': True,
            'message': 'Notification marked as read'
        })
    
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400


@admin_bp.route('/notifications/read-all', methods=['POST'])
@login_required
@admin_required
def mark_all_notifications_read():
    """Mark all notifications as read"""
    try:
        # This would update all notifications in the database
        # For now, just return success
        
        return jsonify({
            'success': True,
            'message': 'All notifications marked as read'
        })
    
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400


# Common AJAX endpoints that might be missing
@admin_bp.route('/api/check-session')
@login_required
@admin_required
def check_session():
    """Check if user session is valid"""
    return jsonify({
        'success': True,
        'user': {
            'id': current_user.id,
            'username': current_user.username,
            'role': current_user.role
        },
        'session_valid': True
    })


@admin_bp.route('/api/get-current-term')
@login_required
@admin_required
def get_current_term():
    """Get current academic term"""
    try:
        current_term = AcademicTerm.query.filter_by(is_active=True).first()
        
        if current_term:
            return jsonify({
                'success': True,
                'term': {
                    'id': current_term.id,
                    'name': current_term.name,
                    'term_number': current_term.term_number,
                    'start_date': current_term.start_date.strftime('%Y-%m-%d'),
                    'end_date': current_term.end_date.strftime('%Y-%m-%d'),
                    'session': current_term.session.name
                }
            })
        else:
            return jsonify({
                'success': True,
                'term': None,
                'message': 'No active term found'
            })
    
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400
    
# Academic Session Management
@admin_bp.route('/academic-sessions')
@login_required
@admin_required
def manage_academic_sessions():
    """Manage academic sessions"""
    sessions = AcademicSession.query.order_by(AcademicSession.start_date.desc()).all()
    
    # Calculate statistics
    active_sessions = AcademicSession.query.filter_by(is_active=True).count()
    total_terms = AcademicTerm.query.count()
    total_classes = ClassRoom.query.count()
    
    return render_template('admin/academic_sessions.html', 
                         sessions=sessions,
                         active_sessions=active_sessions,
                         total_terms=total_terms,
                         total_classes=total_classes)

@admin_bp.route('/academic-sessions/add', methods=['POST'])
@login_required
@admin_required
def add_academic_session():
    """Add new academic session"""
    try:
        name = request.form['name']
        start_date = datetime.strptime(request.form['start_date'], '%Y-%m-%d').date()
        end_date = datetime.strptime(request.form['end_date'], '%Y-%m-%d').date()
        is_active = 'is_active' in request.form
        
        # Validate dates
        if start_date >= end_date:
            return jsonify({'success': False, 'message': 'Start date must be before end date'}), 400
        
        # Check if session already exists
        existing_session = AcademicSession.query.filter(
            (AcademicSession.name == name) |
            (
                (AcademicSession.start_date <= end_date) &
                (AcademicSession.end_date >= start_date)
            )
        ).first()
        
        if existing_session:
            return jsonify({
                'success': False, 
                'message': 'Session with this name or overlapping dates already exists'
            }), 400
        
        # Deactivate other sessions if this one is active
        if is_active:
            AcademicSession.query.update({'is_active': False})
        
        session = AcademicSession(
            name=name,
            start_date=start_date,
            end_date=end_date,
            is_active=is_active
        )
        db.session.add(session)
        db.session.commit()
        
        # Log action
        audit_log = AuditLog(
            user_id=current_user.id,
            action='CREATE_ACADEMIC_SESSION',
            table_name='academic_sessions',
            record_id=session.id,
            new_values={
                'name': name,
                'start_date': start_date.strftime('%Y-%m-%d'),
                'end_date': end_date.strftime('%Y-%m-%d'),
                'is_active': is_active
            },
            ip_address=request.remote_addr
        )
        db.session.add(audit_log)
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': 'Academic session added successfully',
            'session_id': session.id
        })
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400
    
@admin_bp.route('/academic-sessions/<session_id>/data')
@login_required
@admin_required
def get_academic_session_data(session_id):
    """Get academic session data for editing"""
    try:
        session = AcademicSession.query.get_or_404(session_id)
        
        return jsonify({
            'success': True,
            'session': {
                'id': session.id,
                'name': session.name,
                'start_date': session.start_date.strftime('%Y-%m-%d'),
                'end_date': session.end_date.strftime('%Y-%m-%d'),
                'is_active': session.is_active
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400


@admin_bp.route('/academic-sessions/update', methods=['POST'])
@login_required
@admin_required
def update_academic_session():
    """Update existing academic session"""
    try:
        session_id = request.form.get('session_id')
        if not session_id:
            return jsonify({'success': False, 'message': 'Session ID is required'}), 400
        
        session = AcademicSession.query.get_or_404(session_id)
        
        name = request.form['name']
        start_date = datetime.strptime(request.form['start_date'], '%Y-%m-%d').date()
        end_date = datetime.strptime(request.form['end_date'], '%Y-%m-%d').date()
        is_active = 'is_active' in request.form
        
        # Validate dates
        if start_date >= end_date:
            return jsonify({'success': False, 'message': 'Start date must be before end date'}), 400
        
        # Deactivate other sessions if this one is being activated
        if is_active and not session.is_active:
            AcademicSession.query.filter(AcademicSession.id != session_id).update({'is_active': False})
        
        # Update session
        session.name = name
        session.start_date = start_date
        session.end_date = end_date
        session.is_active = is_active
        
        # Log action
        audit_log = AuditLog(
            user_id=current_user.id,
            action='UPDATE_ACADEMIC_SESSION',
            table_name='academic_sessions',
            record_id=session.id,
            old_values={'name': session.name, 'is_active': session.is_active},
            new_values={'name': name, 'is_active': is_active},
            ip_address=request.remote_addr
        )
        db.session.add(audit_log)
        
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Academic session updated successfully'})
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400


@admin_bp.route('/academic-sessions/activate', methods=['POST'])
@login_required
@admin_required
def activate_academic_session():
    """Activate an academic session"""
    try:
        data = request.get_json()
        session_id = data.get('session_id')
        
        if not session_id:
            return jsonify({'success': False, 'message': 'Session ID is required'}), 400
        
        # Deactivate all other sessions
        AcademicSession.query.update({'is_active': False})
        
        # Activate the selected session
        session = AcademicSession.query.get_or_404(session_id)
        session.is_active = True
        
        # Log action
        audit_log = AuditLog(
            user_id=current_user.id,
            action='ACTIVATE_ACADEMIC_SESSION',
            table_name='academic_sessions',
            record_id=session.id,
            new_values={'name': session.name, 'is_active': True},
            ip_address=request.remote_addr
        )
        db.session.add(audit_log)
        
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Academic session activated successfully'})
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400


@admin_bp.route('/academic-sessions/delete/<session_id>', methods=['DELETE'])
@login_required
@admin_required
def delete_academic_session(session_id):
    """Delete an academic session"""
    try:
        session = AcademicSession.query.get_or_404(session_id)
        
        # Check if session has associated data
        if session.terms.count() > 0:
            return jsonify({
                'success': False, 
                'message': 'Cannot delete session with associated academic terms'
            }), 400
        
        if session.classrooms.count() > 0:
            return jsonify({
                'success': False, 
                'message': 'Cannot delete session with associated classrooms'
            }), 400
        
        if session.promotions.count() > 0:
            return jsonify({
                'success': False, 
                'message': 'Cannot delete session with associated student promotions'
            }), 400
        
        # Log before deletion
        audit_log = AuditLog(
            user_id=current_user.id,
            action='DELETE_ACADEMIC_SESSION',
            table_name='academic_sessions',
            record_id=session.id,
            old_values={'name': session.name, 'is_active': session.is_active},
            ip_address=request.remote_addr
        )
        db.session.add(audit_log)
        
        # Delete session
        db.session.delete(session)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Academic session deleted successfully'})
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400
    
@admin_bp.route('/academic-terms')
@login_required
@admin_required
def manage_academic_terms():
    """Manage academic terms"""
    # Get session filter if provided
    session_id = request.args.get('session_id')
    
    # Get all sessions for dropdown
    sessions = AcademicSession.query.order_by(AcademicSession.start_date.desc()).all()
    
    # Filter terms if session_id is provided
    if session_id:
        terms = AcademicTerm.query.filter_by(session_id=session_id).order_by(AcademicTerm.term_number).all()
        selected_session = AcademicSession.query.get(session_id)
    else:
        terms = AcademicTerm.query.order_by(AcademicTerm.session_id, AcademicTerm.term_number).all()
        selected_session = None
    
    # Calculate statistics
    active_terms = AcademicTerm.query.filter_by(is_active=True).count()
    total_sessions = AcademicSession.query.count()
    
    # Count upcoming terms (terms starting in the future)
    today = datetime.now(timezone.utc).date()
    upcoming_terms = AcademicTerm.query.filter(AcademicTerm.start_date > today).count()
    
    return render_template('admin/academic_terms.html', 
                         terms=terms,
                         sessions=sessions,
                         selected_session=selected_session,
                         active_terms=active_terms,
                         total_sessions=total_sessions,
                         upcoming_terms=upcoming_terms)

@admin_bp.route('/academic-terms/add', methods=['POST'])
@login_required
@admin_required
def add_academic_term():
    """Add new academic term"""
    try:
        session_id = request.form['session_id']
        name = request.form['name']
        term_number = int(request.form['term_number'])
        start_date = datetime.strptime(request.form['start_date'], '%Y-%m-%d').date()
        end_date = datetime.strptime(request.form['end_date'], '%Y-%m-%d').date()
        is_active = 'is_active' in request.form
        
        # Validate dates
        if start_date >= end_date:
            return jsonify({'success': False, 'message': 'Start date must be before end date'}), 400
        
        # Check for duplicate term number in same session
        existing = AcademicTerm.query.filter_by(
            session_id=session_id,
            term_number=term_number
        ).first()
        if existing:
            return jsonify({'success': False, 'message': 'Term number already exists in this session'}), 400
        
        term = AcademicTerm(
            session_id=session_id,
            name=name,
            term_number=term_number,
            start_date=start_date,
            end_date=end_date,
            is_active=is_active,
            ca_start_date=datetime.strptime(request.form['ca_start_date'], '%Y-%m-%d').date() if request.form.get('ca_start_date') else None,
            ca_end_date=datetime.strptime(request.form['ca_end_date'], '%Y-%m-%d').date() if request.form.get('ca_end_date') else None,
            exam_start_date=datetime.strptime(request.form['exam_start_date'], '%Y-%m-%d').date() if request.form.get('exam_start_date') else None,
            exam_end_date=datetime.strptime(request.form['exam_end_date'], '%Y-%m-%d').date() if request.form.get('exam_end_date') else None
        )
        db.session.add(term)
        db.session.commit()
        
        # Log action
        audit_log = AuditLog(
            user_id=current_user.id,
            action='CREATE_ACADEMIC_TERM',
            table_name='academic_terms',
            record_id=term.id,
            new_values={'name': name, 'term_number': term_number, 'session_id': session_id},
            ip_address=request.remote_addr
        )
        db.session.add(audit_log)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Academic term added successfully'})
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400

@admin_bp.route('/academic-terms/<term_id>/data')
@login_required
@admin_required
def get_academic_term_data(term_id):
    """Get academic term data for editing"""
    try:
        term = AcademicTerm.query.get_or_404(term_id)
        
        # Format dates for JSON serialization
        term_data = {
            'id': term.id,
            'session_id': term.session_id,
            'name': term.name,
            'term_number': term.term_number,
            'start_date': term.start_date.strftime('%Y-%m-%d') if term.start_date else None,
            'end_date': term.end_date.strftime('%Y-%m-%d') if term.end_date else None,
            'ca_start_date': term.ca_start_date.strftime('%Y-%m-%d') if term.ca_start_date else None,
            'ca_end_date': term.ca_end_date.strftime('%Y-%m-%d') if term.ca_end_date else None,
            'exam_start_date': term.exam_start_date.strftime('%Y-%m-%d') if term.exam_start_date else None,
            'exam_end_date': term.exam_end_date.strftime('%Y-%m-%d') if term.exam_end_date else None,
            'is_active': term.is_active
        }
        
        return jsonify({
            'success': True,
            'term': term_data
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400


@admin_bp.route('/academic-terms/update', methods=['POST'])
@login_required
@admin_required
def update_academic_term():
    """Update existing academic term"""
    try:
        term_id = request.form.get('term_id')
        if not term_id:
            return jsonify({'success': False, 'message': 'Term ID is required'}), 400
        
        term = AcademicTerm.query.get_or_404(term_id)
        
        # Get form data
        session_id = request.form['session_id']
        name = request.form['name']
        term_number = int(request.form['term_number'])
        start_date = datetime.strptime(request.form['start_date'], '%Y-%m-%d').date()
        end_date = datetime.strptime(request.form['end_date'], '%Y-%m-%d').date()
        is_active = 'is_active' in request.form
        
        # Validate dates
        if start_date >= end_date:
            return jsonify({'success': False, 'message': 'Start date must be before end date'}), 400
        
        # Check if term number is already used in this session (excluding current term)
        existing = AcademicTerm.query.filter(
            AcademicTerm.session_id == session_id,
            AcademicTerm.term_number == term_number,
            AcademicTerm.id != term_id
        ).first()
        
        if existing:
            return jsonify({
                'success': False, 
                'message': f'Term number {term_number} already exists in this session'
            }), 400
        
        # Store old values for audit log
        old_values = {
            'session_id': term.session_id,
            'name': term.name,
            'term_number': term.term_number,
            'is_active': term.is_active
        }
        
        # Update term
        term.session_id = session_id
        term.name = name
        term.term_number = term_number
        term.start_date = start_date
        term.end_date = end_date
        term.is_active = is_active
        
        # Update optional dates
        term.ca_start_date = datetime.strptime(request.form['ca_start_date'], '%Y-%m-%d').date() if request.form.get('ca_start_date') else None
        term.ca_end_date = datetime.strptime(request.form['ca_end_date'], '%Y-%m-%d').date() if request.form.get('ca_end_date') else None
        term.exam_start_date = datetime.strptime(request.form['exam_start_date'], '%Y-%m-%d').date() if request.form.get('exam_start_date') else None
        term.exam_end_date = datetime.strptime(request.form['exam_end_date'], '%Y-%m-%d').date() if request.form.get('exam_end_date') else None
        
        # Deactivate other terms in the same session if this term is being activated
        if is_active and not old_values['is_active']:
            AcademicTerm.query.filter(
                AcademicTerm.session_id == session_id,
                AcademicTerm.id != term_id
            ).update({'is_active': False})
        
        # Log action
        audit_log = AuditLog(
            user_id=current_user.id,
            action='UPDATE_ACADEMIC_TERM',
            table_name='academic_terms',
            record_id=term.id,
            old_values=old_values,
            new_values={
                'session_id': session_id,
                'name': name,
                'term_number': term_number,
                'is_active': is_active
            },
            ip_address=request.remote_addr
        )
        db.session.add(audit_log)
        
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': 'Academic term updated successfully',
            'term_id': term.id
        })
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400


@admin_bp.route('/academic-terms/activate', methods=['POST'])
@login_required
@admin_required
def activate_academic_term():
    """Activate an academic term"""
    try:
        data = request.get_json()
        term_id = data.get('term_id')
        
        if not term_id:
            return jsonify({'success': False, 'message': 'Term ID is required'}), 400
        
        term = AcademicTerm.query.get_or_404(term_id)
        
        # Store old status for audit log
        old_is_active = term.is_active
        
        # Deactivate all other terms in the same session
        AcademicTerm.query.filter(
            AcademicTerm.session_id == term.session_id,
            AcademicTerm.id != term_id
        ).update({'is_active': False})
        
        # Activate the selected term
        term.is_active = True
        
        # Log action
        audit_log = AuditLog(
            user_id=current_user.id,
            action='ACTIVATE_ACADEMIC_TERM',
            table_name='academic_terms',
            record_id=term.id,
            old_values={'is_active': old_is_active},
            new_values={
                'name': term.name,
                'term_number': term.term_number,
                'is_active': True
            },
            ip_address=request.remote_addr
        )
        db.session.add(audit_log)
        
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': f'Academic term "{term.name}" activated successfully. All other terms in "{term.session.name}" have been deactivated.'
        })
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400


@admin_bp.route('/academic-terms/delete/<term_id>', methods=['DELETE'])
@login_required
@admin_required
def delete_academic_term(term_id):
    """Delete an academic term"""
    try:
        term = AcademicTerm.query.get_or_404(term_id)
        
        # Check if term has associated data
        if term.subject_assignments.count() > 0:
            return jsonify({
                'success': False, 
                'message': 'Cannot delete term with subject assignments. Remove assignments first.'
            }), 400
        
        if term.exams.count() > 0:
            return jsonify({
                'success': False, 
                'message': 'Cannot delete term with scheduled exams. Remove exams first.'
            }), 400
        
        # Store term info for audit log before deletion
        term_info = {
            'name': term.name,
            'term_number': term.term_number,
            'session_id': term.session_id,
            'is_active': term.is_active
        }
        
        # Log before deletion
        audit_log = AuditLog(
            user_id=current_user.id,
            action='DELETE_ACADEMIC_TERM',
            table_name='academic_terms',
            record_id=term.id,
            old_values=term_info,
            ip_address=request.remote_addr
        )
        db.session.add(audit_log)
        
        # Delete term
        db.session.delete(term)
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': f'Academic term "{term_info["name"]}" deleted successfully'
        })
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400


@admin_bp.route('/academic-terms/validate-term-number', methods=['POST'])
@login_required
@admin_required
def validate_term_number():
    """Validate term number for a session"""
    try:
        data = request.get_json()
        session_id = data.get('session_id')
        term_number = data.get('term_number')
        exclude_term_id = data.get('exclude_term_id')
        
        if not session_id or not term_number:
            return jsonify({'success': False, 'message': 'Session ID and term number are required'}), 400
        
        query = AcademicTerm.query.filter_by(
            session_id=session_id,
            term_number=term_number
        )
        
        if exclude_term_id:
            query = query.filter(AcademicTerm.id != exclude_term_id)
        
        existing = query.first()
        
        return jsonify({
            'success': True,
            'is_valid': existing is None,
            'message': 'Term number already exists in this session' if existing else 'Term number is available'
        })
    
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400


@admin_bp.route('/academic-terms/validate-dates', methods=['POST'])
@login_required
@admin_required
def validate_term_dates():
    """Validate term dates against session dates"""
    try:
        data = request.get_json()
        session_id = data.get('session_id')
        start_date_str = data.get('start_date')
        end_date_str = data.get('end_date')
        
        if not session_id or not start_date_str or not end_date_str:
            return jsonify({'success': False, 'message': 'Session ID and dates are required'}), 400
        
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        
        # Get session dates
        session = AcademicSession.query.get_or_404(session_id)
        
        errors = []
        
        # Check if start date is before end date
        if start_date >= end_date:
            errors.append('Term start date must be before end date')
        
        # Check if term dates are within session dates
        if start_date < session.start_date:
            errors.append(f'Term start date must be on or after session start date ({session.start_date.strftime("%d %b %Y")})')
        
        if end_date > session.end_date:
            errors.append(f'Term end date must be on or before session end date ({session.end_date.strftime("%d %b %Y")})')
        
        return jsonify({
            'success': True,
            'is_valid': len(errors) == 0,
            'errors': errors,
            'session_dates': {
                'start_date': session.start_date.strftime('%Y-%m-%d'),
                'end_date': session.end_date.strftime('%Y-%m-%d')
            }
        })
    
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400


@admin_bp.route('/academic-terms/bulk-deactivate', methods=['POST'])
@login_required
@admin_required
def bulk_deactivate_terms():
    """Deactivate all terms in a session"""
    try:
        data = request.get_json()
        session_id = data.get('session_id')
        
        if not session_id:
            return jsonify({'success': False, 'message': 'Session ID is required'}), 400
        
        # Deactivate all terms in the session
        updated_count = AcademicTerm.query.filter_by(session_id=session_id).update(
            {'is_active': False}
        )
        
        # Log action
        audit_log = AuditLog(
            user_id=current_user.id,
            action='BULK_DEACTIVATE_TERMS',
            table_name='academic_terms',
            details={'session_id': session_id, 'count': updated_count},
            ip_address=request.remote_addr
        )
        db.session.add(audit_log)
        
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': f'{updated_count} terms deactivated successfully'
        })
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400


@admin_bp.route('/academic-terms/current-active')
@login_required
@admin_required
def get_current_active_term():
    """Get the currently active academic term"""
    try:
        active_term = AcademicTerm.query.filter_by(is_active=True).first()
        
        if not active_term:
            return jsonify({
                'success': True,
                'has_active_term': False,
                'message': 'No active academic term found'
            })
        
        term_data = {
            'id': active_term.id,
            'name': active_term.name,
            'term_number': active_term.term_number,
            'start_date': active_term.start_date.strftime('%Y-%m-%d'),
            'end_date': active_term.end_date.strftime('%Y-%m-%d'),
            'session': {
                'id': active_term.session.id,
                'name': active_term.session.name
            }
        }
        
        return jsonify({
            'success': True,
            'has_active_term': True,
            'term': term_data
        })
    
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400
    



# Student Management
@admin_bp.route('/students')
@login_required
@admin_required
def manage_students():
    """Manage students with filters"""
    # Get filter parameters
    class_id = request.args.get('class_id')
    status = request.args.get('status')
    search = request.args.get('search')
    
    # Base query
    query = Student.query
    
    # Apply filters
    if class_id and class_id != 'all':
        query = query.filter_by(current_class_id=class_id)
    
    if status and status != 'all':
        query = query.filter_by(academic_status=status)
    
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            (Student.first_name.ilike(search_term)) |
            (Student.last_name.ilike(search_term)) |
            (Student.admission_number.ilike(search_term)) |
            (Student.parent_name.ilike(search_term))
        )
    
    # Order by admission number
    query = query.order_by(Student.admission_number)
    
    # Get all students for the page
    students = query.all()
    
    # Get classes for dropdown
    classes = ClassRoom.query.all()
    
    # Get active session
    active_session = AcademicSession.query.filter_by(is_active=True).first()
    
    # Calculate statistics
    total_students = Student.query.count()
    active_students = Student.query.filter_by(academic_status='active', is_active=True).count()
    
    # Get today's date for form
    today = datetime.now(timezone.utc).date()
    
    return render_template('admin/students.html', 
                         students=students, 
                         classes=classes,
                         active_session=active_session,
                         total_students=total_students,
                         active_students=active_students,
                         today=today.strftime('%Y-%m-%d'))

@admin_bp.route('/students/<student_id>/data')
@login_required
@admin_required
def get_student_data(student_id):
    """Get student data for editing"""
    try:
        student = Student.query.get_or_404(student_id)
        
        # Format dates for JSON
        student_data = {
            'id': student.id,
            'admission_number': student.admission_number,
            'first_name': student.first_name,
            'last_name': student.last_name,
            'middle_name': student.middle_name,
            'dob': student.date_of_birth.strftime('%Y-%m-%d') if student.date_of_birth else '',
            'gender': student.gender,
            'email': student.user.email if student.user else '',  # Get email from User model
            'address': student.address,
            'parent_name': student.parent_name,
            'parent_phone': student.parent_phone,
            'parent_email': student.parent_email,
            'current_class_id': student.current_class_id,
            'enrollment_date': student.enrollment_date.strftime('%Y-%m-%d') if student.enrollment_date else '',
            'academic_status': student.academic_status,
            'is_active': student.is_active
        }
        
        return jsonify({
            'success': True,
            'student': student_data
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400
    
@admin_bp.route('/students/add', methods=['POST'])
@login_required
@admin_required
def add_student():
    """Add new student"""
    try:
        # Get active academic session
        active_session = AcademicSession.query.filter_by(is_active=True).first()
        if not active_session:
            return jsonify({'success': False, 'message': 'No active academic session'}), 400
        
        # Parse date fields
        dob = None
        if request.form.get('dob'):
            dob = datetime.strptime(request.form['dob'], '%Y-%m-%d').date()
        
        enrollment_date = None
        if request.form.get('enrollment_date'):
            enrollment_date = datetime.strptime(request.form['enrollment_date'], '%Y-%m-%d').date()
        else:
            enrollment_date = datetime.now(timezone.utc).date()
        
        # Check if admission number already exists
        admission_number = request.form['admission_number']
        existing_student = Student.query.filter_by(admission_number=admission_number).first()
        if existing_student:
            return jsonify({'success': False, 'message': 'Admission number already exists'}), 400
        
        # Get email from form or generate default
        email = request.form.get('email', f"{admission_number}@school.edu")
        
        # Create user account first
        user = User(
            username=admission_number,
            email=email,
            role='student'
        )
        user.set_password(admission_number)  # Default password is admission number
        user.password_changed_at = datetime.now(timezone.utc)
        db.session.add(user)
        db.session.flush()  # Get user ID
        
        # Create student profile (without email field)
        student = Student(
            user_id=user.id,
            admission_number=admission_number,
            first_name=request.form['first_name'],
            last_name=request.form['last_name'],
            middle_name=request.form.get('middle_name'),
            date_of_birth=dob,
            gender=request.form['gender'],
            address=request.form.get('address'),
            parent_name=request.form.get('parent_name'),
            parent_phone=request.form.get('parent_phone'),
            parent_email=request.form.get('parent_email'),
            current_class_id=request.form.get('class_id'),
            enrollment_date=enrollment_date,
            academic_status=request.form.get('academic_status', 'active'),
            is_active=True
        )
        
        db.session.add(student)
        
        # Log action
        audit_log = AuditLog(
            user_id=current_user.id,
            action='CREATE_STUDENT',
            table_name='students',
            record_id=student.id,
            new_values={
                'admission_number': student.admission_number, 
                'name': f"{student.first_name} {student.last_name}"
            },
            ip_address=request.remote_addr
        )
        db.session.add(audit_log)
        
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Student added successfully'})
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400
    
@admin_bp.route('/students/update', methods=['POST'])
@login_required
@admin_required
def update_student():
    """Update existing student"""
    try:
        # Check if request is JSON
        if request.is_json:
            data = request.get_json()
            student_id = data.get('student_id')
        else:
            student_id = request.form.get('student_id')
            data = request.form
        
        if not student_id:
            return jsonify({'success': False, 'message': 'Student ID is required'}), 400
        
        student = Student.query.get_or_404(student_id)
        
        # Store old values for audit log
        old_values = {
            'first_name': student.first_name,
            'last_name': student.last_name,
            'admission_number': student.admission_number,
            'current_class_id': student.current_class_id
        }
        
        # Parse date fields
        dob = None
        if data.get('dob'):
            dob = datetime.strptime(data['dob'], '%Y-%m-%d').date()
        
        enrollment_date = None
        if data.get('enrollment_date'):
            enrollment_date = datetime.strptime(data['enrollment_date'], '%Y-%m-%d').date()
        
        # Check if admission number is being changed and if it already exists
        new_admission_number = data['admission_number']
        if new_admission_number != student.admission_number:
            existing = Student.query.filter_by(admission_number=new_admission_number).first()
            if existing:
                return jsonify({'success': False, 'message': 'Admission number already exists'}), 400
        
        # Update student (without email field)
        student.admission_number = new_admission_number
        student.first_name = data['first_name']
        student.last_name = data['last_name']
        student.middle_name = data.get('middle_name')
        student.date_of_birth = dob
        student.gender = data['gender']
        student.address = data.get('address')
        student.parent_name = data.get('parent_name')
        student.parent_phone = data.get('parent_phone')
        student.parent_email = data.get('parent_email')
        student.current_class_id = data.get('class_id')
        student.enrollment_date = enrollment_date if enrollment_date else student.enrollment_date
        student.academic_status = data.get('academic_status', 'active')
        
        # Update user account if exists (email is in User model)
        if student.user:
            student.user.username = new_admission_number
            if data.get('email'):
                student.user.email = data['email']
        
        # Log action
        audit_log = AuditLog(
            user_id=current_user.id,
            action='UPDATE_STUDENT',
            table_name='students',
            record_id=student.id,
            old_values=old_values,
            new_values={
                'first_name': student.first_name,
                'last_name': student.last_name,
                'admission_number': student.admission_number,
                'current_class_id': student.current_class_id
            },
            ip_address=request.remote_addr
        )
        db.session.add(audit_log)
        
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Student updated successfully'})
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400
    
@admin_bp.route('/students/delete/<student_id>', methods=['DELETE'])
@login_required
@admin_required
def delete_student(student_id):
    """Delete a student"""
    try:
        student = Student.query.get_or_404(student_id)
        
        # Check if student has associated data that would prevent deletion
        if student.exam_results.count() > 0:
            return jsonify({
                'success': False, 
                'message': 'Cannot delete student with exam results. Archive the student instead.'
            }), 400
        
        if student.attendance_records.count() > 0:
            return jsonify({
                'success': False, 
                'message': 'Cannot delete student with attendance records. Archive the student instead.'
            }), 400
        
        # Store student info for audit log before deletion
        student_info = {
            'name': f"{student.first_name} {student.last_name}",
            'admission_number': student.admission_number,
            'current_class_id': student.current_class_id
        }
        
        # Log before deletion
        audit_log = AuditLog(
            user_id=current_user.id,
            action='DELETE_STUDENT',
            table_name='students',
            record_id=student.id,
            old_values=student_info,
            ip_address=request.remote_addr
        )
        db.session.add(audit_log)
        
        # Delete associated user if exists
        if student.user:
            # Delete user's audit logs first to avoid foreign key constraint
            AuditLog.query.filter_by(user_id=student.user.id).delete()
            db.session.delete(student.user)
        
        # Delete student
        db.session.delete(student)
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': f'Student "{student_info["name"]}" deleted successfully'
        })
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400

@admin_bp.route('/students/validate-admission-number', methods=['POST'])
@login_required
@admin_required
def validate_admission_number():
    """Validate admission number uniqueness"""
    try:
        data = request.get_json()
        admission_number = data.get('admission_number')
        exclude_student_id = data.get('exclude_student_id')
        
        if not admission_number:
            return jsonify({'success': False, 'message': 'Admission number is required'}), 400
        
        query = Student.query.filter_by(admission_number=admission_number)
        
        if exclude_student_id:
            query = query.filter(Student.id != exclude_student_id)
        
        existing = query.first()
        
        return jsonify({
            'success': True,
            'exists': existing is not None,
            'message': 'Admission number already exists' if existing else 'Admission number is available'
        })
    
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400

@admin_bp.route('/students/<student_id>/profile')
@login_required
@admin_required
def view_student_profile(student_id):
    """View student profile page"""
    try:
        student = Student.query.get_or_404(student_id)
        
        # Get all classes for the edit modal
        classes = ClassRoom.query.all()
        
        # Get student's exam results
        exam_results = ExamResult.query.filter_by(student_id=student_id).all()

        current_term = AcademicTerm.query.filter_by(is_active=True).first()
        
        # Get REAL student's attendance summary
        if student.current_class_id:
            attendance_records = Attendance.query.filter_by(
                student_id=student_id,
                classroom_id=student.current_class_id
            ).all()
            
            total_days = len(attendance_records)
            present_count = len([r for r in attendance_records if r.status in ['present', 'late']])
            absent_count = len([r for r in attendance_records if r.status == 'absent'])
            late_count = len([r for r in attendance_records if r.status == 'late'])
            
            attendance_rate = round((present_count / total_days * 100), 1) if total_days > 0 else 0
        else:
            attendance_records = []
            total_days = 0
            present_count = 0
            absent_count = 0
            late_count = 0
            attendance_rate = 0
        
        attendance_summary = {
            'total_days': total_days,
            'present': present_count,
            'absent': absent_count,
            'late': late_count,
            'attendance_rate': attendance_rate
        }
        
        # Get student's assessments (updated for new JSON format)
        student_assessments = StudentAssessment.query.filter_by(student_id=student_id).all()
        
        # Process assessments to include assessment details
        assessments_data = []
        for sa in student_assessments:
            # Get subject, class, and term info
            subject = Subject.query.get(sa.subject_id)
            classroom = ClassRoom.query.get(sa.class_id)
            term = AcademicTerm.query.get(sa.term_id)
            
            # Get individual assessment scores
            assessment_details = []
            if sa.assessment_scores:
                for assessment_id, score in sa.assessment_scores.items():
                    assessment = Assessment.query.get(assessment_id)
                    if assessment:
                        assessment_details.append({
                            'assessment': assessment,
                            'score': score
                        })
            
            assessments_data.append({
                'student_assessment': sa,
                'subject': subject,
                'classroom': classroom,
                'term': term,
                'assessment_details': assessment_details,
                'total_score': sa.total_score,
                'average_score': sa.average_score
            })
        
        # Get student's parent information
        parent_links = StudentParent.query.filter_by(student_id=student_id).all()
        parents = [link.parent for link in parent_links]
        
        # Calculate today's date for age calculation
        today = datetime.now(timezone.utc).date()
        
        # Get domain evaluations
        domain_evaluations = DomainEvaluation.query.filter_by(student_id=student_id).all()
        
        # Get teacher comments
        teacher_comments = TeacherComment.query.filter_by(student_id=student_id).all()
        
        # Get form teacher comments
        form_teacher_comments = FormTeacherComment.query.filter_by(student_id=student_id).all()
        
        # Get principal remarks
        principal_remarks = PrincipalRemark.query.filter_by(student_id=student_id).all()
        
        return render_template('admin/student_profile.html', 
                             student=student,
                             exam_results=exam_results,
                             attendance_summary=attendance_summary,
                             assessments=assessments_data,  # Updated to use assessments_data
                             term=current_term,
                             parents=parents,
                             classes=classes,
                             today=today,
                             domain_evaluations=domain_evaluations,
                             teacher_comments=teacher_comments,
                             form_teacher_comments=form_teacher_comments,
                             principal_remarks=principal_remarks)
    
    except Exception as e:
        flash(f'Error loading student profile: {str(e)}', 'danger')
        return redirect(url_for('admin.manage_students'))
            
@admin_bp.route('/students/<student_id>/toggle-active', methods=['POST'])
@login_required
@admin_required
def toggle_student_active(student_id):
    """Toggle student active status"""
    try:
        student = Student.query.get_or_404(student_id)
        student.is_active = not student.is_active
        
        # Also update user account if exists
        if student.user:
            student.user.is_active = student.is_active
        
        # Log action
        audit_log = AuditLog(
            user_id=current_user.id,
            action='TOGGLE_STUDENT_ACTIVE',
            table_name='students',
            record_id=student_id,
            new_values={'is_active': student.is_active},
            ip_address=request.remote_addr
        )
        db.session.add(audit_log)
        
        db.session.commit()
        
        status = 'activated' if student.is_active else 'deactivated'
        return jsonify({
            'success': True, 
            'message': f'Student {status} successfully',
            'is_active': student.is_active
        })
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400

@admin_bp.route('/students/<student_id>/reset-password', methods=['POST'])
@login_required
@admin_required
def reset_student_password(student_id):
    """Reset student password"""
    try:
        student = Student.query.get_or_404(student_id)
        
        if not student.user:
            return jsonify({'success': False, 'message': 'Student does not have a user account'}), 400
        
        # Reset password to admission number
        student.user.set_password(student.admission_number)
        student.user.password_changed_at = datetime.now(timezone.utc)
        
        # Log action
        audit_log = AuditLog(
            user_id=current_user.id,
            action='RESET_STUDENT_PASSWORD',
            table_name='users',
            record_id=student.user.id,
            new_values={'student_id': student.id},
            ip_address=request.remote_addr
        )
        db.session.add(audit_log)
        
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': f'Password reset successfully for {student.first_name} {student.last_name}. New password is their admission number.'
        })
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400

@admin_bp.route('/students/bulk-actions', methods=['POST'])
@login_required
@admin_required
def student_bulk_actions():
    """Handle bulk actions for students"""
    try:
        data = request.get_json()
        student_ids = data.get('student_ids', [])
        action = data.get('action')
        
        if not student_ids:
            return jsonify({'success': False, 'message': 'No students selected'}), 400
        
        if not action:
            return jsonify({'success': False, 'message': 'No action specified'}), 400
        
        if action == 'activate':
            count = Student.query.filter(Student.id.in_(student_ids)).update(
                {'is_active': True},
                synchronize_session=False
            )
            message = f'{count} students activated successfully'
            
        elif action == 'deactivate':
            count = Student.query.filter(Student.id.in_(student_ids)).update(
                {'is_active': False},
                synchronize_session=False
            )
            message = f'{count} students deactivated successfully'
            
        elif action == 'transfer':
            new_class_id = data.get('new_class_id')
            if not new_class_id:
                return jsonify({'success': False, 'message': 'New class ID is required for transfer'}), 400
            
            count = Student.query.filter(Student.id.in_(student_ids)).update(
                {'current_class_id': new_class_id},
                synchronize_session=False
            )
            message = f'{count} students transferred successfully'
            
        elif action == 'promote':
            from_class_id = data.get('from_class_id')
            to_class_id = data.get('to_class_id')
            
            if not from_class_id or not to_class_id:
                return jsonify({'success': False, 'message': 'Both from and to class IDs are required for promotion'}), 400
            
            # Update students' class
            count = Student.query.filter(
                Student.id.in_(student_ids),
                Student.current_class_id == from_class_id
            ).update(
                {'current_class_id': to_class_id},
                synchronize_session=False
            )
            
            # Create promotion records
            active_session = AcademicSession.query.filter_by(is_active=True).first()
            if active_session:
                for student_id in student_ids:
                    promotion = StudentPromotion(
                        student_id=student_id,
                        from_class_id=from_class_id,
                        to_class_id=to_class_id,
                        academic_session_id=active_session.id,
                        term=1,  # Default term
                        promotion_type='promotion',
                        promoted_by=current_user.id
                    )
                    db.session.add(promotion)
            
            message = f'{count} students promoted successfully'
            
        else:
            return jsonify({'success': False, 'message': 'Invalid action'}), 400
        
        # Log action
        audit_log = AuditLog(
            user_id=current_user.id,
            action=f'BULK_{action.upper()}_STUDENTS',
            details={'student_ids': student_ids, 'count': count, 'action': action},
            ip_address=request.remote_addr
        )
        db.session.add(audit_log)
        
        db.session.commit()
        
        return jsonify({'success': True, 'message': message, 'count': count})
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400


@admin_bp.route('/students/import', methods=['POST'])
@login_required
@admin_required
def import_students():
    """Import students data from CSV or Excel"""
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'message': 'No file uploaded'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'success': False, 'message': 'No file selected'}), 400
        
        # Validate file extension
        allowed_extensions = {'csv', 'xlsx', 'xls'}
        if '.' not in file.filename or file.filename.rsplit('.', 1)[1].lower() not in allowed_extensions:
            return jsonify({
                'success': False,
                'message': 'Invalid file type. Please upload CSV or Excel file.'
            }), 400
        
        # Get import options
        import_format = request.form.get('format', 'csv')
        update_existing = request.form.get('update_existing', 'false').lower() == 'true'
        skip_duplicates = request.form.get('skip_duplicates', 'true').lower() == 'true'
        
        # Read file based on format
        import_data = []
        try:
            if import_format == 'csv':
                stream = io.StringIO(file.stream.read().decode("UTF8"), newline=None)
                csv_reader = csv.DictReader(stream)
                import_data = list(csv_reader)
                
                # Validate CSV has required headers
                required_fields = ['admission_number']
                if csv_reader.fieldnames:
                    missing_fields = [f for f in required_fields if f not in csv_reader.fieldnames]
                    if missing_fields:
                        return jsonify({
                            'success': False,
                            'message': f'CSV missing required fields: {", ".join(missing_fields)}'
                        }), 400
                
            elif import_format == 'excel':
                try:
                    import pandas as pd
                    df = pd.read_excel(file)
                    # Convert NaN to empty string
                    df = df.fillna('')
                    import_data = df.to_dict('records')
                    
                    # Validate Excel has required columns
                    required_fields = ['admission_number']
                    if not df.empty:
                        missing_fields = [f for f in required_fields if f not in df.columns]
                        if missing_fields:
                            return jsonify({
                                'success': False,
                                'message': f'Excel missing required columns: {", ".join(missing_fields)}'
                            }), 400
                            
                except ImportError:
                    return jsonify({
                        'success': False,
                        'message': 'Excel import requires pandas and openpyxl. Please install with: pip install pandas openpyxl'
                    }), 400
                except Exception as e:
                    return jsonify({
                        'success': False,
                        'message': f'Error reading Excel file: {str(e)}'
                    }), 400
            
            else:
                return jsonify({'success': False, 'message': 'Unsupported import format'}), 400
                
        except Exception as e:
            return jsonify({
                'success': False,
                'message': f'Error reading file: {str(e)}'
            }), 400
        
        if not import_data:
            return jsonify({'success': False, 'message': 'File contains no data'}), 400
        
        # Process import
        results = {
            'total': len(import_data),
            'created': 0,
            'updated': 0,
            'skipped': 0,
            'errors': []
        }
        
        for index, row in enumerate(import_data):
            try:
                # Clean up row data - convert all values to strings and strip
                cleaned_row = {}
                for key, value in row.items():
                    if value is None:
                        cleaned_row[key] = ''
                    elif isinstance(value, (int, float)):
                        cleaned_row[key] = str(int(value)) if value.is_integer() else str(value)
                    else:
                        cleaned_row[key] = str(value).strip()
                
                # Check required fields
                if not cleaned_row.get('admission_number'):
                    results['errors'].append(f"Row {index + 2}: Missing admission_number")
                    results['skipped'] += 1
                    continue
                
                # Check if student exists
                student = Student.query.filter_by(admission_number=cleaned_row['admission_number']).first()
                
                if student:
                    if skip_duplicates:
                        results['skipped'] += 1
                        continue
                    
                    if update_existing:
                        # Update existing student
                        if cleaned_row.get('first_name'):
                            student.first_name = cleaned_row['first_name']
                        if cleaned_row.get('last_name'):
                            student.last_name = cleaned_row['last_name']
                        if cleaned_row.get('middle_name'):
                            student.middle_name = cleaned_row['middle_name']
                        if cleaned_row.get('gender'):
                            student.gender = cleaned_row['gender']
                        
                        if cleaned_row.get('date_of_birth'):
                            try:
                                student.date_of_birth = datetime.strptime(cleaned_row['date_of_birth'], '%Y-%m-%d').date()
                            except ValueError:
                                results['errors'].append(f"Row {index + 2}: Invalid date format for date_of_birth (use YYYY-MM-DD)")
                        
                        if cleaned_row.get('parent_name'):
                            student.parent_name = cleaned_row['parent_name']
                        if cleaned_row.get('parent_phone'):
                            student.parent_phone = cleaned_row['parent_phone']
                        if cleaned_row.get('parent_email'):
                            student.parent_email = cleaned_row['parent_email']
                        
                        # Handle classroom
                        if cleaned_row.get('class'):
                            classroom = ClassRoom.query.filter_by(name=cleaned_row['class']).first()
                            if classroom:
                                student.current_class_id = classroom.id
                            else:
                                results['errors'].append(f"Row {index + 2}: Class '{cleaned_row['class']}' not found")
                        
                        if cleaned_row.get('enrollment_date'):
                            try:
                                student.enrollment_date = datetime.strptime(cleaned_row['enrollment_date'], '%Y-%m-%d').date()
                            except ValueError:
                                results['errors'].append(f"Row {index + 2}: Invalid date format for enrollment_date (use YYYY-MM-DD)")
                        
                        if cleaned_row.get('academic_status'):
                            student.academic_status = cleaned_row['academic_status']
                        
                        if cleaned_row.get('is_active'):
                            student.is_active = str(cleaned_row['is_active']).lower() in ['yes', 'true', '1', 'active']
                        
                        results['updated'] += 1
                    else:
                        results['skipped'] += 1
                else:
                    # Create new student
                    student = Student()
                    student.admission_number = cleaned_row['admission_number']
                    student.first_name = cleaned_row.get('first_name', '')
                    student.last_name = cleaned_row.get('last_name', '')
                    student.middle_name = cleaned_row.get('middle_name', '')
                    student.gender = cleaned_row.get('gender', '')
                    
                    if cleaned_row.get('date_of_birth'):
                        try:
                            student.date_of_birth = datetime.strptime(cleaned_row['date_of_birth'], '%Y-%m-%d').date()
                        except ValueError:
                            results['errors'].append(f"Row {index + 2}: Invalid date format for date_of_birth (use YYYY-MM-DD)")
                    
                    student.parent_name = cleaned_row.get('parent_name', '')
                    student.parent_phone = cleaned_row.get('parent_phone', '')
                    student.parent_email = cleaned_row.get('parent_email', '')
                    
                    # Handle classroom
                    if cleaned_row.get('class'):
                        classroom = ClassRoom.query.filter_by(name=cleaned_row['class']).first()
                        if classroom:
                            student.current_class_id = classroom.id
                        else:
                            results['errors'].append(f"Row {index + 2}: Class '{cleaned_row['class']}' not found")
                    
                    if cleaned_row.get('enrollment_date'):
                        try:
                            student.enrollment_date = datetime.strptime(cleaned_row['enrollment_date'], '%Y-%m-%d').date()
                        except ValueError:
                            student.enrollment_date = datetime.now().date()
                            results['errors'].append(f"Row {index + 2}: Invalid enrollment_date format, using today's date")
                    else:
                        student.enrollment_date = datetime.now().date()
                    
                    student.academic_status = cleaned_row.get('academic_status', 'active')
                    student.is_active = str(cleaned_row.get('is_active', 'yes')).lower() in ['yes', 'true', '1', 'active']
                    
                    db.session.add(student)
                    db.session.flush()
                    
                    # Create user account if email is provided
                    if cleaned_row.get('email'):
                        # Check if user already exists
                        existing_user = User.query.filter_by(email=cleaned_row['email']).first()
                        if not existing_user:
                            user = User()
                            user.email = cleaned_row['email']
                            user.username = cleaned_row['admission_number']
                            user.role = 'student'
                            user.set_password(cleaned_row['admission_number'])  # Default password is admission number
                            db.session.add(user)
                            db.session.flush()
                            student.user_id = user.id
                        else:
                            results['errors'].append(f"Row {index + 2}: Email '{cleaned_row['email']}' already exists")
                    
                    results['created'] += 1
                
                # Commit after each successful record
                db.session.commit()
                
            except Exception as e:
                db.session.rollback()
                results['errors'].append(f"Row {index + 2} ({cleaned_row.get('admission_number', 'unknown')}): {str(e)}")
                results['skipped'] += 1
        
        # Log import action
        audit_log = AuditLog(
            user_id=current_user.id,
            action='IMPORT_STUDENTS',
            details={
                'total': results['total'],
                'created': results['created'],
                'updated': results['updated'],
                'skipped': results['skipped'],
                'errors': len(results['errors'])
            },
            ip_address=request.remote_addr
        )
        db.session.add(audit_log)
        db.session.commit()
        
        # Prepare success message
        if results['errors']:
            message = f"Import completed with errors: {results['created']} created, {results['updated']} updated, {results['skipped']} skipped. Check errors list."
        else:
            message = f"Import completed successfully: {results['created']} created, {results['updated']} updated, {results['skipped']} skipped"
        
        return jsonify({
            'success': True,
            'results': results,
            'message': message
        })
    
    except Exception as e:
        db.session.rollback()
        print(f"Error importing students: {str(e)}")  # For debugging
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'Error importing students: {str(e)}'
        }), 500

@admin_bp.route('/students/export', methods=['POST'])
@login_required
@admin_required
def export_students():
    """Export students data to CSV or Excel"""
    try:
        data = request.get_json()
        student_ids = data.get('student_ids', [])
        export_format = data.get('format', 'csv')
        
        # Build query
        query = Student.query
        
        if student_ids and len(student_ids) > 0:
            # Export selected students
            students = query.filter(Student.id.in_(student_ids)).all()
        else:
            # Export all students
            students = query.all()
        
        if not students:
            return jsonify({
                'success': False,
                'message': 'No students found to export'
            }), 404
        
        # Prepare data for export
        export_data = []
        for student in students:
            student_data = {
                'admission_number': student.admission_number,
                'first_name': student.first_name,
                'last_name': student.last_name,
                'middle_name': student.middle_name or '',
                'gender': student.gender or '',
                'date_of_birth': student.date_of_birth.strftime('%Y-%m-%d') if student.date_of_birth else '',
                'email': student.user.email if student.user else '',
                'parent_name': student.parent_name or '',
                'parent_phone': student.parent_phone or '',
                'parent_email': student.parent_email or '',
                'class': student.classroom.name if student.classroom else '',
                'enrollment_date': student.enrollment_date.strftime('%Y-%m-%d') if student.enrollment_date else '',
                'academic_status': student.academic_status,
                'is_active': 'Yes' if student.is_active else 'No'
            }
            export_data.append(student_data)
        
        # Log export action
        audit_log = AuditLog(
            user_id=current_user.id,
            action='EXPORT_STUDENTS',
            details={
                'count': len(export_data),
                'format': export_format,
                'selected': bool(student_ids)
            },
            ip_address=request.remote_addr
        )
        db.session.add(audit_log)
        db.session.commit()
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if export_format == 'csv':
            # Generate CSV
            output = io.StringIO()
            if export_data:
                # Use the keys from the first item as fieldnames
                fieldnames = export_data[0].keys()
                writer = csv.DictWriter(output, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(export_data)
            else:
                # Write headers even if no data
                fieldnames = ['admission_number', 'first_name', 'last_name', 'middle_name', 
                             'gender', 'date_of_birth', 'email', 'parent_name', 'parent_phone',
                             'parent_email', 'class', 'enrollment_date', 'academic_status', 'is_active']
                writer = csv.DictWriter(output, fieldnames=fieldnames)
                writer.writeheader()
            
            csv_data = output.getvalue()
            output.close()
            
            return jsonify({
                'success': True,
                'data': csv_data,
                'filename': f'students_export_{timestamp}.csv'
            })
        
        elif export_format == 'excel':
            try:
                import pandas as pd
                from io import BytesIO
                
                # Create DataFrame
                df = pd.DataFrame(export_data) if export_data else pd.DataFrame(columns=[
                    'admission_number', 'first_name', 'last_name', 'middle_name',
                    'gender', 'date_of_birth', 'email', 'parent_name', 'parent_phone',
                    'parent_email', 'class', 'enrollment_date', 'academic_status', 'is_active'
                ])
                
                # Create Excel file in memory
                excel_buffer = BytesIO()
                with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                    df.to_excel(writer, index=False, sheet_name='Students')
                
                # Get the value and convert to hex for JSON transmission
                excel_data = excel_buffer.getvalue()
                hex_data = excel_data.hex()
                excel_buffer.close()
                
                return jsonify({
                    'success': True,
                    'data': hex_data,
                    'filename': f'students_export_{timestamp}.xlsx'
                })
            except ImportError:
                return jsonify({
                    'success': False,
                    'message': 'Excel export requires pandas and openpyxl. Please install with: pip install pandas openpyxl'
                }), 400
        
        else:
            return jsonify({
                'success': False,
                'message': 'Unsupported export format'
            }), 400
    
    except Exception as e:
        db.session.rollback()
        print(f"Error exporting students: {str(e)}")  # For debugging
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'Error exporting students: {str(e)}'
        }), 500
    

@admin_bp.route('/students/template', methods=['GET'])
@login_required
@admin_required
def download_template():
    """Download import template"""
    try:
        import csv
        import io
        
        output = io.StringIO()
        fieldnames = [
            'admission_number', 'first_name', 'last_name', 'middle_name',
            'gender', 'date_of_birth', 'email', 'parent_name', 'parent_phone',
            'parent_email', 'class', 'enrollment_date', 'academic_status', 'is_active'
        ]
        
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        
        # Add sample row
        writer.writerow({
            'admission_number': 'STU001',
            'first_name': 'John',
            'last_name': 'Doe',
            'middle_name': '',
            'gender': 'Male',
            'date_of_birth': '2010-01-15',
            'email': 'john.doe@example.com',
            'parent_name': 'Jane Doe',
            'parent_phone': '+1234567890',
            'parent_email': 'jane.doe@example.com',
            'class': 'Grade 1A',
            'enrollment_date': '2024-01-10',
            'academic_status': 'active',
            'is_active': 'Yes'
        })
        
        return jsonify({
            'success': True,
            'data': output.getvalue(),
            'filename': 'students_import_template.csv'
        })
    
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400
    

@admin_bp.route('/students/statistics')
@login_required
@admin_required
def student_statistics():
    """Get student statistics"""
    try:
        # Count by class
        classes = ClassRoom.query.all()
        class_distribution = []
        for classroom in classes:
            student_count = classroom.class_students.count()
            if student_count > 0:
                class_distribution.append({
                    'name': classroom.name,
                    'count': student_count
                })
        
        # Count by gender
        male_count = Student.query.filter_by(gender='male').count()
        female_count = Student.query.filter_by(gender='female').count()
        unspecified_gender = Student.query.filter((Student.gender.is_(None)) | (Student.gender == '')).count()
        
        # Count by status
        active_count = Student.query.filter_by(academic_status='active', is_active=True).count()
        inactive_count = Student.query.filter_by(academic_status='inactive', is_active=False).count()
        graduated_count = Student.query.filter_by(academic_status='graduated').count()
        transferred_count = Student.query.filter_by(academic_status='transferred').count()
        
        # Enrollment by month (current year)
        current_year = datetime.now().year
        monthly_enrollment = []
        for month in range(1, 13):
            month_start = datetime(current_year, month, 1)
            if month == 12:
                month_end = datetime(current_year + 1, 1, 1)
            else:
                month_end = datetime(current_year, month + 1, 1)
            
            count = Student.query.filter(
                Student.enrollment_date >= month_start,
                Student.enrollment_date < month_end
            ).count()
            
            monthly_enrollment.append({
                'month': month_start.strftime('%b'),
                'count': count
            })
        
        statistics = {
            'class_distribution': class_distribution,
            'gender_distribution': {
                'male': male_count,
                'female': female_count,
                'unspecified': unspecified_gender
            },
            'status_distribution': {
                'active': active_count,
                'inactive': inactive_count,
                'graduated': graduated_count,
                'transferred': transferred_count
            },
            'monthly_enrollment': monthly_enrollment,
            'total_students': Student.query.count(),
            'active_students': active_count
        }
        
        return jsonify({
            'success': True,
            'statistics': statistics
        })
    
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400
    
@admin_bp.route('/students/promote', methods=['POST'])
@login_required
@admin_required
def promote_students():
    """Promote/demote students"""
    try:
        from models import StudentPromotion, AcademicSession
        
        student_ids = request.form.getlist('student_ids[]')
        from_class_id = request.form['from_class_id']
        to_class_id = request.form['to_class_id']
        promotion_type = request.form['promotion_type']
        reason = request.form.get('reason', '')
        term = int(request.form['term'])
        
        # Get active academic session
        active_session = AcademicSession.query.filter_by(is_active=True).first()
        if not active_session:
            return jsonify({'success': False, 'message': 'No active academic session'}), 400
        
        promoted_count = 0
        for student_id in student_ids:
            student = Student.query.get(student_id)
            if student:
                # Create promotion record
                promotion = StudentPromotion(
                    student_id=student_id,
                    from_class_id=from_class_id,
                    to_class_id=to_class_id,
                    academic_session_id=active_session.id,
                    term=term,
                    promotion_type=promotion_type,
                    reason=reason,
                    promoted_by=current_user.id
                )
                db.session.add(promotion)
                
                # Update student's current class
                student.current_class_id = to_class_id
                
                promoted_count += 1
        
        if promoted_count > 0:
            db.session.commit()
            flash(f'Successfully promoted {promoted_count} students!', 'success')
        else:
            flash('No students selected for promotion.', 'warning')
        
        return jsonify({'success': True, 'count': promoted_count})
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400

# Teacher Management
@admin_bp.route('/teachers')
@login_required
@admin_required
def manage_teachers():
    """Manage teachers"""
    teachers = Teacher.query.all()
    classes = ClassRoom.query.all()
    
    # Get subjects for filter dropdown
    subjects = Subject.query.filter_by(is_active=True).all()
    
    # Calculate statistics
    form_teachers = Teacher.query.filter(Teacher.form_class_assignment != None).count()
    
    # Count teachers with subject assignments
    teachers_with_subjects = 0
    total_subjects_assigned = 0
    
    for teacher in teachers:
        subject_count = len(teacher.subject_assignments)
        if subject_count > 0:
            teachers_with_subjects += 1
            total_subjects_assigned += subject_count
    
    # Calculate average subjects per teacher
    average_subjects_per_teacher = total_subjects_assigned / len(teachers) if teachers else 0
    
    return render_template('admin/teachers.html', 
                         teachers=teachers, 
                         classes=classes,
                         subjects=subjects,
                         form_teachers=form_teachers,
                         teachers_with_subjects=teachers_with_subjects,
                         average_subjects_per_teacher=average_subjects_per_teacher)

@admin_bp.route('/teachers/add', methods=['POST'])
@login_required
@admin_required
def add_teacher():
    """Add new teacher"""
    try:
        # Create user account first
        user = User(
            username=request.form['staff_id'],
            email=request.form['email'],
            role='teacher'
        )
        user.set_password(request.form['staff_id'])  # Default password is staff ID
        user.password_changed_at = datetime.now(timezone.utc)
        db.session.add(user)
        db.session.flush()
        
        # Create teacher profile with conditional fields
        teacher_data = {
            'user_id': user.id,
            'staff_id': request.form['staff_id'],
            'first_name': request.form['first_name'],
            'last_name': request.form['last_name']
        }
        
        # Add optional fields if they exist in the model
        if hasattr(Teacher, 'email'):
            teacher_data['email'] = request.form['email']
        
        if hasattr(Teacher, 'phone'):
            teacher_data['phone'] = request.form.get('phone')
        
        if hasattr(Teacher, 'form_class_id'):
            teacher_data['form_class_id'] = request.form.get('form_class_id') or None   # '' -> None
        
        if hasattr(Teacher, 'qualification'):
            teacher_data['qualification'] = request.form.get('qualification')
        
        if hasattr(Teacher, 'specialization'):
            teacher_data['specialization'] = request.form.get('specialization')
        
        if hasattr(Teacher, 'address'):
            teacher_data['address'] = request.form.get('address')
        
        teacher = Teacher(**teacher_data)
        
        db.session.add(teacher)
        
        # Log action
        audit_log = AuditLog(
            user_id=current_user.id,
            action='CREATE_TEACHER',
            table_name='teachers',
            record_id=teacher.id,
            new_values={
                'staff_id': teacher.staff_id, 
                'name': f"{teacher.first_name} {teacher.last_name}"
            },
            ip_address=request.remote_addr
        )
        db.session.add(audit_log)
        
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Teacher added successfully'})
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400
    
@admin_bp.route('/teachers/<teacher_id>/data')
@login_required
@admin_required
def get_teacher_data(teacher_id):
    """Get teacher data for editing"""
    try:
        teacher = Teacher.query.get_or_404(teacher_id)
        
        return jsonify({
            'success': True,
            'teacher': {
                'id': teacher.id,
                'first_name': teacher.first_name,
                'last_name': teacher.last_name,
                'staff_id': teacher.staff_id,
                'email': teacher.email,
                'phone': teacher.phone,
                'form_class_id': teacher.form_class_id,
                'qualification': teacher.qualification,
                'specialization': teacher.specialization,
                'address': teacher.address
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400


@admin_bp.route('/teachers/update', methods=['POST'])
@login_required
@admin_required
def update_teacher():
    """Update existing teacher"""
    try:
        # Check if request is JSON
        if request.is_json:
            data = request.get_json()
            teacher_id = data.get('teacher_id')
        else:
            teacher_id = request.form.get('teacher_id')
            data = request.form
        
        if not teacher_id:
            return jsonify({'success': False, 'message': 'Teacher ID is required'}), 400
        
        teacher = Teacher.query.get_or_404(teacher_id)
        
        # Store old values for audit log
        old_values = {
            'first_name': teacher.first_name,
            'last_name': teacher.last_name,
            'staff_id': teacher.staff_id,
            'email': teacher.email
        }
        
        # Update teacher
        teacher.first_name = data['first_name']
        teacher.last_name = data['last_name']
        teacher.staff_id = data['staff_id']
        teacher.email = data['email']
        teacher.phone = data.get('phone')
        teacher.form_class_id = data.get('form_class_id') or None
        teacher.qualification = data.get('qualification')
        teacher.specialization = data.get('specialization')
        teacher.address = data.get('address')
        
        # Update user email if user exists
        if teacher.user:
            teacher.user.email = data['email']
            teacher.user.username = data['staff_id']  # Update username too
        
        # Log action
        audit_log = AuditLog(
            user_id=current_user.id,
            action='UPDATE_TEACHER',
            table_name='teachers',
            record_id=teacher.id,
            old_values=old_values,
            new_values={
                'first_name': teacher.first_name,
                'last_name': teacher.last_name,
                'staff_id': teacher.staff_id,
                'email': teacher.email
            },
            ip_address=request.remote_addr
        )
        db.session.add(audit_log)
        
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Teacher updated successfully'})
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400

@admin_bp.route('/teachers/delete/<teacher_id>', methods=['DELETE'])
@login_required
@admin_required
def delete_teacher(teacher_id):
    """Delete a teacher"""
    try:
        teacher = Teacher.query.get_or_404(teacher_id)
        
        # Check if teacher has associated data
        if teacher.subject_assignments.count() > 0:
            return jsonify({
                'success': False, 
                'message': 'Cannot delete teacher with subject assignments. Remove assignments first.'
            }), 400
        
        if teacher.exams.count() > 0:
            return jsonify({
                'success': False, 
                'message': 'Cannot delete teacher with scheduled exams. Remove exams first.'
            }), 400
        
        # Store teacher info for audit log before deletion
        teacher_info = {
            'name': f"{teacher.first_name} {teacher.last_name}",
            'staff_id': teacher.staff_id,
            'email': teacher.email
        }
        
        # Log before deletion
        audit_log = AuditLog(
            user_id=current_user.id,
            action='DELETE_TEACHER',
            table_name='teachers',
            record_id=teacher.id,
            old_values=teacher_info,
            ip_address=request.remote_addr
        )
        db.session.add(audit_log)
        
        # Delete associated user if exists
        if teacher.user:
            # Delete user's audit logs first to avoid foreign key constraint
            AuditLog.query.filter_by(user_id=teacher.user.id).delete()
            db.session.delete(teacher.user)
        
        # Delete teacher
        db.session.delete(teacher)
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': f'Teacher "{teacher_info["name"]}" deleted successfully'
        })
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400


@admin_bp.route('/teachers/validate-staff-id', methods=['POST'])
@login_required
@admin_required
def validate_staff_id():
    """Validate staff ID uniqueness"""
    try:
        data = request.get_json()
        staff_id = data.get('staff_id')
        exclude_teacher_id = data.get('exclude_teacher_id')
        
        if not staff_id:
            return jsonify({'success': False, 'message': 'Staff ID is required'}), 400
        
        query = Teacher.query.filter_by(staff_id=staff_id)
        
        if exclude_teacher_id:
            query = query.filter(Teacher.id != exclude_teacher_id)
        
        existing = query.first()
        
        return jsonify({
            'success': True,
            'exists': existing is not None,
            'message': 'Staff ID already exists' if existing else 'Staff ID is available'
        })
    
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400


@admin_bp.route('/teachers/<teacher_id>/profile')
@login_required
@admin_required
def view_teacher(teacher_id):
    """View teacher profile"""
    try:
        teacher = Teacher.query.get_or_404(teacher_id)
        
        # Get teacher's subject assignments with details
        assignments = []
        for assignment in teacher.subject_assignments:
            assignments.append({
                'subject': assignment.subject.name,
                'subject_code': assignment.subject.code,
                'class': assignment.classroom.name,
                'term': assignment.academic_term.name,
                'status': 'Active' if assignment.is_active else 'Inactive'
            })
        
        # Get teacher's exams
        exams = Exam.query.filter_by(teacher_id=teacher_id).order_by(Exam.created_at.desc()).limit(10).all()
        
        # Get all classes for the form class dropdown
        classes = ClassRoom.query.all()
        
        return render_template('admin/teacher_profile.html', 
                             teacher=teacher,
                             assignments=assignments,
                             exams=exams,
                             classes=classes)  # Add this
    
    except Exception as e:
        flash(f'Error loading teacher profile: {str(e)}', 'danger')
        return redirect(url_for('admin.manage_teachers'))
    
@admin_bp.route('/teachers/<teacher_id>/reset-password', methods=['POST'])
@login_required
@admin_required
def reset_teacher_password(teacher_id):
    """Reset teacher password"""
    try:
        teacher = Teacher.query.get_or_404(teacher_id)
        
        if not teacher.user:
            return jsonify({'success': False, 'message': 'Teacher does not have a user account'}), 400
        
        # Reset password to staff ID
        teacher.user.set_password(teacher.staff_id)
        teacher.user.password_changed_at = datetime.now(timezone.utc)
        
        # Log action
        audit_log = AuditLog(
            user_id=current_user.id,
            action='RESET_TEACHER_PASSWORD',
            table_name='users',
            record_id=teacher.user.id,
            new_values={'teacher_id': teacher.id},
            ip_address=request.remote_addr
        )
        db.session.add(audit_log)
        
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': f'Password reset successfully for {teacher.first_name} {teacher.last_name}. New password is their staff ID.'
        })
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400
       
# Class Management
@admin_bp.route('/classes')
@login_required
@admin_required
def manage_classes():
    """Manage classes"""
    classes = ClassRoom.query.all()
    teachers = Teacher.query.all()
    sessions = AcademicSession.query.all()
    
    # Get active session
    active_session = AcademicSession.query.filter_by(is_active=True).first()
    
    # Calculate total students across all classes
    total_students = db.session.query(Student).count()
    
    return render_template('admin/classes.html', 
                         classes=classes, 
                         teachers=teachers, 
                         sessions=sessions,
                         active_session=active_session,
                         total_students=total_students)

@admin_bp.route('/classes/add', methods=['POST'])
@login_required
@admin_required
def add_class():
    """Add new class"""
    try:
        # Get form data
        name = request.form['name']
        level = request.form.get('level')
        section = request.form.get('section')
        max_students = int(request.form.get('max_students', 40))
        room_number = request.form.get('room_number')
        form_teacher_id = request.form.get('form_teacher_id')
        
        # Get active academic session
        active_session = AcademicSession.query.filter_by(is_active=True).first()
        if not active_session:
            return jsonify({'success': False, 'message': 'No active academic session'}), 400
        
        # Check if class name already exists in this session
        existing_class = ClassRoom.query.filter_by(
            academic_session_id=active_session.id,
            name=name
        ).first()
        if existing_class:
            return jsonify({'success': False, 'message': 'Class with this name already exists in this session'}), 400
        
        # Create new class
        classroom = ClassRoom(
            academic_session_id=active_session.id,
            name=name,
            level=level,
            section=section,
            max_students=max_students,
            room_number=room_number,
            form_teacher_id=form_teacher_id if form_teacher_id else None
        )
        
        db.session.add(classroom)
        db.session.flush()  # Get the ID without committing
        
        # If form teacher is assigned, update the teacher's form_class_id
        if form_teacher_id:
            teacher = Teacher.query.get(form_teacher_id)
            if teacher:
                # Check if teacher is already a form teacher for another class
                if teacher.form_class_id:
                    # Remove teacher from previous class
                    old_class = ClassRoom.query.get(teacher.form_class_id)
                    if old_class:
                        old_class.form_teacher_id = None
                
                # Update teacher's form_class_id
                teacher.form_class_id = classroom.id
                classroom.form_teacher_id = teacher.id
        
        db.session.commit()
        
        # Log action
        audit_log = AuditLog(
            user_id=current_user.id,
            action='CREATE_CLASS',
            table_name='classrooms',
            record_id=classroom.id,
            new_values={
                'name': name,
                'level': level,
                'academic_session_id': active_session.id,
                'form_teacher_id': form_teacher_id
            },
            ip_address=request.remote_addr
        )
        db.session.add(audit_log)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Class added successfully'})
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400
        
@admin_bp.route('/classes/<class_id>/data')
@login_required
@admin_required
def get_class_data(class_id):
    """Get class data for editing"""
    try:
        classroom = ClassRoom.query.get_or_404(class_id)
        
        return jsonify({
            'success': True,
            'class': {
                'id': classroom.id,
                'academic_session_id': classroom.academic_session_id,
                'name': classroom.name,
                'level': classroom.level or '',
                'section': classroom.section or '',
                'max_students': classroom.max_students or 40,
                'room_number': classroom.room_number or '',
                'form_teacher_id': classroom.form_teacher_id
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400


@admin_bp.route('/classes/update', methods=['POST'])
@login_required
@admin_required
def update_class():
    """Update existing class"""
    try:
        class_id = request.form.get('class_id')
        if not class_id:
            return jsonify({'success': False, 'message': 'Class ID is required'}), 400
        
        classroom = ClassRoom.query.get_or_404(class_id)
        
        # Get form data
        name = request.form['name']
        level = request.form.get('level')
        section = request.form.get('section')
        max_students = int(request.form.get('max_students', 40))
        room_number = request.form.get('room_number')
        form_teacher_id = request.form.get('form_teacher_id')
        
        # Store old values for audit log
        old_values = {
            'name': classroom.name,
            'level': classroom.level,
            'form_teacher_id': classroom.form_teacher_id
        }
        
        # Handle form teacher assignment changes
        old_form_teacher_id = classroom.form_teacher_id
        new_form_teacher_id = form_teacher_id if form_teacher_id else None
        
        # If form teacher is being changed
        if old_form_teacher_id != new_form_teacher_id:
            # Remove old form teacher assignment if exists
            if old_form_teacher_id:
                old_teacher = Teacher.query.get(old_form_teacher_id)
                if old_teacher:
                    old_teacher.form_class_id = None
            
            # Assign new form teacher if provided
            if new_form_teacher_id:
                new_teacher = Teacher.query.get(new_form_teacher_id)
                if new_teacher:
                    # Check if new teacher is already a form teacher for another class
                    if new_teacher.form_class_id and new_teacher.form_class_id != classroom.id:
                        # Remove teacher from previous class
                        previous_class = ClassRoom.query.get(new_teacher.form_class_id)
                        if previous_class:
                            previous_class.form_teacher_id = None
                    
                    # Update teacher's form_class_id
                    new_teacher.form_class_id = classroom.id
                    classroom.form_teacher_id = new_teacher.id
        
        # Update class
        classroom.name = name
        classroom.level = level if level else None
        classroom.section = section if section else None
        classroom.max_students = max_students
        classroom.room_number = room_number if room_number else None
        classroom.form_teacher_id = new_form_teacher_id
        
        # Log action
        audit_log = AuditLog(
            user_id=current_user.id,
            action='UPDATE_CLASS',
            table_name='classrooms',
            record_id=classroom.id,
            old_values=old_values,
            new_values={
                'name': name,
                'level': level,
                'form_teacher_id': new_form_teacher_id
            },
            ip_address=request.remote_addr
        )
        db.session.add(audit_log)
        
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Class updated successfully'})
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400
    
@admin_bp.route('/classes/<class_id>/remove-form-teacher', methods=['POST'])
@login_required
@admin_required
def remove_form_teacher(class_id):
    """Remove form teacher from class"""
    try:
        classroom = ClassRoom.query.get_or_404(class_id)
        
        if not classroom.form_teacher_id:
            return jsonify({'success': False, 'message': 'No form teacher assigned to this class'}), 400
        
        # Get the teacher
        teacher = Teacher.query.get(classroom.form_teacher_id)
        
        # Store for audit log
        old_teacher_id = classroom.form_teacher_id
        old_teacher_name = f"{teacher.first_name} {teacher.last_name}" if teacher else "Unknown"
        
        # Remove form teacher from class
        classroom.form_teacher_id = None
        
        # Remove class assignment from teacher
        if teacher:
            teacher.form_class_id = None
        
        # Log action
        audit_log = AuditLog(
            user_id=current_user.id,
            action='REMOVE_FORM_TEACHER',
            table_name='classrooms',
            record_id=classroom.id,
            old_values={'form_teacher_id': old_teacher_id, 'form_teacher_name': old_teacher_name},
            ip_address=request.remote_addr
        )
        db.session.add(audit_log)
        
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Form teacher removed successfully'})
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400
    
@admin_bp.route('/classes/delete/<class_id>', methods=['DELETE'])
@login_required
@admin_required
def delete_class(class_id):
    """Delete a class"""
    try:
        classroom = ClassRoom.query.get_or_404(class_id)
        
        # Check if class has students
        if classroom.class_students.count() > 0:
            return jsonify({
                'success': False, 
                'message': 'Cannot delete class with students. Reassign students first.'
            }), 400
        
        # Check if class has subject assignments
        if classroom.subject_assignments.count() > 0:
            return jsonify({
                'success': False, 
                'message': 'Cannot delete class with subject assignments. Remove assignments first.'
            }), 400
        
        # Store class info for audit log before deletion
        class_info = {
            'name': classroom.name,
            'level': classroom.level,
            'academic_session_id': classroom.academic_session_id
        }
        
        # Log before deletion
        audit_log = AuditLog(
            user_id=current_user.id,
            action='DELETE_CLASS',
            table_name='classrooms',
            record_id=classroom.id,
            old_values=class_info,
            ip_address=request.remote_addr
        )
        db.session.add(audit_log)
        
        # Delete class
        db.session.delete(classroom)
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': f'Class "{class_info["name"]}" deleted successfully'
        })
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400


@admin_bp.route('/classes/students/<class_id>')
@login_required
@admin_required
def get_class_students(class_id):
    """Get students in a class"""
    try:
        classroom = ClassRoom.query.get_or_404(class_id)
        students = classroom.class_students
        
        student_list = []
        for student in students:
            student_list.append({
                'id': student.id,
                'admission_number': student.admission_number,
                'full_name': f"{student.first_name} {student.last_name}",
                'gender': student.gender,
                'academic_status': student.academic_status
            })
        
        return jsonify({
            'success': True,
            'class_name': classroom.name,
            'students': student_list,
            'count': len(student_list)
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400
    

# Subject Management
@admin_bp.route('/subjects')
@login_required
@admin_required
def manage_subjects():
    """Manage subjects"""
    subjects = Subject.query.all()
    categories = SubjectCategory.query.all()
    
    # Calculate statistics
    active_subjects = Subject.query.filter_by(is_active=True).count()
    core_subjects = Subject.query.filter_by(category='Core').count()
    elective_subjects = Subject.query.filter_by(category='Elective').count()
    
    return render_template('admin/subjects.html', 
                         subjects=subjects, 
                         categories=categories,
                         active_subjects=active_subjects,
                         core_subjects=core_subjects,
                         elective_subjects=elective_subjects)

@admin_bp.route('/subjects/add', methods=['POST'])
@login_required
@admin_required
def add_subject():
    """Add new subject"""
    try:
        subject = Subject(
            name=request.form['name'],
            code=request.form['code'],
            description=request.form.get('description'),
            category=request.form.get('category'),
            pass_mark=float(request.form.get('pass_mark', 40)),
            max_mark=float(request.form.get('max_mark', 100)),
            is_active=True
        )
        
        db.session.add(subject)
        db.session.commit()
        
        # Log action
        audit_log = AuditLog(
            user_id=current_user.id,
            action='CREATE_SUBJECT',
            table_name='subjects',
            record_id=subject.id,
            new_values={'name': subject.name, 'code': subject.code},
            ip_address=request.remote_addr
        )
        db.session.add(audit_log)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Subject added successfully'})
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400

@admin_bp.route('/subjects/<subject_id>/data')
@login_required
@admin_required
def get_subject_data(subject_id):
    """Get subject data for editing"""
    try:
        subject = Subject.query.get_or_404(subject_id)
        
        return jsonify({
            'success': True,
            'subject': {
                'id': subject.id,
                'name': subject.name,
                'code': subject.code,
                'description': subject.description,
                'category': subject.category,
                'pass_mark': subject.pass_mark,
                'max_mark': subject.max_mark,
                'is_active': subject.is_active
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400


@admin_bp.route('/subjects/update', methods=['POST'])
@login_required
@admin_required
def update_subject():
    """Update existing subject"""
    try:
        subject_id = request.form.get('subject_id')
        if not subject_id:
            return jsonify({'success': False, 'message': 'Subject ID is required'}), 400
        
        subject = Subject.query.get_or_404(subject_id)
        
        # Store old values for audit log
        old_values = {
            'name': subject.name,
            'code': subject.code,
            'is_active': subject.is_active
        }
        
        # Update subject
        subject.name = request.form['name']
        subject.code = request.form['code']
        subject.description = request.form.get('description')
        subject.category = request.form.get('category')
        subject.pass_mark = float(request.form.get('pass_mark', 40))
        subject.max_mark = float(request.form.get('max_mark', 100))
        subject.is_active = request.form.get('is_active') == 'true'
        
        # Log action
        audit_log = AuditLog(
            user_id=current_user.id,
            action='UPDATE_SUBJECT',
            table_name='subjects',
            record_id=subject.id,
            old_values=old_values,
            new_values={
                'name': subject.name,
                'code': subject.code,
                'is_active': subject.is_active
            },
            ip_address=request.remote_addr
        )
        db.session.add(audit_log)
        
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Subject updated successfully'})
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400


@admin_bp.route('/subjects/delete/<subject_id>', methods=['DELETE'])
@login_required
@admin_required
def delete_subject(subject_id):
    """Delete a subject"""
    try:
        subject = Subject.query.get_or_404(subject_id)
        
        # Check if subject has associated data
        if subject.subject_assignments.count() > 0:
            return jsonify({
                'success': False, 
                'message': 'Cannot delete subject with teacher assignments. Remove assignments first.'
            }), 400
        
        if subject.exams.count() > 0:
            return jsonify({
                'success': False, 
                'message': 'Cannot delete subject with scheduled exams. Remove exams first.'
            }), 400
        
        if subject.exam_results.count() > 0:
            return jsonify({
                'success': False, 
                'message': 'Cannot delete subject with student results. Remove results first.'
            }), 400
        
        # Store subject info for audit log before deletion
        subject_info = {
            'name': subject.name,
            'code': subject.code,
            'is_active': subject.is_active
        }
        
        # Log before deletion
        audit_log = AuditLog(
            user_id=current_user.id,
            action='DELETE_SUBJECT',
            table_name='subjects',
            record_id=subject.id,
            old_values=subject_info,
            ip_address=request.remote_addr
        )
        db.session.add(audit_log)
        
        # Delete subject
        db.session.delete(subject)
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': f'Subject "{subject_info["name"]}" deleted successfully'
        })
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400


@admin_bp.route('/subjects/validate-code', methods=['POST'])
@login_required
@admin_required
def validate_subject_code():
    """Validate subject code uniqueness"""
    try:
        data = request.get_json()
        code = data.get('code')
        exclude_subject_id = data.get('exclude_subject_id')
        
        if not code:
            return jsonify({'success': False, 'message': 'Subject code is required'}), 400
        
        query = Subject.query.filter_by(code=code)
        
        if exclude_subject_id:
            query = query.filter(Subject.id != exclude_subject_id)
        
        existing = query.first()
        
        return jsonify({
            'success': True,
            'is_valid': existing is None,
            'message': 'Subject code already exists' if existing else 'Subject code is available'
        })
    
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400

# Subject Assignment Management
@admin_bp.route('/subject-assignments')
@login_required
@admin_required
def manage_subject_assignments():
    """Manage subject assignments to teachers"""
    assignments = SubjectAssignment.query.all()
    teachers = Teacher.query.all()
    subjects = Subject.query.filter_by(is_active=True).all()
    classes = ClassRoom.query.all()
    terms = AcademicTerm.query.filter_by(is_active=True).all()
    
    # Calculate statistics
    active_assignments = SubjectAssignment.query.filter_by(is_active=True).count()
    unique_teachers = db.session.query(SubjectAssignment.teacher_id).distinct().count()
    unique_subjects = db.session.query(SubjectAssignment.subject_id).distinct().count()
    
    return render_template('admin/subject_assignments.html', 
                         assignments=assignments, 
                         teachers=teachers, 
                         subjects=subjects,
                         classes=classes,
                         terms=terms,
                         active_assignments=active_assignments,
                         unique_teachers=unique_teachers,
                         unique_subjects=unique_subjects)

@admin_bp.route('/subject-assignments/add', methods=['POST'])
@login_required
@admin_required
def add_subject_assignment():
    """Assign subject to teacher for a class"""
    try:
        assignment = SubjectAssignment(
            teacher_id=request.form['teacher_id'],
            subject_id=request.form['subject_id'],
            class_id=request.form['class_id'],
            academic_term_id=request.form['academic_term_id'],
            is_active=True
        )
        
        db.session.add(assignment)
        db.session.commit()
        
        # Log action
        audit_log = AuditLog(
            user_id=current_user.id,
            action='CREATE_SUBJECT_ASSIGNMENT',
            table_name='subject_assignments',
            record_id=assignment.id,
            ip_address=request.remote_addr
        )
        db.session.add(audit_log)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Subject assignment added successfully'})
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400

@admin_bp.route('/subject-assignments/<assignment_id>/data')
@login_required
@admin_required
def get_assignment_data(assignment_id):
    """Get subject assignment data for editing"""
    try:
        assignment = SubjectAssignment.query.get_or_404(assignment_id)
        
        return jsonify({
            'success': True,
            'assignment': {
                'id': assignment.id,
                'teacher_id': assignment.teacher_id,
                'subject_id': assignment.subject_id,
                'class_id': assignment.class_id,
                'academic_term_id': assignment.academic_term_id,
                'is_active': assignment.is_active
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400


@admin_bp.route('/subject-assignments/update', methods=['POST'])
@login_required
@admin_required
def update_subject_assignment():
    """Update existing subject assignment"""
    try:
        assignment_id = request.form.get('assignment_id')
        if not assignment_id:
            return jsonify({'success': False, 'message': 'Assignment ID is required'}), 400
        
        assignment = SubjectAssignment.query.get_or_404(assignment_id)
        
        # Store old values for audit log
        old_values = {
            'teacher_id': assignment.teacher_id,
            'subject_id': assignment.subject_id,
            'class_id': assignment.class_id,
            'is_active': assignment.is_active
        }
        
        # Update assignment
        assignment.teacher_id = request.form['teacher_id']
        assignment.subject_id = request.form['subject_id']
        assignment.class_id = request.form['class_id']
        assignment.academic_term_id = request.form['academic_term_id']
        assignment.is_active = 'is_active' in request.form
        
        # Log action
        audit_log = AuditLog(
            user_id=current_user.id,
            action='UPDATE_SUBJECT_ASSIGNMENT',
            table_name='subject_assignments',
            record_id=assignment.id,
            old_values=old_values,
            new_values={
                'teacher_id': assignment.teacher_id,
                'subject_id': assignment.subject_id,
                'class_id': assignment.class_id,
                'is_active': assignment.is_active
            },
            ip_address=request.remote_addr
        )
        db.session.add(audit_log)
        
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Subject assignment updated successfully'})
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400


@admin_bp.route('/subject-assignments/delete/<assignment_id>', methods=['DELETE'])
@login_required
@admin_required
def delete_subject_assignment(assignment_id):
    """Delete a subject assignment"""
    try:
        assignment = SubjectAssignment.query.get_or_404(assignment_id)
        
        # Store assignment info for audit log before deletion
        assignment_info = {
            'teacher_id': assignment.teacher_id,
            'subject_id': assignment.subject_id,
            'class_id': assignment.class_id,
            'academic_term_id': assignment.academic_term_id
        }
        
        # Log before deletion
        audit_log = AuditLog(
            user_id=current_user.id,
            action='DELETE_SUBJECT_ASSIGNMENT',
            table_name='subject_assignments',
            record_id=assignment.id,
            old_values=assignment_info,
            ip_address=request.remote_addr
        )
        db.session.add(audit_log)
        
        # Delete assignment
        db.session.delete(assignment)
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': 'Subject assignment deleted successfully'
        })
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400


@admin_bp.route('/subject-assignments/activate/<assignment_id>', methods=['POST'])
@login_required
@admin_required
def activate_subject_assignment(assignment_id):
    """Activate a subject assignment"""
    try:
        assignment = SubjectAssignment.query.get_or_404(assignment_id)
        assignment.is_active = True
        
        # Log action
        audit_log = AuditLog(
            user_id=current_user.id,
            action='ACTIVATE_SUBJECT_ASSIGNMENT',
            table_name='subject_assignments',
            record_id=assignment.id,
            new_values={'is_active': True},
            ip_address=request.remote_addr
        )
        db.session.add(audit_log)
        
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': 'Subject assignment activated successfully'
        })
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400


@admin_bp.route('/subject-assignments/deactivate/<assignment_id>', methods=['POST'])
@login_required
@admin_required
def deactivate_subject_assignment(assignment_id):
    """Deactivate a subject assignment"""
    try:
        assignment = SubjectAssignment.query.get_or_404(assignment_id)
        assignment.is_active = False
        
        # Log action
        audit_log = AuditLog(
            user_id=current_user.id,
            action='DEACTIVATE_SUBJECT_ASSIGNMENT',
            table_name='subject_assignments',
            record_id=assignment.id,
            new_values={'is_active': False},
            ip_address=request.remote_addr
        )
        db.session.add(audit_log)
        
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': 'Subject assignment deactivated successfully'
        })
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400


@admin_bp.route('/subject-assignments/check-duplicate', methods=['POST'])
@login_required
@admin_required
def check_duplicate_assignment():
    """Check for duplicate subject assignment"""
    try:
        data = request.get_json()
        teacher_id = data.get('teacher_id')
        subject_id = data.get('subject_id')
        class_id = data.get('class_id')
        term_id = data.get('academic_term_id')
        exclude_id = data.get('exclude_id')
        
        query = SubjectAssignment.query.filter_by(
            teacher_id=teacher_id,
            subject_id=subject_id,
            class_id=class_id,
            academic_term_id=term_id
        )
        
        if exclude_id:
            query = query.filter(SubjectAssignment.id != exclude_id)
        
        existing = query.first()
        
        return jsonify({
            'success': True,
            'exists': existing is not None,
            'message': 'Assignment already exists' if existing else 'No duplicate found'
        })
    
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400

# app/routes/admin.py - Update assessment configuration routes
@admin_bp.route('/assessment-config')
@login_required
@admin_required
def assessment_config():
    """Configure term-based assessment structure"""
    # Get active academic terms
    terms = AcademicTerm.query.order_by(AcademicTerm.is_active.desc(), 
                                       AcademicTerm.start_date.desc()).all()
    
    # Get selected term if provided
    selected_term = None
    term_id = request.args.get('term_id')
    
    if term_id:
        selected_term = AcademicTerm.query.get(int(term_id))
    elif terms:
        # Default to active term or first term
        selected_term = next((t for t in terms if t.is_active), terms[0])
    
    assessments = []
    if selected_term:
        # Get assessments for the selected term
        assessments = Assessment.query.filter_by(
            academic_term_id=selected_term.id
        ).order_by(Assessment.order).all()
    
    return render_template('admin/assessment_config.html', 
                         terms=terms,
                         selected_term=selected_term,
                         assessments=assessments)

@admin_bp.route('/configure-assessment', methods=['POST'])
@login_required
@admin_required
def configure_assessment():
    """Configure term-based assessment structure"""
    try:
        data = request.get_json()
        academic_term_id = data.get('academic_term_id')
        
        if not academic_term_id:
            return jsonify({'success': False, 'message': 'Academic term ID is required'}), 400
        
        academic_term = AcademicTerm.query.get_or_404(academic_term_id)
        
        # Clear existing assessments for this term
        Assessment.query.filter_by(academic_term_id=academic_term_id).delete()
        
        # Create new assessments
        assessments_data = data.get('assessments', [])
        
        for i, assessment_data in enumerate(assessments_data):
            if assessment_data.get('type') and assessment_data.get('weight'):
                # Get max_score from data, default to 100 if not provided
                max_score = assessment_data.get('maxScore', 100)                
                assessment = Assessment(
                    academic_term_id=academic_term_id,
                    assessment_type=assessment_data['type'],
                    weight=float(assessment_data['weight']),
                    max_score=float(max_score),
                    order=i + 1,
                    is_active=True
                )

                db.session.add(assessment)
        
        db.session.commit()
        
        # Log action
        audit_log = AuditLog(
            user_id=current_user.id,
            action='CONFIGURE_TERM_ASSESSMENT',
            table_name='assessments',
            new_values={'academic_term_id': academic_term_id, 'assessments_count': len(assessments_data)},
            ip_address=request.remote_addr
        )
        db.session.add(audit_log)
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': f'Assessment structure for {academic_term.name} updated successfully!'
        })
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400

@admin_bp.route('/api/assessments/<term_id>', methods=['GET'])
@login_required
@admin_required
def get_term_assessments(term_id):
    """Get assessments for a specific term"""
    assessments = Assessment.query.filter_by(academic_term_id=term_id).order_by(Assessment.order).all()
    
    assessments_data = []
    for assessment in assessments:
        assessments_data.append({
            'id': assessment.id,
            'type': assessment.assessment_type,
            'weight': assessment.weight,
            'max_score': assessment.max_score,
            'order': assessment.order,
            'is_active': assessment.is_active
        })
    
    return jsonify({'success': True, 'assessments': assessments_data})

# Grade Scale Management
@admin_bp.route('/grade-scales')
@login_required
@admin_required
def manage_grade_scales():
    """Manage grade scales"""
    grade_scales = GradeScale.query.filter_by(is_active=True).order_by(GradeScale.min_score.desc()).all()
    return render_template('admin/grade_scales.html', grade_scales=grade_scales)

@admin_bp.route('/grade-scales/add', methods=['POST'])
@login_required
@admin_required
def add_grade_scale():
    """Add new grade scale"""
    try:
        grade_scale = GradeScale(
            name=request.form['name'],
            min_score=float(request.form['min_score']),
            max_score=float(request.form['max_score']),
            grade=request.form['grade'],
            remark=request.form.get('remark'),
            point=float(request.form.get('point', 0)),
            is_active=True
        )
        
        db.session.add(grade_scale)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Grade scale added successfully'})
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400

@admin_bp.route('/grade-scales/check-overlap', methods=['POST'])
@login_required
@admin_required
def check_grade_overlap():
    """Check if grade scale overlaps with existing ones"""
    try:
        data = request.get_json()
        min_score = float(data.get('min_score', 0))
        max_score = float(data.get('max_score', 100))
        
        # Check for overlaps
        overlapping = GradeScale.query.filter(
            GradeScale.is_active == True,
            db.or_(
                db.and_(GradeScale.min_score <= min_score, GradeScale.max_score >= min_score),
                db.and_(GradeScale.min_score <= max_score, GradeScale.max_score >= max_score),
                db.and_(GradeScale.min_score >= min_score, GradeScale.max_score <= max_score)
            )
        ).first()
        
        if overlapping:
            return jsonify({
                'success': False,
                'message': f'Overlaps with existing grade scale: {overlapping.name} ({overlapping.min_score}%-{overlapping.max_score}%)'
            })
        
        return jsonify({'success': True})
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400


@admin_bp.route('/grade-scales/get/<grade_id>')
@login_required
@admin_required
def get_grade_scale(grade_id):
    """Get grade scale by ID"""
    grade_scale = GradeScale.query.get_or_404(grade_id)
    return jsonify({
        'success': True,
        'data': {
            'id': grade_scale.id,
            'name': grade_scale.name,
            'min_score': grade_scale.min_score,
            'max_score': grade_scale.max_score,
            'grade': grade_scale.grade,
            'remark': grade_scale.remark,
            'point': grade_scale.point
        }
    })


@admin_bp.route('/grade-scales/update', methods=['PUT'])
@login_required
@admin_required
def update_grade_scale():
    """Update grade scale"""
    try:
        grade_id = request.form.get('id')
        grade_scale = GradeScale.query.get_or_404(grade_id)
        
        grade_scale.name = request.form['name']
        grade_scale.min_score = float(request.form['min_score'])
        grade_scale.max_score = float(request.form['max_score'])
        grade_scale.grade = request.form['grade']
        grade_scale.remark = request.form.get('remark')
        grade_scale.point = float(request.form.get('point', 0))
        
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Grade scale updated successfully'})
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400


@admin_bp.route('/grade-scales/delete/<grade_id>', methods=['DELETE'])
@login_required
@admin_required
def delete_grade_scale(grade_id):
    """Delete (soft delete) grade scale"""
    try:
        grade_scale = GradeScale.query.get_or_404(grade_id)
        grade_scale.is_active = False
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Grade scale deleted successfully'})
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400


@admin_bp.route('/grade-scales/apply-default', methods=['POST'])
@login_required
@admin_required
def apply_default_grade_scales():
    """Apply default grade scales"""
    try:
        # Delete existing active grade scales (soft delete)
        GradeScale.query.filter_by(is_active=True).update({'is_active': False})
        
        # Create default grade scales
        default_scales = [
            {
                'name': 'Excellent',
                'min_score': 80,
                'max_score': 100,
                'grade': 'A',
                'remark': 'Excellent',
                'point': 4.0
            },
            {
                'name': 'Very Good',
                'min_score': 70,
                'max_score': 79.9,
                'grade': 'B',
                'remark': 'Very Good',
                'point': 3.0
            },
            {
                'name': 'Good',
                'min_score': 60,
                'max_score': 69.9,
                'grade': 'C',
                'remark': 'Good',
                'point': 2.0
            },
            {
                'name': 'Fair',
                'min_score': 50,
                'max_score': 59.9,
                'grade': 'D',
                'remark': 'Fair',
                'point': 1.0
            },
            {
                'name': 'Pass',
                'min_score': 40,
                'max_score': 49.9,
                'grade': 'E',
                'remark': 'Pass',
                'point': 0.5
            },
            {
                'name': 'Fail',
                'min_score': 0,
                'max_score': 39.9,
                'grade': 'F',
                'remark': 'Fail',
                'point': 0.0
            }
        ]
        
        for scale in default_scales:
            grade_scale = GradeScale(**scale, is_active=True)
            db.session.add(grade_scale)
        
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Default grade scales applied successfully'})
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400
    

# System Configuration
@admin_bp.route('/system-config')
@login_required
@admin_required
def system_config():
    """System configuration page"""
    try:
        # Get all configurations
        configs = SystemConfiguration.query.order_by(SystemConfiguration.config_key).all()
        
        # Get specific configs
        principal_signature = SystemConfiguration.get_principal_signature()
        resumption_date = SystemConfiguration.get_resumption_date()
        
        return render_template('admin/system_config.html', 
                             configs=configs,
                             principal_signature=principal_signature,
                             resumption_date=resumption_date)
    except Exception as e:
        current_app.logger.error(f"Error loading system config: {str(e)}")
        flash('Error loading system configuration', 'error')
        return render_template('admin/system_config.html', 
                             configs=[], 
                             principal_signature='', 
                             resumption_date='')

@admin_bp.route('/upload-principal-signature', methods=['POST'])
@login_required
@admin_required
def upload_principal_signature():
    """Upload principal signature"""
    try:
        if 'signature' not in request.files:
            flash('No file selected', 'error')
            return redirect(url_for('admin.system_config'))
        
        file = request.files['signature']
        if file.filename == '':
            flash('No file selected', 'error')
            return redirect(url_for('admin.system_config'))
        
        if file:
            # Create uploads directory inside static folder
            upload_folder = os.path.join(
                current_app.root_path,  # Root of the app
                'static',  # Go into static folder
                'uploads',  # Then uploads folder
                'signatures'  # Then signatures folder
            )
            os.makedirs(upload_folder, exist_ok=True)
            print(f"Upload folder: {upload_folder}")  # Debug
            
            # Secure filename and save
            filename = secure_filename(f"principal_signature_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.filename}")
            file_path = os.path.join(upload_folder, filename)
            print(f"Saving to: {file_path}")  # Debug
            file.save(file_path)
            
            # Save to database (relative path from static folder)
            # This path will be relative to static folder: uploads/signatures/filename.png
            relative_path = f"uploads/signatures/{filename}"
            print(f"Relative path: {relative_path}")  # Debug
            
            SystemConfiguration.update_principal_signature(
                relative_path, 
                current_user.id
            )
            
            # Log the action
            audit_log = AuditLog(
                user_id=current_user.id,
                action='UPLOAD_PRINCIPAL_SIGNATURE',
                table_name='system_configuration',
                details={'filename': filename, 'path': relative_path},
                ip_address=request.remote_addr,
                user_agent=request.user_agent.string
            )
            db.session.add(audit_log)
            db.session.commit()
            
            flash('Principal signature uploaded successfully', 'success')
        else:
            flash('Invalid file type', 'error')
            
    except Exception as e:
        current_app.logger.error(f"Error uploading signature: {str(e)}")
        flash('Error uploading signature', 'error')
        db.session.rollback()
    
    return redirect(url_for('admin.system_config'))

@admin_bp.route('/update-resumption-date', methods=['POST'])
@login_required
@admin_required
def update_resumption_date():
    """Update resumption date"""
    try:
        date_str = request.form.get('resumption_date')
        
        if not date_str:
            flash('Resumption date is required', 'error')
            return redirect(url_for('admin.system_config'))
        
        # Validate date format
        try:
            datetime.strptime(date_str, '%Y-%m-%d')
        except ValueError:
            flash('Invalid date format. Use YYYY-MM-DD', 'error')
            return redirect(url_for('admin.system_config'))
        
        # Save to database
        SystemConfiguration.update_resumption_date(date_str, current_user.id)
        
        # Log the action
        audit_log = AuditLog(
            user_id=current_user.id,
            action='UPDATE_RESUMPTION_DATE',
            table_name='system_configuration',
            details={'new_date': date_str},
            ip_address=request.remote_addr,
            user_agent=request.user_agent.string
        )
        db.session.add(audit_log)
        db.session.commit()
        
        flash('Resumption date updated successfully', 'success')
        
    except Exception as e:
        current_app.logger.error(f"Error updating resumption date: {str(e)}")
        flash('Error updating resumption date', 'error')
        db.session.rollback()
    
    return redirect(url_for('admin.system_config'))
    
@admin_bp.route('/update-config', methods=['POST'])
@login_required
@admin_required
def update_config():
    """Update system configuration"""
    try:
        config_key = request.form['config_key']
        config_value = request.form['config_value']
        description = request.form.get('description')
        
        config = SystemConfiguration.query.filter_by(config_key=config_key).first()
        
        if config:
            config.config_value = config_value
            config.description = description
            config.updated_by = current_user.id
        else:
            config = SystemConfiguration(
                config_key=config_key,
                config_value=config_value,
                description=description,
                updated_by=current_user.id
            )
            db.session.add(config)
        
        db.session.commit()
        
        # Log action
        audit_log = AuditLog(
            user_id=current_user.id,
            action='UPDATE_SYSTEM_CONFIG',
            table_name='system_configuration',
            record_id=config.id,
            new_values={'config_key': config_key, 'config_value': config_value},
            ip_address=request.remote_addr
        )
        db.session.add(audit_log)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Configuration updated successfully!'})
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400

# Report Generation
@admin_bp.route('/reports')
@login_required
@admin_required
def generate_reports():
    """Generate reports with student list and filtering"""
    try:
        # Get all classes for dropdown
        classes = ClassRoom.query.order_by(ClassRoom.name).all()
        terms = AcademicTerm.query.order_by(AcademicTerm.start_date.desc()).all()
        sessions = AcademicSession.query.order_by(AcademicSession.created_at.desc()).all()
        
        # Get filter parameters
        class_id = request.args.get('class_id')
        term_id = request.args.get('term_id')
        session_id = request.args.get('session_id')
        
        students = []
        reports_by_student = {}
        generated_reports = []
        
        if class_id and term_id:
            # Get students in the selected class
            students = Student.query.filter_by(
                current_class_id=class_id,
                is_active=True,
                academic_status='active'
            ).order_by(Student.admission_number).all()
            
            # Get selected term
            term = AcademicTerm.query.get(term_id)
            
            if term:
                # Get existing reports for these students for this term
                student_ids = [s.id for s in students]
                reports = ReportCard.query.filter(
                    ReportCard.student_id.in_(student_ids),
                    ReportCard.term == term.term_number,
                    ReportCard.academic_year == term.session.name
                ).all()
                
                # Create a dictionary for quick lookup
                for report in reports:
                    reports_by_student[report.student_id] = report
                
                # Get recently generated reports for this class/term
                generated_reports = ReportCard.query.filter(
                    ReportCard.student_id.in_(student_ids),
                    ReportCard.term == term.term_number
                ).order_by(ReportCard.generated_at.desc()).limit(10).all()
        
        return render_template('admin/reports.html', 
                             classes=classes, 
                             terms=terms, 
                             sessions=sessions,
                             students=students,
                             reports_by_student=reports_by_student,
                             generated_reports=generated_reports)
    
    except Exception as e:
        flash(f'Error loading reports page: {str(e)}', 'danger')
        return redirect(url_for('admin.dashboard'))

@admin_bp.route('/generate-report-cards', methods=['POST'])
@login_required
@admin_required
def generate_report_cards():
    """Generate report cards for a class/term"""
    try:
        from ..utils.reporting import generate_class_report_cards
        
        class_id = request.form['class_id']
        term = int(request.form['term'])
        academic_year = request.form['academic_year']
        
        # Generate report cards
        generated_count = generate_class_report_cards(class_id, term, academic_year, current_user.id)
        
        # Log action
        audit_log = AuditLog(
            user_id=current_user.id,
            action='GENERATE_REPORT_CARDS',
            details={'class_id': class_id, 'term': term, 'academic_year': academic_year, 'count': generated_count},
            ip_address=request.remote_addr
        )
        db.session.add(audit_log)
        db.session.commit()
        
        flash(f'Successfully generated {generated_count} report cards!', 'success')
        return jsonify({'success': True, 'count': generated_count})
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400


# Audit logs management
@admin_bp.route('/audit-logs')
@login_required
@admin_required
def audit_logs():
    """View audit logs with filtering"""
    page = request.args.get('page', 1, type=int)
    per_page = 50
    export = request.args.get('export')
    
    # Build query with filters
    query = AuditLog.query
    
    # Filter by action type
    action_type = request.args.get('action_type')
    if action_type:
        if action_type == 'create':
            query = query.filter(AuditLog.action.ilike('%create%') | AuditLog.action.ilike('%add%') | AuditLog.action.ilike('%insert%'))
        elif action_type == 'update':
            query = query.filter(AuditLog.action.ilike('%update%') | AuditLog.action.ilike('%edit%') | AuditLog.action.ilike('%modify%'))
        elif action_type == 'delete':
            query = query.filter(AuditLog.action.ilike('%delete%') | AuditLog.action.ilike('%remove%') | AuditLog.action.ilike('%archive%'))
        elif action_type == 'login':
            query = query.filter(AuditLog.action.ilike('%login%') | AuditLog.action.ilike('%signin%'))
        elif action_type == 'logout':
            query = query.filter(AuditLog.action.ilike('%logout%') | AuditLog.action.ilike('%signout%'))
        elif action_type == 'system':
            query = query.filter(~AuditLog.action.ilike('%create%'), 
                                 ~AuditLog.action.ilike('%update%'), 
                                 ~AuditLog.action.ilike('%delete%'),
                                 ~AuditLog.action.ilike('%login%'),
                                 ~AuditLog.action.ilike('%logout%'))
    
    # Filter by user
    user_id = request.args.get('user_id')
    if user_id:
        query = query.filter(AuditLog.user_id == user_id)
    
    # Filter by table name
    table_name = request.args.get('table_name')
    if table_name:
        query = query.filter(AuditLog.table_name.ilike(f'%{table_name}%'))
    
    # Filter by date range
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    if date_from:
        query = query.filter(AuditLog.timestamp >= f'{date_from} 00:00:00')
    if date_to:
        query = query.filter(AuditLog.timestamp <= f'{date_to} 23:59:59')
    
    # Order by timestamp
    query = query.order_by(AuditLog.timestamp.desc())
    
    # Handle export
    if export == 'csv':
        logs = query.all()
        return export_audit_logs_csv(logs)
    
    # Paginate results
    logs = query.paginate(page=page, per_page=per_page)
    
    # Get users for filter dropdown
    users = User.query.order_by(User.username).all()
    
    return render_template('admin/audit_logs.html', 
                         logs=logs,
                         users=users)


def export_audit_logs_csv(logs):
    """Export audit logs to CSV"""
    import csv
    from io import StringIO
    
    output = StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow([
        'Timestamp', 'User', 'Action', 'Table', 'Record ID',
        'Old Values', 'New Values', 'IP Address', 'User Agent'
    ])
    
    # Write data
    for log in logs:
        writer.writerow([
            log.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            log.user.username if log.user else 'System',
            log.action,
            log.table_name or '',
            log.record_id or '',
            str(log.old_values) if log.old_values else '',
            str(log.new_values) if log.new_values else '',
            log.ip_address or '',
            log.user_agent or ''
        ])
    
    output.seek(0)
    
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=audit_logs.csv"}
    )


@admin_bp.route('/audit-log-details/<log_id>')
@login_required
@admin_required
def audit_log_details(log_id):
    """Get detailed view of an audit log"""
    log = AuditLog.query.get_or_404(log_id)
    
    # Render details template
    html = render_template('admin/audit_log_details.html', log=log)
    
    return jsonify({
        'success': True,
        'html': html
    })


@admin_bp.route('/audit-log-changes/<log_id>')
@login_required
@admin_required
def audit_log_changes(log_id):
    """Get changes view for an audit log"""
    log = AuditLog.query.get_or_404(log_id)
    
    # Render changes template
    html = render_template('admin/audit_log_changes.html', log=log)
    
    return jsonify({
        'success': True,
        'html': html
    })


@admin_bp.context_processor
def utility_processor():
    def get_action_type(action):
        """Helper function to determine action type for badge"""
        if not action:
            return 'system'
        
        action_lower = action.lower()
        if any(word in action_lower for word in ['create', 'add', 'insert']):
            return 'create'
        elif any(word in action_lower for word in ['update', 'edit', 'modify']):
            return 'update'
        elif any(word in action_lower for word in ['delete', 'remove', 'archive']):
            return 'delete'
        elif any(word in action_lower for word in ['login', 'signin']):
            return 'login'
        elif any(word in action_lower for word in ['logout', 'signout']):
            return 'logout'
        else:
            return 'system'
    
    return dict(get_action_type=get_action_type)

# User Management
@admin_bp.route('/users')
@login_required
@admin_required
def manage_users():
    """Manage all users"""
    users = User.query.all()
    
    # Calculate statistics
    total_users = len(users)
    active_users = sum(1 for user in users if user.is_active)
    admin_count = sum(1 for user in users if user.role == 'admin')
    
    # Check for locked accounts (locked_until is in the future)
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    locked_users = sum(1 for user in users if user.locked_until and user.locked_until > now)
    
    # Prepare user data with computed fields
    user_data = []
    for user in users:
        user_dict = {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'role': user.role,
            'is_active': user.is_active,
            'created_at': user.created_at,
            'last_login': user.last_login,
            'failed_login_attempts': user.failed_login_attempts,
            'locked_until': user.locked_until,
            'is_locked': user.locked_until and user.locked_until > now,
            'profile_name': get_user_profile_name(user)
        }
        user_data.append(user_dict)
    
    return render_template('admin/users.html', 
                         users=user_data,
                         total_users=total_users,
                         active_users=active_users,
                         admin_count=admin_count,
                         locked_users=locked_users)

def get_user_profile_name(user):
    """Get the profile name based on user role"""
    if user.teacher_profile:
        return f"{user.teacher_profile.first_name} {user.teacher_profile.last_name}"
    elif user.student_profile:
        return f"{user.student_profile.first_name} {user.student_profile.last_name}"
    elif user.parent_profile:
        return f"{user.parent_profile.first_name} {user.parent_profile.last_name}"
    else:
        return user.username
    
@admin_bp.route('/users/<user_id>/data')
@login_required
@admin_required
def get_user_data(user_id):
    """Get user data for editing"""
    try:
        user = User.query.get_or_404(user_id)
        
        # Get profile data based on role
        profile_data = {}
        if user.teacher_profile:
            profile_data = {
                'first_name': user.teacher_profile.first_name,
                'last_name': user.teacher_profile.last_name,
                'staff_id': user.teacher_profile.staff_id,
                'phone': user.teacher_profile.phone
            }
        elif user.student_profile:
            profile_data = {
                'first_name': user.student_profile.first_name,
                'last_name': user.student_profile.last_name,
                'admission_number': user.student_profile.admission_number,
                'class_id': user.student_profile.current_class_id
            }
        elif user.parent_profile:
            profile_data = {
                'first_name': user.parent_profile.first_name,
                'last_name': user.parent_profile.last_name,
                'phone': user.parent_profile.phone,
                'occupation': user.parent_profile.occupation
            }
        
        user_data = {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'role': user.role,
            'is_active': user.is_active
        }
        
        return jsonify({
            'success': True,
            'user': user_data,
            'profile_data': profile_data
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400

@admin_bp.route('/users/add', methods=['POST'])
@login_required
@admin_required
def add_user():
    """Add new user"""
    try:
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        role = request.form['role']
        is_active = 'is_active' in request.form
        
        # Check if username already exists
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            return jsonify({'success': False, 'message': 'Username already exists'}), 400
        
        # Check if email already exists
        existing_email = User.query.filter_by(email=email).first()
        if existing_email:
            return jsonify({'success': False, 'message': 'Email already exists'}), 400
        
        # Validate password strength
        if len(password) < 8:
            return jsonify({'success': False, 'message': 'Password must be at least 8 characters long'}), 400
        
        # Create user
        user = User(
            username=username,
            email=email,
            role=role,
            is_active=is_active
        )
        user.set_password(password)
        
        db.session.add(user)
        db.session.flush()  # Get user ID
        
        # Create profile based on role
        if role == 'teacher':
            teacher = Teacher(
                user_id=user.id,
                staff_id=request.form.get('staff_id', f"STAFF{user.id:04d}"),
                first_name=request.form['first_name'],
                last_name=request.form['last_name'],
                phone=request.form.get('phone'),
                email=email
            )
            db.session.add(teacher)
        elif role == 'student':
            student = Student(
                user_id=user.id,
                admission_number=request.form.get('admission_number', f"STU{user.id:04d}"),
                first_name=request.form['first_name'],
                last_name=request.form['last_name'],
                current_class_id=request.form.get('class_id'),
                email=email,
                enrollment_date=datetime.now(timezone.utc).date()
            )
            db.session.add(student)
        elif role == 'parent':
            parent = Parent(
                user_id=user.id,
                first_name=request.form['first_name'],
                last_name=request.form['last_name'],
                phone=request.form['phone'],
                email=email,
                occupation=request.form.get('occupation')
            )
            db.session.add(parent)
        
        # Log action
        audit_log = AuditLog(
            user_id=current_user.id,
            action='CREATE_USER',
            table_name='users',
            record_id=user.id,
            new_values={'username': username, 'role': role},
            ip_address=request.remote_addr
        )
        db.session.add(audit_log)
        
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'User added successfully'})
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400

@admin_bp.route('/users/update', methods=['POST'])
@login_required
@admin_required
def update_user():
    """Update existing user"""
    try:
        user_id = request.form.get('user_id')
        if not user_id:
            return jsonify({'success': False, 'message': 'User ID is required'}), 400
        
        user = User.query.get_or_404(user_id)
        
        # Store old values for audit log
        old_values = {
            'username': user.username,
            'email': user.email,
            'role': user.role,
            'is_active': user.is_active
        }
        
        # Update user
        user.username = request.form['username']
        user.email = request.form['email']
        user.role = request.form['role']
        user.is_active = 'is_active' in request.form
        
        # Update password if provided
        if request.form.get('password'):
            if len(request.form['password']) < 8:
                return jsonify({'success': False, 'message': 'Password must be at least 8 characters long'}), 400
            user.set_password(request.form['password'])
        
        # Update profile based on role
        if user.role == 'teacher' and user.teacher_profile:
            user.teacher_profile.first_name = request.form.get('first_name', '')
            user.teacher_profile.last_name = request.form.get('last_name', '')
            user.teacher_profile.staff_id = request.form.get('staff_id', '')
            user.teacher_profile.phone = request.form.get('phone')
        elif user.role == 'student' and user.student_profile:
            user.student_profile.first_name = request.form.get('first_name', '')
            user.student_profile.last_name = request.form.get('last_name', '')
            user.student_profile.admission_number = request.form.get('admission_number', '')
            user.student_profile.current_class_id = request.form.get('class_id')
        elif user.role == 'parent' and user.parent_profile:
            user.parent_profile.first_name = request.form.get('first_name', '')
            user.parent_profile.last_name = request.form.get('last_name', '')
            user.parent_profile.phone = request.form.get('phone', '')
            user.parent_profile.occupation = request.form.get('occupation')
        
        # Log action
        audit_log = AuditLog(
            user_id=current_user.id,
            action='UPDATE_USER',
            table_name='users',
            record_id=user.id,
            old_values=old_values,
            new_values={
                'username': user.username,
                'email': user.email,
                'role': user.role,
                'is_active': user.is_active
            },
            ip_address=request.remote_addr
        )
        db.session.add(audit_log)
        
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'User updated successfully'})
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400

@admin_bp.route('/users/delete/<user_id>', methods=['DELETE'])
@login_required
@admin_required
def delete_user(user_id):
    """Delete a user"""
    try:
        user = User.query.get_or_404(user_id)
        
        # Prevent deleting own account
        if user.id == current_user.id:
            return jsonify({
                'success': False, 
                'message': 'You cannot delete your own account'
            }), 400
        
        # Store user info for audit log before deletion
        user_info = {
            'username': user.username,
            'email': user.email,
            'role': user.role
        }
        
        # Log before deletion
        audit_log = AuditLog(
            user_id=current_user.id,
            action='DELETE_USER',
            table_name='users',
            record_id=user.id,
            old_values=user_info,
            ip_address=request.remote_addr
        )
        db.session.add(audit_log)
        
        # Delete user (cascades to related profiles)
        db.session.delete(user)
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': f'User "{user_info["username"]}" deleted successfully'
        })
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400

@admin_bp.route('/users/<user_id>/reset-password', methods=['POST'])
@login_required
@admin_required
def reset_user_password(user_id):
    """Reset user password"""
    try:
        user = User.query.get_or_404(user_id)
        
        # Get new password from request or use username as default
        new_password = request.json.get('new_password') if request.is_json else None
        if not new_password:
            new_password = user.username  # Default to username
        
        # Reset password
        user.set_password(new_password)
        user.password_changed_at = datetime.now(timezone.utc)
        
        # Clear lock status if account was locked
        user.failed_login_attempts = 0
        user.locked_until = None
        
        # Log action
        audit_log = AuditLog(
            user_id=current_user.id,
            action='RESET_USER_PASSWORD',
            table_name='users',
            record_id=user.id,
            new_values={'user_id': user.id},
            ip_address=request.remote_addr
        )
        db.session.add(audit_log)
        
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': f'Password reset successfully for {user.username}.'
        })
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400

@admin_bp.route('/users/<user_id>/unlock', methods=['POST'])
@login_required
@admin_required
def unlock_user(user_id):
    """Unlock a locked user account"""
    try:
        user = User.query.get_or_404(user_id)
        
        # Clear lock status
        user.failed_login_attempts = 0
        user.locked_until = None
        
        # Log action
        audit_log = AuditLog(
            user_id=current_user.id,
            action='UNLOCK_USER',
            table_name='users',
            record_id=user.id,
            new_values={'username': user.username},
            ip_address=request.remote_addr
        )
        db.session.add(audit_log)
        
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': f'User account {user.username} unlocked successfully'
        })
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400
    
@admin_bp.route('/users/toggle-active/<user_id>', methods=['POST'])
@login_required
@admin_required
def toggle_user_active(user_id):
    """Toggle user active status"""
    try:
        user = User.query.get_or_404(user_id)
        user.is_active = not user.is_active
        
        # Log action
        audit_log = AuditLog(
            user_id=current_user.id,
            action='TOGGLE_USER_ACTIVE',
            table_name='users',
            record_id=user_id,
            new_values={'is_active': user.is_active},
            ip_address=request.remote_addr
        )
        db.session.add(audit_log)
        
        db.session.commit()
        
        status = 'activated' if user.is_active else 'deactivated'
        return jsonify({'success': True, 'message': f'User {status} successfully'})
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400

# Question Bank Management
@admin_bp.route('/question-bank')
@login_required
@admin_required
def manage_question_bank():
    """Manage question bank"""
    questions = QuestionBank.query.all()
    subjects = Subject.query.filter_by(is_active=True).all()
    teachers = Teacher.query.all()
    
    return render_template('admin/question_bank.html', 
                         questions=questions, 
                         subjects=subjects, 
                         teachers=teachers)

@admin_bp.route('/question-bank/approve/<question_id>', methods=['POST'])
@login_required
@admin_required
def approve_question(question_id):
    """Approve a question in the question bank"""
    try:
        question = QuestionBank.query.get_or_404(question_id)
        question.is_approved = True
        question.approved_by = current_user.id
        
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Question approved successfully'})
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400
    
def validate_password_strength(password):
        """Validate password meets policy requirements"""
        if len(password) < Config.PASSWORD_POLICY['min_length']:
            return False, f"Password must be at least {Config.PASSWORD_POLICY['min_length']} characters long"
        
        if Config.PASSWORD_POLICY['require_uppercase'] and not any(c.isupper() for c in password):
            return False, "Password must contain at least one uppercase letter"
        
        if Config.PASSWORD_POLICY['require_lowercase'] and not any(c.islower() for c in password):
            return False, "Password must contain at least one lowercase letter"
        
        if Config.PASSWORD_POLICY['require_numbers'] and not any(c.isdigit() for c in password):
            return False, "Password must contain at least one number"
        
        return True, "Password meets requirements"

@admin_bp.route('/manage-passwords', methods=['GET', 'POST'])
@login_required
@admin_required
def manage_passwords():
    """Admin-only password management interface"""
    if request.method == 'POST':
        user_id = request.form.get('user_id')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        if not user_id or not new_password or not confirm_password:
            flash('All fields are required.', 'danger')
            return redirect(url_for('admin.manage_passwords'))
        
        if new_password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return redirect(url_for('admin.manage_passwords'))
        
        # Validate password strength
        if len(new_password) < 8:
            flash('Password must be at least 8 characters long.', 'danger')
            return redirect(url_for('admin.manage_passwords'))
        
        user = User.query.get(user_id)
        if not user:
            flash('User not found.', 'danger')
            return redirect(url_for('admin.manage_passwords'))
        
        # Update password
        user.set_password(new_password)
        db.session.commit()
        
        # Log the password change
        audit_log = AuditLog(
            user_id=current_user.id,
            action='PASSWORD_RESET_ADMIN',
            table_name='users',
            record_id=user.id,
            old_values=None,
            new_values={'user_id': user.id, 'user_role': user.role},
            ip_address=request.remote_addr,
            user_agent=request.user_agent.string
        )
        db.session.add(audit_log)
        db.session.commit()
        
        flash(f'Password updated successfully for {user.username}.', 'success')
        return redirect(url_for('admin.manage_passwords'))
    
    # GET request - show password management interface
    users = User.query.filter(User.id != current_user.id).all()
    return render_template('admin/manage_passwords.html', users=users)


# Assessment approvals
@admin_bp.route('/assessment-approvals')
@login_required
@admin_required
def assessment_approvals():
    """View and approve assessment scores"""
    # Get filters from request
    subject_id = request.args.get('subject_id')
    class_id = request.args.get('class_id')
    term_id = request.args.get('term_id')
    status = request.args.get('status', 'pending')  # pending, approved, all
    
    # Build query
    query = db.session.query(StudentAssessment).join(
        Student, StudentAssessment.student_id == Student.id
    ).join(
        Subject, StudentAssessment.subject_id == Subject.id
    ).join(
        ClassRoom, StudentAssessment.class_id == ClassRoom.id
    ).join(
        AcademicTerm, StudentAssessment.term_id == AcademicTerm.id
    )
    
    # Apply filters
    if subject_id:
        query = query.filter(StudentAssessment.subject_id == subject_id)
    if class_id:
        query = query.filter(StudentAssessment.class_id == class_id)
    if term_id:
        query = query.filter(StudentAssessment.term_id == term_id)
    
    if status == 'pending':
        query = query.filter(StudentAssessment.is_approved == False)
    elif status == 'approved':
        query = query.filter(StudentAssessment.is_approved == True)
    
    # Get results
    student_assessments = query.order_by(
        StudentAssessment.entered_at.desc()
    ).all()
    
    # Get filter options
    subjects = Subject.query.filter_by(is_active=True).order_by(Subject.name).all()
    classes = ClassRoom.query.order_by(ClassRoom.name).all()
    terms = AcademicTerm.query.filter_by(is_active=True).first()
    
    # Calculate statistics
    total = len(student_assessments)
    pending = len([sa for sa in student_assessments if not sa.is_approved])
    approved = len([sa for sa in student_assessments if sa.is_approved])
    
    return render_template('admin/assessment_approvals.html',
                         student_assessments=student_assessments,
                         subjects=subjects,
                         classes=classes,
                         terms=terms,
                         current_filters={
                             'subject_id': subject_id,
                             'class_id': class_id,
                             'term_id': term_id,
                             'status': status
                         },
                         stats={
                             'total': total,
                             'pending': pending,
                             'approved': approved
                         })


@admin_bp.route('/approve-assessment/<assessment_id>', methods=['POST'])
@login_required
@admin_required
def approve_assessment(assessment_id):
    """Approve a student assessment"""
    try:
        data = request.get_json()
        action = data.get('action')  # approve or reject
        comment = data.get('comment', '')
        
        student_assessment = StudentAssessment.query.get_or_404(assessment_id)
        
        if action == 'approve':
            student_assessment.is_approved = True
            student_assessment.approved_by = current_user.id
            student_assessment.approved_at = datetime.now(timezone.utc)
            
            # Log the approval
            audit_log = AuditLog(
                user_id=current_user.id,
                action='APPROVE_ASSESSMENT',
                table_name='student_assessments',
                record_id=assessment_id,
                new_values={
                    'assessment_id': assessment_id,
                    'student_id': student_assessment.student_id,
                    'subject_id': student_assessment.subject_id,
                    'comment': comment
                },
                ip_address=request.remote_addr
            )
            db.session.add(audit_log)
            
            message = 'Assessment approved successfully!'
        elif action == 'reject':
            # For rejection, we might want to unapprove and add comment
            student_assessment.is_approved = False
            student_assessment.comment = comment  # Add comment field to model if needed
            
            # Log the rejection
            audit_log = AuditLog(
                user_id=current_user.id,
                action='REJECT_ASSESSMENT',
                table_name='student_assessments',
                record_id=assessment_id,
                new_values={
                    'assessment_id': assessment_id,
                    'student_id': student_assessment.student_id,
                    'subject_id': student_assessment.subject_id,
                    'comment': comment
                },
                ip_address=request.remote_addr
            )
            db.session.add(audit_log)
            
            message = 'Assessment rejected successfully!'
        else:
            return jsonify({'success': False, 'message': 'Invalid action'}), 400
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': message
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"Error approving assessment: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 400


@admin_bp.route('/bulk-approve-assessments', methods=['POST'])
@login_required
@admin_required
def bulk_approve_assessments():
    """Bulk approve multiple assessments"""
    try:
        data = request.get_json()
        assessment_ids = data.get('assessment_ids', [])
        action = data.get('action')  # approve or reject
        comment = data.get('comment', '')
        
        if not assessment_ids:
            return jsonify({'success': False, 'message': 'No assessments selected'}), 400
        
        approved_count = 0
        rejected_count = 0
        
        for assessment_id in assessment_ids:
            student_assessment = StudentAssessment.query.get(assessment_id)
            if student_assessment:
                if action == 'approve':
                    student_assessment.is_approved = True
                    student_assessment.approved_by = current_user.id
                    student_assessment.approved_at = datetime.now(timezone.utc)
                    approved_count += 1
                elif action == 'reject':
                    student_assessment.is_approved = False
                    student_assessment.comment = comment
                    rejected_count += 1
        
        # Log bulk action
        audit_log = AuditLog(
            user_id=current_user.id,
            action=f'BULK_{action.upper()}_ASSESSMENTS',
            table_name='student_assessments',
            details={
                'assessment_ids': assessment_ids,
                'count': len(assessment_ids),
                'comment': comment
            },
            ip_address=request.remote_addr
        )
        db.session.add(audit_log)
        
        db.session.commit()
        
        message = f"Successfully {action}d {len(assessment_ids)} assessments!"
        return jsonify({
            'success': True,
            'message': message,
            'approved_count': approved_count,
            'rejected_count': rejected_count
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"Error in bulk approval: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 400

@admin_bp.route('/assessment-details/<assessment_id>')
@login_required
@admin_required
def assessment_details(assessment_id):
    """Get detailed view of an assessment"""
    student_assessment = StudentAssessment.query.get_or_404(assessment_id)
    terms = AcademicTerm.query.filter_by(is_active=True).first()
    
    # Get assessment objects for each score
    assessment_details = []
    for assessment_id, score in student_assessment.assessment_scores.items():
        assessment = Assessment.query.get(assessment_id)
        if assessment:
            assessment_details.append({
                'assessment': assessment,
                'score': score
            })
    
    # Render template string
    html = render_template('admin/assessment_details.html',
                         student_assessment=student_assessment,
                         terms=terms,
                         assessment_details=assessment_details)
    
    return jsonify({
        'success': True,
        'html': html
    })




































@admin_bp.route('/database/export', methods=['GET'])
def export_database():
    """Export all database tables to CSV"""
    try:
        import csv
        import io
        import zipfile
        from datetime import datetime
        
        # Create a timestamp for the filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Create a zip file in memory
        zip_buffer = io.BytesIO()
        
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            
            # List of all models to export
            models_to_export = [
                ('users', User),
                ('students', Student),
                ('teachers', Teacher),
                ('parents', Parent),
                ('student_parents', StudentParent),
                ('academic_sessions', AcademicSession),
                ('academic_terms', AcademicTerm),
                ('classrooms', ClassRoom),
                ('subjects', Subject),
                ('subject_assignments', SubjectAssignment),
                ('assessments', Assessment),
                ('student_assessments', StudentAssessment),
                ('assessment_score_mappings', AssessmentScoreMapping),
                ('exams', Exam),
                ('exam_questions', ExamQuestion),
                ('exam_sessions', ExamSession),
                ('exam_responses', ExamResponse),
                ('exam_results', ExamResult),
                ('question_banks', QuestionBank),
                ('attendance', Attendance),
                ('domain_evaluations', DomainEvaluation),
                ('teacher_comments', TeacherComment),
                ('form_teacher_comments', FormTeacherComment),
                ('principal_remarks', PrincipalRemark),
                ('report_cards', ReportCard),
                ('parent_notifications', ParentNotification),
                ('student_promotions', StudentPromotion),
                ('grade_scales', GradeScale),
                ('subject_categories', SubjectCategory),
                ('system_configuration', SystemConfiguration),
                ('audit_logs', AuditLog),
                ('security_logs', SecurityLog),
                ('login_attempts', LoginAttempt),
                ('learning_materials', LearningMaterial),
                ('student_material_downloads', StudentMaterialDownload),
                ('exam_question_analysis', ExamQuestionAnalysis),
                ('student_performance_analysis', StudentPerformanceAnalysis),
                ('teacher_reports', TeacherReport)
            ]
            
            for table_name, model in models_to_export:
                try:
                    # Query all records
                    records = model.query.all()
                    
                    if not records:
                        # Create empty CSV with headers
                        output = io.StringIO()
                        
                        # Try to get column names from model
                        if hasattr(model, '__table__'):
                            columns = [col.name for col in model.__table__.columns]
                        else:
                            columns = ['id']  # Fallback
                        
                        writer = csv.DictWriter(output, fieldnames=columns)
                        writer.writeheader()
                        
                        # Add to zip
                        zip_file.writestr(f'{table_name}.csv', output.getvalue())
                        output.close()
                        continue
                    
                    # Create CSV in memory
                    output = io.StringIO()
                    
                    # Get column names from first record
                    if hasattr(records[0], '__table__'):
                        columns = [col.name for col in records[0].__table__.columns]
                    else:
                        # Fallback to using dict keys
                        sample_dict = records[0].__dict__
                        columns = [key for key in sample_dict.keys() if not key.startswith('_')]
                    
                    writer = csv.DictWriter(output, fieldnames=columns)
                    writer.writeheader()
                    
                    # Write records
                    for record in records:
                        row = {}
                        for column in columns:
                            value = getattr(record, column, '')
                            
                            # Handle different data types
                            if value is None:
                                row[column] = ''
                            elif isinstance(value, (datetime)):
                                row[column] = value.isoformat()
                            elif isinstance(value, (date)):
                                row[column] = value.isoformat()
                            elif isinstance(value, (dict, list)):
                                import json
                                row[column] = json.dumps(value)
                            else:
                                row[column] = str(value)
                        
                        writer.writerow(row)
                    
                    # Add to zip
                    zip_file.writestr(f'{table_name}.csv', output.getvalue())
                    output.close()
                    
                except Exception as e:
                    # Log error but continue with other tables
                    print(f"Error exporting {table_name}: {str(e)}")
                    # Create error file
                    zip_file.writestr(f'{table_name}_ERROR.txt', 
                                     f"Error exporting {table_name}: {str(e)}")
            
            # Add metadata file
            metadata = f"""Database Export
Generated: {datetime.now().isoformat()}
Generated By: {current_user.username} (ID: {current_user.id})
Total Tables: {len(models_to_export)}

This export contains all database tables in CSV format.
Each table is exported as a separate CSV file.
JSON fields are exported as JSON strings.
"""
            zip_file.writestr('export_metadata.txt', metadata)
        
        # Prepare zip for download
        zip_buffer.seek(0)
        
        # Log export action
        audit_log = AuditLog(
            user_id=current_user.id,
            action='EXPORT_DATABASE',
            details={
                'tables_exported': len(models_to_export),
                'filename': f'database_export_{timestamp}.zip'
            },
            ip_address=request.remote_addr
        )
        db.session.add(audit_log)
        db.session.commit()
        
        # Return zip file
        return Response(
            zip_buffer.getvalue(),
            mimetype='application/zip',
            headers={
                'Content-Disposition': f'attachment;filename=database_export_{timestamp}.zip',
                'Content-Type': 'application/zip'
            }
        )
    
    except Exception as e:
        print(f"Error exporting database: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'Error exporting database: {str(e)}'
        }), 500


@admin_bp.route('/database/export/json', methods=['GET'])
def export_database_json():
    """Export all database tables as JSON"""
    try:
        import json
        import zipfile
        import io
        from datetime import datetime
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        zip_buffer = io.BytesIO()
        
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            
            # Same list of models as above
            models_to_export = [
                ('users', User),
                ('students', Student),
                ('teachers', Teacher),
                ('parents', Parent),
                ('student_parents', StudentParent),
                ('academic_sessions', AcademicSession),
                ('academic_terms', AcademicTerm),
                ('classrooms', ClassRoom),
                ('subjects', Subject),
                ('subject_assignments', SubjectAssignment),
                ('assessments', Assessment),
                ('student_assessments', StudentAssessment),
                ('assessment_score_mappings', AssessmentScoreMapping),
                ('exams', Exam),
                ('exam_questions', ExamQuestion),
                ('exam_sessions', ExamSession),
                ('exam_responses', ExamResponse),
                ('exam_results', ExamResult),
                ('question_banks', QuestionBank),
                ('attendance', Attendance),
                ('domain_evaluations', DomainEvaluation),
                ('teacher_comments', TeacherComment),
                ('form_teacher_comments', FormTeacherComment),
                ('principal_remarks', PrincipalRemark),
                ('report_cards', ReportCard),
                ('parent_notifications', ParentNotification),
                ('student_promotions', StudentPromotion),
                ('grade_scales', GradeScale),
                ('subject_categories', SubjectCategory),
                ('system_configuration', SystemConfiguration),
                ('audit_logs', AuditLog),
                ('security_logs', SecurityLog),
                ('login_attempts', LoginAttempt),
                ('learning_materials', LearningMaterial),
                ('student_material_downloads', StudentMaterialDownload),
                ('exam_question_analysis', ExamQuestionAnalysis),
                ('student_performance_analysis', StudentPerformanceAnalysis),
                ('teacher_reports', TeacherReport)
            ]
            
            all_data = {}
            
            for table_name, model in models_to_export:
                try:
                    records = model.query.all()
                    table_data = []
                    
                    for record in records:
                        record_dict = {}
                        
                        # Get all columns
                        if hasattr(record, '__table__'):
                            columns = [col.name for col in record.__table__.columns]
                        else:
                            columns = [key for key in record.__dict__.keys() if not key.startswith('_')]
                        
                        for column in columns:
                            value = getattr(record, column, None)
                            
                            # Handle different data types
                            if value is None:
                                record_dict[column] = None
                            elif isinstance(value, (datetime, date)):
                                record_dict[column] = value.isoformat()
                            elif isinstance(value, (dict, list)):
                                record_dict[column] = value
                            else:
                                try:
                                    # Try to convert to appropriate type
                                    record_dict[column] = value
                                except:
                                    record_dict[column] = str(value)
                        
                        table_data.append(record_dict)
                    
                    all_data[table_name] = table_data
                    
                except Exception as e:
                    all_data[table_name] = {'error': str(e)}
            
            # Add metadata
            all_data['_metadata'] = {
                'generated_at': datetime.now().isoformat(),
                'generated_by': current_user.username,
                'generated_by_id': current_user.id,
                'total_tables': len(models_to_export)
            }
            
            # Write JSON file
            json_data = json.dumps(all_data, indent=2, default=str)
            zip_file.writestr('database_export.json', json_data)
            
            # Add metadata file
            metadata = f"""JSON Database Export
Generated: {datetime.now().isoformat()}
Generated By: {current_user.username} (ID: {current_user.id})
Total Tables: {len(models_to_export)}

This export contains all database tables in a single JSON file.
The file is structured with table names as keys and arrays of records as values.
"""
            zip_file.writestr('export_metadata.txt', metadata)
        
        zip_buffer.seek(0)
        
        # Log export action
        audit_log = AuditLog(
            user_id=current_user.id,
            action='EXPORT_DATABASE_JSON',
            details={
                'tables_exported': len(models_to_export),
                'filename': f'database_export_{timestamp}.zip'
            },
            ip_address=request.remote_addr
        )
        db.session.add(audit_log)
        db.session.commit()
        
        return Response(
            zip_buffer.getvalue(),
            mimetype='application/zip',
            headers={
                'Content-Disposition': f'attachment;filename=database_export_{timestamp}.zip',
                'Content-Type': 'application/zip'
            }
        )
    
    except Exception as e:
        print(f"Error exporting database as JSON: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'Error exporting database: {str(e)}'
        }), 500


@admin_bp.route('/database/export/single-csv', methods=['GET'])
def export_database_single_csv():
    """Export all database tables as a single CSV file (for viewing in spreadsheet apps)"""
    try:
        import csv
        import io
        from datetime import datetime
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output = io.StringIO()
        
        # Same list of models
        models_to_export = [
            ('users', User),
            ('students', Student),
            ('teachers', Teacher),
            ('parents', Parent),
            ('academic_sessions', AcademicSession),
            ('academic_terms', AcademicTerm),
            ('classrooms', ClassRoom),
            ('subjects', Subject),
            ('assessments', Assessment),
            ('exams', Exam),
            ('attendance', Attendance),
            ('audit_logs', AuditLog)
        ]
        
        for table_name, model in models_to_export:
            try:
                # Write table header
                output.write(f"\n\n--- {table_name.upper()} ---\n")
                
                records = model.query.all()
                if not records:
                    output.write("No records found\n")
                    continue
                
                # Get column names
                if hasattr(records[0], '__table__'):
                    columns = [col.name for col in records[0].__table__.columns]
                else:
                    columns = [key for key in records[0].__dict__.keys() if not key.startswith('_')]
                
                # Write headers
                output.write(','.join(columns) + '\n')
                
                # Write records
                for record in records:
                    row = []
                    for column in columns:
                        value = getattr(record, column, '')
                        
                        if value is None:
                            row.append('')
                        elif isinstance(value, (datetime, date)):
                            row.append(value.isoformat())
                        elif isinstance(value, (dict, list)):
                            import json
                            row.append(json.dumps(value))
                        else:
                            # Escape commas and quotes for CSV
                            str_value = str(value)
                            if ',' in str_value or '"' in str_value or '\n' in str_value:
                                str_value = '"' + str_value.replace('"', '""') + '"'
                            row.append(str_value)
                    
                    output.write(','.join(row) + '\n')
                
            except Exception as e:
                output.write(f"Error exporting {table_name}: {str(e)}\n")
        
        # Log export action
        audit_log = AuditLog(
            user_id=current_user.id,
            action='EXPORT_DATABASE_SINGLE_CSV',
            ip_address=request.remote_addr
        )
        db.session.add(audit_log)
        db.session.commit()
        
        # Return CSV file
        output.seek(0)
        return Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={
                'Content-Disposition': f'attachment;filename=database_export_{timestamp}.csv',
                'Content-Type': 'text/csv'
            }
        )
    
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error exporting database: {str(e)}'
        }), 500





















@admin_bp.route('/database/import', methods=['POST'])
@login_required
@admin_required
def import_database():
    """Import database data from uploaded CSV/ZIP files"""
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'message': 'No file uploaded'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'success': False, 'message': 'No file selected'}), 400
        
        # Get import options
        import_mode = request.form.get('import_mode', 'safe')  # 'safe', 'overwrite', 'update'
        clear_existing = request.form.get('clear_existing', 'false').lower() == 'true'
        
        # Validate file extension
        filename = file.filename.lower()
        is_zip = filename.endswith('.zip')
        is_csv = filename.endswith('.csv')
        
        if not (is_zip or is_csv):
            return jsonify({
                'success': False, 
                'message': 'Invalid file type. Please upload a CSV or ZIP file.'
            }), 400
        
        # Track import results
        results = {
            'success': True,
            'tables_processed': 0,
            'records_created': 0,
            'records_updated': 0,
            'records_skipped': 0,
            'errors': [],
            'tables': {}
        }
        
        if is_zip:
            # Process ZIP file
            import zipfile
            import io
            
            zip_data = io.BytesIO(file.read())
            
            with zipfile.ZipFile(zip_data, 'r') as zip_file:
                # Get list of CSV files in zip
                csv_files = [f for f in zip_file.namelist() if f.endswith('.csv')]
                
                for csv_file in csv_files:
                    try:
                        # Extract table name from filename (remove .csv)
                        table_name = csv_file.replace('.csv', '')
                        
                        # Read CSV content
                        with zip_file.open(csv_file) as f:
                            content = f.read().decode('utf-8')
                            table_results = process_csv_import(
                                table_name, 
                                content, 
                                import_mode,
                                clear_existing
                            )
                            
                            results['tables'][table_name] = table_results
                            results['records_created'] += table_results.get('created', 0)
                            results['records_updated'] += table_results.get('updated', 0)
                            results['records_skipped'] += table_results.get('skipped', 0)
                            results['tables_processed'] += 1
                            
                            if table_results.get('errors'):
                                results['errors'].extend(table_results['errors'])
                                
                    except Exception as e:
                        error_msg = f"Error processing {csv_file}: {str(e)}"
                        results['errors'].append(error_msg)
                        results['tables'][csv_file] = {'error': error_msg}
        
        elif is_csv:
            # Process single CSV file
            content = file.read().decode('utf-8')
            
            # Try to determine table name from filename or content
            table_name = filename.replace('.csv', '')
            table_results = process_csv_import(table_name, content, import_mode, clear_existing)
            
            results['tables'][table_name] = table_results
            results['records_created'] += table_results.get('created', 0)
            results['records_updated'] += table_results.get('updated', 0)
            results['records_skipped'] += table_results.get('skipped', 0)
            results['tables_processed'] = 1
            
            if table_results.get('errors'):
                results['errors'].extend(table_results['errors'])
        
        # Log import action
        audit_log = AuditLog(
            user_id=current_user.id,
            action='IMPORT_DATABASE',
            details={
                'filename': file.filename,
                'import_mode': import_mode,
                'tables_processed': results['tables_processed'],
                'records_created': results['records_created'],
                'records_updated': results['records_updated'],
                'records_skipped': results['records_skipped'],
                'errors': len(results['errors'])
            },
            ip_address=request.remote_addr
        )
        db.session.add(audit_log)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Import completed. {results["records_created"]} created, {results["records_updated"]} updated, {results["records_skipped"]} skipped.',
            'results': results
        })
    
    except Exception as e:
        db.session.rollback()
        print(f"Error importing database: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'Error importing database: {str(e)}'
        }), 500


def process_csv_import(table_name, csv_content, import_mode='safe', clear_existing=False):
    """Process a single CSV file import"""
    import csv
    import io
    import json
    from datetime import datetime, date
    
    results = {
        'created': 0,
        'updated': 0,
        'skipped': 0,
        'errors': [],
        'table': table_name
    }
    
    # Map table names to models
    model_map = {
        'users': User,
        'students': Student,
        'teachers': Teacher,
        'parents': Parent,
        'student_parents': StudentParent,
        'academic_sessions': AcademicSession,
        'academic_terms': AcademicTerm,
        'classrooms': ClassRoom,
        'subjects': Subject,
        'subject_assignments': SubjectAssignment,
        'assessments': Assessment,
        'student_assessments': StudentAssessment,
        'assessment_score_mappings': AssessmentScoreMapping,
        'exams': Exam,
        'exam_questions': ExamQuestion,
        'exam_sessions': ExamSession,
        'exam_responses': ExamResponse,
        'exam_results': ExamResult,
        'question_banks': QuestionBank,
        'attendance': Attendance,
        'domain_evaluations': DomainEvaluation,
        'teacher_comments': TeacherComment,
        'form_teacher_comments': FormTeacherComment,
        'principal_remarks': PrincipalRemark,
        'report_cards': ReportCard,
        'parent_notifications': ParentNotification,
        'student_promotions': StudentPromotion,
        'grade_scales': GradeScale,
        'subject_categories': SubjectCategory,
        'system_configuration': SystemConfiguration,
        'audit_logs': AuditLog,
        'security_logs': SecurityLog,
        'login_attempts': LoginAttempt,
        'learning_materials': LearningMaterial,
        'student_material_downloads': StudentMaterialDownload,
        'exam_question_analysis': ExamQuestionAnalysis,
        'student_performance_analysis': StudentPerformanceAnalysis,
        'teacher_reports': TeacherReport
    }
    
    if table_name not in model_map:
        results['errors'].append(f"Unknown table: {table_name}")
        return results
    
    model = model_map[table_name]
    
    try:
        # Parse CSV
        csv_reader = csv.DictReader(io.StringIO(csv_content))
        
        if clear_existing and import_mode != 'safe':
            # Clear existing records (be careful with this!)
            model.query.delete()
            db.session.commit()
        
        for row_num, row in enumerate(csv_reader, start=2):  # Start at 2 for row numbers
            try:
                # Clean and convert data types
                cleaned_data = {}
                for key, value in row.items():
                    if value == '' or value is None:
                        cleaned_data[key] = None
                    else:
                        # Try to detect and convert data types
                        cleaned_data[key] = parse_value(value)
                
                # Check if record exists (by ID)
                record_id = cleaned_data.get('id')
                existing_record = None
                
                if record_id:
                    existing_record = model.query.get(record_id)
                
                if existing_record:
                    # Record exists
                    if import_mode == 'safe':
                        # Skip existing records in safe mode
                        results['skipped'] += 1
                        continue
                    elif import_mode == 'update':
                        # Update existing record
                        for key, value in cleaned_data.items():
                            if hasattr(existing_record, key):
                                setattr(existing_record, key, value)
                        results['updated'] += 1
                    elif import_mode == 'overwrite':
                        # Delete and recreate
                        db.session.delete(existing_record)
                        db.session.flush()
                        new_record = model(**cleaned_data)
                        db.session.add(new_record)
                        results['created'] += 1
                else:
                    # Create new record
                    # Handle relationships and special fields
                    new_record = model(**cleaned_data)
                    db.session.add(new_record)
                    results['created'] += 1
                
                # Commit every 100 records to avoid memory issues
                if (results['created'] + results['updated']) % 100 == 0:
                    db.session.commit()
                    
            except Exception as e:
                db.session.rollback()
                results['errors'].append(f"Row {row_num}: {str(e)}")
                results['skipped'] += 1
        
        # Final commit
        db.session.commit()
        
    except Exception as e:
        db.session.rollback()
        results['errors'].append(f"Error processing table {table_name}: {str(e)}")
    
    return results


def parse_value(value):
    """Parse string value to appropriate Python type"""
    if value is None or value == '':
        return None
    
    # Try to parse as JSON
    if value.startswith('{') or value.startswith('['):
        try:
            return json.loads(value)
        except:
            pass
    
    # Try to parse as boolean
    if value.lower() in ('true', 'false', 'yes', 'no'):
        return value.lower() in ('true', 'yes')
    
    # Try to parse as number
    try:
        if '.' in value:
            return float(value)
        else:
            return int(value)
    except:
        pass
    
    # Try to parse as datetime
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00'))
    except:
        pass
    
    # Try to parse as date
    try:
        return date.fromisoformat(value)
    except:
        pass
    
    # Return as string
    return value


@admin_bp.route('/database/import/preview', methods=['POST'])
@login_required
@admin_required
def preview_database_import():
    """Preview database import without actually importing"""
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'message': 'No file uploaded'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'success': False, 'message': 'No file selected'}), 400
        
        filename = file.filename.lower()
        is_zip = filename.endswith('.zip')
        is_csv = filename.endswith('.csv')
        
        if not (is_zip or is_csv):
            return jsonify({'success': False, 'message': 'Invalid file type'}), 400
        
        preview = {
            'filename': file.filename,
            'tables': [],
            'total_records': 0
        }
        
        if is_zip:
            import zipfile
            import io
            
            zip_data = io.BytesIO(file.read())
            
            with zipfile.ZipFile(zip_data, 'r') as zip_file:
                csv_files = [f for f in zip_file.namelist() if f.endswith('.csv')]
                
                for csv_file in csv_files:
                    table_name = csv_file.replace('.csv', '')
                    
                    with zip_file.open(csv_file) as f:
                        content = f.read().decode('utf-8')
                        csv_reader = csv.DictReader(io.StringIO(content))
                        
                        rows = list(csv_reader)
                        preview['tables'].append({
                            'name': table_name,
                            'records': len(rows),
                            'columns': csv_reader.fieldnames
                        })
                        preview['total_records'] += len(rows)
        
        elif is_csv:
            content = file.read().decode('utf-8')
            csv_reader = csv.DictReader(io.StringIO(content))
            
            rows = list(csv_reader)
            preview['tables'].append({
                'name': filename.replace('.csv', ''),
                'records': len(rows),
                'columns': csv_reader.fieldnames
            })
            preview['total_records'] += len(rows)
        
        return jsonify({
            'success': True,
            'preview': preview
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error previewing import: {str(e)}'
        }), 500





































