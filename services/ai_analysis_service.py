import os
import json
from typing import Dict, List, Any, Optional
import numpy as np
from datetime import datetime, timezone
from openai import OpenAI  # Using OpenAI client with Hugging Face base_url
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from collections import Counter

load_dotenv()

class StudentAnalysis(BaseModel):
    strengths: List[str] = Field(description="List of student's academic strengths")
    weaknesses: List[str] = Field(description="List of student's academic weaknesses")
    recommendations: List[str] = Field(description="Recommendations for improvement")
    comment: str = Field(description="AI-generated comment for the student")

class AIAnalysisService:
    def __init__(self):
        self.huggingface_api_key = os.getenv("HUGGINGFACE_API_KEY")
        self.openai_client = None
        
        # Default models to try (free and open source)
        self.models = [
            "deepseek-ai/DeepSeek-V3.2-Exp:novita",  # DeepSeek (powerful)
            "meta-llama/Llama-3.3-70B-Instruct",     # Llama 3.3
            "google/gemma-2-9b-it",                  # Gemma 2
            "Qwen/Qwen2.5-7B-Instruct",              # Qwen 2.5
            "microsoft/Phi-3.5-mini-instruct",       # Phi 3.5 Mini
        ]
        
        if self.huggingface_api_key:
            try:
                # Initialize OpenAI client with Hugging Face base URL
                self.openai_client = OpenAI(
                    base_url="https://router.huggingface.co/v1",
                    api_key=self.huggingface_api_key,
                )
                print("Hugging Face client initialized successfully")
                
                # Test connection with first available model
                self._test_connection()
                
            except Exception as e:
                print(f"Error initializing Hugging Face client: {e}")
                self.openai_client = None
        else:
            print("Warning: HUGGINGFACE_API_KEY not found. AI features will use rule-based analysis.")
    
    def _test_connection(self):
        """Test connection to Hugging Face API"""
        try:
            # Try a simple request with each model until one works
            for model in self.models[:2]:  # Try first two models
                try:
                    test_response = self.openai_client.chat.completions.create(
                        model=model,
                        messages=[
                            {"role": "user", "content": "Say 'Connected' if you can read this."}
                        ],
                        max_tokens=10,
                        timeout=10
                    )
                    print(f"✓ Connected to model: {model}")
                    self.preferred_model = model
                    return
                except Exception as e:
                    print(f"  Model {model} not available: {e}")
                    continue
            
            # If no model worked, try to get available models
            try:
                models_list = self.openai_client.models.list()
                available_models = [model.id for model in models_list.data[:5]]
                print(f"Available models: {available_models}")
                if available_models:
                    self.preferred_model = available_models[0]
                    print(f"✓ Using model: {self.preferred_model}")
            except:
                print("Could not fetch available models")
                self.preferred_model = self.models[0]
                
        except Exception as e:
            print(f"Connection test failed: {e}")
            self.openai_client = None
    
    def analyze_student_performance(self, student_data: Dict, exam_data: Dict, 
                                  question_responses: List[Dict]) -> Dict:
        """Analyze student performance and generate insights"""
        
        if self.openai_client:
            return self._analyze_with_huggingface(student_data, exam_data, question_responses)
        else:
            return self._analyze_with_rules(student_data, exam_data, question_responses)
    
    def _analyze_with_huggingface(self, student_data: Dict, exam_data: Dict, 
                                 question_responses: List[Dict]) -> Dict:
        """Use Hugging Face models via OpenAI-compatible API"""
        
        # Try multiple models until one works
        models_to_try = [self.preferred_model] if hasattr(self, 'preferred_model') else self.models
        
        for model in models_to_try:
            try:
                print(f"Trying analysis with model: {model}")
                
                # Prepare the prompt
                prompt = self._create_analysis_prompt(student_data, exam_data, question_responses)
                
                # Call Hugging Face API
                response = self.openai_client.chat.completions.create(
                    model=model,
                    messages=[
                        {
                            "role": "system", 
                            "content": """You are an experienced educational analyst. Analyze the student's exam 
                            performance and provide constructive feedback focusing on strengths, weaknesses, 
                            and recommendations. Format your response as a valid JSON object with these keys: 
                            strengths (array of strings), weaknesses (array of strings), 
                            recommendations (array of strings), comment (string).
                            
                            IMPORTANT: Return ONLY valid JSON, no additional text."""
                        },
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.7,
                    max_tokens=1000,
                    response_format={"type": "json_object"}
                )
                
                # Parse the JSON response
                ai_response = response.choices[0].message.content
                print(f"Raw response from {model}: {ai_response[:200]}...")
                
                # Try to parse JSON
                try:
                    analysis = json.loads(ai_response)
                except json.JSONDecodeError:
                    # Try to extract JSON from text
                    analysis = self._extract_json_from_text(ai_response)
                
                # Validate and clean the analysis
                analysis = self._validate_analysis(analysis)
                
                # Calculate accuracy
                total_questions = len(question_responses)
                correct_answers = sum(1 for q in question_responses if q.get('is_correct', False))
                accuracy = (correct_answers / total_questions * 100) if total_questions > 0 else 0
                
                return {
                    "strengths": analysis.get('strengths', [])[:5],
                    "weaknesses": analysis.get('weaknesses', [])[:5],
                    "recommendations": analysis.get('recommendations', [])[:5],
                    "ai_comment": analysis.get('comment', ''),
                    "accuracy_rate": accuracy,
                    "analysis_method": f"huggingface_{model.split('/')[-1]}",
                    "confidence_score": 0.85,
                    "model_used": model
                }
                
            except Exception as e:
                print(f"Model {model} failed: {e}")
                continue
        
        # If all models fail, fall back to rule-based
        print("All Hugging Face models failed, falling back to rule-based analysis")
        return self._analyze_with_rules(student_data, exam_data, question_responses)
    
    def _extract_json_from_text(self, text: str) -> Dict:
        """Extract JSON from text response if not properly formatted"""
        try:
            # Try to find JSON object in the text
            import re
            
            # Look for JSON-like structure
            json_pattern = r'\{.*\}'
            match = re.search(json_pattern, text, re.DOTALL)
            
            if match:
                json_str = match.group(0)
                return json.loads(json_str)
            else:
                # Create a basic analysis from text
                return {
                    'strengths': ['Analysis completed'],
                    'weaknesses': [],
                    'recommendations': ['Review the material'],
                    'comment': 'AI analysis completed.'
                }
        except:
            return {
                'strengths': [],
                'weaknesses': [],
                'recommendations': [],
                'comment': 'Could not parse AI response.'
            }
    
    def _validate_analysis(self, analysis: Dict) -> Dict:
        """Validate and clean the analysis response"""
        validated = {
            'strengths': [],
            'weaknesses': [],
            'recommendations': [],
            'comment': ''
        }
        
        # Ensure lists are actually lists
        if isinstance(analysis.get('strengths'), list):
            validated['strengths'] = [str(s) for s in analysis['strengths'] if s]
        elif isinstance(analysis.get('strengths'), str):
            validated['strengths'] = [analysis['strengths']]
        
        if isinstance(analysis.get('weaknesses'), list):
            validated['weaknesses'] = [str(w) for w in analysis['weaknesses'] if w]
        elif isinstance(analysis.get('weaknesses'), str):
            validated['weaknesses'] = [analysis['weaknesses']]
        
        if isinstance(analysis.get('recommendations'), list):
            validated['recommendations'] = [str(r) for r in analysis['recommendations'] if r]
        elif isinstance(analysis.get('recommendations'), str):
            validated['recommendations'] = [analysis['recommendations']]
        
        # Ensure comment is a string
        comment = analysis.get('comment', '')
        if isinstance(comment, str):
            validated['comment'] = comment
        else:
            validated['comment'] = str(comment)
        
        return validated
    
    def _create_analysis_prompt(self, student_data: Dict, exam_data: Dict, 
                              question_responses: List[Dict]) -> str:
        """Create prompt for analysis"""
        
        student_name = f"{student_data.get('first_name', '')} {student_data.get('last_name', '')}"
        
        # Calculate metrics
        total_questions = len(question_responses)
        correct_answers = sum(1 for q in question_responses if q.get('is_correct', False))
        accuracy = (correct_answers / total_questions * 100) if total_questions > 0 else 0
        
        # Analyze question types
        type_analysis = {}
        for q in question_responses:
            q_type = q.get('question_type', 'unknown')
            is_correct = q.get('is_correct', False)
            
            if q_type not in type_analysis:
                type_analysis[q_type] = {'total': 0, 'correct': 0}
            
            type_analysis[q_type]['total'] += 1
            if is_correct:
                type_analysis[q_type]['correct'] += 1
        
        # Format type analysis
        type_analysis_text = ""
        for q_type, stats in type_analysis.items():
            type_accuracy = (stats['correct'] / stats['total'] * 100) if stats['total'] > 0 else 0
            type_analysis_text += f"- {q_type.replace('_', ' ').title()}: {stats['correct']}/{stats['total']} ({type_accuracy:.1f}%)\n"
        
        # Create prompt
        prompt = f"""
        Analyze this student's exam performance and provide feedback.
        
        STUDENT INFORMATION:
        - Name: {student_name}
        - Class: {student_data.get('class_name', 'Unknown')}
        - Subject: {exam_data.get('subject_name', 'Unknown')}
        
        EXAM INFORMATION:
        - Title: {exam_data.get('title', 'Unknown')}
        - Total Marks: {exam_data.get('total_marks', 0)}
        - Student Score: {student_data.get('score', 0)}
        - Percentage: {student_data.get('percentage', 0)}%
        
        PERFORMANCE METRICS:
        - Total Questions: {total_questions}
        - Correct Answers: {correct_answers}
        - Accuracy Rate: {accuracy:.1f}%
        
        QUESTION TYPE ANALYSIS:
        {type_analysis_text}
        
        Based on this data, provide a JSON response with:
        1. "strengths": Array of 3-5 specific academic strengths
        2. "weaknesses": Array of 3-5 areas needing improvement
        3. "recommendations": Array of 3-5 actionable recommendations
        4. "comment": A constructive 2-3 sentence comment for the student
        
        IMPORTANT: Return ONLY valid JSON, no additional text.
        """
        
        return prompt
    
    def _analyze_with_rules(self, student_data: Dict, exam_data: Dict, 
                           question_responses: List[Dict]) -> Dict:
        """Rule-based analysis when AI is not available"""
        
        # Calculate basic metrics
        total_questions = len(question_responses)
        correct_answers = sum(1 for q in question_responses if q.get('is_correct', False))
        accuracy = (correct_answers / total_questions * 100) if total_questions > 0 else 0
        
        # Analyze question types
        question_types = {}
        for q in question_responses:
            q_type = q.get('question_type', 'unknown')
            is_correct = q.get('is_correct', False)
            
            if q_type not in question_types:
                question_types[q_type] = {'total': 0, 'correct': 0}
            
            question_types[q_type]['total'] += 1
            if is_correct:
                question_types[q_type]['correct'] += 1
        
        # Determine strengths and weaknesses based on accuracy
        strengths = []
        weaknesses = []
        
        for q_type, stats in question_types.items():
            type_accuracy = (stats['correct'] / stats['total'] * 100) if stats['total'] > 0 else 0
            
            if type_accuracy >= 70:
                strengths.append(f"Strong performance in {q_type.replace('_', ' ')} questions")
            elif type_accuracy <= 40:
                weaknesses.append(f"Needs improvement in {q_type.replace('_', ' ')} questions")
        
        # Add general strengths/weaknesses based on overall accuracy
        if accuracy >= 80:
            strengths.append("Excellent overall understanding of the subject")
            strengths.append("Good problem-solving skills")
        elif accuracy >= 60:
            strengths.append("Solid foundational knowledge")
        else:
            weaknesses.append("Needs to review core concepts")
            weaknesses.append("Requires more practice with application questions")
        
        # Generate recommendations
        recommendations = []
        if accuracy < 60:
            recommendations.append("Review fundamental concepts before next assessment")
            recommendations.append("Practice with more example problems")
            recommendations.append("Seek clarification on challenging topics")
        elif accuracy < 80:
            recommendations.append("Focus on application-based questions")
            recommendations.append("Work on time management during exams")
            recommendations.append("Review incorrect answers to understand mistakes")
        else:
            recommendations.append("Challenge yourself with advanced topics")
            recommendations.append("Help peers who are struggling")
            recommendations.append("Maintain consistent study habits")
        
        # Generate comment
        if accuracy >= 90:
            comment = "Outstanding performance! You've demonstrated excellent mastery of the subject. Keep up the great work!"
        elif accuracy >= 75:
            comment = "Good performance. You have a solid understanding of the material. Focus on areas where you lost marks to achieve even better results."
        elif accuracy >= 60:
            comment = "Satisfactory performance. You understand the basics well. With more practice on application questions, you can improve significantly."
        else:
            comment = "There's room for improvement. Review the fundamental concepts and practice regularly. Don't hesitate to ask for help when needed."
        
        return {
            "strengths": strengths[:5],
            "weaknesses": weaknesses[:5],
            "recommendations": recommendations[:5],
            "ai_comment": comment,
            "accuracy_rate": accuracy,
            "analysis_method": "rule_based",
            "confidence_score": 0.65,
            "model_used": "rule_based"
        }
    
    def analyze_exam_questions(self, exam_data: Dict, all_responses: List[List[Dict]]) -> Dict:
        """Analyze question performance across all students"""
        if not all_responses:
            return {}
        
        question_stats = {}
        
        for student_responses in all_responses:
            for response in student_responses:
                question_id = response.get('question_id')
                if not question_id:
                    continue
                
                if question_id not in question_stats:
                    question_stats[question_id] = {
                        'total_attempts': 0,
                        'correct_attempts': 0,
                        'incorrect_attempts': 0,
                        'question_text': response.get('question_text', '')[:100],
                        'question_type': response.get('question_type', 'unknown')
                    }
                
                question_stats[question_id]['total_attempts'] += 1
                if response.get('is_correct', False):
                    question_stats[question_id]['correct_attempts'] += 1
                else:
                    question_stats[question_id]['incorrect_attempts'] += 1
        
        # Calculate difficulty and identify problematic questions
        analysis_results = {}
        for question_id, stats in question_stats.items():
            difficulty = (1 - (stats['correct_attempts'] / stats['total_attempts'])) * 10 if stats['total_attempts'] > 0 else 5
            accuracy = (stats['correct_attempts'] / stats['total_attempts'] * 100) if stats['total_attempts'] > 0 else 0
            
            analysis_results[question_id] = {
                'difficulty_rating': round(difficulty, 2),
                'accuracy_rate': round(accuracy, 2),
                'needs_review': accuracy < 50,  # Flag questions with <50% accuracy
                'total_attempts': stats['total_attempts'],
                'correct_attempts': stats['correct_attempts'],
                'question_type': stats['question_type']
            }
        
        return analysis_results
    
    def generate_class_report(self, class_data: Dict, student_performances: List[Dict]) -> Dict:
        """Generate class-level performance report"""
        if not student_performances:
            return {}
        
        # Calculate class statistics
        scores = []
        all_strengths = []
        all_weaknesses = []
        
        for student_data in student_performances:
            # Extract score if available
            score = student_data.get('score', 0)
            if score:
                scores.append(score)
            
            # Extract analysis if available
            analysis = student_data.get('analysis')
            if analysis:
                # Handle both dictionary and model object
                if hasattr(analysis, 'strengths'):  # Model object
                    if analysis.strengths:
                        all_strengths.extend(analysis.strengths)
                elif isinstance(analysis, dict):  # Dictionary
                    if analysis.get('strengths'):
                        all_strengths.extend(analysis.get('strengths', []))
                
                if hasattr(analysis, 'weaknesses'):  # Model object
                    if analysis.weaknesses:
                        all_weaknesses.extend(analysis.weaknesses)
                elif isinstance(analysis, dict):  # Dictionary
                    if analysis.get('weaknesses'):
                        all_weaknesses.extend(analysis.get('weaknesses', []))
        
        # Calculate statistics
        avg_score = np.mean(scores) if scores else 0
        max_score = max(scores) if scores else 0
        min_score = min(scores) if scores else 0
        std_dev = np.std(scores) if len(scores) > 1 else 0
        
        # Performance distribution
        score_bins = {'Excellent (80-100%)': 0, 'Good (60-79%)': 0, 
                    'Average (40-59%)': 0, 'Below Average (<40%)': 0}
        
        for score in scores:
            percentage = (score / 100 * 100) if 100 != 0 else 0
            if percentage >= 80:
                score_bins['Excellent (80-100%)'] += 1
            elif percentage >= 60:
                score_bins['Good (60-79%)'] += 1
            elif percentage >= 40:
                score_bins['Average (40-59%)'] += 1
            else:
                score_bins['Below Average (<40%)'] += 1
        
        # Count frequencies
        common_strengths = Counter(all_strengths).most_common(3)
        common_weaknesses = Counter(all_weaknesses).most_common(3)
        
        # Generate insights and recommendations
        insights = []
        recommendations = []
        
        if self.openai_client and student_performances:
            try:
                insight_prompt = f"""
                Analyze the class performance for {class_data.get('subject_name', 'the subject')}:
                
                Class Statistics:
                - Average Score: {avg_score:.1f}%
                - Highest Score: {max_score:.1f}%
                - Lowest Score: {min_score:.1f}%
                - Score Distribution: {score_bins}
                - Standard Deviation: {std_dev:.2f}
                
                Common Strengths: {common_strengths}
                Common Weaknesses: {common_weaknesses}
                
                Provide 3 key insights and 3 recommendations for teaching improvement.
                Return as JSON with 'insights' and 'recommendations' arrays.
                """
                
                response = self.openai_client.chat.completions.create(
                    model=getattr(self, 'preferred_model', self.models[0]),
                    messages=[
                        {"role": "system", "content": "You are an educational consultant analyzing class performance data."},
                        {"role": "user", "content": insight_prompt}
                    ],
                    temperature=0.7,
                    max_tokens=500,
                    response_format={"type": "json_object"}
                )
                
                ai_response = response.choices[0].message.content
                parsed_response = json.loads(ai_response)
                
                insights = parsed_response.get('insights', [])[:3]
                recommendations = parsed_response.get('recommendations', [])[:3]
                
            except Exception as e:
                print(f"AI class analysis failed: {e}")
                # Fallback to rule-based insights
                insights = [
                    f"Class average is {avg_score:.1f}% with {std_dev:.2f} standard deviation.",
                    f"Score distribution: {score_bins['Excellent (80-100%)']} excellent, {score_bins['Good (60-79%)']} good, {score_bins['Average (40-59%)']} average, {score_bins['Below Average (<40%)']} below average."
                ]
                recommendations = [
                    "Review topics where most students performed poorly",
                    "Provide additional practice for below-average students",
                    "Consider differentiated instruction for varied skill levels"
                ]
        else:
            # Rule-based insights when no AI
            insights = [
                f"Class average is {avg_score:.1f}% with {std_dev:.2f} standard deviation.",
                f"Score distribution: {score_bins['Excellent (80-100%)']} excellent, {score_bins['Good (60-79%)']} good, {score_bins['Average (40-59%)']} average, {score_bins['Below Average (<40%)']} below average."
            ]
            recommendations = [
                "Review topics where most students performed poorly",
                "Provide additional practice for below-average students",
                "Consider differentiated instruction for varied skill levels"
            ]
        
        return {
            "statistics": {
                "average_score": round(avg_score, 2),
                "max_score": round(max_score, 2),
                "min_score": round(min_score, 2),
                "std_deviation": round(std_dev, 2),
                "total_students": len(student_performances),
                "score_distribution": score_bins
            },
            "insights": insights[:3],
            "recommendations": recommendations[:3],
            "common_strengths": [s[0] for s in common_strengths],
            "common_weaknesses": [w[0] for w in common_weaknesses],
            "top_performers": sorted(student_performances, 
                                    key=lambda x: x.get('score', 0), 
                                    reverse=True)[:3],
            "need_improvement": sorted(student_performances, 
                                    key=lambda x: x.get('score', 0))[:3]
        }
    
    def get_available_models(self) -> List[str]:
        """Get list of available Hugging Face models"""
        if self.openai_client:
            try:
                models = self.openai_client.models.list()
                return [model.id for model in models.data[:10]]  # First 10 models
            except Exception as e:
                print(f"Could not fetch available models: {e}")
                return self.models
        return self.models


# Example usage
if __name__ == "__main__":
    # Create .env file with: HUGGINGFACE_API_KEY=your_key_here
    service = AIAnalysisService()
    
    # Example student data
    student_data = {
        "first_name": "John",
        "last_name": "Doe",
        "class_name": "10A",
        "score": 85,
        "percentage": 85.0
    }
    
    exam_data = {
        "title": "Mathematics Midterm",
        "subject_name": "Mathematics",
        "total_marks": 100
    }
    
    question_responses = [
        {"question_id": 1, "question_text": "Solve 2x + 5 = 15", "question_type": "algebra", "is_correct": True},
        {"question_id": 2, "question_text": "Calculate area of circle", "question_type": "geometry", "is_correct": True},
        {"question_id": 3, "question_text": "Differentiate x^2", "question_type": "calculus", "is_correct": False},
        {"question_id": 4, "question_text": "Probability question", "question_type": "statistics", "is_correct": True},
        {"question_id": 5, "question_text": "Trigonometry problem", "question_type": "trigonometry", "is_correct": True},
    ]
    
    # Analyze student performance
    result = service.analyze_student_performance(student_data, exam_data, question_responses)
    print("\nStudent Analysis Result:")
    print(json.dumps(result, indent=2))
    
    # Get available models
    models = service.get_available_models()
    print(f"\nAvailable models: {models}")