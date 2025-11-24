from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.db import transaction
import json

from .models import UserProfile, InterviewSession, InterviewQuestion, InterviewAnswer
from .forms import LoginForm, RoleSelectionForm, UserProfileForm
from .utils import update_profile_from_resume
from .gemini_integration import GeminiInterviewService


def home(request):
    """Landing page - redirects to appropriate dashboard based on user role."""
    if request.user.is_authenticated:
        try:
            profile = request.user.userprofile
            if profile.role == 'candidate':
                return redirect('candidate_dashboard')
            else:
                return redirect('interviewer_dashboard')
        except UserProfile.DoesNotExist:
            return redirect('login')
    return render(request, 'core/home.html')


def login_view(request):
    """Login view for both candidates and interviewers."""
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            role = form.cleaned_data['role']

            user = authenticate(username=username, password=password)
            if user is not None:
                try:
                    profile = user.userprofile
                    if profile.role == role:
                        login(request, user)
                        messages.success(request, f'Welcome back, {user.username}!')

                        if role == 'candidate':
                            return redirect('candidate_dashboard')
                        else:
                            return redirect('interviewer_dashboard')
                    else:
                        messages.error(request, 'Invalid role for this account.')
                except UserProfile.DoesNotExist:
                    messages.error(request, 'User profile not found.')
            else:
                messages.error(request, 'Invalid username or password.')
    else:
        form = LoginForm()

    return render(request, 'core/login.html', {'form': form})


def register_candidate(request):
    """Registration for candidates."""
    if request.method == 'POST':
        # Handle form submission for candidate registration
        username = request.POST.get('username')
        email = request.POST.get('email')
        password1 = request.POST.get('password1')
        password2 = request.POST.get('password2')

        if password1 != password2:
            messages.error(request, 'Passwords do not match.')
            return render(request, 'core/register_candidate.html')

        try:
            from django.contrib.auth.models import User
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password1
            )
            UserProfile.objects.create(user=user, role='candidate')
            messages.success(request, 'Account created successfully! Please log in.')
            return redirect('login')
        except Exception as e:
            print(f"Registration error: {e}")
            messages.error(request, 'Username already exists or invalid data.')

    return render(request, 'core/register_candidate.html')


def register_interviewer(request):
    """Registration for interviewers."""
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password1 = request.POST.get('password1')
        password2 = request.POST.get('password2')

        if password1 != password2:
            messages.error(request, 'Passwords do not match.')
            return render(request, 'core/register_interviewer.html')

        try:
            from django.contrib.auth.models import User
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password1
            )
            UserProfile.objects.create(user=user, role='interviewer')
            messages.success(request, 'Account created successfully! Please log in.')
            return redirect('login')
        except Exception as e:
            print(f"Registration error: {e}")
            messages.error(request, 'Username already exists or invalid data.')

    return render(request, 'core/register_interviewer.html')


def logout_view(request):
    """Logout view."""
    logout(request)
    messages.info(request, 'You have been logged out.')
    return redirect('home')


