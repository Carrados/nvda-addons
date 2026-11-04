# Every change gent can make: all of NVDA 2026.2's Speech settings panel (the synthesizer, the
# voice's own settings and the panel's options), plus typing echo and command keys from Keyboard.
# Each change is made the way NVDA's own settings panel or commands make it, and comes with
# what to say and a function that undoes it.

from collections.abc import Callable
from dataclasses import dataclass

import addonHandler
import characterProcessing
import config
import synthDriverHandler
from config.configFlags import TypingEcho
from synthDriverHandler import getSynth

from . import logic

addonHandler.initTranslation()


class CannotDo(Exception):
	"""The action makes sense but can't be done right now; the message says why."""


# What to say after the change, and a function that undoes it and returns what to say then.
Change = tuple[str, Callable[[], str]]


@dataclass(frozen=True)
class Action:
	# Completes "Did you mean ...?"
	description: str
	# Makes the change. Takes "large": whether a big change was asked for.
	run: Callable[[bool], Change]


# Stands for the current synthesizer's name in a config path, as in config.conf["speech"][synth.name].
SYNTH = object()


def _onOff(on: bool) -> str:
	# Translators: The state of a setting, spoken by gent, as in "Beep for capitals on".
	return _("on") if on else _("off")


def _already(label: str, state: str) -> CannotDo:
	# Translators: Spoken when a setting is already as asked. {setting} is e.g. "Beep for capitals", {state} e.g. "on".
	return CannotDo(_("{setting} is already {state}.").format(setting=label, state=state))


def _synth():
	synth = getSynth()
	if synth is None:
		# Translators: Spoken when no synthesizer is running.
		raise CannotDo(_("No voice is running."))
	return synth


def _requireSynthSetting(settingId: str, label: str):
	synth = _synth()
	if not synth.isSupported(settingId):
		# Translators: Spoken when the current voice lacks a setting. {setting} is e.g. "Pitch".
		raise CannotDo(_("This voice has no {setting} setting.").format(setting=label))
	return synth


def _resolve(path: tuple) -> tuple:
	return tuple(_synth().name if key is SYNTH else key for key in path)


def _confGet(path: tuple):
	node = config.conf
	for key in path:
		node = node[key]
	return node


def _confSet(path: tuple, value) -> None:
	node = config.conf
	for key in path[:-1]:
		node = node[key]
	node[path[-1]] = value


# The synthesizer's own settings, as NVDA's voice settings and settings ring change them.


def _setSynthValue(settingId: str, value) -> None:
	synth = getSynth()
	setattr(synth, settingId, value)
	config.conf["speech"][synth.name][settingId] = value


def _stepSynth(settingId: str, label: str, up: bool, large: bool) -> Change:
	synth = _requireSynthSetting(settingId, label)
	old = getattr(synth, settingId)
	new = logic.stepValue(old, up, large)
	if new == old:
		# Translators: Spoken when a setting is at its limit. {setting} is e.g. "Pitch".
		raise CannotDo(
			_("{setting} is already as high as it goes.").format(setting=label)
			if up
			else _("{setting} is already as low as it goes.").format(setting=label),
		)
	_setSynthValue(settingId, new)

	def undo() -> str:
		_setSynthValue(settingId, old)
		return f"{label} {old}"

	return f"{label} {new}", undo


def _toggleSynth(settingId: str, label: str, on: bool) -> Change:
	synth = _requireSynthSetting(settingId, label)
	old = bool(getattr(synth, settingId))
	if old == on:
		raise _already(label, _onOff(on))
	_setSynthValue(settingId, on)

	def undo() -> str:
		_setSynthValue(settingId, old)
		return f"{label} {_onOff(old)}"

	return f"{label} {_onOff(on)}", undo


def _applyChoice(settingId: str, value: str) -> None:
	synth = getSynth()
	if settingId == "voice":
		# As NVDA's settings ring does: changeVoice also updates the voice's speech dictionary.
		synthDriverHandler.changeVoice(synth, value)
		synth.saveSettings()
	else:
		_setSynthValue(settingId, value)


