import unittest
from core.time_utils import get_greeting, get_time_period


class TimeContextTests(unittest.TestCase):
    def test_morning_greeting(self):
        self.assertEqual(get_time_period(7), "mañana")
        self.assertEqual(get_greeting(7), "Buenos días")

    def test_afternoon_greeting(self):
        self.assertEqual(get_time_period(15), "tarde")
        self.assertEqual(get_greeting(15), "Buenas tardes")

    def test_night_greeting(self):
        self.assertEqual(get_time_period(22), "noche")
        self.assertEqual(get_greeting(22), "Buenas noches")


if __name__ == "__main__":
    unittest.main()
