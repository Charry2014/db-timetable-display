import unittest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from trains import app


def departure_entry(minutes_ahead, delay_minutes):
    now = datetime.now()
    planned = now + timedelta(minutes=minutes_ahead)
    actual = planned + timedelta(minutes=delay_minutes)
    return {
        "bahnhofsId": "8006671",
        "zeit": planned.strftime('%Y-%m-%dT%H:%M:%S'),
        "ezZeit": actual.strftime('%Y-%m-%dT%H:%M:%S'),
        "gleis": "4",
        "meldungen": [],
        "verkehrmittel": {"name": "S 6", "produktGattung": "SBAHN"},
        "terminus": "Grafing Bahnhof",
    }


class UpdateEndpointTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    @patch("trains.BahnBrowser")
    def test_update_initializes_browser_on_wsgi_import_path(self, mock_browser_cls):
        mock_browser = mock_browser_cls.return_value
        mock_browser.get.return_value = {"entries": [departure_entry(10, 2)]}

        with patch("trains.bahn_browser", None):
            response = self.client.get("/update")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "application/json")
        payload = response.get_json()
        self.assertEqual(payload["timestamp"].split()[0], "Updated")
        self.assertEqual(payload["direction1_title"], "Direction Ebersberg")
        self.assertEqual(payload["direction2_title"], "Direction Munich")
        self.assertEqual(payload["trains_east"][0][0], "Grafing Bahnhof")
        mock_browser_cls.assert_called_once()
        mock_browser.get.assert_called_once()

    def test_update_reuses_initialized_browser(self):
        existing = MagicMock()
        existing.get.return_value = {"entries": []}

        with patch("trains.BahnBrowser") as mock_browser_cls, \
                patch("trains.bahn_browser", existing):
            response = self.client.get("/update")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "application/json")
        payload = response.get_json()
        self.assertEqual(payload["timestamp"].split()[0], "Updated")
        self.assertEqual(payload["trains_east"], [])
        self.assertEqual(payload["trains_west"], [])
        mock_browser_cls.assert_not_called()


if __name__ == "__main__":
    unittest.main()
