"""Runs every gent action, and its undo, against stand-ins for NVDA's modules.

The stand-ins copy how NVDA 2026.2 stores these settings (see settings.py), so this catches
mistakes in gent's code. It can't prove NVDA itself behaves the same: that needs a real run.
Run from the repo root: python -m unittest discover addons/gent/tests
"""

import builtins
import enum
import sys
import types
import unittest
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[1] / "addon" / "globalPlugins"


class BoolFlag(enum.Enum):
	DEFAULT = "default"
	ENABLED = "enabled"
	DISABLED = "disabled"


class FeatureFlag:
	"""Like NVDA's: truthy when enabled, with DEFAULT behaving as behaviorOfDefault."""

	def __init__(self, name: str, behaviorOfDefault: str = "ENABLED"):
		self.value = BoolFlag[name]
		self._default = behaviorOfDefault

	def __bool__(self):
		name = self._default if self.value is BoolFlag.DEFAULT else self.value.name
		return name == "ENABLED"


class Section(dict):
	"""A config section. Feature flags are saved by name and read back as flags, as in NVDA."""

	FLAGS = {"unicodeNormalization"}

	def __setitem__(self, key, value):
		if key in self.FLAGS and isinstance(value, str):
			value = FeatureFlag(value)
		super().__setitem__(key, value)


class SymbolLevel(enum.IntEnum):
	NONE = 0
	SOME = 100
	MOST = 200
	ALL = 300
	CHAR = 1000


class TypingEcho(enum.IntEnum):
	OFF = 0
	EDIT_CONTROLS = 1
	ALWAYS = 2

	@property
	def displayString(self):
		return self.name.lower()


class Info:
	def __init__(self, id, displayName):
		self.id, self.displayName = id, displayName


class FakeSynth:
	SUPPORTED = {"voice", "variant", "rate", "rateBoost", "pitch", "volume", "inflection"}

	def __init__(self, name, description):
		self.name, self.description = name, description
		self.voice, self.variant = "v1", "a"
		self.rate, self.pitch, self.volume, self.inflection, self.rateBoost = 50, 50, 100, 80, False
		self.availableVoices = {i: Info(i, f"Voice {i}") for i in ("v1", "v2", "v3")}
		self.availableVariants = {i: Info(i, f"Variant {i}") for i in ("a", "b")}
		self.saved = 0

	def isSupported(self, settingId):
		return settingId in self.SUPPORTED

	def saveSettings(self):
		self.saved += 1


def install_fakes():
	"""Puts stand-ins for NVDA's modules in sys.modules, and returns the shared state."""
	state = types.SimpleNamespace()
	state.synths = {
		"espeak": FakeSynth("espeak", "eSpeak NG"),
		"oneCore": FakeSynth("oneCore", "Windows OneCore voices"),
	}
	state.synth = state.synths["espeak"]
	state.symbolsCleared = 0

	def synthSection():
		# NVDA saves every setting a synth has into its section, alongside the capitals settings.
		return Section(
			capPitchChange=30,
			sayCapForCapitals=False,
			beepForCapitals=False,
			useSpellingFunctionality=True,
			voice="v1",
			variant="a",
			rate=50,
			pitch=50,
			volume=100,
			inflection=80,
			rateBoost=False,
		)

	speech = Section(
		symbolLevel=100,
		trustVoiceLanguage=True,
		reportNormalizedForCharacterNavigation=True,
		symbolDictionaries=["cldr"],
		speechDictionaries=["default", "voice"],
		autoLanguageSwitching=True,
		autoDialectSwitching=False,
		reportLanguage=False,
		reportNotSupportedLanguage="speech",
		delayedCharacterDescriptions=False,
		espeak=synthSection(),
		oneCore=synthSection(),
	)
	speech["unicodeNormalization"] = "DEFAULT"
	keyboard = Section(speakTypedCharacters=1, speakTypedWords=0, speakCommandKeys=False)
	state.conf = {"speech": speech, "keyboard": keyboard}

	def module(name, **attrs):
		m = types.ModuleType(name)
		m.__dict__.update(attrs)
		sys.modules[name] = m
		return m

	config = module("config", conf=state.conf)
	config.configFlags = module("config.configFlags", TypingEcho=TypingEcho)
	module("addonHandler", initTranslation=lambda: None)
	module(
		"characterProcessing",
		SymbolLevel=SymbolLevel,
		CONFIGURABLE_SPEECH_SYMBOL_LEVELS=(
			SymbolLevel.NONE,
			SymbolLevel.SOME,
			SymbolLevel.MOST,
			SymbolLevel.ALL,
		),
		SPEECH_SYMBOL_LEVEL_LABELS={level: level.name.lower() for level in SymbolLevel},
		clearSpeechSymbols=lambda: setattr(state, "symbolsCleared", state.symbolsCleared + 1),
	)

	def setSynth(name):
		state.synth = state.synths[name]
		state.conf["speech"]["synth"] = name
		return True

	def changeVoice(synth, voice):
		synth.voice = voice

	module(
		"synthDriverHandler",
		getSynth=lambda: state.synth,
		getSynthList=lambda: [("espeak", "eSpeak NG"), ("oneCore", "OneCore"), ("silence", "No speech")],
		setSynth=setSynth,
		changeVoice=changeVoice,
	)
	builtins._ = lambda text: text
	return state


