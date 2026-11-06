# Works out what's stopping a web form from submitting, from what NVDA can see of each field.
# No NVDA imports, so it can be tested outside NVDA. forms.py collects the fields and shows the result.

import re
from dataclasses import dataclass

# Words that mean someone wants their form checked, typed into gent's prompt.
_FORM = re.compile(r"\bforms?\b|\bsubmit")
_TROUBLE = re.compile(
	r"wrong|check|miss|submit|won'?t|will not|isn'?t|not work|doesn'?t|problem|error|stuck|next|finish|complete"
)
_MISSED = re.compile(r"\bwhat (have|did) i (miss|forget|leave out)|\bwhat'?s missing\b")

# Text a site shows when something is wrong. Kept narrow: instructions such as
# "Please enter your current weight" are not errors, and must not be reported as one.
_ERRORS = [
	re.compile(p, re.IGNORECASE)
	for p in (
		r"\bfield is required\b",
		r"\b(is|are) required\b",
		r"\brequired field\b",
		r"\b(is|are) (not valid|invalid|incorrect)\b",
		r"\binvalid\b",
		r"\benter a valid\b",
		r"\bplease (select|choose) (an?|one|your) (option|answer)\b",
		r"\b(select|choose) an option\b",
		r"\bplease answer\b",
		r"\byou must (select|choose|tick|check|enter|answer|provide|accept|agree|confirm)\b",
		r"\bmust be (at least|at most|between|a number|a valid|less|more|no more|no less|filled)\b",
		r"\bcan(no|')?t be (empty|blank|left blank)\b",
		r"\b(please )?(fill in|complete) this field\b",
		r"^error\b",
		r"\bthere (is|was) a problem\b",
	)
]

# Longer lines are explanations or instructions, not error messages.
_ERROR_MAX = 150

# A choice list showing one of these hasn't been chosen yet.
_PLACEHOLDER = re.compile(
	r"^\s*(-+|please (select|choose)\b.*|(select|choose)( one| an option)?\b.*)\s*$", re.IGNORECASE
)

LABEL_MAX = 80

# Radio buttons further apart than this, with different groups, answer different questions.
_GAP_MAX = 80

# Kinds of field, as forms.py sorts them.
TEXT = "text"
CHECKBOX = "checkbox"
RADIO = "radio"
CHOICE = "choice"


@dataclass
class Field:
	kind: str
	label: str = ""
	value: str = ""
	required: bool = False
	invalid: bool = False
	checked: bool = False
	# The site's own error message, linked to the field (aria-errormessage).
	errorMessage: str = ""
	description: str = ""
	# For radio buttons: one key per group, and the group's question if the page gives one.
	group: str = ""
	groupLabel: str = ""
	# The page's text between the previous field and this one, and between this one and the next.
	before: str = ""
	after: str = ""


@dataclass
class Finding:
	# Index into the list of fields, so the user can be taken to it.
	index: int
	# True when gent is sure this stops the form; False for things worth checking.
	problem: bool
	message: str


def asksForFormCheck(text: str) -> bool:
	"""Whether what was typed into gent is asking about a form, such as "what's wrong with this form?"."""
	t = text.lower()
	if _MISSED.search(t):
		return True
	return bool(_FORM.search(t) and _TROUBLE.search(t))


def errorLines(text: str) -> list[str]:
	"""The short lines in text that read like an error message."""
	found = []
	for line in text.splitlines():
		line = " ".join(line.split())
		if line and len(line) <= _ERROR_MAX and any(p.search(line) for p in _ERRORS) and line not in found:
			found.append(line)
	return found


def shorten(text: str, limit: int = LABEL_MAX) -> str:
	"""Long labels, such as a whole paragraph on a tickbox, cut at a word to keep the list readable."""
	text = " ".join(text.split())
	if len(text) <= limit:
		return text
	cut = text[:limit].rsplit(" ", 1)[0].rstrip(" ,.;:")
	return cut + "…"


def question(before: str) -> str:
	"""The question just before a set of radio buttons: the last line ending "?", or else the first line."""
	lines = [" ".join(line.split()) for line in before.splitlines()]
	lines = [line for line in lines if line]
	for line in reversed(lines):
		if line.endswith("?"):
			return line
	return lines[0] if lines else ""


def radioGroups(fields: list[Field]) -> list[list[int]]:
	"""Indexes of the radio buttons that answer each question, in page order.

	Pages don't always group their radio buttons properly; some wrap each one on its own.
	So buttons next to each other count as one question unless a new question comes between them.
	"""
	groups: list[list[int]] = []
	for i, field in enumerate(fields):
		if field.kind != RADIO:
			continue
		previous = fields[i - 1] if i else None
		together = (
			previous is not None
			and previous.kind == RADIO
			and groups
			and (
				(field.group and field.group == previous.group)
				or (len(" ".join(field.before.split())) <= _GAP_MAX and "?" not in field.before)
			)
		)
		if together:
			groups[-1].append(i)
		else:
			groups.append([i])
	return groups


def isEmpty(field: Field) -> bool:
	value = field.value.strip()
	if field.kind == CHOICE:
		return not value or bool(_PLACEHOLDER.match(value))
	return not value


def _name(field: Field, fallback: str) -> str:
	return shorten(field.label) or fallback