def _cycleSynthChoice(settingId: str, label: str, forward: bool) -> Change:
	synth = _requireSynthSetting(settingId, label)
	available = synth.availableVoices if settingId == "voice" else synth.availableVariants
	choices = list(available.values())
	if len(choices) < 2:
		# Translators: Spoken when there's nothing to switch to. {setting} is e.g. "voice".
		raise CannotDo(_("There is only one {setting} to choose from.").format(setting=label.lower()))
	ids = [choice.id for choice in choices]
	current = getattr(synth, settingId)
	index = ids.index(current) if current in ids else 0
	old = choices[index]
	new = choices[(index + (1 if forward else -1)) % len(choices)]
	_applyChoice(settingId, new.id)

	def undo() -> str:
		_applyChoice(settingId, old.id)
		return old.displayName

	return new.displayName, undo


def _nextSynth(large: bool) -> Change:
	old = _synth().name
	# Never "No speech": switching to silence would leave the user with no voice to undo it with.
	names = [name for name, description in synthDriverHandler.getSynthList() if name != "silence"]
	if old not in names or len(names) < 2:
		# Translators: Spoken when there is no other synthesizer to switch to.
		raise CannotDo(_("There is no other synthesizer to switch to."))
	new = names[(names.index(old) + 1) % len(names)]
	if not synthDriverHandler.setSynth(new):
		# Translators: Spoken when switching synthesizer fails.
		raise CannotDo(_("That synthesizer wouldn't start, so the voice hasn't changed."))

	def undo() -> str:
		synthDriverHandler.setSynth(old)
		return _synth().description

	return _synth().description, undo


# Options on the Speech panel and elsewhere, as their settings panels save them.


def _toggleConf(path: tuple, label: str, on: bool) -> Change:
	path = _resolve(path)
	old = bool(_confGet(path))
	if old == on:
		raise _already(label, _onOff(on))
	_confSet(path, on)

	def undo() -> str:
		_confSet(path, old)
		return f"{label} {_onOff(old)}"

	return f"{label} {_onOff(on)}", undo


def _stepConf(path: tuple, label: str, up: bool, large: bool, low: int, high: int) -> Change:
	path = _resolve(path)
	old = _confGet(path)
	new = logic.stepValue(old, up, large, low, high)
	if new == old:
		raise CannotDo(
			_("{setting} is already as high as it goes.").format(setting=label)
			if up
			else _("{setting} is already as low as it goes.").format(setting=label),
		)
	_confSet(path, new)

	def undo() -> str:
		_confSet(path, old)
		return f"{label} {old}"

	return f"{label} {new}", undo


def _toggleFlag(path: tuple, label: str, on: bool) -> Change:
	"""For feature flags, which the settings panel saves by name: ENABLED, DISABLED or DEFAULT."""
	flag = _confGet(path)
	if bool(flag) == on:
		raise _already(label, _onOff(on))
	oldName = flag.value.name
	_confSet(path, "ENABLED" if on else "DISABLED")

	def undo() -> str:
		_confSet(path, oldName)
		return f"{label} {_onOff(bool(_confGet(path)))}"

	return f"{label} {_onOff(on)}", undo


def _toggleListMember(key: str, member: str, label: str, on: bool, afterChange=lambda: None) -> Change:
	"""For the checked lists of symbol and speech dictionaries."""
	old = list(config.conf["speech"][key])
	if (member in old) == on:
		raise _already(label, _onOff(on))
	config.conf["speech"][key] = old + [member] if on else [m for m in old if m != member]
	afterChange()

	def undo() -> str:
		config.conf["speech"][key] = old
		afterChange()
		return f"{label} {_onOff(not on)}"

	return f"{label} {_onOff(on)}", undo


UNSUPPORTED_LANGUAGE = {
	# Translators: A choice for what NVDA does when the voice can't speak a language.
	"speech": _("say so"),
	# Translators: A choice for what NVDA does when the voice can't speak a language.
	"beep": _("beep"),
	# Translators: A choice for what NVDA does when the voice can't speak a language.
	"off": _("off"),
}


def _setUnsupportedLanguage(value: str) -> Change:
	# Translators: Name of the setting for languages the voice can't speak, as spoken by gent.
	label = _("Unsupported language")
	old = config.conf["speech"]["reportNotSupportedLanguage"]
	if old == value:
		raise _already(label, UNSUPPORTED_LANGUAGE[value])
	config.conf["speech"]["reportNotSupportedLanguage"] = value

	def undo() -> str:
		config.conf["speech"]["reportNotSupportedLanguage"] = old
		return f"{label}: {UNSUPPORTED_LANGUAGE[old]}"

	return f"{label}: {UNSUPPORTED_LANGUAGE[value]}", undo


