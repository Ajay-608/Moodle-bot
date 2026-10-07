"""Create missing demo data locally; this command refuses production settings."""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from chat.models import ChatSession, Message
from core.models import LearningGap, ResponseFeedback, TAMSurvey, UserProfile
from knowledge.models import Document

User = get_user_model()

DEMO_USERS = [
    {
        "username": "admin",
        "password": "admin123",
        "email": "admin@moodlebot.edu",
        "first_name": "System",
        "last_name": "Administrator",
        "user_type": "admin",
        "is_staff": True,
        "is_superuser": True,
    },
    {
        "username": "prof_smith",
        "password": "teacher123",
        "email": "prof.smith@university.edu",
        "first_name": "Dr. John",
        "last_name": "Smith",
        "user_type": "teacher",
        "is_staff": True,
    },
    {
        "username": "prof_jones",
        "password": "teacher123",
        "email": "prof.jones@university.edu",
        "first_name": "Dr. Sarah",
        "last_name": "Jones",
        "user_type": "teacher",
        "is_staff": True,
    },
    {
        "username": "alice_student",
        "password": "student123",
        "email": "alice@student.edu",
        "first_name": "Alice",
        "last_name": "Anderson",
        "user_type": "student",
    },
    {
        "username": "bob_student",
        "password": "student123",
        "email": "bob@student.edu",
        "first_name": "Bob",
        "last_name": "Brown",
        "user_type": "student",
    },
    {
        "username": "charlie_student",
        "password": "student123",
        "email": "charlie@student.edu",
        "first_name": "Charlie",
        "last_name": "Clark",
        "user_type": "student",
    },
    {
        "username": "diana_student",
        "password": "student123",
        "email": "diana@student.edu",
        "first_name": "Diana",
        "last_name": "Davis",
        "user_type": "student",
    },
    {
        "username": "eve_student",
        "password": "student123",
        "email": "eve@student.edu",
        "first_name": "Eve",
        "last_name": "Evans",
        "user_type": "student",
    },
]

DOCUMENTS = [
    (
        "Introduction to SQL",
        "SQL basics: SELECT, INSERT, UPDATE, DELETE. Master database queries.",
    ),
    (
        "Database Normalization Guide",
        "1NF, 2NF, 3NF, BCNF - reducing redundancy through normalization.",
    ),
    (
        "JOIN Operations Tutorial",
        "INNER JOIN, LEFT JOIN, RIGHT JOIN, FULL OUTER JOIN explained.",
    ),
    (
        "Indexing & Query Optimization",
        "Learn how indexes improve query performance in databases.",
    ),
]

SAMPLE_MESSAGES = [
    ("user", "What is SQL?", None),
    (
        "bot",
        "SQL (Structured Query Language) is used to manage relational databases.",
        0.95,
    ),
    ("user", "What are JOINs?", None),
    (
        "bot",
        "JOINs combine rows from multiple tables based on related columns.",
        0.92,
    ),
    ("user", "What is normalization?", None),
    (
        "bot",
        "Normalization reduces data redundancy by organizing data into multiple tables.",
        0.90,
    ),
]


class Command(BaseCommand):
    help = "Create missing demo users and sample data without resetting existing records"

    @transaction.atomic
    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError(
                "populate_sample_data is for local development only; it must "
                "not be run in production."
            )

        users_by_username = {}
        for user_data in DEMO_USERS:
            values = user_data.copy()
            password = values.pop("password")
            user_type = values.pop("user_type")
            user = User.objects.filter(username=values["username"]).first()
            if user is None:
                user = User.objects.create_user(password=password, **values)
                UserProfile.objects.create(user=user, user_type=user_type)
                self.stdout.write(f"Created demo account {user.username}.")
            else:
                self.stdout.write(f"Preserved existing account {user.username}.")
            users_by_username[user.username] = user

        students = [
            users_by_username[username]
            for username in (
                "alice_student",
                "bob_student",
                "charlie_student",
                "diana_student",
                "eve_student",
            )
            if username in users_by_username
        ]
        sample_sessions = []
        for student in students[:3]:
            title = f"Database Learning - {student.first_name}"
            session, created = ChatSession.objects.get_or_create(
                user=student,
                title=title,
            )
            if not created:
                continue
            sample_sessions.append(session)
            for index, (message_type, content, confidence) in enumerate(SAMPLE_MESSAGES):
                Message.objects.create(
                    session=session,
                    message_type=message_type,
                    content=content,
                    confidence_score=confidence,
                    created_at=timezone.now() - timedelta(days=index // 2),
                )

        for title, content in DOCUMENTS:
            Document.objects.get_or_create(
                title=title,
                content=content,
                course_id=1,
            )

        for session in sample_sessions[:2]:
            bot_messages = Message.objects.filter(
                session=session,
                message_type="bot",
                content__in=[message[1] for message in SAMPLE_MESSAGES if message[0] == "bot"],
            )
            for message in bot_messages:
                ResponseFeedback.objects.get_or_create(
                    message=message,
                    user=session.user,
                    defaults={"rating": 5, "comment": "Very helpful explanation!"},
                )

        for student in students:
            for topic, attempts, resources in (
                ("sql", 2, "SQL Tutorial Videos"),
                ("normalization", 3, "Normalization Examples & Exercises"),
            ):
                LearningGap.objects.get_or_create(
                    user=student,
                    topic=topic,
                    defaults={
                        "incorrect_attempts": attempts,
                        "suggested_resources": resources,
                    },
                )

        for student in students[:3]:
            TAMSurvey.objects.get_or_create(
                user=student,
                pu_score=5,
                eou_score=4,
                attitude_score=5,
                intention_score=4,
                feedback="MoodleBot is very useful for learning database concepts!",
            )

        self.stdout.write(self.style.SUCCESS("Sample data is ready; existing records were preserved."))
