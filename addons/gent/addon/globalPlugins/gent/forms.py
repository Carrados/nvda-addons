# gent's form check: finds what's stopping a web form from submitting and takes you to it.
# Everything happens on this computer. Nothing about the form is sent to the relay.
# It reads what Chrome, Edge or Firefox expose to NVDA in browse mode; formcheck.py decides what's wrong.

import addonHandler
import api
import browseMode
import controlTypes
import core
import gui
import speech
import textInfos
import ui
import wx
from logHandler import log

from . import formcheck
from .formcheck import CHECKBOX, CHOICE, RADIO, TEXT, Field

addonHandler.initTranslation()

Role = controlTypes.Role
State = controlTypes.State

_KINDS = {
	Role.EDITABLETEXT: TEXT,
	Role.SPINBUTTON: TEXT,
	Role.PASSWORDEDIT: TEXT,
	Role.CHECKBOX: CHECKBOX,
	Role.SWITCH: CHECKBOX,
	Role.RADIOBUTTON: RADIO,
	Role.LIST: CHOICE,
}

# Text kept on each side of a field. Enough for an error message and the question before it.
_NEARBY = 1500


def document():
	"""The web page NVDA is in, or None."""
	ti = api.getFocusObject().treeInterceptor
	if isinstance(ti, browseMode.BrowseModeDocumentTreeInterceptor) and ti.isReady:
		return ti
	return None


def check(doc) -> None:
	"""Checks the page's form fields, then shows what's wrong."""
	if doc is None:
		# Translators: Spoken when gent's form check is used away from a web page.
		ui.message(_("Go to the web page with the form first, then ask gent again."))
		return
	try:
		items, fields = _collect(doc)
	except Exception:
		log.exception("gent: form check failed")
		# Translators: Spoken when gent's form check fails unexpectedly.
		ui.message(_("Sorry, I couldn't read the form on this page."))
		return
	if not fields:
		# Translators: Spoken when gent's form check finds no form on the page.
		ui.message(_("I can't find any form fields on this page."))
		return
	findings = formcheck.findProblems(fields)
	summary = formcheck.summary(findings, len(fields))
	if not findings:
		ui.message(summary)
		return
	gui.mainFrame.prePopup()
	dialog = _FindingsDialog(gui.mainFrame, summary, findings)
	try:
		result = dialog.ShowModal()
		chosen = dialog.chosen
	finally:
		dialog.Destroy()
		gui.mainFrame.postPopup()
	if result == wx.ID_OK and chosen is not None:
		_goTo(doc, items[findings[chosen].index])


def _collect(doc) -> tuple[list, list[Field]]:
	"""Every form field on the page, in page order, with the page's text around it."""
	items = []
	# Each lookup of item.obj asks the browser again, so keep what was found.
	found = []
	for item in doc._iterNodesByType("formField"):
		obj = item.obj
		kind = _kind(obj) if obj is not None else None
		if kind is None:
			continue
		# An editable list contains its own text box; one entry for the pair is enough.
		if items and item.isChild(items[-1]):
			continue
		items.append(item)
		found.append((obj, kind))
	# gaps[i] is the text before field i; gaps[i + 1] the text after it.
	ends = [None] + [item.textInfo for item in items] + [None]
	gaps = [_between(doc, ends[i], ends[i + 1]) for i in range(len(items) + 1)]
	fields = []
	for i, (obj, kind) in enumerate(found):
		states = obj.states
		field = Field(
			kind=kind,
			label=obj.name or "",
			value=(obj.value or "") if kind in (TEXT, CHOICE) else "",
			required=State.REQUIRED in states,
			invalid=State.INVALID_ENTRY in states,
			checked=State.CHECKED in states,
			errorMessage=_safe(obj, "errorMessage"),
			description=_safe(obj, "description"),
			before=gaps[i][-_NEARBY:],
			after=gaps[i + 1][:_NEARBY],
		)
		if kind == RADIO:
			parent = obj.parent
			field.group = str(getattr(parent, "IA2UniqueID", None) or id(parent))
			field.groupLabel = (
				(parent.name or "") if parent is not None and parent.role == Role.GROUPING else ""
			)
		fields.append(field)
	return items, fields


