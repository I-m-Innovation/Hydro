from unittest import mock

from django.contrib.auth import get_user_model
from django.core import signing
from django.test import TestCase, override_settings
from django.urls import reverse

from portale import views


SSO_SETTINGS = {
    "EYEQ_PORTALE_IMPIANTI_ENTRY_URL": "http://eyeq.test/portale-impianti/",
    "EYEQ_PORTALE_IMPIANTI_SSO_SECRET": "test-shared-secret",
    "EYEQ_PORTALE_IMPIANTI_SSO_SALT": "eyeq-portale-impianti-sso",
    "EYEQ_PORTALE_IMPIANTI_SSO_MAX_AGE_SECONDS": 60,
    "EYEQ_PORTALE_IMPIANTI_SSO_ISSUER": "eyeq",
    "EYEQ_PORTALE_IMPIANTI_SSO_AUDIENCE": "portale_impianti",
}


@override_settings(**SSO_SETTINGS)
class SsoTests(TestCase):
    def _token(self, **overrides):
        payload = {
            "iss": "eyeq",
            "aud": "portale_impianti",
            "page": "portale_impianti",
            "username": "mario.rossi",
            "email": "mario.rossi@example.test",
            "first_name": "Mario",
            "last_name": "Rossi",
            "next": reverse("misuratori_index"),
        }
        payload.update(overrides)
        return signing.dumps(
            payload,
            key=SSO_SETTINGS["EYEQ_PORTALE_IMPIANTI_SSO_SECRET"],
            salt=SSO_SETTINGS["EYEQ_PORTALE_IMPIANTI_SSO_SALT"],
        )

    def test_valid_token_creates_local_session(self):
        resp = self.client.get(reverse("sso_login"), {"token": self._token()})

        self.assertRedirects(resp, reverse("misuratori_index"), fetch_redirect_response=False)
        user = get_user_model().objects.get(username="mario.rossi")
        self.assertEqual(user.email, "mario.rossi@example.test")
        self.assertEqual(str(self.client.session["_auth_user_id"]), str(user.pk))

    def test_token_without_page_gets_403(self):
        resp = self.client.get(reverse("sso_login"), {"token": self._token(page="")})

        self.assertEqual(resp.status_code, 403)

    def test_token_with_wrong_audience_gets_403(self):
        resp = self.client.get(reverse("sso_login"), {"token": self._token(aud="altro")})

        self.assertEqual(resp.status_code, 403)

    def test_token_with_wrong_issuer_gets_403(self):
        resp = self.client.get(reverse("sso_login"), {"token": self._token(iss="altro")})

        self.assertEqual(resp.status_code, 403)

    def test_expired_token_redirects_to_eyeq(self):
        with mock.patch.object(views, "_load_sso_payload", side_effect=signing.SignatureExpired):
            resp = self.client.get(reverse("sso_login"), {"token": "expired"})

        self.assertEqual(resp.status_code, 302)
        self.assertTrue(resp["Location"].startswith("http://eyeq.test/portale-impianti/?next="))

    def test_anonymous_user_is_redirected_to_eyeq(self):
        resp = self.client.get(reverse("login"))

        self.assertEqual(resp.status_code, 302)
        self.assertTrue(resp["Location"].startswith("http://eyeq.test/portale-impianti/?next="))
