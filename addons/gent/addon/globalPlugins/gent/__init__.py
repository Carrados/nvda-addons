# gent: say what you want NVDA to change, in plain words.
# Jev, through the gent relay, picks which known action you mean; this code makes the change.

import threading
import uuid
from collections.abc import Callable

import addonHandler
import characterProcessing
import config
import globalPluginHandler
import gui
import ui
import wx
from config.configFlags import TypingEcho
from gui.message import MessageDialog, ReturnCode
from logHandler import log
from scriptHandler import script
from synthDriverHandler import getSynth

from . import logic, relay

addonHandler.initTranslation()

config.conf.spec["gent"] = {
	"installId": "string(default='')",
	"consented": "boolean(default=false)",
}

# How many changes gent remembers for "undo that" and for Jev's context.
HISTORY = 5


class CannotDo(Exception):
	"""The action makes sense but can't be done right now; the message says why."""


# Each action returns what to say, and a function that undoes it and returns what to say then.
Change = tuple[str, Callable[[], str]]


def _setRate(value: int) -> None:
	synth = getSynth()
	synth.rate = value
	config.conf["speech"][synth.name]["rate"] = value


def _changeRate(faster: bool, large: bool) -> Change:
	synth = getSynth()
	if synth is None or not synth.isSupported("rate"):
		# Translators: Spoken when the current voice has no speed setting.
		raise CannotDo(_("This voice can't change speed."))
	old = synth.rate
	new = logic.stepRate(old, faster, large)
	if new == old:
		# Translators: Spoken when speech is already at its fastest or slowest.
		raise CannotDo(
			_("Speech is already as fast as it goes.")
			if faster
			else _("Speech is already as slow as it goes.")
		)
	_setRate(new)

	def undo() -> str:
		_setRate(old)
		# Translators: Spoken after changing speech rate. {rate} is a number from 0 to 100.
		return _("Speech rate {rate}").format(rate=old)

	return _("Speech rate {rate}").format(rate=new), undo


def _symbolLevelMessage(level: int) -> str:
	label = characterProcessing.SPEECH_SYMBOL_LEVEL_LABELS[characterProcessing.SymbolLevel(level)]
	# Translators: Spoken after changing punctuation level. {level} is none, some, most or all.
	return _("Punctuation {level}").format(level=label)


def _changePunctuation(more: bool, large: bool) -> Change:
	levels = [level.value for level in characterProcessing.CONFIGURABLE_SPEECH_SYMBOL_LEVELS]
	old = config.conf["speech"]["symbolLevel"]
	new = logic.stepLevel(levels, old, more, large)
	if new == old:
		# Translators: Spoken when punctuation is already at its highest or lowest level.
		raise CannotDo(_("Punctuation is already at all.") if more else _("Punctuation is already at none."))
	config.conf["speech"]["symbolLevel"] = new

	def undo() -> str:
		config.conf["speech"]["symbolLevel"] = old
		return _symbolLevelMessage(old)

	return _symbolLevelMessage(new), undo


def _changeTypingEcho(key: str, label: str, on: bool) -> Change:
	old = config.conf["keyboard"][key]
	if on and old != TypingEcho.OFF.value:
		# Translators: Spoken when typing echo is already on. {setting} is e.g. "Speak typed characters".
		raise CannotDo(_("{setting} is already on.").format(setting=label))
	if not on and old == TypingEcho.OFF.value:
		# Translators: Spoken when typing echo is already off. {setting} is e.g. "Speak typed characters".
		raise CannotDo(_("{setting} is already off.").format(setting=label))
	# "On" means NVDA's default, which is only in edit controls.
	new = TypingEcho.EDIT_CONTROLS.value if on else TypingEcho.OFF.value
	config.conf["keyboard"][key] = new

	def message(value: int) -> str:
		return f"{label} {TypingEcho(value).displayString}"

	def undo() -> str:
		config.conf["keyboard"][key] = old
		return message(old)

	return message(new), undo


def _typedCharacters(on: bool) -> Callable[[bool], Change]:
	# Translators: Name of NVDA's typed characters setting, as spoken by gent.
	return lambda large: _changeTypingEcho("speakTypedCharacters", _("Speak typed characters"), on)