def _kind(obj) -> str | None:
	states = obj.states
	if State.UNAVAILABLE in states or State.READONLY in states:
		return None
	role = obj.role
	if role == Role.COMBOBOX:
		return TEXT if State.EDITABLE in states else CHOICE
	return _KINDS.get(role, TEXT if State.EDITABLE in states else None)


def _between(doc, start, end) -> str:
	"""The page's text from the end of start to the beginning of end. None means the page's edge."""
	info = doc.makeTextInfo(textInfos.POSITION_ALL)
	if start is not None:
		info.setEndPoint(start, "startToEnd")
	if end is not None:
		info.setEndPoint(end, "endToStart")
	if info.compareEndPoints(info, "startToEnd") >= 0:
		return ""
	return info.text


def _safe(obj, name: str) -> str:
	"""A property some pages or NVDA versions can't give; an empty string if so."""
	try:
		return getattr(obj, name) or ""
	except Exception:  # noqa: BLE001
		log.debugWarning(f"gent: couldn't read {name} of a form field", exc_info=True)
		return ""


def _goTo(doc, item) -> None:
	"""Moves to the field and reads it, as NVDA's Elements List does."""

	def move():
		speech.cancelSpeech()
		item.report()
		item.moveTo()

	# core.callLater, not wx, so this runs in NVDA's core pump once the dialog has gone (see browseMode.py).
	core.callLater(100, move)


class _FindingsDialog(wx.Dialog):
	def __init__(self, parent, summary: str, findings: list):
		# Translators: Title of gent's form check window.
		super().__init__(parent, title=_("gent form check"))
		self.chosen = None
		sizer = wx.BoxSizer(wx.VERTICAL)
		# Translators: Above the list in gent's form check. {summary} is e.g. "1 problem, in 42 fields."
		label = wx.StaticText(self, label=_("{summary} Press Enter to go to one.").format(summary=summary))
		sizer.Add(label, flag=wx.ALL, border=8)
		self._list = wx.ListBox(self, choices=[_line(f) for f in findings], style=wx.LB_SINGLE)
		self._list.SetSelection(0)
		self._list.Bind(wx.EVT_LISTBOX_DCLICK, self._onGo)
		sizer.Add(self._list, proportion=1, flag=wx.EXPAND | wx.LEFT | wx.RIGHT, border=8)
		buttons = wx.BoxSizer(wx.HORIZONTAL)
		# Translators: Button in gent's form check.
		go = wx.Button(self, wx.ID_OK, _("&Go to field"))
		go.SetDefault()
		go.Bind(wx.EVT_BUTTON, self._onGo)
		buttons.Add(go)
		# Translators: Button in gent's form check.
		buttons.Add(wx.Button(self, wx.ID_CANCEL, _("Close")), flag=wx.LEFT, border=8)
		sizer.Add(buttons, flag=wx.ALL | wx.ALIGN_RIGHT, border=8)
		self.SetSizerAndFit(sizer)
		self.SetSize((640, 420))
		self.CentreOnScreen()
		self._list.SetFocus()

	def _onGo(self, _event) -> None:
		selection = self._list.GetSelection()
		self.chosen = selection if selection != wx.NOT_FOUND else None
		self.EndModal(wx.ID_OK)


def _line(finding) -> str:
	if finding.problem:
		# Translators: A line in gent's form check. {message} is e.g. "Postcode: Enter a valid postcode".
		return _("Problem: {message}").format(message=finding.message)
	# Translators: A line in gent's form check, for something that may be fine but is worth checking.
	return _("Check: {message}").format(message=finding.message)
