from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('register/candidate/', views.register_candidate, name='register_candidate'),
    path('register/interviewer/', views.register_interviewer, name='register_interviewer'),

    # Candidate views
    path('dashboard/', views.candidate_dashboard, name='candidate_dashboard'),
    path('interview/<int:session_id>/', views.interview, name='interview'),

    # Interviewer views
    path('interviewer/dashboard/', views.interviewer_dashboard, name='interviewer_dashboard'),
    path('interviewer/interview/<int:session_id>/', views.interview_detail, name='interview_detail'),

    # API endpoints
    path('api/submit-answer/', views.submit_answer, name='submit_answer'),
]