# gent: say what you want NVDA to change, in plain words.
# Jev, through the gent relay, picks which known action you mean; settings.py makes the change.

import os
import threading
import time
import uuid
from collections.abc import Callable

import addonHandler
import api
import config
import globalPluginHandler
import gui
import tones
import ui
import wx
from gui.message import MessageDialog, ReturnCode
from logHandler import log
from scriptHandler import script

from . import formcheck, forms, logic, recorder, relay, settings

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
					'When a web form won\'t submit, press NVDA+G, then F. Or type "form help". '
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
		f"<p>{_('Press NVDA+G, then Space. Type what you want in your own words, and press Enter.')}</p>",
		# Translators: Introduction in gent's overview, listing the keys after NVDA+G.
		f"<p>{_('After NVDA+G you can also press F to check a form, R to record a page, H for this help, U to undo, or Escape to leave.')}</p>",
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
		# True after NVDA+G, while gent waits for one key: see logic.LAYER.
		self._layer = False
		# The page recording in progress, if any.
		self._recorder: recorder.Recorder | None = None

	def getScript(self, gesture):
		if self._recorder is not None and self._recorder.running:
			# Any key the user presses ends a recording. gent's own Tab presses never come through here.
			if getattr(gesture, "isModifier", False):
				return None
			return self._stopRecording
		if not self._layer:
			return super().getScript(gesture)
		if getattr(gesture, "isModifier", False):
			return None
		self._layer = False
		command = logic.layerCommand(gesture.normalizedIdentifiers)
		return getattr(self, f"_layer_{command}", self._layer_unknown)

	@script(
		# Translators: Describes the gent command in NVDA's Input gestures dialog.
		description=_(
			"gent: then press Space to type what you want, F to check a form, R to record a page, H for help or U to undo"
		),
		# Translators: Category for gent's commands in NVDA's Input gestures dialog.
		category=_("gent"),
		gesture="kb:NVDA+g",
	)
	def script_ask(self, gesture):
		if self._busy:
			return
		self._layer = True
		# Translators: Spoken after NVDA+G, while gent waits for the next key.
		ui.message(_("gent"))

	@script(
		# Translators: Describes a gent command in NVDA's Input gestures dialog.
		description=_("Check the form on this web page and list what's stopping it from submitting"),
		category=_("gent"),
	)
	def script_checkForm(self, gesture):
		doc = forms.document()
		wx.CallAfter(forms.check, doc)

	# What each key does after NVDA+G. Each takes the gesture, like a script.
	def _layer_type(self, gesture):
		# Remember the page now: once gent's dialog opens, the focus is no longer on it.
		wx.CallAfter(self._prompt, forms.document())

	def _layer_form(self, gesture):
		self.script_checkForm(gesture)

	def _layer_help(self, gesture):
		wx.CallAfter(_showOverview)

	def _layer_undo(self, gesture):
		ui.message(self._do("undo", False))

	def _layer_record(self, gesture):
		doc = forms.document()
		if doc is None:
			# Translators: Spoken when gent's page recorder is used away from a web page.
			ui.message(_("Go to the web page you want to record first, then press NVDA+G, R."))
			return
		# Translators: Spoken when gent starts recording a page. Nothing else is spoken until it finishes.
		ui.message(_("Recording this page silently. Press any key to stop."))
		self._recorder = recorder.Recorder(doc, lambda text: wx.CallAfter(self._recorded, text))
		# Let the message above reach the synthesizer before speech is muted.
		wx.CallLater(500, self._recorder.start)

	def _stopRecording(self, gesture):
		if self._recorder is not None:
			# Translators: Why a gent page recording ended.
			self._recorder.stop(_("Stopped by a key press."))

	def _recorded(self, text: str) -> None:
		"""Saves the recording on this computer, then offers to share it as a link."""
		path = _saveRecording(text)
		steps = text.count("\nTab ")
		share = MessageDialog.confirm(
			# Translators: Asked when a gent page recording finishes. {path} is where it was saved.
			_(
				"Recording finished, with {steps} presses of Tab. It's saved in {path}.\n\n"
				"Send it to Blind Ant's relay and copy a link to it? Anyone with the link can read it "
				"for 7 days. It holds everything NVDA said, including anything typed into the page's forms."
			).format(steps=steps, path=path),
			_("gent"),
			# Translators: Button when sharing a gent page recording.
			okLabel=_("&Send and copy link"),
			# Translators: Button when sharing a gent page recording.
			cancelLabel=_("&Keep it on this computer"),
		)
		if share != ReturnCode.OK:
			# Translators: Spoken when a gent page recording is kept on this computer only.
			ui.message(_("Kept on this computer only."))
			return
		threading.Thread(target=self._share, args=(text,), daemon=True).start()

	def _share(self, text: str) -> None:
		try:
			answer = relay.shareRecording(_installId(), text, addonHandler.getCodeAddon().version)
		except relay.RelayError as e:
			wx.CallAfter(ui.message, str(e))
			return
		except Exception:
			log.exception("gent: unexpected error sharing a recording")
			# Translators: Spoken when sharing a gent page recording fails unexpectedly.
			wx.CallAfter(ui.message, _("Sorry, the recording couldn't be sent."))
			return
		wx.CallAfter(_linkReady, answer["url"])

	def _layer_exit(self, gesture):
		# Translators: Spoken when leaving gent's keys with Escape.
		ui.message(_("Cancelled"))

	def _layer_unknown(self, gesture):
		tones.beep(200, 80)

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


def _saveRecording(text: str) -> str:
	"""Keeps a copy in Documents\\gent recordings, so nothing is lost if it isn't shared."""
	folder = os.path.join(os.path.expanduser("~"), "Documents", "gent recordings")
	os.makedirs(folder, exist_ok=True)
	path = os.path.join(folder, time.strftime("page %Y-%m-%d %H%M%S.txt"))
	with open(path, "w", encoding="utf-8") as f:
		f.write(text)
	return path


def _linkReady(url: str) -> None:
	api.copyToClip(url)
	# Translators: Spoken once a gent page recording has been shared.
	ui.message(_("Link copied. Paste it to Claude, or anyone you want to check the page."))


def _installId() -> str:
	"""A random ID for this install, so the relay can limit requests fairly. It identifies nothing else."""
	installId = config.conf["gent"]["installId"]
	if not installId:
		installId = str(uuid.uuid4())
		config.conf["gent"]["installId"] = installId
	return installId
