import os
import json
import tempfile
import threading
import time
from unittest.mock import patch
from pathlib import Path

import faiss
import numpy as np
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.core.management import call_command
from django.contrib.auth.models import User
from django.core.management.base import CommandError
from django.test import override_settings

from core.models import LearningGap, ResponseFeedback, TAMSurvey, UserProfile
from core.faiss_index import (
    EMBEDDING_DIMENSION,
    build_faiss_index,
    document_ids,
    ensure_faiss_index,
    index_build_lock,
    validate_index,
)
from chat.models import ChatSession, Message
from knowledge.models import Document


class FakeEmbeddingModel:
    def get_sentence_embedding_dimension(self):
        return EMBEDDING_DIMENSION

    def encode(self, texts, **kwargs):
        return np.ones((len(texts), EMBEDDING_DIMENSION), dtype=np.float32)


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

    def test_faiss_builder_and_rag_engine_use_the_same_configured_path(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            index_path = Path(temporary_directory) / 'rag_index.faiss'
            document = Document.objects.create(
                title='SQL',
                content='Structured Query Language',
                course_id=1,
            )
            with override_settings(FAISS_INDEX_PATH=index_path):
                built_index = build_faiss_index(model=FakeEmbeddingModel())
                from rag_engine import RAGEngine

                engine = RAGEngine()
                engine.model = FakeEmbeddingModel()
                docs, _ = engine.search('What is SQL?')

            self.assertTrue(index_path.is_file())
            self.assertEqual(built_index.ntotal, 1)
            self.assertEqual([doc.pk for doc in docs], [document.pk])


class FAISSIndexTests(TestCase):
    def setUp(self):
        self.documents = [
            Document.objects.create(
                title=f'Document {number}',
                content=f'Course text {number}',
                course_id=1,
            )
            for number in range(1, 3)
        ]
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.index_path = Path(self.temporary_directory.name) / 'rag_index.faiss'

    def tearDown(self):
        self.temporary_directory.cleanup()

    def test_missing_index_is_built_from_active_documents(self):
        index = ensure_faiss_index(
            self.index_path,
            model_factory=FakeEmbeddingModel,
        )

        self.assertTrue(self.index_path.is_file())
        self.assertEqual(index.ntotal, len(self.documents))
        validate_index(faiss.read_index(str(self.index_path)), document_ids())

    def test_valid_index_is_reused_without_loading_the_model(self):
        built = build_faiss_index(self.index_path, model=FakeEmbeddingModel())

        with patch(
            'core.faiss_index._build_faiss_index',
            side_effect=AssertionError('valid index should be reused'),
        ):
            loaded = ensure_faiss_index(self.index_path)

        self.assertEqual(loaded.ntotal, built.ntotal)

    def test_corrupt_index_is_rebuilt(self):
        self.index_path.write_bytes(b'not a FAISS index')

        rebuilt = ensure_faiss_index(
            self.index_path,
            model_factory=FakeEmbeddingModel,
        )

        self.assertEqual(rebuilt.ntotal, len(self.documents))

    def test_wrong_dimensional_index_is_rebuilt(self):
        invalid = faiss.IndexIDMap2(faiss.IndexFlatL2(128))
        invalid.add_with_ids(
            np.zeros((len(self.documents), 128), dtype=np.float32),
            np.asarray([document.pk for document in self.documents], dtype=np.int64),
        )
        faiss.write_index(invalid, str(self.index_path))

        rebuilt = ensure_faiss_index(
            self.index_path,
            model_factory=FakeEmbeddingModel,
        )

        self.assertEqual(rebuilt.d, EMBEDDING_DIMENSION)

    def test_document_count_mismatch_is_rebuilt(self):
        one_document_index = faiss.IndexIDMap2(
            faiss.IndexFlatL2(EMBEDDING_DIMENSION)
        )
        one_document_index.add_with_ids(
            np.ones((1, EMBEDDING_DIMENSION), dtype=np.float32),
            np.asarray([self.documents[0].pk], dtype=np.int64),
        )
        faiss.write_index(one_document_index, str(self.index_path))

        rebuilt = ensure_faiss_index(
            self.index_path,
            model_factory=FakeEmbeddingModel,
        )

        self.assertEqual(rebuilt.ntotal, len(self.documents))

    def test_document_id_mismatch_is_rebuilt(self):
        mismatched_index = faiss.IndexIDMap2(
            faiss.IndexFlatL2(EMBEDDING_DIMENSION)
        )
        mismatched_index.add_with_ids(
            np.ones((len(self.documents), EMBEDDING_DIMENSION), dtype=np.float32),
            np.asarray([901, 902], dtype=np.int64),
        )
        faiss.write_index(mismatched_index, str(self.index_path))

        rebuilt = ensure_faiss_index(
            self.index_path,
            model_factory=FakeEmbeddingModel,
        )

        self.assertEqual(
            set(faiss.vector_to_array(rebuilt.id_map).tolist()),
            set(document_ids()),
        )

    def test_changed_document_set_invalidates_cached_runtime_index(self):
        build_faiss_index(self.index_path, model=FakeEmbeddingModel())
        from rag_engine import RAGEngine

        with override_settings(FAISS_INDEX_PATH=self.index_path):
            engine = RAGEngine()
            engine.model = FakeEmbeddingModel()
            engine.search('course text')
            Document.objects.create(
                title='New document',
                content='New course text',
                course_id=1,
            )
            engine.search('new course text')

        self.assertEqual(engine.index.ntotal, 3)

    def test_changed_document_content_invalidates_index_metadata(self):
        build_faiss_index(self.index_path, model=FakeEmbeddingModel())
        from rag_engine import RAGEngine

        with override_settings(FAISS_INDEX_PATH=self.index_path):
            engine = RAGEngine()
            engine.model = FakeEmbeddingModel()
            engine.search('course text')
            metadata_path = self.index_path.with_name(
                f'{self.index_path.name}.metadata.json'
            )
            original_fingerprint = json.loads(
                metadata_path.read_text(encoding='utf-8')
            )['document_fingerprint']
            self.documents[0].content = 'Updated course content'
            self.documents[0].save(update_fields=['content'])
            engine.search('updated course content')
            updated_fingerprint = json.loads(
                metadata_path.read_text(encoding='utf-8')
            )['document_fingerprint']

        self.assertNotEqual(original_fingerprint, updated_fingerprint)

    def test_runtime_missing_index_is_rebuilt_and_retrievable(self):
        Document.objects.create(
            title='DBMS',
            content='A database management system stores organized data.',
            course_id=1,
        )
        from rag_engine import RAGEngine

        with override_settings(FAISS_INDEX_PATH=self.index_path):
            engine = RAGEngine()
            engine.model = FakeEmbeddingModel()
            docs, _ = engine.search('what is DBMS')

        self.assertTrue(self.index_path.is_file())
        self.assertEqual(len(docs), len(self.documents) + 1)

    def test_index_build_lock_serializes_threads(self):
        active = 0
        maximum_active = 0
        state_lock = threading.Lock()
        barrier = threading.Barrier(2)

        def critical_section():
            nonlocal active, maximum_active
            barrier.wait()
            with index_build_lock(self.index_path):
                with state_lock:
                    active += 1
                    maximum_active = max(maximum_active, active)
                time.sleep(0.05)
                with state_lock:
                    active -= 1

        threads = [threading.Thread(target=critical_section) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=5)

        self.assertTrue(all(not thread.is_alive() for thread in threads))
        self.assertEqual(maximum_active, 1)


class ProductionInitializationTests(TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.base_dir = Path(self.temporary_directory.name)
        media_dir = self.base_dir / 'media'
        media_dir.mkdir()
        (media_dir / 'Course.txt').write_text(
            'Database management systems organize and retrieve data.',
            encoding='utf-8',
        )
        self.index_path = self.base_dir / 'runtime' / 'rag_index.faiss'

    def tearDown(self):
        self.temporary_directory.cleanup()

    @patch.dict(
        os.environ,
        {
            'DJANGO_SUPERUSER_USERNAME': '',
            'DJANGO_SUPERUSER_EMAIL': '',
            'DJANGO_SUPERUSER_PASSWORD': '',
        },
    )
    def test_missing_admin_environment_does_not_break_local_initialization(self):
        with override_settings(
            BASE_DIR=self.base_dir,
            FAISS_INDEX_PATH=self.index_path,
            DEBUG=True,
        ), patch(
            'core.faiss_index.create_embedding_model',
            return_value=FakeEmbeddingModel(),
        ):
            call_command('initialize_production', verbosity=0)

        self.assertTrue(Document.objects.exists())
        self.assertTrue(self.index_path.is_file())
        self.assertFalse(get_user_model().objects.filter(is_superuser=True).exists())

    @patch.dict(
        os.environ,
        {
            'DJANGO_SUPERUSER_USERNAME': 'deployment-admin',
            'DJANGO_SUPERUSER_EMAIL': 'deployment-admin@example.com',
            'DJANGO_SUPERUSER_PASSWORD': 'Private-admin-password-123!',
        },
    )
    def test_repeated_initialization_preserves_documents_and_existing_admin(self):
        User = get_user_model()
        admin = User.objects.create_user(
            username='deployment-admin',
            email='existing@example.com',
            password='Existing-password-456!',
            is_staff=False,
            is_superuser=False,
        )
        original_password = admin.password

        with override_settings(
            BASE_DIR=self.base_dir,
            FAISS_INDEX_PATH=self.index_path,
            DEBUG=True,
        ), patch(
            'core.faiss_index.create_embedding_model',
            return_value=FakeEmbeddingModel(),
        ):
            call_command('initialize_production', verbosity=0)
            document_count = Document.objects.count()
            call_command('initialize_production', verbosity=0)

        admin.refresh_from_db()
        self.assertEqual(User.objects.filter(username='deployment-admin').count(), 1)
        self.assertTrue(admin.is_staff)
        self.assertTrue(admin.is_superuser)
        self.assertEqual(admin.password, original_password)
        self.assertEqual(Document.objects.count(), document_count)
        self.assertTrue(self.index_path.is_file())


class ChatIndexErrorTests(TestCase):
    def test_unavailable_index_returns_controlled_service_error(self):
        from rag_engine import RAGUnavailableError

        user = get_user_model().objects.create_user(
            username='chat-index-error-user',
            password='Chat-test-password-123',
        )
        self.client.force_login(user)
        with patch('chat.views._get_rag_engine') as get_engine:
            get_engine.return_value.search.side_effect = RAGUnavailableError(
                'The knowledge index is temporarily unavailable.'
            )
            response = self.client.post(
                reverse('chat:send_message'),
                data='{"message": "what is SQL"}',
                content_type='application/json',
            )

        self.assertEqual(response.status_code, 503)
        self.assertFalse(response.json()['success'])
        self.assertIn('temporarily unavailable', response.json()['error'])
