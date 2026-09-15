import json
import os
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

os.environ.setdefault("DB_CLIENT_ID", "test-client")
os.environ.setdefault("DB_API_KEY", "test-key")

from trains import app, service


def departure_entry(minutes_ahead, delay_minutes):
    now = datetime.now()
    planned = now + timedelta(minutes=minutes_ahead)
    actual = planned + timedelta(minutes=delay_minutes)
    return {"bahnhofsId": "8006671", "zeit": planned.strftime('%Y-%m-%dT%H:%M:%S'), "ezZeit": actual.strftime('%Y-%m-%dT%H:%M:%S'), "gleis": "4", "meldungen": [], "verkehrmittel": {"name": "S 6", "produktGattung": "SBAHN"}, "terminus": "Grafing Bahnhof"}


class UpdateEndpointTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    @patch.object(service, "get_departures")
    def test_update_fetches_service_and_serializes_payload(self, mock_get):
        mock_get.return_value = {"entries": [departure_entry(10, 2)]}
        response = self.client.get("/update")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "application/json")
        payload = response.get_json()
        self.assertEqual(payload["timestamp"].split()[0], "Updated")
        self.assertEqual(payload["trains_east"][0][0], "Grafing Bahnhof")
        mock_get.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
