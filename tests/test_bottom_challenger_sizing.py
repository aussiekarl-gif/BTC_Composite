import math
import unittest

from engines.research.research_model import bottom_challenger_sizing_weight


class BottomChallengerSizingTests(unittest.TestCase):
    def test_recovery_confirmation_does_not_front_load_when_zone_inactive(self):
        self.assertEqual(
            bottom_challenger_sizing_weight(1.0, 3.0, False, "RECOVERY CONFIRMATION"),
            1.0,
        )

    def test_recovery_confirmation_never_front_loads_even_if_zone_flag_is_true(self):
        self.assertEqual(
            bottom_challenger_sizing_weight(1.0, 3.0, True, "RECOVERY CONFIRMATION"),
            1.0,
        )

    def test_initial_exceptional_event_can_apply_multiplier_in_active_zone(self):
        self.assertEqual(
            bottom_challenger_sizing_weight(1.0, 3.0, True, "INITIAL EXCEPTIONAL ZONE"),
            3.0,
        )

    def test_lower_capitulation_event_can_apply_multiplier_in_active_zone(self):
        self.assertEqual(
            bottom_challenger_sizing_weight(1.0, 4.0, True, "LOWER CAPITULATION STAGE"),
            4.0,
        )

    def test_inactive_zone_ignores_exceptional_multiplier(self):
        self.assertEqual(
            bottom_challenger_sizing_weight(0.8, 4.0, False, "LOWER CAPITULATION STAGE"),
            0.8,
        )

    def test_missing_multiplier_falls_back_to_base(self):
        self.assertEqual(
            bottom_challenger_sizing_weight(0.9, math.nan, True, "INITIAL EXCEPTIONAL ZONE"),
            0.9,
        )

    def test_event_never_reduces_base_weight(self):
        self.assertEqual(
            bottom_challenger_sizing_weight(1.2, 3.0, True, "INITIAL EXCEPTIONAL ZONE"),
            3.0,
        )


if __name__ == "__main__":
    unittest.main()
