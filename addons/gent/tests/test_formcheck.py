"""Tests for gent's form check. Run from the repo root: python -m unittest discover addons/gent/tests"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "addon" / "globalPlugins" / "gent"))

from formcheck import (
	CHECKBOX,
	CHOICE,
	RADIO,
	TEXT,
	Field,
	asksForFormCheck,
	findProblems,
	summary,
)

ACCURATE = (
	"It is essential that all information you provide is accurate and honest. Medications used for weight "
	"loss have the potential to cause serious illness and severe side effects if used inappropriately, and our "
	"doctors will not be able to assess your health risks if false or inaccurate information is provided. "
	"Please tick to confirm you understand and agree."
)


def asdaForm(accurateTicked: bool, showError: bool) -> list[Field]:
	"""Part of the Asda Online Doctor weight loss questionnaire, as it reached NVDA in November 2026.

	The accuracy tickbox sits among the questions, isn't marked required, and its only error is
	"This field is required" as plain text after it. That's what this check was built to find.
	"""
	error = "\nThis field is required" if showError else ""
	return [
		Field(
			RADIO,
			"Yes",
			before="Have there been any changes to your health or medication since your last order?\n"
			"This includes new symptoms, diagnoses, or medication you've started, stopped or changed.\n",
			after=" Yes\n",
			group="a",
			checked=True,
		),
		Field(RADIO, "No", before=" Yes\n", after=" No\nYour saved health details\n", group="b"),
		Field(
			CHECKBOX,
			ACCURATE,
			before=" No\nYour saved health details\nProvide treatment related information\n",
			after=ACCURATE.replace("provided. ", "provided.\n\n")
			+ error
			+ "\nWhat dose of Mounjaro are you using at the moment?\n"
			"We need to know what dose you're taking so we can advise you about what you can move on to.\n",
			checked=accurateTicked,
		),
		Field(RADIO, "2.5mg", group="c", after=" 2.5mg\n"),
		Field(RADIO, "5mg", group="c", checked=True, before=" 2.5mg\n", after=" 5mg\n"),
		Field(
			TEXT,
			"Please enter your current weight. st",
			value="17",
			before="Please enter your current weight.\nDo not guess your weight. If you're not sure how much you "
			"weigh, measure yourself first before entering this information.\n",
			after="st\n",
		),
		Field(TEXT, "lb", value="10", before="st\n", after="lb\nSwitch to kg.\nYour GP\n"),
		Field(
			CHECKBOX,
			"I have read, understand and agree to Asda Online Doctor's terms and conditions",
			checked=True,
		),
	]


class AsdaTests(unittest.TestCase):
	def test_finds_the_tickbox_from_its_error_text(self):
		findings = findProblems(asdaForm(accurateTicked=False, showError=True))
		self.assertTrue(findings[0].problem)
		self.assertEqual(findings[0].index, 2)
		self.assertIn("This field is required", findings[0].message)
		self.assertTrue(findings[0].message.startswith("It is essential that all information"))

	def test_unticked_box_is_worth_checking_before_any_error_shows(self):
		findings = findProblems(asdaForm(accurateTicked=False, showError=False))
		self.assertEqual([(f.index, f.problem) for f in findings], [(2, False)])
		self.assertIn("not ticked", findings[0].message)

	def test_instructions_are_not_errors(self):
		# "Please enter your current weight" and "Please tick to confirm" are instructions, not errors.
		self.assertEqual(findProblems(asdaForm(accurateTicked=True, showError=False)), [])

	def test_yes_no_wrapped_separately_count_as_one_question(self):
		form = asdaForm(accurateTicked=True, showError=False)
		form[0].checked = False
		findings = findProblems(form)
		self.assertEqual(len(findings), 1)
		self.assertEqual(findings[0].index, 0)
		self.assertTrue(findings[0].message.startswith("Have there been any changes"))
		self.assertIn("nothing chosen", findings[0].message)


class FieldTests(unittest.TestCase):
	def test_site_error_message_and_invalid(self):
		findings = findProblems(
			[Field(TEXT, "Postcode", value="X1", invalid=True, errorMessage="Enter a valid postcode")]
		)
		self.assertEqual(findings[0].message, "Postcode: Enter a valid postcode")
		self.assertTrue(findings[0].problem)

	def test_invalid_without_reason(self):
		self.assertEqual(
			findProblems([Field(TEXT, "Email", value="me", invalid=True)])[0].message,
			"Email: marked as invalid",
		)

	def test_required_and_empty(self):
		findings = findProblems([Field(TEXT, "Surname", required=True), Field(TEXT, "Middle name")])
		self.assertEqual(
			[(f.message, f.problem) for f in findings],
			[
				("Surname: required, and empty", True),
				("Middle name: empty", False),
			],
		)

	def test_choice_left_on_placeholder(self):
		findings = findProblems([Field(CHOICE, "Title", value="Please select", required=True)])
		self.assertEqual(findings[0].message, "Title: required, and empty")

	def test_banner_above_form(self):
		form = [Field(TEXT, "Name", value="Lottie", before="There is a problem with your answers\n")]
		self.assertEqual(
			findProblems(form)[0].message, "Above the form: There is a problem with your answers"
		)

	def test_long_labels_are_shortened(self):
		message = findProblems([Field(CHECKBOX, ACCURATE)])[0].message
		self.assertLess(len(message), 110)
		self.assertTrue(message.endswith("…: not ticked"))

	def test_problems_come_first(self):
		findings = findProblems([Field(CHECKBOX, "Newsletter"), Field(TEXT, "Email", required=True)])
		self.assertEqual([f.index for f in findings], [1, 0])


class SummaryTests(unittest.TestCase):
	def test_summary(self):
		findings = findProblems([Field(CHECKBOX, "A"), Field(CHECKBOX, "B"), Field(TEXT, "C", required=True)])
		self.assertEqual(summary(findings, 42), "1 problem, 2 things to check, in 42 fields.")
		self.assertEqual(summary([], 5), "No problems found in 5 form fields.")


class AskingTests(unittest.TestCase):
	def test_form_questions(self):
		for text in (
			"what's wrong with this form?",
			"why won't this form submit",
			"the form won't let me press next",
			"what have I missed",
			"check the form",
			"why won't it submit",
		):
			self.assertTrue(asksForFormCheck(text), text)

	def test_settings_requests_still_go_to_jev(self):
		for text in ("talk a bit faster", "make the voice deeper", "stop reading punctuation", "undo that"):
			self.assertFalse(asksForFormCheck(text), text)


if __name__ == "__main__":
	unittest.main()
