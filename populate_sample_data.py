import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'moodlebot.settings')
django.setup()

from core.models import User, Course
from django.contrib.auth import get_user_model

User = get_user_model()

# Create sample course
course, created = Course.objects.get_or_create(
    code='CS401',
    defaults={
        'title': 'Database Systems',
        'description': 'Advanced Database Management Systems with SQL and Normalization',
        'teacher_id': 1  # Admin user
    }
)

print(f"✅ Course created: {course}")