def findProblems(fields: list[Field]) -> list[Finding]:
	"""Everything gent thinks is wrong, problems first, each group in page order."""
	findings: list[Finding] = []
	reported: set[int] = set()

	def add(index: int, problem: bool, message: str) -> None:
		findings.append(Finding(index, problem, message))
		reported.add(index)

	# An error banner above the first field, such as "There is a problem with your answers".
	if fields:
		banner = errorLines(fields[0].before)
		if banner:
			# Translators: in gent's form check, error text found above the form's first field.
			add(0, True, _("Above the form: {reasons}").format(reasons="; ".join(banner)))
			reported.discard(0)

	groups = radioGroups(fields)

	for i, field in enumerate(fields):
		reasons: list[str] = []
		errors = [field.errorMessage.strip()] if field.errorMessage.strip() else []
		errors += [e for e in errorLines(field.description + "\n" + field.after) if e not in errors]
		if errors:
			reasons += errors
		elif field.invalid:
			# Translators: in gent's form check, a field the page has marked as wrong but gives no reason.
			reasons.append(_("marked as invalid"))
		if field.required and field.kind in (TEXT, CHOICE) and isEmpty(field):
			# Translators: in gent's form check.
			reasons.append(_("required, and empty"))
		if field.required and field.kind == CHECKBOX and not field.checked:
			# Translators: in gent's form check.
			reasons.append(_("required, and not ticked"))
		if field.kind == RADIO:
			# Errors after a radio button belong to its group; reported on the group's first button below.
			continue
		if reasons:
			# Translators: in gent's form check, e.g. "Postcode: Enter a valid postcode". {field} is the field's label.
			add(
				i,
				True,
				_("{field}: {reasons}").format(
					field=_name(field, _kindName(field.kind)), reasons="; ".join(reasons)
				),
			)

	for members in groups:
		first = fields[members[0]]
		label = shorten(first.groupLabel or question(first.before)) or _("Choice starting {option}").format(
			option=_name(first, _kindName(RADIO))
		)
		errors: list[str] = []
		for m in members:
			for e in [fields[m].errorMessage.strip()] + errorLines(
				fields[m].description + "\n" + fields[m].after
			):
				if e and e not in errors:
					errors.append(e)
		answered = any(fields[m].checked for m in members)
		invalid = any(fields[m].invalid for m in members)
		required = any(fields[m].required for m in members)
		if errors:
			add(members[0], True, _("{field}: {reasons}").format(field=label, reasons="; ".join(errors)))
		elif not answered and (required or invalid):
			# Translators: in gent's form check, a question with no option chosen.
			add(members[0], True, _("{field}: nothing chosen").format(field=label))
		elif invalid:
			add(members[0], True, _("{field}: marked as invalid").format(field=label))
		elif not answered:
			add(members[0], False, _("{field}: nothing chosen").format(field=label))
		else:
			reported.update(members)

	# Not marked as required, but often are: the site that started this flagged a tickbox only in plain text.
	for i, field in enumerate(fields):
		if i in reported:
			continue
		if field.kind == CHECKBOX and not field.checked:
			# Translators: in gent's form check.
			add(i, False, _("{field}: not ticked").format(field=_name(field, _kindName(CHECKBOX))))
		elif field.kind in (TEXT, CHOICE) and isEmpty(field):
			# Translators: in gent's form check.
			add(i, False, _("{field}: empty").format(field=_name(field, _kindName(field.kind))))

	findings.sort(key=lambda f: (not f.problem, f.index))
	return findings


def _kindName(kind: str) -> str:
	return {
		# Translators: in gent's form check, a field with no label.
		TEXT: _("unlabelled text box"),
		# Translators: in gent's form check, a field with no label.
		CHECKBOX: _("unlabelled tickbox"),
		# Translators: in gent's form check, a field with no label.
		RADIO: _("unlabelled option"),
		# Translators: in gent's form check, a field with no label.
		CHOICE: _("unlabelled list"),
	}[kind]


def summary(findings: list[Finding], fieldCount: int) -> str:
	"""What gent says first, e.g. "1 problem, 3 things to check, in 42 fields"."""
	problems = sum(f.problem for f in findings)
	checks = len(findings) - problems
	if not findings:
		# Translators: gent's form check found nothing wrong. {count} is how many fields it looked at.
		return _("No problems found in {count} form fields.").format(count=fieldCount)
	# Translators: part of gent's form check summary.
	parts = [ngettext("{n} problem", "{n} problems", problems).format(n=problems)] if problems else []
	if checks:
		# Translators: part of gent's form check summary.
		parts.append(ngettext("{n} thing to check", "{n} things to check", checks).format(n=checks))
	# Translators: gent's form check summary, e.g. "1 problem, 3 things to check, in 42 fields".
	return _("{parts}, in {count} fields.").format(parts=", ".join(parts), count=fieldCount)


# Inside NVDA, use gent's translations. Outside it, as in the tests, plain English.
try:
	import addonHandler

	addonHandler.initTranslation()
except ImportError:
	pass
if "_" not in globals():

	def _(text: str) -> str:
		return text


if "ngettext" not in globals():

	def ngettext(singular: str, plural: str, n: int) -> str:
		return singular if n == 1 else plural
