import os
import google.generativeai as genai
from typing import List, Dict, Tuple
from django.conf import settings


class GeminiInterviewService:
    def __init__(self):
        api_key = os.getenv('GEMINI_API_KEY') or getattr(settings, 'GEMINI_API_KEY', None)
        if not api_key:
            print("WARNING: No GEMINI_API_KEY found, using fallback questions")
            self.model = None
            return

        try:
            genai.configure(api_key=api_key)
            self.model = genai.GenerativeModel('gemini-pro')
        except Exception as e:
            print(f"WARNING: Failed to configure Gemini API: {e}")
            self.model = None

    def generate_interview_questions(self, role: str, resume_content: str = "") -> List[Dict[str, str]]:
        """
        Generate 6 role-specific interview questions (2 easy, 2 medium, 2 hard).
        Questions can be personalized based on resume content if provided.

        Args:
            role: Job role (frontend, backend, data_analyst)
            resume_content: Optional resume text to personalize questions

        Returns:
            List of question dictionaries with 'difficulty' and 'question' keys
        """
        role_names = {
            'frontend': 'Frontend Developer',
            'backend': 'Backend Developer',
            'data_analyst': 'Data Analyst'
        }

        # Create personalized prompt based on resume content
        resume_section = ""
        if resume_content.strip():
            resume_section = f"""

            CANDIDATE'S RESUME INFORMATION:
            {resume_content[:2000]}  # Limit to first 2000 chars to avoid token limits

            Please personalize the questions based on the candidate's background and experience shown in their resume.
            """

        prompt = f"""
        Generate 6 technical interview questions for a {role_names[role]} position.{resume_section}
        Return exactly 6 questions in this format:

        EASY QUESTIONS:
        1. [Question 1]
        2. [Question 2]

        MEDIUM QUESTIONS:
        3. [Question 3]
        4. [Question 4]

        HARD QUESTIONS:
        5. [Question 5]
        6. [Question 6]

        Requirements:
        - Questions should be technical and relevant to the role
        - If resume information is provided, tailor questions to the candidate's experience level and background
        - Easy questions should test basic concepts
        - Medium questions should require some problem-solving
        - Hard questions should challenge deep understanding
        - Each question should be clear and concise
        """

        if not self.model:
            print("No Gemini model available, using fallback questions")
            return self._get_fallback_questions(role)

        try:
            response = self.model.generate_content(prompt)
            content = response.text

            questions = []
            difficulties = ['easy', 'easy', 'medium', 'medium', 'hard', 'hard']

            # Parse the response and extract questions
            lines = content.split('\n')
            question_count = 0

            for line in lines:
                line = line.strip()
                if line and (line[0].isdigit() and line[1] == '.'):
                    try:
                        question = line.split('.', 1)[1].strip()
                        if question and question_count < 6:
                            questions.append({
                                'difficulty': difficulties[question_count],
                                'question': question
                            })
                            question_count += 1
                    except:
                        continue

            # Ensure we have exactly 6 questions
            while len(questions) < 6:
                questions.append({
                    'difficulty': difficulties[len(questions)],
                    'question': f'Default question {len(questions) + 1} for {role_names[role]}'
                })

            return questions[:6]

        except Exception as e:
            print(f"Error generating questions: {e}")
            # Return fallback questions (with resume personalization if possible)
            return self._get_fallback_questions(role, resume_content)

    def evaluate_answer(self, question: str, answer: str, difficulty: str) -> Tuple[float, str]:
        """
        Evaluate a candidate's answer and return score and feedback.

        Args:
            question: The interview question
            answer: The candidate's answer
            difficulty: Difficulty level (easy/medium/hard)

        Returns:
            Tuple of (score, feedback)
        """
        prompt = f"""
        Evaluate this technical interview answer as an expert interviewer:

        Question: {question}
        Difficulty: {difficulty}
        Candidate's Answer: {answer}

        You are an expert technical interviewer. Evaluate the answer based on:
        - Technical accuracy and correctness
        - Completeness and depth of understanding
        - Relevance to the question asked
        - Clarity and coherence

        Scoring Scale (be strict and accurate):
        - 0-2: Completely incorrect, irrelevant, or shows no understanding
        - 3-4: Major errors, partial understanding, significant gaps
        - 5-6: Basic understanding but incomplete or with errors
        - 7-8: Good understanding with minor inaccuracies
        - 9-10: Excellent, accurate, comprehensive answer

        IMPORTANT: Be critical and accurate. For example:
        - If asked "What is HTML?" and answer is "hut", score should be 0-2
        - If asked "What is HTML?" and answer is "markup language for web", score should be 5-7
        - If asked "What is HTML?" and answer is "HTML is HyperText Markup Language used to structure web content", score should be 9-10

        Provide ONLY the score and feedback in this exact format:
        SCORE: [single number 0-10]
        FEEDBACK: [2-3 sentences explaining the evaluation and suggestions]
        """

        if not self.model:
            print("WARNING: No Gemini model available, using fallback scoring")
            return self._fallback_score_evaluation(question, answer, difficulty)

        try:
            response = self.model.generate_content(prompt)
            content = response.text

            # Parse score and feedback
            lines = content.split('\n')
            score = 0.0
            feedback = "Unable to evaluate answer."

            for line in lines:
                line = line.strip()
                if line.startswith('SCORE:'):
                    try:
                        score_str = line.split(':', 1)[1].strip()
                        score = float(score_str)
                        score = max(0, min(10, score))  # Clamp between 0-10
                    except:
                        pass
                elif line.startswith('FEEDBACK:'):
                    feedback = line.split(':', 1)[1].strip()

            return score, feedback

        except Exception as e:
            print(f"Error evaluating answer: {e}")
            # Return fallback evaluation when AI fails
            return self._fallback_score_evaluation(question, answer, difficulty)

    def generate_final_summary(self, role: str, questions_and_answers: List[Dict]) -> Tuple[float, str]:
        """
        Generate final holistic score and qualitative summary.

        Args:
            role: Job role
            questions_and_answers: List of dicts with question, answer, score, difficulty

        Returns:
            Tuple of (final_score, summary)
        """
        role_names = {
            'frontend': 'Frontend Developer',
            'backend': 'Backend Developer',
            'data_analyst': 'Data Analyst'
        }

        qa_text = ""
        total_score = 0
        count = 0

        for item in questions_and_answers:
            qa_text += f"Q: {item['question']}\nA: {item['answer']}\nScore: {item['score']}/10\n\n"
            total_score += item['score']
            count += 1

        avg_score = total_score / count if count > 0 else 0

        prompt = f"""
        Based on this {role_names[role]} interview, provide:

        1. A final holistic score from 0-100 (weighted average considering difficulty)
        2. A qualitative summary (3-4 sentences) evaluating the candidate's overall performance

        Interview Details:
        {qa_text}

        Format your response as:
        FINAL_SCORE: [number]
        SUMMARY: [your summary here]
        """

        if not self.model:
            return self._fallback_final_summary(role, questions_and_answers)

        try:
            response = self.model.generate_content(prompt)
            content = response.text

            lines = content.split('\n')
            final_score = avg_score * 10  # Default to scaled average
            summary = "Interview completed successfully."

            for line in lines:
                line = line.strip()
                if line.startswith('FINAL_SCORE:'):
                    try:
                        score_str = line.split(':', 1)[1].strip()
                        final_score = float(score_str)
                        final_score = max(0, min(100, final_score))
                    except:
                        pass
                elif line.startswith('SUMMARY:'):
                    summary = line.split(':', 1)[1].strip()

            return final_score, summary

        except Exception as e:
            print(f"Error generating summary: {e}")
            return avg_score * 10, "Interview completed. Performance evaluation available."

    def _get_fallback_questions(self, role: str, resume_content: str = "") -> List[Dict[str, str]]:
        """Return fallback questions if API fails. Attempts basic personalization if resume provided."""
        fallbacks = {
            'frontend': [
                {'difficulty': 'easy', 'question': 'What is HTML?'},
                {'difficulty': 'easy', 'question': 'What is CSS?'},
                {'difficulty': 'medium', 'question': 'Explain the box model in CSS.'},
                {'difficulty': 'medium', 'question': 'What is responsive design?'},
                {'difficulty': 'hard', 'question': 'How does the virtual DOM work in React?'},
                {'difficulty': 'hard', 'question': 'Explain CSS Grid vs Flexbox.'},
            ],
            'backend': [
                {'difficulty': 'easy', 'question': 'What is a database?'},
                {'difficulty': 'easy', 'question': 'What is an API?'},
                {'difficulty': 'medium', 'question': 'Explain REST vs GraphQL.'},
                {'difficulty': 'medium', 'question': 'What is authentication vs authorization?'},
                {'difficulty': 'hard', 'question': 'How would you design a scalable microservices architecture?'},
                {'difficulty': 'hard', 'question': 'Explain database indexing and its importance.'},
            ],
            'data_analyst': [
                {'difficulty': 'easy', 'question': 'What is SQL?'},
                {'difficulty': 'easy', 'question': 'What is data visualization?'},
                {'difficulty': 'medium', 'question': 'Explain the difference between inner and outer joins.'},
                {'difficulty': 'medium', 'question': 'What is data normalization?'},
                {'difficulty': 'hard', 'question': 'How would you handle missing data in a dataset?'},
                {'difficulty': 'hard', 'question': 'Explain A/B testing and its statistical significance.'},
            ]
        }
        # Try basic personalization if resume content is available
        if resume_content and len(resume_content.strip()) > 50:
            print("DEBUG: Attempting basic resume-based personalization for fallback questions")
            # This is a simple fallback - ideally we'd use AI for this too

        return fallbacks.get(role, fallbacks['frontend'])

    def _fallback_final_summary(self, role: str, questions_and_answers: List[Dict]) -> Tuple[float, str]:
        """
        Generate final summary when AI is unavailable.
        """
        if not questions_and_answers:
            return 0.0, "No answers provided for evaluation."

        total_score = sum(item['score'] for item in questions_and_answers)
        avg_score = total_score / len(questions_and_answers)
        final_score = avg_score * 10  # Convert to 0-100 scale

        # Generate performance summary based on score
        if final_score >= 80:
            summary = f"Excellent performance in {role} interview. Strong technical knowledge and problem-solving skills demonstrated."
        elif final_score >= 70:
            summary = f"Good performance in {role} interview. Solid understanding of core concepts with room for improvement in advanced topics."
        elif final_score >= 60:
            summary = f"Adequate performance in {role} interview. Basic knowledge demonstrated but needs strengthening in several areas."
        elif final_score >= 50:
            summary = f"Below average performance in {role} interview. Foundational knowledge present but significant gaps in understanding."
        else:
            summary = f"Poor performance in {role} interview. Consider additional training and preparation before reapplying."

        return final_score, summary

    def _fallback_score_evaluation(self, question: str, answer: str, difficulty: str) -> Tuple[float, str]:
        """
        Intelligent fallback scoring when AI is unavailable.
        Analyzes answer quality based on basic heuristics.
        """
        answer = answer.strip().lower()
        question_lower = question.lower()

        # Check for obviously wrong/incorrect answers
        wrong_indicators = {
            'html': ['hut', 'cut', 'but', 'put', 'gut', 'hut', 'hot', 'hit', 'hat'],
            'css': ['sis', 'cus', 'cos', 'ces', 'cuss'],
            'javascript': ['java script', 'java-script', 'java scrip', 'java script language'],
            'python': ['pithon', 'pyton', 'python language only', 'snake'],
            'database': ['data base', 'data-base', 'data file', 'file storage'],
            'api': ['a p i', 'application', 'app interface', 'web service only']
        }

        # Check if answer matches wrong indicators
        for key, wrongs in wrong_indicators.items():
            if key in question_lower:
                for wrong in wrongs:
                    if wrong in answer:
                        return 1.0, "This answer appears to be incorrect. Please review the concept and provide a more accurate response."

        # Check for very short or empty answers
        if len(answer) < 5:
            return 2.0, "Answer is too brief. Please provide more detail about the concept."

        # Check for admissions of not knowing
        not_knowing = ['i don\'t know', 'i dont know', 'no idea', 'not sure', 'i have no idea', 'i\'m not sure']
        if any(phrase in answer for phrase in not_knowing):
            return 1.0, "It's better to attempt an answer than to admit you don't know. Consider what you do understand about the topic."

        # Basic keyword matching for common questions
        basic_keywords = {
            'html': ['markup', 'language', 'web', 'structure', 'hypertext'],
            'css': ['style', 'stylesheet', 'design', 'layout', 'cascading'],
            'javascript': ['programming', 'language', 'client', 'browser', 'dynamic'],
            'python': ['programming', 'language', 'versatile', 'scripting', 'general-purpose'],
            'database': ['data', 'storage', 'management', 'tables', 'queries'],
            'api': ['interface', 'communication', 'web', 'services', 'endpoints']
        }

        keyword_matches = 0
        total_keywords = 0

        for key, keywords in basic_keywords.items():
            if key in question_lower:
                total_keywords = len(keywords)
                keyword_matches = sum(1 for keyword in keywords if keyword in answer)
                break

        if total_keywords > 0:
            match_percentage = keyword_matches / total_keywords
            if match_percentage >= 0.6:
                score = 8.0
                feedback = "Good answer with relevant technical details."
            elif match_percentage >= 0.3:
                score = 6.0
                feedback = "Basic understanding shown, but could use more technical detail."
            else:
                score = 4.0
                feedback = "Answer lacks key technical concepts. Consider studying the fundamentals."
        else:
            # Generic evaluation for other questions
            score = 5.0
            feedback = "Answer provided basic information. Consider adding more technical depth."

        return score, feedback