def symbolLevelMessage(level: int) -> str:
	label = characterProcessing.SPEECH_SYMBOL_LEVEL_LABELS[characterProcessing.SymbolLevel(level)]
	# Translators: Spoken after changing punctuation level. {level} is none, some, most or all.
	return _("Punctuation {level}").format(level=label)


def _setPunctuation(new: int) -> Change:
	old = config.conf["speech"]["symbolLevel"]
	if new == old:
		# Translators: Spoken when punctuation is already at the level asked for.
		raise CannotDo(_("{level} already.").format(level=symbolLevelMessage(new)))
	config.conf["speech"]["symbolLevel"] = new

	def undo() -> str:
		config.conf["speech"]["symbolLevel"] = old
		return symbolLevelMessage(old)

	return symbolLevelMessage(new), undo


def _stepPunctuation(more: bool, large: bool) -> Change:
	levels = [level.value for level in characterProcessing.CONFIGURABLE_SPEECH_SYMBOL_LEVELS]
	return _setPunctuation(logic.stepLevel(levels, config.conf["speech"]["symbolLevel"], more, large))


def _changeTypingEcho(key: str, label: str, on: bool) -> Change:
	old = config.conf["keyboard"][key]
	if on == (old != TypingEcho.OFF.value):
		raise _already(label, _onOff(on))
	# "On" means NVDA's default, which is only in edit controls.
	new = TypingEcho.EDIT_CONTROLS.value if on else TypingEcho.OFF.value
	config.conf["keyboard"][key] = new

	def message(value: int) -> str:
		return f"{label} {TypingEcho(value).displayString}"

	def undo() -> str:
		config.conf["keyboard"][key] = old
		return message(old)

	return message(new), undo


# Labels for settings, as gent speaks them.
# Translators: Settings named by gent when it reports a change.
RATE = _("Speech rate")
RATE_BOOST = _("Rate boost")  # Translators: as above.
PITCH = _("Pitch")  # Translators: as above.
VOLUME = _("Volume")  # Translators: as above.
INFLECTION = _("Inflection")  # Translators: as above.
VOICE = _("Voice")  # Translators: as above.
VARIANT = _("Variant")  # Translators: as above.
CAP_PITCH = _("Capital pitch change")  # Translators: as above.
SAY_CAP = _("Say cap before capitals")  # Translators: as above.
BEEP_CAPS = _("Beep for capitals")  # Translators: as above.
SPELLING = _("Spelling functionality")  # Translators: as above.
DELAYED = _("Delayed character descriptions")  # Translators: as above.
EMOJI = _("Unicode and emoji names")  # Translators: as above.
AUTO_LANGUAGE = _("Automatic language switching")  # Translators: as above.
AUTO_DIALECT = _("Automatic dialect switching")  # Translators: as above.
REPORT_LANGUAGE = _("Report language changes")  # Translators: as above.
TRUST_LANGUAGE = _("Trust voice's language for symbols")  # Translators: as above.
NORMALIZATION = _("Unicode normalization")  # Translators: as above.
REPORT_NORMALIZED = _("Report normalized")  # Translators: as above.
USER_DICT = _("Default speech dictionary")  # Translators: as above.
VOICE_DICT = _("Voice speech dictionary")  # Translators: as above.
TYPED_CHARACTERS = _("Speak typed characters")  # Translators: as above.
TYPED_WORDS = _("Speak typed words")  # Translators: as above.
COMMAND_KEYS = _("Speak command keys")  # Translators: as above.


def _pair(onName: str, offName: str, onDescription: str, offDescription: str, run) -> dict[str, Action]:
	"""Two actions that set something on and off; run(on, large) makes the change."""
	return {
		onName: Action(onDescription, lambda large: run(True, large)),
		offName: Action(offDescription, lambda large: run(False, large)),
	}


def _confPair(onName, offName, path, label, onDescription, offDescription) -> dict[str, Action]:
	return _pair(
		onName, offName, onDescription, offDescription, lambda on, large: _toggleConf(path, label, on)
	)


def _stepPair(upName, downName, settingId, label, upDescription, downDescription) -> dict[str, Action]:
	return _pair(
		upName,
		downName,
		upDescription,
		downDescription,
		lambda up, large: _stepSynth(settingId, label, up, large),
	)


