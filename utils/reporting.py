# app/utils/reporting.py
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from models import db, Student, ExamResult, TeacherComment, FormTeacherComment, DomainEvaluation, ReportCard
import os
from datetime import datetime, timezone, timedelta

from flask import current_app

def generate_report_card(student_id, term, academic_year, generated_by):
    """Generate a single report card"""
    student = Student.query.get_or_404(student_id)
    
    # Get results for the term
    results = ExamResult.query.filter_by(
        student_id=student_id,
        term=term,
        academic_year=academic_year
    ).all()
    
    # Get teacher comments
    teacher_comments = TeacherComment.query.filter_by(
        student_id=student_id,
        term=term,
        academic_year=academic_year
    ).all()
    
    # Get form teacher comment
    form_comment = FormTeacherComment.query.filter_by(
        student_id=student_id,
        term=term,
        academic_year=academic_year
    ).first()
    
    # Get domain evaluations
    domain_evaluations = DomainEvaluation.query.filter_by(
        student_id=student_id,
        term=term,
        academic_year=academic_year
    ).all()
    
    # Create PDF
    filename = f"report_{student.admission_number}_T{term}_{academic_year}.pdf"
    filepath = os.path.join(current_app.config['REPORT_FOLDER'], filename)
    
    doc = SimpleDocTemplate(filepath, pagesize=landscape(letter))
    elements = []
    
    # Title
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        spaceAfter=30,
        alignment=1  # Center
    )
    
    elements.append(Paragraph("ARNDALE ACADEMY", title_style))
    elements.append(Paragraph("STUDENT REPORT CARD", title_style))
    elements.append(Spacer(1, 20))
    
    # Student Information
    student_info = [
        ['Student Name:', f"{student.last_name.upper()}, {student.first_name} {student.middle_name or ''}"],
        ['Admission Number:', student.admission_number],
        ['Class:', student.class_rel.name if student.class_rel else 'N/A'],
        ['Term:', str(term)],
        ['Academic Year:', academic_year]
    ]
    
    student_table = Table(student_info, colWidths=[2*inch, 4*inch])
    student_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.grey),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.whitesmoke),
        ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 12),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ('BACKGROUND', (1, 0), (1, -1), colors.beige),
    ]))
    
    elements.append(student_table)
    elements.append(Spacer(1, 20))
    
    # Academic Results Table
    if results:
        results_data = [['Subject', 'CA Score', 'Exam Score', 'Total', 'Grade', 'Position', 'Remark']]
        
        for result in results:
            results_data.append([
                result.subject.name,
                f"{result.ca_score:.1f}" if result.ca_score else '-',
                f"{result.exam_score:.1f}",
                f"{result.total_score:.1f}" if result.total_score else '-',
                result.grade or '-',
                f"{result.position_in_class}" if result.position_in_class else '-',
                result.remark or '-'
            ])
        
        results_table = Table(results_data, colWidths=[1.5*inch, 0.8*inch, 0.8*inch, 0.8*inch, 0.6*inch, 0.8*inch, 1.5*inch])
        results_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('ALIGN', (1, 1), (3, -1), 'CENTER'),
        ]))
        
        elements.append(results_table)
        elements.append(Spacer(1, 20))
    
    # Domain Evaluations
    if domain_evaluations:
        elements.append(Paragraph("DOMAIN EVALUATIONS", styles['Heading2']))
        
        domain_data = [['Domain', 'Criteria', 'Rating', 'Comments']]
        for eval in domain_evaluations:
            domain_data.append([
                eval.domain_type,
                eval.criteria,
                str(eval.rating),
                eval.comments or ''
            ])
        
        domain_table = Table(domain_data, colWidths=[1.5*inch, 2.5*inch, 0.8*inch, 3*inch])
        domain_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
        ]))
        
        elements.append(domain_table)
        elements.append(Spacer(1, 20))
    
    # Comments Section
    elements.append(Paragraph("COMMENTS", styles['Heading2']))
    
    # Teacher Comments
    if teacher_comments:
        for comment in teacher_comments:
            elements.append(Paragraph(f"<b>{comment.subject.name}:</b> {comment.comment}", styles['Normal']))
    
    # Form Teacher Comment
    if form_comment:
        elements.append(Spacer(1, 10))
        elements.append(Paragraph(f"<b>Form Teacher's Comment:</b> {form_comment.comment}", styles['Normal']))
    
    # Build PDF
    doc.build(elements)
    
    # Save report card record
    report = ReportCard(
        student_id=student_id,
        term=term,
        academic_year=academic_year,
        file_path=filepath,
        generated_by=generated_by,
        generated_at=datetime.utcnow()
    )
    
    db.session.add(report)
    db.session.commit()
    
    return report

def generate_class_report_cards(class_id, term, academic_year, generated_by):
    """Generate report cards for all students in a class"""
    students = Student.query.filter_by(
        current_class_id=class_id,
        is_active=True
    ).all()
    
    generated_count = 0
    for student in students:
        try:
            generate_report_card(student.id, term, academic_year, generated_by)
            generated_count += 1
        except Exception as e:
            print(f"Error generating report for student {student.id}: {e}")
            continue
    
    return generated_count