@login_required
def candidate_dashboard(request):
    """Candidate dashboard with role selection and resume upload."""
    profile = request.user.userprofile

    if request.method == 'POST':
        if 'resume_upload' in request.POST:
            form = UserProfileForm(request.POST, request.FILES, instance=profile)
            if form.is_valid():
                form.save()
                update_profile_from_resume(profile)
                messages.success(request, 'Resume uploaded and processed successfully!')
                return redirect('candidate_dashboard')
        elif 'role_selection' in request.POST:
            form = RoleSelectionForm(request.POST)
            if form.is_valid():
                role = form.cleaned_data['role']
                print(f"DEBUG: Starting interview for role: {role}")  # Debug log
                # Check if there's an existing incomplete session
                existing_session = InterviewSession.objects.filter(
                    candidate=profile,
                    role=role,
                    status__in=['in_progress', 'abandoned']
                ).first()

                if existing_session:
                    print(f"DEBUG: Found existing session: {existing_session.id}")  # Debug log
                    return redirect('interview', session_id=existing_session.id)
                else:
                    print(f"DEBUG: Creating new session for role: {role}")  # Debug log
                    # Create new session
                    try:
                        session = InterviewSession.objects.create(candidate=profile, role=role)
                        print(f"DEBUG: Created session: {session.id}")  # Debug log

                        # Generate questions using Gemini with resume context
                        try:
                            gemini_service = GeminiInterviewService()

                            # Read resume content if available for personalized questions
                            resume_content = ""
                            if profile.resume:
                                try:
                                    file_path = profile.resume.path
                                    file_extension = file_path.split('.')[-1].lower()

                                    if file_extension == 'pdf':
                                        # Handle PDF files
                                        from PyPDF2 import PdfReader
                                        reader = PdfReader(file_path)
                                        resume_content = ""
                                        for page in reader.pages:
                                            resume_content += page.extract_text() + "\n"
                                    elif file_extension in ['docx', 'doc']:
                                        # Handle Word documents
                                        from docx2txt import process
                                        resume_content = process(file_path)
                                    else:
                                        # Try as plain text
                                        with open(file_path, 'r', encoding='utf-8') as f:
                                            resume_content = f.read()

                                    print(f"DEBUG: Read resume content ({len(resume_content)} chars) from {file_extension.upper()} file for personalized questions")  # Debug log

                                    # Limit content to avoid token limits
                                    if len(resume_content) > 2000:
                                        resume_content = resume_content[:2000] + "..."

                                except Exception as e:
                                    print(f"DEBUG: Could not read resume file: {e}")  # Debug log
                                    resume_content = ""

                            questions_data = gemini_service.generate_interview_questions(role, resume_content)
                            print(f"DEBUG: Generated {len(questions_data)} questions")  # Debug log

                            if len(questions_data) == 0:
                                raise ValueError("No questions generated")

                            for i, q_data in enumerate(questions_data):
                                InterviewQuestion.objects.create(
                                    session=session,
                                    question_text=q_data['question'],
                                    difficulty=q_data['difficulty'],
                                    order=i+1
                                )
                                print(f"DEBUG: Created question {i+1}: {q_data['question'][:50]}...")  # Debug log

                            print(f"DEBUG: Redirecting to interview: {session.id}")  # Debug log
                            messages.success(request, f'Interview session created successfully for {role} role!')
                            return redirect('interview', session_id=session.id)
                        except Exception as e:
                            print(f"DEBUG: Failed to generate questions: {str(e)}")  # Debug log
                            # Use fallback questions if Gemini fails
                            try:
                                questions_data = gemini_service._get_fallback_questions(role)
                                print(f"DEBUG: Using fallback questions: {len(questions_data)}")  # Debug log

                                for i, q_data in enumerate(questions_data):
                                    InterviewQuestion.objects.create(
                                        session=session,
                                        question_text=q_data['question'],
                                        difficulty=q_data['difficulty'],
                                        order=i+1
                                    )
                                    print(f"DEBUG: Created fallback question {i+1}: {q_data['question'][:50]}...")  # Debug log

                                print(f"DEBUG: Redirecting to interview with fallback questions: {session.id}")  # Debug log
                                messages.success(request, f'Interview session created successfully for {role} role!')
                                return redirect('interview', session_id=session.id)
                            except Exception as fallback_e:
                                print(f"DEBUG: Fallback also failed: {str(fallback_e)}")  # Debug log
                                messages.error(request, f'Failed to generate questions: {str(e)}')
                                session.delete()
                                return redirect('candidate_dashboard')
                    except Exception as e:
                        print(f"DEBUG: Failed to create session: {str(e)}")  # Debug log
                        messages.error(request, f'Failed to create interview session: {str(e)}')
                        return redirect('candidate_dashboard')
            else:
                print(f"DEBUG: Role selection form is invalid: {form.errors}")  # Debug log
                messages.error(request, 'Please select a valid role.')

    profile_form = UserProfileForm(instance=profile)
    role_form = RoleSelectionForm()

    # Get existing sessions
    sessions = InterviewSession.objects.filter(candidate=profile).order_by('-created_at')
    print(f"DEBUG: Found {sessions.count()} sessions for user {profile.user.username}")  # Debug log

    context = {
        'profile': profile,
        'profile_form': profile_form,
        'role_form': role_form,
        'sessions': sessions,
    }

    return render(request, 'core/candidate_dashboard.html', context)


@login_required
def interviewer_dashboard(request):
    """Interviewer dashboard showing all candidates and their results."""
    profile = request.user.userprofile

    if profile.role != 'interviewer':
        messages.error(request, 'Access denied.')
        return redirect('home')

    # Get all completed interview sessions
    sessions = InterviewSession.objects.filter(
        status='completed'
    ).select_related('candidate__user').order_by('-completed_at')

    # Search and filter functionality
    search_query = request.GET.get('search', '')
    role_filter = request.GET.get('role', '')
    status_filter = request.GET.get('status', '')

    if search_query:
        sessions = sessions.filter(
            candidate__user__username__icontains=search_query
        ) | sessions.filter(
            candidate__name__icontains=search_query
        )

    if role_filter:
        sessions = sessions.filter(role=role_filter)

    if status_filter:
        sessions = sessions.filter(status=status_filter)

    context = {
        'sessions': sessions,
        'search_query': search_query,
        'role_filter': role_filter,
        'status_filter': status_filter,
        'roles': InterviewSession.ROLE_CHOICES,
        'statuses': InterviewSession.STATUS_CHOICES,
    }

    return render(request, 'core/interviewer_dashboard.html', context)


