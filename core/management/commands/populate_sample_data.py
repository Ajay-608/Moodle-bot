"""
Django management command to populate sample data for testing
Usage: python manage.py populate_sample_data
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
from core.models import UserProfile, ResponseFeedback, LearningGap, TAMSurvey
from chat.models import ChatSession, Message
from knowledge.models import Document

class Command(BaseCommand):
    help = 'Populate database with sample data for testing'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('🚀 Starting data population...'))
        
        # Clear existing data (optional)
        # User.objects.all().delete()
        
        # Create Admin User
        admin, _ = User.objects.get_or_create(
            username='admin',
            defaults={
                'email': 'admin@moodlebot.edu',
                'is_staff': True,
                'is_superuser': True,
                'first_name': 'System',
                'last_name': 'Administrator'
            }
        )
        admin.set_password('admin123')
        admin.save()
        profile, _ = UserProfile.objects.get_or_create(user=admin, defaults={'user_type': 'admin'})
        self.stdout.write(self.style.SUCCESS(f'✅ Admin created/updated: {admin.username}'))
        
        # Create Teacher Users
        teachers_data = [
            {'username': 'prof_smith', 'email': 'prof.smith@university.edu', 'first_name': 'Dr. John', 'last_name': 'Smith'},
            {'username': 'prof_jones', 'email': 'prof.jones@university.edu', 'first_name': 'Dr. Sarah', 'last_name': 'Jones'},
        ]
        
        for teacher_data in teachers_data:
            teacher, _ = User.objects.get_or_create(
                username=teacher_data['username'],
                defaults={**teacher_data, 'is_staff': True}
            )
            teacher.set_password('teacher123')
            teacher.save()
            profile, _ = UserProfile.objects.get_or_create(user=teacher, defaults={'user_type': 'teacher'})
            self.stdout.write(self.style.SUCCESS(f'✅ Teacher created/updated: {teacher.username}'))
        
        # Create Student Users
        students_data = [
            {'username': 'alice_student', 'email': 'alice@student.edu', 'first_name': 'Alice', 'last_name': 'Anderson'},
            {'username': 'bob_student', 'email': 'bob@student.edu', 'first_name': 'Bob', 'last_name': 'Brown'},
            {'username': 'charlie_student', 'email': 'charlie@student.edu', 'first_name': 'Charlie', 'last_name': 'Clark'},
            {'username': 'diana_student', 'email': 'diana@student.edu', 'first_name': 'Diana', 'last_name': 'Davis'},
            {'username': 'eve_student', 'email': 'eve@student.edu', 'first_name': 'Eve', 'last_name': 'Evans'},
        ]
        
        students = []
        for student_data in students_data:
            student, _ = User.objects.get_or_create(
                username=student_data['username'],
                defaults=student_data
            )
            student.set_password('student123')
            student.save()
            profile, _ = UserProfile.objects.get_or_create(user=student, defaults={'user_type': 'student'})
            students.append(student)
            self.stdout.write(self.style.SUCCESS(f'✅ Student created/updated: {student.username}'))
        
        # Create sample chat sessions and messages
        for student in students[:3]:
            session = ChatSession.objects.create(
                user=student,
                title=f"Database Learning - {student.first_name}",
            )
            
            # Create sample messages
            questions = [
                ("What is SQL?", "SQL (Structured Query Language) is used to manage relational databases.", 0.95),
                ("What are JOINs?", "JOINs combine rows from multiple tables based on related columns.", 0.92),
                ("What is normalization?", "Normalization reduces data redundancy by organizing data into multiple tables.", 0.90),
            ]
            
            for i, (q, a, conf) in enumerate(questions):
                Message.objects.create(
                    session=session,
                    message_type='user',
                    content=q,
                    created_at=timezone.now() - timedelta(days=i)
                )
                Message.objects.create(
                    session=session,
                    message_type='bot',
                    content=a,
                    confidence_score=conf,
                    created_at=timezone.now() - timedelta(days=i, hours=1)
                )
        
        self.stdout.write(self.style.SUCCESS('✅ Chat sessions and messages created'))
        
        # Create sample documents
        documents_data = [
            {
                'title': 'Introduction to SQL',
                'content': 'SQL basics: SELECT, INSERT, UPDATE, DELETE. Master database queries.',
                'course_id': 1
            },
            {
                'title': 'Database Normalization Guide',
                'content': '1NF, 2NF, 3NF, BCNF - reducing redundancy through normalization.',
                'course_id': 1
            },
            {
                'title': 'JOIN Operations Tutorial',
                'content': 'INNER JOIN, LEFT JOIN, RIGHT JOIN, FULL OUTER JOIN explained.',
                'course_id': 1
            },
            {
                'title': 'Indexing & Query Optimization',
                'content': 'Learn how indexes improve query performance in databases.',
                'course_id': 1
            },
        ]
        
        for doc_data in documents_data:
            Document.objects.create(**doc_data)
        
        self.stdout.write(self.style.SUCCESS('✅ Sample documents created'))
        
        # Create sample feedback
        for student in students[:2]:
            messages = Message.objects.filter(session__user=student, message_type='bot')[:2]
            for msg in messages:
                ResponseFeedback.objects.get_or_create(
                    message=msg,
                    user=student,
                    defaults={'rating': 5, 'comment': 'Very helpful explanation!'}
                )
        
        self.stdout.write(self.style.SUCCESS('✅ Sample feedback created'))
        
        # Create sample learning gaps
        for student in students:
            LearningGap.objects.get_or_create(
                user=student,
                topic='sql',
                defaults={'incorrect_attempts': 2, 'suggested_resources': 'SQL Tutorial Videos'}
            )
            LearningGap.objects.get_or_create(
                user=student,
                topic='normalization',
                defaults={'incorrect_attempts': 3, 'suggested_resources': 'Normalization Examples & Exercises'}
            )
        
        self.stdout.write(self.style.SUCCESS('✅ Sample learning gaps created'))
        
        # Create sample TAM surveys
        for student in students[:3]:
            TAMSurvey.objects.create(
                user=student,
                pu_score=5,  # Perceived Usefulness
                eou_score=4,  # Ease of Use
                attitude_score=5,  # Attitude toward Using
                intention_score=4,  # Behavioral Intention
                feedback='MoodleBot is very useful for learning database concepts!'
            )
        
        self.stdout.write(self.style.SUCCESS('✅ Sample TAM surveys created'))
        
        # Print summary
        self.stdout.write(self.style.SUCCESS('\n' + '='*60))
        self.stdout.write(self.style.SUCCESS('📊 DATA POPULATION SUMMARY'))
        self.stdout.write(self.style.SUCCESS('='*60))
        self.stdout.write(self.style.SUCCESS(f'✅ Admins: {User.objects.filter(profile__user_type="admin").count()}'))
        self.stdout.write(self.style.SUCCESS(f'✅ Teachers: {User.objects.filter(profile__user_type="teacher").count()}'))
        self.stdout.write(self.style.SUCCESS(f'✅ Students: {User.objects.filter(profile__user_type="student").count()}'))
        self.stdout.write(self.style.SUCCESS(f'✅ Chat Sessions: {ChatSession.objects.count()}'))
        self.stdout.write(self.style.SUCCESS(f'✅ Messages: {Message.objects.count()}'))
        self.stdout.write(self.style.SUCCESS(f'✅ Documents: {Document.objects.count()}'))
        self.stdout.write(self.style.SUCCESS(f'✅ Feedback Entries: {ResponseFeedback.objects.count()}'))
        self.stdout.write(self.style.SUCCESS(f'✅ Learning Gaps: {LearningGap.objects.count()}'))
        self.stdout.write(self.style.SUCCESS(f'✅ TAM Surveys: {TAMSurvey.objects.count()}'))
        self.stdout.write(self.style.SUCCESS('='*60))
        
        self.stdout.write(self.style.SUCCESS('\n🎉 Sample data population complete!'))
        self.stdout.write(self.style.WARNING('\n🔑 DEFAULT CREDENTIALS:'))
        self.stdout.write('   Admin: admin / admin123')
        self.stdout.write('   Teacher: prof_smith / teacher123')
        self.stdout.write('   Student: alice_student / student123')