class SettingsTests(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		cls.state = install_fakes()
		# Load settings.py as part of the gent package, without running the package's __init__,
		# which needs NVDA's interface (wx, gui).
		package = types.ModuleType("gent")
		package.__path__ = [str(PLUGIN / "gent")]
		sys.modules["gent"] = package
		import gent.settings as settings

		cls.settings = settings

	def run_action(self, name, large=False):
		return self.settings.ACTIONS[name].run(large)

	def snapshot(self):
		"""Every setting's value, plus which synth is running and its settings."""

		def plain(value):
			if isinstance(value, dict):
				return {k: plain(v) for k, v in value.items() if k != "synth"}
			if isinstance(value, FeatureFlag):
				return value.value.name
			return value

		synth = {
			k: v
			for k, v in vars(self.state.synth).items()
			if k not in ("saved", "availableVoices", "availableVariants")
		}
		return plain(self.state.conf), self.state.synth.name, synth

	def test_every_action_changes_something_and_undoes_it(self):
		for name in self.settings.ACTIONS:
			with self.subTest(action=name):
				before = self.snapshot()
				try:
					message, undo = self.run_action(name)
				except self.settings.CannotDo as e:
					# Already as asked: fine, as long as nothing changed.
					self.assertEqual(before, self.snapshot(), str(e))
					continue
				self.assertTrue(message)
				self.assertNotEqual(before, self.snapshot())
				self.assertTrue(undo())
				self.assertEqual(before, self.snapshot())

	def test_rate_steps_and_saves_to_config(self):
		message, undo = self.run_action("speechRateFaster", large=True)
		self.assertEqual(self.state.synth.rate, 75)
		self.assertEqual(self.state.conf["speech"]["espeak"]["rate"], 75)
		self.assertEqual(message, "Speech rate 75")
		undo()
		self.assertEqual(self.state.synth.rate, 50)

	def test_voice_cycles_and_wraps(self):
		message, undo = self.run_action("previousVoice")
		self.assertEqual(self.state.synth.voice, "v3")
		self.assertEqual(message, "Voice v3")
		undo()
		self.assertEqual(self.state.synth.voice, "v1")

	def test_next_synth_never_picks_silence(self):
		message, undo = self.run_action("nextSynth")
		self.assertEqual(self.state.synth.name, "oneCore")
		self.run_action("nextSynth")
		self.assertEqual(self.state.synth.name, "espeak")
		undo()

	def test_already_set_says_so(self):
		with self.assertRaises(self.settings.CannotDo) as caught:
			self.run_action("autoLanguageOn")
		self.assertIn("already on", str(caught.exception))

	def test_punctuation_none_and_all(self):
		self.run_action("punctuationNone")
		self.assertEqual(self.state.conf["speech"]["symbolLevel"], 0)
		message, undo = self.run_action("punctuationAll")
		self.assertEqual(message, "Punctuation all")
		undo()
		self.assertEqual(self.state.conf["speech"]["symbolLevel"], 0)
		self.state.conf["speech"]["symbolLevel"] = 100

	def test_emoji_clears_symbol_cache(self):
		cleared = self.state.symbolsCleared
		message, undo = self.run_action("emojiOff")
		self.assertEqual(self.state.conf["speech"]["symbolDictionaries"], [])
		self.assertEqual(self.state.symbolsCleared, cleared + 1)
		undo()
		self.assertEqual(self.state.conf["speech"]["symbolDictionaries"], ["cldr"])

	def test_normalization_default_counts_as_on(self):
		with self.assertRaises(self.settings.CannotDo):
			self.run_action("normalizationOn")
		message, undo = self.run_action("normalizationOff")
		self.assertFalse(self.state.conf["speech"]["unicodeNormalization"])
		undo()
		self.assertIs(self.state.conf["speech"]["unicodeNormalization"].value, BoolFlag.DEFAULT)

	def test_capital_settings_belong_to_the_current_synth(self):
		message, undo = self.run_action("beepForCapsOn")
		self.assertTrue(self.state.conf["speech"]["espeak"]["beepForCapitals"])
		self.assertFalse(self.state.conf["speech"]["oneCore"]["beepForCapitals"])
		undo()

	def test_every_relay_action_is_handled(self):
		relayActions = (Path(__file__).resolve().parents[3] / "relay" / "src" / "gent.js").read_text(
			encoding="utf-8"
		)
		block = relayActions.split("const ACTIONS_V3 = {")[1].split("};")[0]
		names = {line.split(":")[0].strip() for line in block.splitlines() if ":" in line}
		self.assertEqual(names - {"undo", "help", "none"}, set(self.settings.ACTIONS))


if __name__ == "__main__":
	unittest.main()