@login_required
def interview_detail(request, session_id):
    """Detailed view of a specific interview session for interviewers."""
    profile = request.user.userprofile

    if profile.role != 'interviewer':
        messages.error(request, 'Access denied.')
        return redirect('home')

    session = get_object_or_404(
        InterviewSession.objects.select_related('candidate__user'),
        id=session_id
    )

    questions = InterviewQuestion.objects.filter(session=session).prefetch_related('answer')

    context = {
        'session': session,
        'questions': questions,
    }

    return render(request, 'core/interview_detail.html', context)


@login_required
def interview(request, session_id):
    """Main interview interface for candidates."""
    profile = request.user.userprofile

    session = get_object_or_404(
        InterviewSession,
        id=session_id,
        candidate=profile
    )

    if session.status == 'completed':
        messages.info(request, 'This interview has been completed.')
        return redirect('candidate_dashboard')

    questions = InterviewQuestion.objects.filter(session=session).order_by('order')
    total_questions = questions.count()

    # Get current question (first unanswered question)
    current_question = None
    answered_count = 0

    for question in questions:
        if hasattr(question, 'answer'):
            answered_count += 1
        else:
            current_question = question
            break

    if not current_question and answered_count == total_questions:
        # All questions answered, complete the session
        try:
            gemini_service = GeminiInterviewService()

            # Prepare data for final evaluation
            qa_data = []
            for question in questions:
                if hasattr(question, 'answer'):
                    qa_data.append({
                        'question': question.question_text,
                        'answer': question.answer.answer_text,
                        'score': question.answer.score or 0,
                        'difficulty': question.difficulty
                    })

            final_score, summary = gemini_service.generate_final_summary(session.role, qa_data)

            session.final_score = final_score
            session.summary = summary
            session.complete_session()

            messages.success(request, f'Interview completed! Final score: {final_score:.1f}/100')
            return redirect('candidate_dashboard')

        except Exception as e:
            messages.error(request, f'Failed to complete interview: {str(e)}')
            return redirect('candidate_dashboard')

    context = {
        'session': session,
        'current_question': current_question,
        'total_questions': total_questions,
        'answered_count': answered_count,
        'progress_percentage': (answered_count / total_questions) * 100 if total_questions > 0 else 0,
    }

    return render(request, 'core/interview.html', context)


@csrf_exempt
@login_required
@require_POST
def submit_answer(request):
    """AJAX endpoint to submit answer and get evaluation."""
    try:
        data = json.loads(request.body)
        question_id = data.get('question_id')
        answer_text = data.get('answer')

        if not question_id or not answer_text:
            return JsonResponse({'error': 'Missing required fields'}, status=400)

        question = get_object_or_404(InterviewQuestion, id=question_id)

        # Check if user owns this session
        if question.session.candidate.user != request.user:
            return JsonResponse({'error': 'Unauthorized'}, status=403)

        # Check if question already has an answer
        if hasattr(question, 'answer'):
            return JsonResponse({'error': 'Question already answered'}, status=400)

        # Evaluate answer using Gemini
        try:
            gemini_service = GeminiInterviewService()
            score, feedback = gemini_service.evaluate_answer(
                question.question_text,
                answer_text,
                question.difficulty
            )

            # Save answer
            answer = InterviewAnswer.objects.create(
                question=question,
                answer_text=answer_text,
                score=score,
                feedback=feedback
            )

            return JsonResponse({
                'success': True,
                'score': score,
                'feedback': feedback,
                'question_id': question_id
            })

        except Exception as e:
            print(f"Gemini evaluation error: {e}")
            # Save answer without evaluation
            answer = InterviewAnswer.objects.create(
                question=question,
                answer_text=answer_text
            )
            return JsonResponse({
                'success': True,
                'score': None,
                'feedback': 'Evaluation temporarily unavailable.',
                'question_id': question_id
            })

    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        print(f"Submit answer error: {e}")
        return JsonResponse({'error': 'Server error'}, status=500)
