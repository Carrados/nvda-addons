"""Tests for gent's page recording transcript. Run from the repo root: python -m unittest discover addons/gent/tests"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "addon" / "globalPlugins" / "gent"))

import logic
import recording
from recording import Step


class Command:
	"""Stands in for NVDA's speech commands, such as a pitch change or a pause."""


class SpeechTextTests(unittest.TestCase):
	def test_keeps_words_and_drops_commands(self):
		sequence = ["Postcode", Command(), "edit", ["required", Command()], "  invalid entry  "]
		self.assertEqual(recording.speechText(sequence), "Postcode edit required invalid entry")

	def test_nothing_said(self):
		self.assertEqual(recording.speechText([Command(), " ", []]), "")


class TranscriptTests(unittest.TestCase):
	def test_layout(self):
		text = recording.transcript(
			title="Your request - Asda Online Doctor",
			url="https://example.com/questionnaire",
			when="2026-11-13 21:00",
			about="NVDA 2026.2, Google Chrome 142",
			reading=["heading level 1 Questionnaire", "Are you using weight loss medication? Yes"],
			steps=[
				Step("Start, top of the page", "Questionnaire document"),
				Step("Tab 1", "Help? link"),
				Step("Tab 2", ""),
			],
			stopped="Tab left the page.",
		)
		self.assertEqual(
			text.splitlines(),
			[
				"gent page recording",
				"Page: Your request - Asda Online Doctor",
				"Address: https://example.com/questionnaire",
				"Recorded: 2026-11-13 21:00",
				"With: NVDA 2026.2, Google Chrome 142",
				"",
				"== Reading the page, as Say All would (2 lines) ==",
				"",
				"heading level 1 Questionnaire",
				"Are you using weight loss medication? Yes",
				"",
				"== Pressing Tab from the top (2 presses) ==",
				"",
				"Start, top of the page: Questionnaire document",
				"Tab 1: Help? link",
				"Tab 2: (said nothing)",
				"",
				"Stopped: Tab left the page.",
			],
		)

	def test_empty_page(self):
		text = recording.transcript("", "", "now", "NVDA", [], [], "Stopped by a key press.")
		self.assertIn("Page: (no title)", text)
		self.assertIn("(Nothing was read.)", text)
		self.assertIn("(0 presses)", text)


class KeyTests(unittest.TestCase):
	def test_r_records(self):
		self.assertEqual(logic.layerCommand(["kb(desktop):r", "kb:r"]), "record")


if __name__ == "__main__":
	unittest.main()
