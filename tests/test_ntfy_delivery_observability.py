import unittest
from engines.research.ntfy_delivery_observability import classify_delivery_run

def steps(send, reserve="success"):
    return [
        {"name":"Skip expensive preparation if today's message is already reserved","status":"completed","conclusion":"success"},
        {"name":"Reserve Brisbane delivery date BEFORE sending","status":"completed","conclusion":reserve},
        {"name":"Send only one ntfy Cycle Trading message","status":"completed","conclusion":send},
    ]

class NotificationEvidenceTests(unittest.TestCase):
    def test_success_is_not_phone_delivery(self):
        r=classify_delivery_run(steps("success"),"2026-11-07","2026-11-07")
        self.assertEqual(r["outcome"],"POST_STEP_SUCCEEDED_NOT_DEVICE_DELIVERY")
        self.assertFalse(r["confirmed_device_delivery"])
    def test_skipped_is_not_successful_delivery(self):
        r=classify_delivery_run(steps("skipped",reserve="skipped"),"2026-11-07","2026-11-07")
        self.assertEqual(r["outcome"],"SKIPPED_POSSIBLY_ALREADY_RESERVED")
    def test_post_failure_is_ambiguous(self):
        r=classify_delivery_run(steps("failure"),"2026-11-07","2026-11-07")
        self.assertEqual(r["outcome"],"POST_STEP_FAILED_ACCEPTANCE_UNKNOWN")
    def test_marker_alone_is_not_confirmation(self):
        r=classify_delivery_run([], "2026-11-07","2026-11-07")
        self.assertTrue(r["marker_matches_day"])
        self.assertFalse(r["confirmed_device_delivery"])
if __name__=="__main__": unittest.main()
