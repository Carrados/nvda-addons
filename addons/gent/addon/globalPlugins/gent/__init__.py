# gent: say what you want NVDA to change, in plain words.
# Jev, through the gent relay, picks which known action you mean; settings.py makes the change.

import threading
import uuid
from collections.abc import Callable

import addonHandler
import config
import globalPluginHandler
import gui
import ui
import wx
from gui.message import MessageDialog, ReturnCode
from logHandler import log
from scriptHandler import script

from . import formcheck, forms, logic, relay, settings

addonHandler.initTranslation()

config.conf.spec["gent"] = {
	"installId": "string(default='')",
	"consented": "boolean(default=false)",
}

# How many changes gent remembers for "undo that" and for Jev's context.
HISTORY = 5

# What gent says when asking "Did you mean ...?"
DESCRIPTIONS = {name: action.description for name, action in settings.ACTIONS.items()} | {
	# Translators: Completes "Did you mean ...?" in gent.
	"undo": _("undo the last change"),
	# Translators: Completes "Did you mean ...?" in gent.
	"help": _("show what gent can do"),
}


def _overviewHtml() -> str:
	"""What gent can do, with the current settings, for reading in browse mode."""
	sections = [
		(
			# Translators: Heading in gent's overview.
			_("What you can change"),
			[
				# Translators: Item in gent's overview.
				_('Speed. Try "talk a bit faster", "way too slow" or "even faster than the maximum".'),
				# Translators: Item in gent's overview.
				_(
					'Pitch, volume and inflection. Try "make the voice deeper", "I can\'t hear it" or "she sounds flat".'
				),
				# Translators: Item in gent's overview.
				_('Voice, variant and synthesizer. Try "use a different voice" or "switch speech engine".'),
				# Translators: Item in gent's overview.
				_(
					'Punctuation and symbols. Try "stop reading punctuation", "read every symbol" or "stop reading emoji names".'
				),
				# Translators: Item in gent's overview.
				_(
					'Capitals. Try "beep for capitals", "say cap before capitals" or "make capitals stand out more".'
				),
				# Translators: Item in gent's overview.
				_(
					'Languages. Try "tell me when the language changes" or "stop switching accent for French".'
				),
				# Translators: Item in gent's overview.
				_(
					'Characters. Try "describe letters when I pause, like alpha bravo" or "fancy letters are read wrong".'
				),
				# Translators: Item in gent's overview.
				_('Speech dictionaries. Try "turn off my pronunciation dictionary".'),
				# Translators: Item in gent's overview.
				_(
					'Typing and keys. Try "stop saying every letter I type" or "tell me what keys I\'m pressing".'
				),
				# Translators: Item in gent's overview.
				_('Undo. Try "undo that" or "go back to how it was". gent remembers its last five changes.'),
			],
		),
		(
			# Translators: Heading in gent's overview.
			_("Forms"),
			[
				# Translators: Item in gent's overview.
				_(
					"When a web form won't submit, try \"what's wrong with this form?\" or press NVDA+Shift+G. "
					"gent lists what's stopping it, and anything worth checking, and takes you to the one you pick."
				),
				# Translators: Item in gent's overview.
				_("The form check happens on your computer. Nothing on the form is sent anywhere."),
			],
		),
		# Translators: Heading in gent's overview.
		(_("Your settings now"), settings.currentSettings()),
	]
	html = [
		# Translators: Main heading of gent's overview.
		f"<h1>{_('What gent can do')}</h1>",
		# Translators: Introduction in gent's overview.
		f"<p>{_('Press NVDA+G, type what you want in your own words, and press Enter.')}</p>",
	]
	for heading, items in sections:
		html.append(f"<h2>{heading}</h2><ul>")
		html.extend(f"<li>{item}</li>" for item in items)
		html.append("</ul>")
	html.append(
		"<p>{}</p>".format(
			# Translators: End of gent's overview.
			_(
				"If gent isn't sure what you mean, it asks first. If it can't do something, it says so. "
				'Type "help" at any time to see this again.',
			),
		),
	)
	return "".join(html)


def _showOverview() -> None:
	# Translators: Title of gent's overview window.
	ui.browseableMessage(_overviewHtml(), _("gent help"), isHtml=True, closeButton=True)


# Typed on their own, these show the overview without asking the relay.
HELP_WORDS = {
	"",
	"help",
	"what can you do",
	"what can i do",
	"what can i change",
	"overview",
	"give me an overview",
	"how does this work",
}


