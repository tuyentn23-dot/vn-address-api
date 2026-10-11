import json
import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from src.main import app


class APITests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {'RAPIDAPI_PROXY_SECRET': 'synthetic-test-secret'})
        self.env.start()
        self.client = TestClient(app, headers={'X-RapidAPI-Proxy-Secret': 'synthetic-test-secret'})

    def tearDown(self):
        self.client.close()
        self.env.stop()

    def test_fail_closed(self):
        with patch.dict(os.environ, {'RAPIDAPI_PROXY_SECRET': ''}):
            self.assertEqual(self.client.get('/provinces').status_code, 503)

    def test_auth_required(self):
        self.assertEqual(TestClient(app).get('/provinces').status_code, 401)
        self.assertEqual(self.client.get('/provinces', headers={'X-RapidAPI-Proxy-Secret': 'wrong'}).status_code, 401)

    def test_health_public(self):
        self.assertEqual(TestClient(app).get('/health').json()['currentProvinceCount'], 34)

    def test_current_and_legacy(self):
        current = self.client.get('/provinces').json()
        self.assertEqual(current['count'], 34)
        self.assertEqual(current['items'][0]['code'], '01')
        self.assertEqual(self.client.get('/provinces?version=legacy').json()['count'], 63)

    def test_accent_and_ascii(self):
        for q in ('Hà Nội', 'Ha Noi', 'TP.HCM', '12 Nguyen Hue, Ho Chi Minh'):
            row = self.client.get('/normalize', params={'q': q}).json()
            self.assertEqual(row['status'], 'matched')

    def test_ambiguous_never_picks_first(self):
        row = self.client.get('/normalize', params={'q': 'Hà Nội hoặc Hồ Chí Minh'}).json()
        self.assertEqual(row['status'], 'ambiguous')
        self.assertIsNone(row['province'])
        self.assertEqual(len(row['candidates']), 2)

    def test_partial_not_matched(self):
        self.assertEqual(self.client.get('/normalize?q=Nam').json()['status'], 'not_found')

    def test_hue_street_not_a_second_province(self):
        row = self.client.get('/normalize', params={'q': '12 Nguyen Hue, Ho Chi Minh'}).json()
        self.assertEqual(row['province']['code'], '79')
        self.assertEqual(self.client.get('/normalize', params={'q': 'Thành phố Huế'}).json()['province']['code'], '46')

    def test_legacy_not_automatically_current(self):
        self.assertEqual(self.client.get('/normalize?q=Long%20An').json()['status'], 'not_found')
        self.assertEqual(self.client.get('/normalize?q=Long%20An&version=legacy').json()['status'], 'matched')

    def test_batch_order_and_summary(self):
        response = self.client.post('/normalize/batch', json={'queries': ['Ha Noi', 'Nam', 'Ha Noi, Ho Chi Minh']})
        data = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual([r['status'] for r in data['results']], ['matched', 'not_found', 'ambiguous'])
        self.assertEqual(data['summary'], {'matched': 1, 'not_found': 1, 'ambiguous': 1})

    def test_batch_limits(self):
        for queries in ([], ['Ha Noi'] * 51, ['x' * 501], ['   ']):
            self.assertEqual(self.client.post('/normalize/batch', json={'queries': queries}).status_code, 422)

    def test_body_and_query_size(self):
        self.assertEqual(self.client.post('/normalize/batch', content=b'x' * 65537).status_code, 413)
        self.assertEqual(self.client.get('/stats?q=' + 'x' * 4097).status_code, 413)

    def test_phone_rejects_embedded_letters(self):
        self.assertFalse(self.client.get('/validate-phone?p=abc0912345678').json()['ok'])
        self.assertTrue(self.client.get('/validate-phone', params={'p': '+84 912 345 678'}).json()['ok'])

    def test_email_shapes(self):
        for e in ('a@example.com', 'a+b@example.co.uk'):
            self.assertTrue(self.client.get('/validate-email', params={'e': e}).json()['ok'])
        for e in ('a@exampleXcom', 'a..b@example.com', 'a@-example.com', 'a@example..com'):
            self.assertFalse(self.client.get('/validate-email', params={'e': e}).json()['ok'])

    def test_taxcode_no_silent_strip(self):
        self.assertTrue(self.client.get('/validate-taxcode?code=0101234567-001').json()['ok'])
        self.assertFalse(self.client.get('/validate-taxcode?code=bad0101234567').json()['ok'])

    def test_id_no_demographic_inference(self):
        data = self.client.get('/validate-cccd?id=001199012345').json()
        self.assertFalse(data['identityVerified'])
        self.assertNotIn('gender', data)

    def test_bad_version(self):
        self.assertEqual(self.client.get('/provinces?version=unknown').status_code, 422)


if __name__ == '__main__':
    unittest.main()