def _typedWords(on: bool) -> Callable[[bool], Change]:
	# Translators: Name of NVDA's typed words setting, as spoken by gent.
	return lambda large: _changeTypingEcho("speakTypedWords", _("Speak typed words"), on)


# Every action the relay can return except undo and none. Each takes "large" (a big change was asked for).
ACTIONS: dict[str, Callable[[bool], Change]] = {
	"speechRateFaster": lambda large: _changeRate(True, large),
	"speechRateSlower": lambda large: _changeRate(False, large),
	"punctuationMore": lambda large: _changePunctuation(True, large),
	"punctuationLess": lambda large: _changePunctuation(False, large),
	"typedCharactersOn": _typedCharacters(True),
	"typedCharactersOff": _typedCharacters(False),
	"typedWordsOn": _typedWords(True),
	"typedWordsOff": _typedWords(False),
}

# What gent says when asking "Did you mean ...?"
DESCRIPTIONS = {
	# Translators: Completes "Did you mean ...?" in gent.
	"speechRateFaster": _("make speech faster"),
	# Translators: Completes "Did you mean ...?" in gent.
	"speechRateSlower": _("make speech slower"),
	# Translators: Completes "Did you mean ...?" in gent.
	"punctuationMore": _("read more punctuation"),
	# Translators: Completes "Did you mean ...?" in gent.
	"punctuationLess": _("read less punctuation"),
	# Translators: Completes "Did you mean ...?" in gent.
	"typedCharactersOn": _("speak characters as you type"),
	# Translators: Completes "Did you mean ...?" in gent.
	"typedCharactersOff": _("stop speaking characters as you type"),
	# Translators: Completes "Did you mean ...?" in gent.
	"typedWordsOn": _("speak words as you type"),
	# Translators: Completes "Did you mean ...?" in gent.
	"typedWordsOff": _("stop speaking words as you type"),
	# Translators: Completes "Did you mean ...?" in gent.
	"undo": _("undo the last change"),
	# Translators: Completes "Did you mean ...?" in gent.
	"help": _("show what gent can do"),
}


def _overviewHtml() -> str:
	"""What gent can do, with the current settings, for reading in browse mode."""
	synth = getSynth()
	if synth is not None and synth.isSupported("rate"):
		# Translators: Current speech rate in gent's overview. {rate} is a number from 0 to 100.
		rate = _("Speech rate is {rate} out of 100.").format(rate=synth.rate)
	else:
		# Translators: In gent's overview, when the current voice has no speed setting.
		rate = _("This voice can't change speed.")
	keyboard = config.conf["keyboard"]
	current = [
		rate,
		_symbolLevelMessage(config.conf["speech"]["symbolLevel"]) + ".",
		# Translators: In gent's overview. {setting} is e.g. "Only in edit controls" or "Off".
		_("Speak typed characters: {setting}.").format(
			setting=TypingEcho(keyboard["speakTypedCharacters"]).displayString,
		),
		# Translators: In gent's overview. {setting} is e.g. "Only in edit controls" or "Off".
		_("Speak typed words: {setting}.").format(
			setting=TypingEcho(keyboard["speakTypedWords"]).displayString
		),
	]
	sections = [
		(
			# Translators: Heading in gent's overview.
			_("What you can change"),
			[
				# Translators: Item in gent's overview.
				_('Speech rate. Try "talk a bit faster", "slower" or "way too slow".'),
				# Translators: Item in gent's overview.
				_('Punctuation. Try "stop reading so much punctuation" or "read all the symbols".'),
				# Translators: Item in gent's overview.
				_('Typing echo. Try "stop saying every letter I type" or "speak words as I type".'),
				# Translators: Item in gent's overview.
				_('Undo. Try "undo that" or "go back to how it was". gent remembers its last five changes.'),
			],
		),
		# Translators: Heading in gent's overview.
		(_("Your settings now"), current),
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
		wx.CallAfter(self._prompt)

	def _prompt(self) -> None:
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
			message, undo = ACTIONS[action](large)
		except CannotDo as e:
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