class GlobalPlugin(globalPluginHandler.GlobalPlugin):
	def __init__(self):
		super().__init__()
		# (action, undo) for changes made this session, oldest first.
		self._history: list[tuple[str, Callable[[], str]]] = []
		self._busy = False

	@script(
		# Translators: Describes the gent command in NVDA's Input gestures dialog.
		description=_("Tell gent, in plain words, what you want NVDA to change"),
		# Translators: Category for gent's commands in NVDA's Input gestures dialog.
		category=_("gent"),
		gesture="kb:NVDA+g",
	)
	def script_ask(self, gesture):
		if self._busy:
			return
		# Remember the page now: once gent's dialog opens, the focus is no longer on it.
		wx.CallAfter(self._prompt, forms.document())

	@script(
		# Translators: Describes a gent command in NVDA's Input gestures dialog.
		description=_("Check the form on this web page and list what's stopping it from submitting"),
		category=_("gent"),
		gesture="kb:NVDA+shift+g",
	)
	def script_checkForm(self, gesture):
		doc = forms.document()
		wx.CallAfter(forms.check, doc)

	def _prompt(self, doc=None) -> None:
		gui.mainFrame.prePopup()
		dialog = wx.TextEntryDialog(
			gui.mainFrame,
			# Translators: Prompt in the gent dialog.
			_("What would you like to change?"),
			_("gent"),
		)
		try:
			result = dialog.ShowModal()
			text = dialog.GetValue().strip()
		finally:
			dialog.Destroy()
			gui.mainFrame.postPopup()
		if result != wx.ID_OK or not text:
			return
		if text.lower().strip(" ?!.") in HELP_WORDS:
			_showOverview()
			return
		# Checked on this computer, so a form's contents never go to the relay.
		if formcheck.asksForFormCheck(text):
			forms.check(doc)
			return
		if not config.conf["gent"]["consented"]:
			answer = MessageDialog.confirm(
				# Translators: Shown the first time gent is used.
				_(
					"gent sends what you type to Blind Ant's relay and to TypeSafe, whose Jev model works out "
					"which setting you mean. Nothing else on your computer is sent. Continue?",
				),
				# Translators: Title of gent's dialogs.
				_("gent"),
			)
			if answer != ReturnCode.OK:
				return
			config.conf["gent"]["consented"] = True
		self._busy = True
		recent = [action for action, _undo in reversed(self._history)]
		threading.Thread(target=self._decide, args=(text, recent), daemon=True).start()

	def _decide(self, text: str, recent: list[str]) -> None:
		"""Runs off the main thread so NVDA keeps responding while gent waits for the relay."""
		try:
			answer = relay.decide(_installId(), text, recent, addonHandler.getCodeAddon().version)
		except relay.RelayError as e:
			wx.CallAfter(self._finish, str(e))
			return
		except Exception:
			log.exception("gent: unexpected error asking the relay")
			# Translators: Spoken when gent fails unexpectedly.
			wx.CallAfter(self._finish, _("Sorry, something went wrong."))
			return
		wx.CallAfter(self._handle, answer)

	def _handle(self, answer: dict) -> None:
		try:
			lastAction = self._history[-1][0] if self._history else None
			decision, action = logic.plan(answer, lastAction)
			if decision == "none":
				# Translators: Spoken when gent can't match the request to anything it can do.
				ui.message(_('Sorry, I can\'t do that yet. Type "help" to hear what I can do.'))
				return
			if decision == "ask":
				reply = MessageDialog.confirm(
					# Translators: gent asking to check what the user meant. {action} is e.g. "make speech faster".
					_("Did you mean: {action}?").format(action=DESCRIPTIONS[action]),
					_("gent"),
					# Translators: Button in gent's "Did you mean" dialog.
					okLabel=_("&Yes"),
					# Translators: Button in gent's "Did you mean" dialog.
					cancelLabel=_("&No"),
				)
				if reply != ReturnCode.OK:
					# Translators: Spoken when the user says no to "Did you mean".
					ui.message(_("OK, nothing changed."))
					return
			if action == "help":
				_showOverview()
				return
			ui.message(self._do(action, answer["size"] == "large"))
		finally:
			self._busy = False

	def _do(self, action: str, large: bool) -> str:
		if action == "undo":
			if not self._history:
				# Translators: Spoken when there is nothing for gent to undo.
				return _("Nothing to undo.")
			_action, undo = self._history.pop()
			# Translators: Spoken after gent undoes a change. {result} is the restored setting.
			return _("Undone. {result}").format(result=undo())
		try:
			message, undo = settings.ACTIONS[action].run(large)
		except settings.CannotDo as e:
			return str(e)
		self._history = (self._history + [(action, undo)])[-HISTORY:]
		return message

	def _finish(self, message: str) -> None:
		self._busy = False
		ui.message(message)


def _installId() -> str:
	"""A random ID for this install, so the relay can limit requests fairly. It identifies nothing else."""
	installId = config.conf["gent"]["installId"]
	if not installId:
		installId = str(uuid.uuid4())
		config.conf["gent"]["installId"] = installId
	return installId
