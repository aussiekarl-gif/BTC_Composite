import unittest
from engines.research.ntfy_delivery_state_audit import DeliveryState, reserve, acknowledge, should_send

class DeliveryAuditTests(unittest.TestCase):
    def test_reservation_blocks_duplicates_even_before_ack(self):
        a=reserve(DeliveryState(),"2026-11-07","attempt-1")
        self.assertFalse(should_send(a,"2026-11-07"))
        self.assertEqual(reserve(a,"2026-11-07","attempt-2"),a)
    def test_success_is_acknowledged_not_merely_reserved(self):
        a=reserve(DeliveryState(),"2026-11-07","attempt-1")
        self.assertEqual(a.status,"RESERVED")
        self.assertEqual(acknowledge(a,"attempt-1",True).status,"ACCEPTED")
    def test_timeout_is_ambiguous_and_never_auto_retries(self):
        a=reserve(DeliveryState(),"2026-11-07","attempt-1")
        b=acknowledge(a,"attempt-1",None)
        self.assertEqual(b.status,"UNKNOWN")
        self.assertFalse(should_send(b,"2026-11-07"))
        self.assertTrue(should_send(b,"2026-11-08"))
    def test_explicit_failure_cannot_prove_no_delivery(self):
        a=reserve(DeliveryState(),"2026-11-07","attempt-1")
        self.assertEqual(acknowledge(a,"attempt-1",False).status,"UNKNOWN")
    def test_wrong_ack_and_double_ack_rejected(self):
        a=reserve(DeliveryState(),"2026-11-07","attempt-1")
        with self.assertRaises(ValueError): acknowledge(a,"wrong",True)
        with self.assertRaises(ValueError): acknowledge(acknowledge(a,"attempt-1",True),"attempt-1",True)
if __name__=="__main__": unittest.main()
