from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse


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
