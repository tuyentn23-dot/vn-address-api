import unittest,os
from unittest.mock import patch
from fastapi.testclient import TestClient
from src.main import app,COUNTERS,OBSERVED_USERS
class MetricsTests(unittest.TestCase):
    def test_protection_and_owner_scope(self):
        with patch.dict(os.environ,{'RAPIDAPI_PROXY_SECRET':'synthetic','ADMIN_TOKEN':'synthetic-admin'}),TestClient(app) as c:
            COUNTERS.update(total_requests=0,total_errors=0);OBSERVED_USERS.clear()
            self.assertEqual(c.get('/metrics').status_code,401)
            h={'X-RapidAPI-Proxy-Secret':'synthetic','X-RapidAPI-User':'synthetic-owner'}
            self.assertEqual(c.get('/provinces',headers=h).status_code,200)
            self.assertEqual(c.get('/provinces',headers=h).status_code,200)
            m=c.get('/metrics',headers={'Authorization':'Bearer synthetic-admin'}).json()
            self.assertEqual(m['total_requests'],2);self.assertEqual(m['unique_subscribers'],1)
            self.assertNotIn('synthetic-owner',str(OBSERVED_USERS))
            self.assertEqual(c.get('/provinces').status_code,401)
    def test_no_admin_fails_closed(self):
        with patch.dict(os.environ,{'ADMIN_TOKEN':''}),TestClient(app) as c:self.assertEqual(c.get('/metrics').status_code,503)
if __name__=='__main__':unittest.main()
