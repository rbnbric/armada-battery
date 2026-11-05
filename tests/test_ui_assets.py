"""Exercise actual HTTP asset routes, including the branded UI entry point."""
import hashlib
import unittest
from pathlib import Path
from fastapi.testclient import TestClient
from test_api import web

class UIAssetsTests(unittest.TestCase):
    def test_logo_is_served_as_the_exact_existing_brand_asset(self):
        with TestClient(web.app) as client:
            response=client.get('/static/battery-logo.png')
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.headers['content-type'],'image/png')
        expected=(Path(__file__).resolve().parents[1]/'static/battery-logo.png').read_bytes()
        self.assertEqual(hashlib.sha256(response.content).digest(),hashlib.sha256(expected).digest())
        self.assertIn("img-src 'self'",response.headers['content-security-policy'])

    def test_entry_serves_current_ui_with_local_assets(self):
        with TestClient(web.app) as client:
            response=client.get('/')
            self.assertEqual(response.status_code,200)
            for asset in ['/static/app.js','/static/app.css','/static/battery-logo.png']:
                self.assertIn(asset,response.text)
                self.assertEqual(client.get(asset).status_code,200)
            self.assertIn('id="nav-current">Cases',response.text)
