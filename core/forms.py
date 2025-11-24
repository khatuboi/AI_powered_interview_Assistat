from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import UserProfile


class UserProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ['name', 'email', 'phone', 'resume']
        widgets = {
            'resume': forms.FileInput(attrs={'accept': '.pdf,.docx'}),
        }


class CandidateSignUpForm(UserCreationForm):
    profile_form = UserProfileForm()

    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2')


class InterviewerSignUpForm(UserCreationForm):
    profile_form = UserProfileForm()

    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2')


class LoginForm(forms.Form):
    username = forms.CharField(max_length=150)
    password = forms.CharField(widget=forms.PasswordInput)
    role = forms.ChoiceField(choices=UserProfile.ROLE_CHOICES, widget=forms.HiddenInput)


class RoleSelectionForm(forms.Form):
    role = forms.ChoiceField(
        choices=[
            ('frontend', 'Frontend Developer'),
            ('backend', 'Backend Developer'),
            ('data_analyst', 'Data Analyst'),
        ],
        widget=forms.RadioSelect
    )