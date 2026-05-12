import unittest
from unittest.mock import patch

from trains import app


class UpdateEndpointTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    @patch("trains.station.get_departure_details")
    def test_update_returns_station_payload_as_json(self, mock_get_departure_details):
        mock_get_departure_details.return_value = (
            '{"timestamp":"Updated 12:34","direction1_title":"Direction Ebersberg",'
            '"direction2_title":"Direction Munich","trains_east":[],"trains_west":[]}'
        )

        response = self.client.get("/update")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "application/json")
        self.assertEqual(response.get_json()["timestamp"], "Updated 12:34")
        mock_get_departure_details.assert_called_once_with()
