from django.contrib import admin
from .models import UserProfile, InterviewSession, InterviewQuestion, InterviewAnswer


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'name', 'email', 'phone', 'created_at')
    list_filter = ('role', 'created_at')
    search_fields = ('user__username', 'name', 'email')
    readonly_fields = ('created_at',)
    readonly_fields = ('created_at',)


@admin.register(InterviewSession)
class InterviewSessionAdmin(admin.ModelAdmin):
    list_display = ('candidate', 'role', 'status', 'final_score', 'created_at', 'completed_at')
    list_filter = ('role', 'status', 'created_at')
    search_fields = ('candidate__user__username', 'candidate__name')
    readonly_fields = ('created_at', 'completed_at')
    readonly_fields = ('created_at', 'completed_at')


@admin.register(InterviewQuestion)
class InterviewQuestionAdmin(admin.ModelAdmin):
    list_display = ('session', 'difficulty', 'order', 'question_text')
    list_filter = ('difficulty',)
    search_fields = ('question_text',)
    readonly_fields = ('created_at',)


@admin.register(InterviewAnswer)
class InterviewAnswerAdmin(admin.ModelAdmin):
    list_display = ('question', 'score', 'answered_at')
    list_filter = ('answered_at',)
    search_fields = ('answer_text',)
    readonly_fields = ('answered_at',)
