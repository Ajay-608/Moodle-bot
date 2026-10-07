import tempfile
from pathlib import Path

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.core.management import call_command
from django.contrib.auth.models import User
from django.core.management.base import CommandError
from django.test import override_settings

from core.models import LearningGap, ResponseFeedback, TAMSurvey, UserProfile
from chat.models import ChatSession, Message
from knowledge.models import Document


class AuthenticationFlowTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='login-test-user',
            password='Strong-test-password-123',
        )

    def test_login_page_is_public_and_renders_form(self):
        response = self.client.get(reverse('core:login'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Welcome Back')
        self.assertContains(response, 'name="csrfmiddlewaretoken"')

    def test_invalid_login_keeps_login_page_and_shows_error(self):
        response = self.client.post(
            reverse('core:login'),
            {'username': self.user.username, 'password': 'wrong-password'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Please enter a correct username and password.')

    def test_valid_login_redirects_to_dashboard(self):
        response = self.client.post(
            reverse('core:login'),
            {'username': self.user.username, 'password': 'Strong-test-password-123'},
        )

        self.assertRedirects(response, reverse('core:dashboard'))
        self.assertTrue(response.wsgi_request.user.is_authenticated)

    def test_new_django_superuser_gets_admin_profile_and_dashboard(self):
        superuser = get_user_model().objects.create_superuser(
            username='fresh-postgres-admin',
            email='new-admin@example.com',
            password='Strong-admin-password-123',
        )

        response = self.client.post(
            reverse('core:admin_login'),
            {
                'username': superuser.username,
                'password': 'Strong-admin-password-123',
            },
        )

        self.assertRedirects(response, reverse('core:dashboard'))
        self.assertEqual(superuser.profile.user_type, 'admin')
        self.assertTrue(response.wsgi_request.user.is_authenticated)

    def test_logout_redirects_to_login(self):
        self.client.force_login(self.user)

        response = self.client.post(reverse('core:logout'))

        self.assertRedirects(response, reverse('core:login'))
        self.assertEqual(self.client.get(reverse('core:login')).status_code, 200)

    def test_protected_dashboard_redirects_to_login(self):
        response = self.client.get(reverse('core:dashboard'))

        self.assertRedirects(
            response,
            f"{reverse('core:login')}?next={reverse('core:dashboard')}",
            fetch_redirect_response=False,
        )

    def test_public_registration_always_creates_a_student(self):
        response = self.client.post(
            reverse('core:register'),
            {
                'username': 'registered-user',
                'email': 'student@example.com',
                'password1': 'Strong-test-password-456',
                'password2': 'Strong-test-password-456',
                'user_type': 'admin',
            },
        )

        self.assertRedirects(response, reverse('core:login'))
        user = get_user_model().objects.get(username='registered-user')
        self.assertEqual(user.profile.user_type, 'student')
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)

    @override_settings(DEBUG=True)
    def test_sample_data_command_preserves_existing_accounts_and_is_idempotent(self):
        existing_user = User.objects.create_user(
            username='admin',
            password='Existing-secret-password-789',
            email='real-admin@example.com',
            is_staff=False,
        )
        UserProfile.objects.create(user=existing_user, user_type='student')
        existing_student = User.objects.create_user(
            username='alice_student',
            password='Existing-student-password-321',
        )
        UserProfile.objects.create(user=existing_student, user_type='student')
        profileless_user = User.objects.create_user(
            username='prof_jones',
            password='Profileless-existing-password-654',
        )
        existing_session = ChatSession.objects.create(
            user=existing_student,
            title='Database Learning - Alice',
        )
        existing_message = Message.objects.create(
            session=existing_session,
            message_type='user',
            content='Keep this conversation unchanged.',
        )

        call_command('populate_sample_data', verbosity=0)
        self.assertTrue(
            User.objects.get(username='prof_smith').check_password('teacher123')
        )
        counts_after_first_run = (
            User.objects.count(),
            UserProfile.objects.count(),
            ChatSession.objects.count(),
            Message.objects.count(),
            Document.objects.count(),
            LearningGap.objects.count(),
            ResponseFeedback.objects.count(),
            TAMSurvey.objects.count(),
        )
        call_command('populate_sample_data', verbosity=0)

        existing_user.refresh_from_db()
        self.assertEqual(existing_user.email, 'real-admin@example.com')
        self.assertTrue(existing_user.check_password('Existing-secret-password-789'))
        self.assertFalse(existing_user.is_staff)
        self.assertEqual(existing_user.profile.user_type, 'student')
        existing_message.refresh_from_db()
        self.assertEqual(existing_message.content, 'Keep this conversation unchanged.')
        self.assertEqual(existing_session.messages.count(), 1)
        self.assertFalse(UserProfile.objects.filter(user=profileless_user).exists())
        self.assertEqual(
            (
                User.objects.count(),
                UserProfile.objects.count(),
                ChatSession.objects.count(),
                Message.objects.count(),
                Document.objects.count(),
                LearningGap.objects.count(),
                ResponseFeedback.objects.count(),
                TAMSurvey.objects.count(),
            ),
            counts_after_first_run,
        )

    @override_settings(DEBUG=False)
    def test_sample_data_command_does_not_create_default_accounts_in_production(self):
        with self.assertRaises(CommandError):
            call_command('populate_sample_data', verbosity=0)

        self.assertFalse(User.objects.filter(username='admin').exists())

    def test_fresh_knowledge_initializer_creates_deterministic_source_chunks(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            media_dir = Path(temporary_directory) / 'media'
            media_dir.mkdir()
            (media_dir / 'Course.txt').write_text('a' * 510, encoding='utf-8')
            with override_settings(BASE_DIR=Path(temporary_directory)):
                call_command('initialize_knowledge_base', verbosity=0)

        documents = list(Document.objects.order_by('title'))
        self.assertEqual(len(documents), 2)
        self.assertEqual(documents[0].title, 'Course.txt - Part 1')
        self.assertEqual(len(documents[0].content), 500)
        self.assertEqual(documents[0].chunk_id, 1)
        self.assertEqual(documents[1].title, 'Course.txt - Part 2')
        self.assertEqual(documents[1].content, 'a' * 10)
        self.assertNotEqual(documents[0].pk, documents[1].pk)

    def test_knowledge_initializer_refuses_existing_documents_without_deleting_them(self):
        original = Document.objects.create(
            title='Existing content',
            content='Keep this production document.',
            course_id=1,
        )

        with self.assertRaises(CommandError):
            call_command('initialize_knowledge_base', verbosity=0)

        self.assertEqual(Document.objects.count(), 1)
        original.refresh_from_db()
        self.assertEqual(original.content, 'Keep this production document.')
