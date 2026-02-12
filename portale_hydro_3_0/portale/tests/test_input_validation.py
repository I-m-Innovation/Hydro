from django.contrib.auth import get_user_model
from django.test import TestCase 
from django.urls import reverse 

import logging
logger = logging.getLogger(__name__)

class InputValidationTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username="testuser",
            password="testpass",
        )
        self.client.force_login(self.user)
        

    def test_measurements_api_requires_id(self):
        # logger.info("Testing measurements API without 'id' parameter")
        url = reverse("measurements_api")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("error", resp.json())
        
    # id_misuratore con caratteri di controllo (\n, \r, \t, \x00) → 400.
    def test_measurements_api_rejects_control_characters(self):
        url = reverse("measurements_api") + "?id_misuratore=abc\x00def"
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 400)
        
    def test_measurements_api_for_whitespace_id(self):
        url = reverse("measurements_api") + "?id_misuratore=   "
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 400)
    
    def test_measurements_api_for_missing_id(self):
        url = reverse("measurements_api") + "?id_misuratore="
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 400)
        
    def test_measurements_api_for_id_too_long(self):
        url = reverse("measurements_api") + "?id_misuratore=" + ('a' * 129)
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 400)
    
    def test_measurements_api_for_valid_id_with_internal_whitespace(self):
        url = reverse("measurements_api") + "?id_misuratore=abc def"
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)