def _refreshSymbols() -> None:
	# As the Speech panel does when the symbol dictionaries change.
	characterProcessing.clearSpeechSymbols()


# Every action the relay can return except undo, help and none.
# The descriptions complete "Did you mean ...?"
# Translators for every description below: completes "Did you mean ...?" in gent.
ACTIONS: dict[str, Action] = {
	**_stepPair(
		"speechRateFaster", "speechRateSlower", "rate", RATE, _("make speech faster"), _("make speech slower")
	),
	**_pair(
		"rateBoostOn",
		"rateBoostOff",
		_("turn rate boost on"),
		_("turn rate boost off"),
		lambda on, large: _toggleSynth("rateBoost", RATE_BOOST, on),
	),
	**_stepPair("pitchHigher", "pitchLower", "pitch", PITCH, _("raise the pitch"), _("lower the pitch")),
	**_stepPair(
		"volumeLouder", "volumeQuieter", "volume", VOLUME, _("make speech louder"), _("make speech quieter")
	),
	**_stepPair(
		"inflectionMore",
		"inflectionLess",
		"inflection",
		INFLECTION,
		_("give the voice more inflection"),
		_("give the voice less inflection"),
	),
	**_pair(
		"nextVoice",
		"previousVoice",
		_("switch to the next voice"),
		_("go back to the previous voice"),
		lambda forward, large: _cycleSynthChoice("voice", VOICE, forward),
	),
	**_pair(
		"nextVariant",
		"previousVariant",
		_("switch to the next variant"),
		_("go back to the previous variant"),
		lambda forward, large: _cycleSynthChoice("variant", VARIANT, forward),
	),
	"nextSynth": Action(_("switch to a different synthesizer"), _nextSynth),
	"punctuationMore": Action(_("read more punctuation"), lambda large: _stepPunctuation(True, large)),
	"punctuationLess": Action(_("read less punctuation"), lambda large: _stepPunctuation(False, large)),
	"punctuationNone": Action(
		_("read no punctuation at all"),
		lambda large: _setPunctuation(characterProcessing.SymbolLevel.NONE.value),
	),
	"punctuationAll": Action(
		_("read all punctuation"),
		lambda large: _setPunctuation(characterProcessing.SymbolLevel.ALL.value),
	),
	**_pair(
		"capPitchHigher",
		"capPitchLower",
		_("raise the pitch more for capitals"),
		_("raise the pitch less for capitals"),
		lambda up, large: _stepConf(("speech", SYNTH, "capPitchChange"), CAP_PITCH, up, large, -100, 100),
	),
	**_confPair(
		"sayCapOn",
		"sayCapOff",
		("speech", SYNTH, "sayCapForCapitals"),
		SAY_CAP,
		_("say cap before capitals"),
		_("stop saying cap before capitals"),
	),
	**_confPair(
		"beepForCapsOn",
		"beepForCapsOff",
		("speech", SYNTH, "beepForCapitals"),
		BEEP_CAPS,
		_("beep for capitals"),
		_("stop beeping for capitals"),
	),
	**_confPair(
		"spellingOn",
		"spellingOff",
		("speech", SYNTH, "useSpellingFunctionality"),
		SPELLING,
		_("use the voice's spelling"),
		_("stop using the voice's spelling"),
	),
	**_confPair(
		"delayedDescriptionsOn",
		"delayedDescriptionsOff",
		("speech", "delayedCharacterDescriptions"),
		DELAYED,
		_("describe characters after a pause"),
		_("stop describing characters after a pause"),
	),
	**_pair(
		"emojiOn",
		"emojiOff",
		_("read emoji and symbols by name"),
		_("stop reading emoji by name"),
		lambda on, large: _toggleListMember("symbolDictionaries", "cldr", EMOJI, on, _refreshSymbols),
	),
	**_confPair(
		"autoLanguageOn",
		"autoLanguageOff",
		("speech", "autoLanguageSwitching"),
		AUTO_LANGUAGE,
		_("switch language automatically"),
		_("stop switching language automatically"),
	),
	**_confPair(
		"autoDialectOn",
		"autoDialectOff",
		("speech", "autoDialectSwitching"),
		AUTO_DIALECT,
		_("switch dialect automatically"),
		_("stop switching dialect automatically"),
	),
	**_confPair(
		"reportLanguageOn",
		"reportLanguageOff",
		("speech", "reportLanguage"),
		REPORT_LANGUAGE,
		_("announce language changes"),
		_("stop announcing language changes"),
	),
	"unsupportedLanguageSpeak": Action(
		_("say so when the voice can't speak a language"),
		lambda large: _setUnsupportedLanguage("speech"),
	),
	"unsupportedLanguageBeep": Action(
		_("beep when the voice can't speak a language"),
		lambda large: _setUnsupportedLanguage("beep"),
	),
	"unsupportedLanguageOff": Action(
		_("say nothing when the voice can't speak a language"),
		lambda large: _setUnsupportedLanguage("off"),
	),
	**_confPair(
		"trustVoiceLanguageOn",
		"trustVoiceLanguageOff",
		("speech", "trustVoiceLanguage"),
		TRUST_LANGUAGE,
		_("use the voice's language for symbols"),
		_("use NVDA's language for symbols"),
	),
	**_pair(
		"normalizationOn",
		"normalizationOff",
		_("turn Unicode normalization on"),
		_("turn Unicode normalization off"),
		lambda on, large: _toggleFlag(("speech", "unicodeNormalization"), NORMALIZATION, on),
	),
	**_confPair(
		"reportNormalizedOn",
		"reportNormalizedOff",
		("speech", "reportNormalizedForCharacterNavigation"),
		REPORT_NORMALIZED,
		_("say normalized when moving by character"),
		_("stop saying normalized"),
	),
	**_pair(
		"userDictionaryOn",
		"userDictionaryOff",
		_("use your default speech dictionary"),
		_("stop using your default speech dictionary"),
		lambda on, large: _toggleListMember("speechDictionaries", "default", USER_DICT, on),
	),
	**_pair(
		"voiceDictionaryOn",
		"voiceDictionaryOff",
		_("use the voice's speech dictionary"),
		_("stop using the voice's speech dictionary"),
		lambda on, large: _toggleListMember("speechDictionaries", "voice", VOICE_DICT, on),
	),
	**_pair(
		"typedCharactersOn",
		"typedCharactersOff",
		_("speak characters as you type"),
		_("stop speaking characters as you type"),
		lambda on, large: _changeTypingEcho("speakTypedCharacters", TYPED_CHARACTERS, on),
	),
	**_pair(
		"typedWordsOn",
		"typedWordsOff",
		_("speak words as you type"),
		_("stop speaking words as you type"),
		lambda on, large: _changeTypingEcho("speakTypedWords", TYPED_WORDS, on),
	),
	**_confPair(
		"commandKeysOn",
		"commandKeysOff",
		("keyboard", "speakCommandKeys"),
		COMMAND_KEYS,
		_("speak the keys you press"),
		_("stop speaking the keys you press"),
	),
}


