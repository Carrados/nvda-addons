"""Tests for gent's form check. Run from the repo root: python -m unittest discover addons/gent/tests"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "addon" / "globalPlugins" / "gent"))

import formcheck  # noqa: E402
import logic  # noqa: E402
from formcheck import CHECKBOX, CHOICE, RADIO, TEXT, Field  # noqa: E402


class AsksTests(unittest.TestCase):
	def test_form_questions(self):
		for text in (
			"what's wrong with this form?",
			"form help",
			"the form won't submit",
			"what have I missed?",
			"what's missing",
		):
			self.assertTrue(formcheck.asksForFormCheck(text), text)

	def test_settings_requests_are_not_form_checks(self):
		for text in ("talk a bit faster", "help", "undo that", "beep for capitals"):
			self.assertFalse(formcheck.asksForFormCheck(text), text)


class ErrorLineTests(unittest.TestCase):
	def test_finds_errors(self):
		self.assertEqual(
			formcheck.errorLines("Postcode\nEnter a valid postcode\nThis field is required"),
			["Enter a valid postcode", "This field is required"],
		)

	def test_instructions_are_not_errors(self):
		self.assertEqual(formcheck.errorLines("Please enter your current weight"), [])

	def test_long_lines_are_not_errors(self):
		self.assertEqual(formcheck.errorLines("This field is required " + "x" * 200), [])


class ShortenTests(unittest.TestCase):
	def test_short_unchanged(self):
		self.assertEqual(formcheck.shorten("Email"), "Email")

	def test_cuts_at_a_word(self):
		text = "I agree to the terms and conditions, " * 5
		short = formcheck.shorten(text)
		self.assertTrue(short.endswith("…"))
		self.assertLessEqual(len(short), formcheck.LABEL_MAX + 1)


class FindProblemsTests(unittest.TestCase):
	def test_required_empty_text(self):
		findings = formcheck.findProblems([Field(TEXT, label="Name", required=True)])
		self.assertEqual(len(findings), 1)
		self.assertTrue(findings[0].problem)
		self.assertEqual(findings[0].message, "Name: required, and empty")

	def test_site_error_message_wins(self):
		f = Field(TEXT, label="Postcode", value="x", invalid=True, errorMessage="Enter a valid postcode")
		self.assertEqual(formcheck.findProblems([f])[0].message, "Postcode: Enter a valid postcode")

	def test_invalid_with_no_reason(self):
		f = Field(TEXT, label="Age", value="abc", invalid=True)
		self.assertEqual(formcheck.findProblems([f])[0].message, "Age: marked as invalid")

	def test_required_tickbox(self):
		f = Field(CHECKBOX, label="I agree", required=True)
		self.assertEqual(formcheck.findProblems([f])[0].message, "I agree: required, and not ticked")

	def test_optional_empty_is_only_worth_checking(self):
		findings = formcheck.findProblems([Field(TEXT, label="Phone"), Field(CHECKBOX, label="News")])
		self.assertEqual([f.problem for f in findings], [False, False])
		self.assertEqual([f.message for f in findings], ["Phone: empty", "News: not ticked"])

	def test_choice_placeholder_counts_as_empty(self):
		f = Field(CHOICE, label="Country", value="Please select", required=True)
		self.assertEqual(formcheck.findProblems([f])[0].message, "Country: required, and empty")

	def test_filled_form_has_no_findings(self):
		fields = [
			Field(TEXT, label="Name", value="Ann", required=True),
			Field(CHECKBOX, label="I agree", checked=True, required=True),
			Field(CHOICE, label="Country", value="Wales"),
		]
		self.assertEqual(formcheck.findProblems(fields), [])

	def test_banner_above_form(self):
		f = Field(TEXT, label="Name", value="Ann", before="There is a problem with your answers")
		findings = formcheck.findProblems([f])
		self.assertEqual(findings[0].message, "Above the form: There is a problem with your answers")

	def test_problems_come_before_checks(self):
		fields = [Field(TEXT, label="Phone"), Field(TEXT, label="Name", required=True)]
		self.assertEqual([f.index for f in formcheck.findProblems(fields)], [1, 0])

	def test_unlabelled_field(self):
		f = Field(TEXT, required=True)
		self.assertEqual(formcheck.findProblems([f])[0].message, "unlabelled text box: required, and empty")


class RadioTests(unittest.TestCase):
	def yesNo(self, question, **kwargs):
		return [
			Field(RADIO, label="Yes", before=question, **kwargs),
			Field(RADIO, label="No", **kwargs),
		]

	def test_neighbours_are_one_question(self):
		fields = self.yesNo("Do you drive?") + self.yesNo("Do you smoke?")
		self.assertEqual(formcheck.radioGroups(fields), [[0, 1], [2, 3]])

	def test_required_unanswered(self):
		findings = formcheck.findProblems(self.yesNo("Do you drive?", required=True))
		self.assertEqual(len(findings), 1)
		self.assertTrue(findings[0].problem)
		self.assertEqual(findings[0].message, "Do you drive?: nothing chosen")

	def test_optional_unanswered_is_worth_checking(self):
		findings = formcheck.findProblems(self.yesNo("Do you drive?"))
		self.assertEqual([(f.problem, f.message) for f in findings], [(False, "Do you drive?: nothing chosen")])

	def test_answered(self):
		fields = self.yesNo("Do you drive?", required=True)
		fields[1].checked = True
		self.assertEqual(formcheck.findProblems(fields), [])

	def test_group_error_reported_once(self):
		fields = self.yesNo("Do you drive?")
		fields[1].after = "Please answer this question"
		findings = formcheck.findProblems(fields)
		self.assertEqual([f.message for f in findings], ["Do you drive?: Please answer this question"])


class SummaryTests(unittest.TestCase):
	def test_nothing_wrong(self):
		self.assertEqual(formcheck.summary([], 12), "No problems found in 12 form fields.")

	def test_counts(self):
		findings = [
			formcheck.Finding(0, True, "a"),
			formcheck.Finding(1, False, "b"),
			formcheck.Finding(2, False, "c"),
		]
		self.assertEqual(formcheck.summary(findings, 42), "1 problem, 2 things to check, in 42 fields.")


class LayerTests(unittest.TestCase):
	def test_keys(self):
		self.assertEqual(logic.layerCommand(["kb:space"]), "type")
		self.assertEqual(logic.layerCommand(["kb:nvda+g"]), "type")
		self.assertEqual(logic.layerCommand(["kb:f"]), "form")
		self.assertEqual(logic.layerCommand(["kb:h"]), "help")
		self.assertEqual(logic.layerCommand(["kb:u"]), "undo")
		self.assertEqual(logic.layerCommand(["kb:escape"]), "exit")

	def test_first_known_identifier_wins(self):
		self.assertEqual(logic.layerCommand(["kb(desktop):f", "kb:f"]), "form")

	def test_other_keys_do_nothing(self):
		self.assertIsNone(logic.layerCommand(["kb:x"]))
		self.assertIsNone(logic.layerCommand([]))


if __name__ == "__main__":
	unittest.main()
