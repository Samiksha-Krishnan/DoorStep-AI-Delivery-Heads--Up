import unittest
from datetime import datetime
from parser import parse_message

TODAY = datetime(2026, 11, 2)

class ParserTests(unittest.TestCase):
    def test_full_message(self):
        o = parse_message("Your Amazon package Boat Airdopes will be delivered tomorrow between 2 PM - 6 PM. OTP 4821.", today=TODAY)
        self.assertEqual(o["courier"], "Amazon")
        self.assertEqual(o["otp"], "4821")
        self.assertEqual((o["from"], o["to"]), ("14:00", "18:00"))
        self.assertEqual(o["date"], "2026-11-03")

    def test_delay_status(self):
        self.assertEqual(parse_message("Delivery attempt failed, rescheduled", today=TODAY)["status"], "trouble")

    def test_no_details(self):
        o = parse_message("hello there", today=TODAY)
        self.assertNotIn("otp", o)
        self.assertEqual(o["status"], "ok")

if __name__ == "__main__":
    unittest.main()
