from django.db import models
from django.contrib.auth.models import User
from django.core.validators import RegexValidator
from django.utils import timezone


class UserProfile(models.Model):
    ROLE_CHOICES = [
        ('candidate', 'Candidate'),
        ('interviewer', 'Interviewer'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='candidate')
    name = models.CharField(max_length=100, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    phone_regex = RegexValidator(regex=r'^\+?1?\d{9,15}$', message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed.")
    phone = models.CharField(validators=[phone_regex], max_length=17, blank=True, null=True)
    resume = models.FileField(upload_to='resumes/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.role}"


class InterviewSession(models.Model):
    ROLE_CHOICES = [
        ('frontend', 'Frontend Developer'),
        ('backend', 'Backend Developer'),
        ('data_analyst', 'Data Analyst'),
    ]

    STATUS_CHOICES = [
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('abandoned', 'Abandoned'),
    ]

    candidate = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='interview_sessions')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='in_progress')
    final_score = models.FloatField(null=True, blank=True)
    summary = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.candidate.user.username} - {self.role} Interview ({self.status})"

    def complete_session(self):
        """Mark the session as completed and set completion timestamp."""
        self.status = 'completed'
        self.completed_at = timezone.now()
        self.save()


class InterviewQuestion(models.Model):
    DIFFICULTY_CHOICES = [
        ('easy', 'Easy'),
        ('medium', 'Medium'),
        ('hard', 'Hard'),
    ]

    session = models.ForeignKey(InterviewSession, on_delete=models.CASCADE, related_name='questions')
    question_text = models.TextField()
    difficulty = models.CharField(max_length=10, choices=DIFFICULTY_CHOICES)
    order = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order']
        unique_together = ['session', 'order']

    def __str__(self):
        return f"Question {self.order} - {self.difficulty}: {self.question_text[:50]}..."


class InterviewAnswer(models.Model):
    question = models.OneToOneField(InterviewQuestion, on_delete=models.CASCADE, related_name='answer')
    answer_text = models.TextField()
    score = models.FloatField(null=True, blank=True)  # AI-assigned score for this answer
    feedback = models.TextField(blank=True, null=True)  # AI feedback
    answered_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Answer to Question {self.question.order}: {self.answer_text[:50]}..."