def currentSettings() -> list[str]:
	"""A few of the settings as they are now, for gent's overview."""
	lines = []
	synth = getSynth()
	if synth is not None:
		# Translators: In gent's overview. {name} is the synthesizer, e.g. "eSpeak NG".
		lines.append(_("Synthesizer: {name}.").format(name=synth.description))
		if synth.isSupported("voice"):
			voice = synth.availableVoices.get(synth.voice)
			if voice is not None:
				lines.append(f"{VOICE}: {voice.displayName}.")
		for settingId, label in (("rate", RATE), ("pitch", PITCH), ("volume", VOLUME)):
			if synth.isSupported(settingId):
				# Translators: In gent's overview. {setting} is e.g. "Pitch", {value} a number from 0 to 100.
				lines.append(
					_("{setting}: {value} out of 100.").format(setting=label, value=getattr(synth, settingId))
				)
	lines.append(symbolLevelMessage(config.conf["speech"]["symbolLevel"]) + ".")
	keyboard = config.conf["keyboard"]
	lines.append(f"{TYPED_CHARACTERS}: {TypingEcho(keyboard['speakTypedCharacters']).displayString}.")
	lines.append(f"{TYPED_WORDS}: {TypingEcho(keyboard['speakTypedWords']).displayString}.")
	lines.append(f"{COMMAND_KEYS}: {_onOff(keyboard['speakCommandKeys'])}.")
	return lines
