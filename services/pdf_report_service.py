import os
import io
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from reportlab.lib.pagesizes import letter, A4, landscape
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, 
    Image, PageBreak, HRFlowable, KeepTogether
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


class PDFReportService:
    """
    Enhanced PDF Report Service matching The Regent Secondary School design
    with improved styling, colors, and layout
    """
    
    def __init__(self, app_root_path: str):
        self.app_root_path = app_root_path
        self.fonts_registered = False
        self._register_fonts()
        
        # Enhanced color scheme matching the reference design
        self.colors = {
            'primary_blue': colors.HexColor('#1e5ba8'),  # Rich blue for headers
            'header_bg': colors.HexColor('#2563eb'),     # Bright blue for table headers
            'light_blue': colors.HexColor('#dbeafe'),    # Light blue for alternating rows
            'dark_gray': colors.HexColor('#1f2937'),     # Dark gray for text
            'medium_gray': colors.HexColor('#4b5563'),   # Medium gray
            'light_gray': colors.HexColor('#f3f4f6'),    # Light gray background
            'border_gray': colors.HexColor('#d1d5db'),   # Border color
            'white': colors.white,
            'orange': colors.HexColor('#f97316'),        # Orange accent
            'green': colors.HexColor('#10b981'),         # Success green
            'red': colors.HexColor('#ef4444'),           # Warning red
        }
        
    def _register_fonts(self):
        """Register custom fonts if available"""
        try:
            font_paths = [
                '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
                '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
                '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf',
                'C:/Windows/Fonts/arial.ttf',
                '/System/Library/Fonts/Helvetica.ttf'
            ]
            
            for font_path in font_paths:
                if os.path.exists(font_path):
                    pdfmetrics.registerFont(TTFont('CustomFont', font_path))
                    self.fonts_registered = True
                    break
        except Exception as e:
            print(f"Font registration warning: {e}")
    
    def generate_report_card(self, student_data: Dict, term_data: Dict, 
                           academic_data: List[Dict], comments: Dict, 
                           school_info: Dict, grade_scales: List[Dict]) -> bytes:
        """
        Generate a professional report card PDF matching the reference design
        
        Args:
            student_data: Student information
            term_data: Term information
            academic_data: Academic performance data for each subject
            comments: Teacher and principal comments
            school_info: School information
            grade_scales: List of grade scale dictionaries from GradeScale model
        """
        buffer = io.BytesIO()
        
        # Create PDF document in LANDSCAPE orientation
        doc = SimpleDocTemplate(
            buffer,
            pagesize=landscape(A4),
            rightMargin=15,
            leftMargin=15,
            topMargin=15,
            bottomMargin=20
        )
        
        # Build story (content)
        story = []
        
        # Add school header with logo
        story.extend(self._create_enhanced_school_header(school_info))
        
        # Add term report title
        story.extend(self._create_term_title(term_data))
        
        # Add student details section - pass grade_scales for calculations
        story.extend(self._create_student_details_section(student_data, term_data, academic_data, grade_scales))
        
        # Add main academic performance table
        story.extend(self._create_main_academic_table(student_data, academic_data, grade_scales))
        
        # Add summary statistics bar
        story.extend(self._create_summary_bar(academic_data))
        
        # Add grading information section - now uses grade_scales from database
        story.extend(self._create_grading_information_section(grade_scales))
        
        # Add comments section
        story.extend(self._create_enhanced_comments_section(comments))
        
        # Add consultation info
        story.extend(self._create_consultation_section())
        
        # Add signature section
        story.extend(self._create_signature_section(school_info, term_data))
        
        # Build PDF with custom page template
        doc.build(story, onFirstPage=self._add_page_footer, onLaterPages=self._add_page_footer)
        
        # Get PDF bytes
        buffer.seek(0)
        return buffer.getvalue()
    
    def _calculate_grade(self, score: float, grade_scales: List[Dict]) -> Tuple[str, str, float]:
        """
        Calculate grade, remark, and point based on score using grade_scales
        
        Args:
            score: Numeric score
            grade_scales: List of grade scale dictionaries
            
        Returns:
            Tuple of (grade, remark, point)
        """
        for grade_scale in grade_scales:
            if grade_scale['min_score'] <= score <= grade_scale['max_score']:
                return grade_scale['grade'], grade_scale['remark'], grade_scale['point']
        
        # Default if no grade found
        return 'F', 'Fail', 0.0
    
    def _get_grade_scales_for_year(self, student_year: str, all_grade_scales: List[Dict]) -> List[Dict]:
        """
        Get grade scales specific to student's year level
        """
        # Filter active grade scales
        active_scales = [scale for scale in all_grade_scales if scale.get('is_active', True)]
        
        # You can implement year-specific logic here if needed
        # For now, return all active scales
        return active_scales
    
    def _create_enhanced_school_header(self, school_info: Dict) -> List:
        """Create enhanced school header with logo on the right side - compact version"""
        elements = []
        
        # School name style - smaller font
        school_name_style = ParagraphStyle(
            'SchoolName',
            parent=getSampleStyleSheet()['Title'],
            fontSize=18,  # Reduced from 24
            textColor=colors.HexColor('#1e3a8a'),
            fontName='Times-Bold',
            alignment=TA_RIGHT,
            spaceAfter=1  # Reduced from 2
        )
        
        # Address and contact style - smaller font
        contact_style = ParagraphStyle(
            'Contact',
            fontSize=8,  # Reduced from 9
            textColor=colors.HexColor('#4b5563'),
            alignment=TA_RIGHT,
            spaceAfter=0
        )
        
        # Get school info
        school_name = school_info.get('name', 'ARNDALE ACADEMY')
        address = school_info.get('address', 'Plot 647 CADASTAL ZONE CO7 Karmo, Abuja')
        phone = school_info.get('phone', '08166656369')
        logo_path = school_info.get('logo_path', None)
        
        # Create a table with 2 columns
        header_data = []
        
        # Left column: School info
        school_info_cell = Table([
            [Paragraph(school_name, school_name_style)],
            [Paragraph(address, contact_style)],
            [Paragraph(f"Tel: {phone}", contact_style)]
        ], colWidths=[6.5*inch])
        
        # Right column: Smaller logo
        if logo_path and os.path.exists(logo_path):
            # Use actual logo with smaller size
            logo = Image(logo_path, width=0.8*inch, height=0.8*inch)  # Reduced from 1.0 inch
        else:
            # Create a smaller logo placeholder
            logo_placeholder = Paragraph(
                "[LOGO]",
                ParagraphStyle(
                    'LogoPlaceholder',
                    fontSize=10,  # Smaller
                    textColor=colors.HexColor('#cccccc'),
                    alignment=TA_CENTER,
                    fontName='Helvetica-Bold'
                )
            )
            logo = logo_placeholder
        
        # Create table row
        header_data.append([
            school_info_cell,
            logo
        ])
        
        # Create header table with adjusted widths
        header_table = Table(header_data, colWidths=[6.5*inch, 1.0*inch])  # Adjusted widths
        header_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),  # Changed to TOP to reduce height
            ('ALIGN', (0, 0), (0, 0), 'LEFT'),
            ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),  # Remove extra padding
            ('TOPPADDING', (0, 0), (-1, -1), 0),  # Remove extra padding
        ]))
        
        elements.append(header_table)
        elements.append(Spacer(1, 5))  # Reduced from 8
        
        # Add decorative line
        elements.append(HRFlowable(
            width="100%", 
            thickness=1, 
            color=colors.HexColor('#1e40af'),
            spaceBefore=2,  # Reduced
            spaceAfter=2,  # Reduced
            hAlign='CENTER'
        ))
        
        return elements
    
    def _create_term_title(self, term_data: Dict) -> List:
        """Create term report title with blue background"""
        elements = []
        
        # Create title bar
        academic_year = term_data.get('academic_year', '2025/2026')
        term_name = term_data.get('term_name', '1')
        
        title_text = f"{academic_year.upper()} {term_name.upper()} TERM REPORT"
        
        title_style = ParagraphStyle(
            'TitleBar',
            fontSize=18,
            textColor=colors.white,
            fontName='Times-Bold',
            alignment=TA_CENTER,
            spaceAfter=2,  # Reduced from default
            spaceBefore=0
        )
        
        title_para = Paragraph(title_text, title_style)
        
        # Create table for colored background
        title_table = Table([[title_para]], colWidths=[10.8*inch])
        title_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), self.colors['header_bg']),
            ('TOPPADDING', (0, 0), (-1, -1), 10),  # Increased from 8 to 10
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),  # Increased from 8 to 10
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ]))
        
        elements.append(title_table)
        elements.append(Spacer(1, 4))  # Reduced from 8 to 4
        
        return elements

    def _create_student_details_section(self, student_data: Dict, term_data: Dict, 
                                      academic_data: List[Dict], grade_scales: List[Dict]) -> List:
        """Create student details section with enhanced layout"""
        elements = []
        
        # Calculate total score, points, and subjects for final average
        total_subjects = len(academic_data)
        total_score = sum(s.get('total_score', 0) for s in academic_data)
        final_average = (total_score / total_subjects) if total_subjects > 0 else 0
        
        # Calculate total points based on grade scales
        total_points = 0
        for subject in academic_data:
            score = subject.get('total_score', 0)
            grade, remark, point = self._calculate_grade(score, grade_scales)
            total_points += point
        
        # Calculate GPA
        gpa = (total_points / total_subjects) if total_subjects > 0 else 0
        
        # Create a simpler, more structured table
        label_style = ParagraphStyle('Label', fontSize=9, fontName='Times-Bold')
        value_style = ParagraphStyle('Value', fontSize=9)
        
        # Create header row
        header_style = ParagraphStyle(
            'SectionHeader',
            fontSize=11,
            textColor=colors.white,
            fontName='Times-Bold',
            alignment=TA_LEFT,
        )
        
        # Create the table data with proper structure
        details_data = [
            # Header row
            [Paragraph('STUDENT DETAILS', header_style)],
            
            # Data row 1: Basic info
            [
                Paragraph('Name:', label_style),
                Paragraph(student_data.get('full_name', 'Filippo Ferrari'), value_style),
                Paragraph('Form Teacher:', label_style),
                Paragraph('Form Teacher: ' + student_data.get('form_tutor', 'Mr R. Abiodan'), value_style),
            ],
            
            # Data row 2: Additional info
            [
                Paragraph('Admission No.:', label_style),
                Paragraph(str(student_data.get('admission_number', 'AASTxxxx')), value_style),
                Paragraph('Class:', label_style),
                Paragraph(student_data.get('form_group', 'Class'), value_style),
                Paragraph('Final Average:', label_style),
                Paragraph(f'{final_average:.2f}%', ParagraphStyle('Value', fontSize=9, fontName='Times-Bold')),
                Paragraph('GPA:', label_style),
                Paragraph(f'{gpa:.2f}', ParagraphStyle('Value', fontSize=9, fontName='Times-Bold')),
            ]
        ]
        
        # Calculate column widths - adjusted for additional GPA column
        col_widths = [1.2*inch, 1.8*inch, 1.2*inch, 1.8*inch, 1.2*inch, 0.9*inch, 0.6*inch, 0.9*inch]
        
        details_table = Table(details_data, colWidths=col_widths)
        
        # Apply table styling
        details_table.setStyle(TableStyle([
            # Header row styling
            ('SPAN', (0, 0), (7, 0)),  # Span header across all columns
            ('BACKGROUND', (0, 0), (7, 0), colors.HexColor('#1e3a8a')),  # Dark blue
            ('TEXTCOLOR', (0, 0), (7, 0), colors.white),
            ('ALIGN', (0, 0), (7, 0), 'LEFT'),
            ('TOPPADDING', (0, 0), (7, 0), 6),
            ('BOTTOMPADDING', (0, 0), (7, 0), 6),
            ('LEFTPADDING', (0, 0), (7, 0), 8),
            
            # Data row 1 styling
            ('BACKGROUND', (0, 1), (7, 1), colors.HexColor('#f0f9ff')),  # Light blue
            ('SPAN', (1, 1), (3, 1)),  # Span name column
            ('SPAN', (3, 1), (7, 1)),  # Span teacher column
            ('TOPPADDING', (0, 1), (7, 1), 4),
            ('BOTTOMPADDING', (0, 1), (7, 1), 4),
            
            # Data row 2 styling
            ('BACKGROUND', (0, 2), (7, 2), colors.HexColor('#f0f9ff')),
            ('TOPPADDING', (0, 2), (7, 2), 4),
            ('BOTTOMPADDING', (0, 2), (7, 2), 4),
            
            # Grid lines for data rows
            ('GRID', (0, 1), (7, 1), 0.5, colors.HexColor('#d1d5db')),
            ('GRID', (0, 2), (7, 2), 0.5, colors.HexColor('#d1d5db')),
            
            # Align all cells
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('LEFTPADDING', (0, 1), (-1, -1), 6),
            ('RIGHTPADDING', (0, 1), (-1, -1), 6),
        ]))
        
        elements.append(details_table)
        elements.append(Spacer(1, 10))
        
        return elements
    
    def _create_main_academic_table(self, student_data: Dict, academic_data: List[Dict], 
                                  grade_scales: List[Dict]) -> List:
        """Create the main academic performance table with enhanced styling"""
        elements = []
        
        # Define styles
        header_style = ParagraphStyle(
            'TableHeader',
            fontSize=8,
            textColor=colors.white,
            fontName='Times-Bold',
            alignment=TA_CENTER
        )
        
        subject_style = ParagraphStyle('Subject', fontSize=8, alignment=TA_LEFT)
        cell_center_style = ParagraphStyle('CellCenter', fontSize=8, alignment=TA_CENTER)
        comment_style = ParagraphStyle('Comment', fontSize=7.5, alignment=TA_LEFT)
        
        # Table headers
        if student_data.get('year') == 'Junior Secondary':
            headers = [
                Paragraph('Subject and Subject<br/>Teacher', header_style),
                Paragraph('CA 1<br/>(20%)', header_style),
                Paragraph('CA 2<br/>(20%)', header_style),
                Paragraph('Project<br/>(10%)', header_style),
                Paragraph('Exam Mark (50%)', header_style),
                Paragraph('Term\'s Mark', header_style),
                Paragraph('Grade', header_style),
                Paragraph('Remark', header_style),
                Paragraph('Point', header_style),
                Paragraph('Class Average', header_style),
                Paragraph('Effort', header_style),
                Paragraph('Subject Teacher\'s Comment', header_style)
            ]
        else:
            headers = [
                Paragraph('Subject and Subject<br/>Teacher', header_style),
                Paragraph('CA 1<br/>(15%)', header_style),
                Paragraph('CA 2<br/>(15%)', header_style),
                Paragraph('Project<br/>(10%)', header_style),
                Paragraph('Exam Mark (60%)', header_style),
                Paragraph('Term\'s Mark', header_style),
                Paragraph('Grade', header_style),
                Paragraph('Remark', header_style),
                Paragraph('Point', header_style),
                Paragraph('Class Average', header_style),
                Paragraph('Effort', header_style),
                Paragraph('Subject Teacher\'s Comment', header_style)
            ]
        
        table_data = [headers]
        
        # Process academic data
        for subject in academic_data:
            subject_name = subject.get('subject_name', '')
            teacher_name = subject.get('teacher_name', '')
            total_score = subject.get('total_score', 0)
            
            # Calculate grade, remark, and point based on grade_scales
            grade, remark, point = self._calculate_grade(total_score, grade_scales)
            
            row = [
                Paragraph(f"<b>{subject_name}</b><br/>{teacher_name}", subject_style),
                Paragraph(f"{subject.get('ca1_score', 0):.2f}", cell_center_style),
                Paragraph(f"{subject.get('ca2_score', 0):.2f}", cell_center_style),
                Paragraph(f"{subject.get('project_score', 0):.2f}", cell_center_style),
                Paragraph(f"{subject.get('exam_score', 0):.2f}", cell_center_style),
                Paragraph(f"{total_score:.2f}", cell_center_style),
                Paragraph(grade, cell_center_style),
                Paragraph(remark, ParagraphStyle('Remark', fontSize=7, alignment=TA_CENTER)),
                Paragraph(f"{point:.1f}", cell_center_style),
                Paragraph(f"{subject.get('class_average', 0):.2f}", cell_center_style),
                Paragraph(str(subject.get('effort', '2')), cell_center_style),
                Paragraph(subject.get('comment', ''), comment_style)
            ]
            table_data.append(row)
        
        # Column widths optimized for landscape A4 with additional columns
        col_widths = [
            1.4*inch,   # Subject and teacher
            0.5*inch,   # CA 1
            0.5*inch,   # CA 2
            0.5*inch,   # Project
            0.6*inch,   # Exam Mark
            0.6*inch,   # Term's Mark
            0.5*inch,   # Grade
            0.7*inch,   # Remark
            0.4*inch,   # Point
            0.6*inch,   # Class Average
            0.4*inch,   # Effort
            2.7*inch    # Comment
        ]
        
        academic_table = Table(table_data, colWidths=col_widths, repeatRows=1)
        
        # Enhanced table styling
        style_commands = [
            # Header row
            ('BACKGROUND', (0, 0), (-1, 0), self.colors['header_bg']),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Times-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 8),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            
            # Data rows
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('ALIGN', (1, 1), (-3, -1), 'CENTER'),  # Center numeric columns (except comment)
            ('ALIGN', (0, 1), (0, -1), 'LEFT'),     # Left align subject
            ('ALIGN', (-1, 1), (-1, -1), 'LEFT'),   # Left align comments
            
            # Grid
            ('GRID', (0, 0), (-1, -1), 0.5, self.colors['border_gray']),
            ('LINEBELOW', (0, 0), (-1, 0), 1.5, self.colors['header_bg']),
            
            # Padding
            ('LEFTPADDING', (0, 0), (-1, -1), 3),
            ('RIGHTPADDING', (0, 0), (-1, -1), 3),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ]
        
        # Add alternating row colors and grade-based highlighting
        for i in range(1, len(table_data)):
            if i % 2 == 0:
                style_commands.append(('BACKGROUND', (0, i), (-1, i), self.colors['light_gray']))
            
            # Grade-based highlighting
            if i > 0 and i-1 < len(academic_data):
                total_score = academic_data[i-1].get('total_score', 0)
                grade, _, _ = self._calculate_grade(total_score, grade_scales)
                
                if grade in ['A*', 'A']:
                    style_commands.append(('BACKGROUND', (6, i), (6, i), colors.HexColor('#d1fae5')))
                    style_commands.append(('TEXTCOLOR', (6, i), (6, i), colors.HexColor('#065f46')))
                elif grade == 'F':
                    style_commands.append(('BACKGROUND', (6, i), (6, i), colors.HexColor('#fee2e2')))
                    style_commands.append(('TEXTCOLOR', (6, i), (6, i), colors.HexColor('#991b1b')))
        
        academic_table.setStyle(TableStyle(style_commands))
        elements.append(academic_table)
        elements.append(Spacer(1, 8))
        
        return elements
    
    def _create_summary_bar(self, academic_data: List[Dict]) -> List:
        """Create summary statistics bar"""
        elements = []
        
        # Calculate statistics
        total_subjects = len(academic_data)
        total_score = sum(s.get('total_score', 0) for s in academic_data)
        
        summary_style = ParagraphStyle(
            'Summary',
            fontSize=9,
            textColor=colors.white,
            fontName='Times-Bold',
            alignment=TA_CENTER
        )
        
        summary_data = [[
            Paragraph(f'No. of Subjects: {total_subjects}', summary_style),
            Paragraph(f'Total Marks: {total_score:.0f}', summary_style)
        ]]
        
        summary_table = Table(summary_data, colWidths=[5.4*inch, 5.4*inch])
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, 0), self.colors['primary_blue']),
            ('BACKGROUND', (1, 0), (1, 0), self.colors['orange']),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.white),
        ]))
        
        elements.append(summary_table)
        elements.append(Spacer(1, 10))
        
        return elements
    
    def _create_grading_information_section(self, grade_scales: List[Dict]) -> List:
        """Create comprehensive grading information section using grade_scales from database"""
        elements = []
        
        # Section header
        header_style = ParagraphStyle(
            'InfoHeader',
            fontSize=11,
            textColor=colors.white,
            fontName='Times-Bold',
            alignment=TA_CENTER,
        )
        
        header_para = Paragraph('GRADING SYSTEM INFORMATION', header_style)
        header_table = Table([[header_para]], colWidths=[10.8*inch])
        header_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), self.colors['header_bg']),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        
        elements.append(header_table)
        elements.append(Spacer(1, 5))
        
        # Create two-column layout for Achievement and GPA Calculation
        left_column = self._create_achievement_grades_table(grade_scales)
        right_column = self._create_gpa_calculation_table()
        
        grades_layout = Table(
            [[left_column, right_column]],
            colWidths=[5.4*inch, 5.4*inch]
        )
        grades_layout.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ]))
        
        elements.append(grades_layout)
        elements.append(Spacer(1, 8))
        
        return elements
    
    def _create_achievement_grades_table(self, grade_scales: List[Dict]):
        """Create achievement grades reference table from grade_scales"""
        cell_style = ParagraphStyle('Cell', fontSize=8, alignment=TA_LEFT)
        grade_style = ParagraphStyle('Grade', fontSize=8, fontName='Times-Bold', alignment=TA_CENTER)
        
        # Sort grade scales by min_score (ascending)
        sorted_scales = sorted(grade_scales, key=lambda x: x['min_score'])
        
        # Achievement grades data
        achievement_data = [
            [Paragraph('GRADE SCALE', ParagraphStyle('Header', fontSize=10, fontName='Times-Bold'))],
            [Paragraph('The following grade scale is used to evaluate student performance based on percentage scores achieved in assessments and examinations.', cell_style)],
        ]
        
        # Grade scale table
        grade_table_data = [
            [
                Paragraph('Grade', grade_style),
                Paragraph('Score Range', cell_style),
                Paragraph('Remark', cell_style),
                Paragraph('Point', grade_style)
            ]
        ]
        
        for scale in sorted_scales:
            # Format score range
            if scale['min_score'] == scale['max_score']:
                score_range = f"{scale['min_score']}%"
            else:
                score_range = f"{scale['min_score']}% - {scale['max_score']}%"
            
            grade_table_data.append([
                Paragraph(scale['grade'], grade_style),
                Paragraph(score_range, cell_style),
                Paragraph(scale.get('remark', 'N/A'), cell_style),
                Paragraph(f"{scale.get('point', 0):.1f}", grade_style)
            ])
        
        grade_table = Table(grade_table_data, colWidths=[0.6*inch, 1.2*inch, 2.0*inch, 0.5*inch])
        grade_table.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 0.5, self.colors['border_gray']),
            ('BACKGROUND', (0, 0), (-1, 0), self.colors['light_blue']),  # Header row
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        
        achievement_data.append([grade_table])
        
        achievement_table = Table(achievement_data, colWidths=[5.3*inch])
        achievement_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), self.colors['light_blue']),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (0, 0), 5),
            ('BOTTOMPADDING', (0, 0), (0, 0), 5),
            ('TOPPADDING', (0, 1), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 4),
            ('BOX', (0, 0), (-1, -1), 0.5, self.colors['border_gray']),
        ]))
        
        return achievement_table
    
    def _create_gpa_calculation_table(self):
        """Create GPA calculation explanation table"""
        cell_style = ParagraphStyle('Cell', fontSize=7.5, alignment=TA_LEFT)
        
        # GPA calculation data
        gpa_data = [
            [Paragraph('GPA CALCULATION', ParagraphStyle('Header', fontSize=10, fontName='Times-Bold'))],
            [Paragraph('Grade Point Average (GPA) is calculated using the points assigned to each grade. The formula for GPA calculation is:', cell_style)],
            [Paragraph('GPA = (Sum of Grade Points for all subjects) ÷ (Number of subjects)', 
                      ParagraphStyle('Formula', fontSize=8, fontName='Times-Bold', alignment=TA_CENTER, textColor=self.colors['primary_blue']))],
            [Paragraph('Example: If a student gets A (4.0) in 3 subjects, B (3.0) in 4 subjects, and C (2.0) in 2 subjects:', cell_style)],
            [Paragraph('Total Points = (4.0 × 3) + (3.0 × 4) + (2.0 × 2) = 28.0', cell_style)],
            [Paragraph('Total Subjects = 9', cell_style)],
            [Paragraph('GPA = 28.0 ÷ 9 = 3.11', ParagraphStyle('Result', fontSize=8, fontName='Times-Bold'))],
            [Paragraph('Note: GPA is calculated to two decimal places and provides an overall measure of academic performance.', 
                      ParagraphStyle('Note', fontSize=7, fontName='Times-Italic'))],
        ]
        
        gpa_table = Table(gpa_data, colWidths=[5.3*inch])
        gpa_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), self.colors['light_blue']),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (0, 0), 5),
            ('BOTTOMPADDING', (0, 0), (0, 0), 5),
            ('TOPPADDING', (0, 1), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 3),
            ('BOX', (0, 0), (-1, -1), 0.5, self.colors['border_gray']),
        ]))
        
        return gpa_table
    
    def _create_effort_grades_table(self):
        """Create effort grades reference table"""
        cell_style = ParagraphStyle('Cell', fontSize=7.5, alignment=TA_LEFT)
        grade_style = ParagraphStyle('Grade', fontSize=8, fontName='Times-Bold', alignment=TA_CENTER)
        
        # Effort grades data
        effort_data = [
            [Paragraph('EFFORT GRADES', ParagraphStyle('Header', fontSize=10, fontName='Times-Bold'))],
            [Paragraph('Effort grades evaluate student commitment, work ethic, and participation in class activities.', cell_style)],
        ]
        
        # Effort scale
        effort_scale = [
            ['1', 'Exceptional: Produces high-quality work, always meets deadlines, shows great enthusiasm, works independently.'],
            ['2', 'Very Good: Mostly produces high-standard work, meets deadlines, well-prepared for assessments, shows enthusiasm.'],
            ['3', 'Satisfactory: Produces good work when prompted, meets most deadlines, preparations inconsistent, limited independent work.'],
            ['4', 'Needs Improvement: Work quality varies, sometimes late/incomplete, needs thorough preparation, presentation often poor.'],
            ['5', 'Unsatisfactory: Work frequently incomplete/superficial/late, minimal preparation, easily distracted, avoids challenges.'],
        ]
        
        effort_table_data = []
        for grade, description in effort_scale:
            effort_table_data.append([
                Paragraph(grade, grade_style),
                Paragraph(description, cell_style)
            ])
        
        effort_table = Table(effort_table_data, colWidths=[0.4*inch, 4.5*inch])
        effort_table.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 0.5, self.colors['border_gray']),
            ('BACKGROUND', (0, 0), (0, -1), self.colors['light_blue']),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        
        effort_data.append([effort_table])
        
        effort_full_table = Table(effort_data, colWidths=[5.3*inch])
        effort_full_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), self.colors['light_blue']),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (0, 0), 5),
            ('BOTTOMPADDING', (0, 0), (0, 0), 5),
            ('TOPPADDING', (0, 1), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 4),
            ('BOX', (0, 0), (-1, -1), 0.5, self.colors['border_gray']),
        ]))
        
        return effort_full_table
    
    def _create_enhanced_comments_section(self, comments: Dict) -> List:
        """Create enhanced comments section with better formatting"""
        elements = []
        
        # No header - just add comments directly with labels
        label_style = ParagraphStyle(
            'CommentLabel',
            fontSize=9,
            textColor=self.colors['dark_gray'],
            fontName='Times-Bold',
            spaceAfter=2
        )
        
        comment_style = ParagraphStyle(
            'CommentText',
            fontSize=8.5,
            textColor=self.colors['dark_gray'],
            alignment=TA_JUSTIFY,
            spaceAfter=8
        )
        
        # Form Tutor's Comment (if provided)
        if comments.get('form_tutor_comment'):
            elements.append(Paragraph("Form Teacher's Comment:", label_style))
            elements.append(Paragraph(comments['form_tutor_comment'], comment_style))
        
        # Principal's Remark (if provided)
        if comments.get('principal_remark'):
            elements.append(Paragraph("Principal's Remark:", label_style))
            elements.append(Paragraph(comments['principal_remark'], comment_style))
        
        return elements
    
    def _create_consultation_section(self) -> List:
        """Create parent-teacher consultation section"""
        elements = []
        
        header_style = ParagraphStyle(
            'ConsultHeader',
            fontSize=10,
            textColor=colors.white,
            fontName='Times-Bold',
            alignment=TA_LEFT,
        )
        
        text_style = ParagraphStyle(
            'ConsultText',
            fontSize=8,
            textColor=self.colors['dark_gray'],
            alignment=TA_LEFT,
        )
        
        consult_data = [
            [Paragraph('PARENT-TEACHER CONSULTATION', header_style)],
            [Paragraph('All parents are encouraged to meet with teachers. Consultations will be scheduled on an individual basis, and by prior appointment. Details of the appointment procedure will be circulated by the school.', text_style)]
        ]
        
        consult_table = Table(consult_data, colWidths=[10.8*inch])
        consult_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), self.colors['header_bg']),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (0, 0), 5),
            ('BOTTOMPADDING', (0, 0), (0, 0), 5),
            ('TOPPADDING', (0, 1), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
            ('BOX', (0, 0), (-1, -1), 0.5, self.colors['border_gray']),
        ]))
        
        elements.append(consult_table)
        elements.append(Spacer(1, 10))
        
        return elements
    
    def _create_signature_section(self, school_info: Dict, term_data: Dict) -> List:
        """Create signature section with embedded signature image"""
        elements = []
        
        # Add horizontal line
        elements.append(HRFlowable(
            width="100%",
            thickness=1,
            color=colors.HexColor('#d1d5db'),
            spaceBefore=5,
            spaceAfter=15
        ))
        
        # Get values safely
        principal_sig_path = term_data.get('principal_signature', '')
        resumption_date = term_data.get('next_term_resumption_date', 'To Be Announced')
        
        # Ensure values are strings, not None
        if principal_sig_path is None:
            principal_sig_path = ''
        if resumption_date is None:
            resumption_date = 'To Be Announced'
        
        # Create styles
        sig_style = ParagraphStyle('SigLabel', fontSize=9, fontName='Helvetica-Bold', alignment=TA_LEFT)
        date_style = ParagraphStyle('Date', fontSize=9, alignment=TA_LEFT)
        
        # Check if we have a valid signature image
        signature_cell_content = None
        if principal_sig_path and os.path.exists(principal_sig_path):
            try:
                # Create an Image flowable
                signature_cell_content = Image(principal_sig_path, width=2.5*inch, height=0.6*inch)
            except Exception as e:
                print(f"Could not load signature image: {e}")
                signature_cell_content = Paragraph('_________________________', 
                                                ParagraphStyle('SigLine', fontSize=9, alignment=TA_LEFT))
        else:
            # Use placeholder
            signature_cell_content = Paragraph('_________________________', 
                                            ParagraphStyle('SigLine', fontSize=9, alignment=TA_LEFT))
        
        # Create table data with the signature image
        sig_data = [
            [
                Paragraph('Principal\'s Signature:', sig_style),
                signature_cell_content,  # This is either an Image or Paragraph
                Spacer(1.5*inch, 0),
                Paragraph('Resumption Date:', sig_style),
                Paragraph(resumption_date, date_style),
            ]
        ]
        
        # Create the table
        sig_table = Table(sig_data, colWidths=[1.5*inch, 2.5*inch, 1.5*inch, 1.5*inch, 2.5*inch])
        sig_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ]))
        
        elements.append(sig_table)
        
        return elements

    def _add_page_footer(self, canvas, doc):
        """Add page footer"""
        canvas.saveState()
        
        # Page number
        page_num = canvas.getPageNumber()
        canvas.setFont('Times-Bold', 7)
        canvas.setFillColor(self.colors['medium_gray'])
        canvas.drawRightString(
            doc.width + doc.leftMargin,
            15,
            f"Page {page_num}"
        )
        
        canvas.restoreState()