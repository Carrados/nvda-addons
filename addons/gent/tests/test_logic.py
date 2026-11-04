"""Tests for gent's NVDA-free modules. Run from the repo root: python -m unittest discover addons/gent/tests"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "addon" / "globalPlugins" / "gent"))

import logic  # noqa: E402

LEVELS = [0, 100, 200, 300]


def answer(action, confidence, alternatives):
	return {
		"action": action,
		"confidence": confidence,
		"alternatives": [{"action": a, "probability": p} for a, p in alternatives],
	}


class PlanTests(unittest.TestCase):
	def test_confident_acts(self):
		self.assertEqual(
			logic.plan(answer("speechRateFaster", 1.0, [("speechRateFaster", 1.0)]), None),
			("act", "speechRateFaster"),
		)

	def test_unsure_asks(self):
		a = answer("punctuationLess", 0.5, [("punctuationLess", 0.55), ("typedWordsOff", 0.4)])
		self.assertEqual(logic.plan(a, None), ("ask", "punctuationLess"))

	def test_none_refuses(self):
		self.assertEqual(logic.plan(answer("none", 1.0, [("none", 1.0)]), None), ("none", "none"))

	def test_undo_or_opposite_counts_as_sure(self):
		# Seen live: "Undo that" after a change split between undo and its opposite.
		a = answer("undo", 0.56, [("undo", 0.59), ("speechRateSlower", 0.41)])
		self.assertEqual(logic.plan(a, "speechRateFaster"), ("act", "undo"))

	def test_undo_split_with_unrelated_action_asks(self):
		a = answer("undo", 0.56, [("undo", 0.59), ("punctuationMore", 0.41)])
		self.assertEqual(logic.plan(a, "speechRateFaster"), ("ask", "undo"))


class StepTests(unittest.TestCase):
	def test_value_steps_and_clamps(self):
		self.assertEqual(logic.stepValue(50, True, False), 60)
		self.assertEqual(logic.stepValue(50, False, True), 25)
		self.assertEqual(logic.stepValue(95, True, False), 100)
		self.assertEqual(logic.stepValue(5, False, True), 0)

	def test_level_steps_and_clamps(self):
		self.assertEqual(logic.stepLevel(LEVELS, 100, True, False), 200)
		self.assertEqual(logic.stepLevel(LEVELS, 200, False, True), 0)
		self.assertEqual(logic.stepLevel(LEVELS, 300, True, False), 300)

	def test_unknown_level_uses_nearest(self):
		# NVDA also has a "character" level (1000) that isn't in the settings list.
		self.assertEqual(logic.stepLevel(LEVELS, 1000, False, False), 200)


class NewSettingsTests(unittest.TestCase):
	def test_capital_pitch_uses_its_own_range(self):
		self.assertEqual(logic.stepValue(-95, False, False, -100, 100), -100)

	def test_every_pair_is_its_own_opposite(self):
		for a, b in logic.OPPOSITES.items():
			self.assertEqual(logic.OPPOSITES[b], a)

	def test_undo_or_opposite_for_new_settings(self):
		a = answer("undo", 0.5, [("undo", 0.55), ("beepForCapsOff", 0.4)])
		self.assertEqual(logic.plan(a, "beepForCapsOn"), ("act", "undo"))

	def test_last_action_without_an_opposite_asks(self):
		a = answer("undo", 0.5, [("undo", 0.55), ("punctuationMore", 0.4)])
		self.assertEqual(logic.plan(a, "punctuationNone"), ("ask", "undo"))


if __name__ == "__main__":
	unittest.main()
