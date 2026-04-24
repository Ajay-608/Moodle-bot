from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import User

class RegisterForm(UserCreationForm):
    user_type = forms.ChoiceField(
        choices=[
            ('admin', 'Admin (Full Access )'),
            ('teacher', 'Teacher (Courses + PDFs )'),
            ('student', 'Student (View Only )'),
        ],
        widget=forms.RadioSelect,
        required=True
    )
    
    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2', 'user_type']
