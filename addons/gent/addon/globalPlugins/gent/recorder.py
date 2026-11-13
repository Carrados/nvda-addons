# gent's page recorder: writes down what NVDA says on a web page, silently, so someone can check it.
# It reads the page as Say All would, then presses Tab from the top until focus leaves the page.
# recording.py turns that into a transcript.

import time
from collections.abc import Callable

import addonHandler
import api
import buildVersion
import controlTypes
import core
import textInfos
from keyboardHandler import KeyboardInputGesture
from logHandler import log
from speech.extensions import filter_speechSequence
from speech.speech import SpeakTextInfoState, getTextInfoSpeech

from . import recording
from .recording import Step

addonHandler.initTranslation()

# Long enough for most pages to answer a Tab and NVDA to speak about it.
_WAIT_MS = 450
# A little more time when NVDA was still talking at the last check.
_SETTLE_MS = 250
_QUIET_SECONDS = 0.2
_MAX_TABS = 300
_MAX_CHUNKS = 5000


class Recorder:
	"""One recording of one page. Call start(), then it finishes by itself and calls done(text)."""

	def __init__(self, doc, done: Callable[[str], None]):
		self.doc = doc
		self.done = done
		self.running = False
		self._said: list[str] = []
		self._lastSpeech = 0.0
		self._steps: list[Step] = []
		self._first = None
		self._reading: list[str] = []

	def start(self) -> None:
		try:
			self._start()
		except Exception:
			log.exception("gent: starting a page recording failed")
			# Translators: Why a gent page recording ended.
			self.stop(_("Something went wrong starting the recording."))

	def _start(self) -> None:
		self.running = True
		self._title = ""
		self._url = ""
		# Mute from here: everything NVDA says goes into the recording instead.
		filter_speechSequence.register(self._capture)
		self._title = self.doc.rootNVDAObject.name or ""
		self._url = _safe(lambda: self.doc.documentConstantIdentifier) or ""
		try:
			self._reading = self._read()
		except Exception:
			log.exception("gent: reading the page for a recording failed")
			self._reading = []
		self.doc.passThrough = False
		self.doc.selection = self.doc.makeTextInfo(textInfos.POSITION_FIRST)
		self._said.clear()
		self.doc.rootNVDAObject.setFocus()
		core.callLater(_WAIT_MS, self._step)

	def stop(self, reason: str) -> None:
		"""Ends the recording, unmutes NVDA and hands over the transcript."""
		if not self.running:
			return
		self.running = False
		# Never leave NVDA muted.
		filter_speechSequence.unregister(self._capture)
		text = recording.transcript(
			title=self._title,
			url=self._url,
			when=time.strftime("%Y-%m-%d %H:%M"),
			about=f"NVDA {buildVersion.version}, {_appName(self.doc)}",
			reading=self._reading,
			steps=self._steps,
			stopped=reason,
		)
		self.done(text)

	def _capture(self, sequence):
		text = recording.speechText(sequence)
		if text:
			self._said.append(text)
			self._lastSpeech = time.monotonic()
		# Nothing is spoken while recording.
		return []

	def _read(self) -> list[str]:
		"""What Say All would say from the top of the page, worked out without speaking it."""
		state = SpeakTextInfoState(self.doc)
		reader = self.doc.makeTextInfo(textInfos.POSITION_FIRST)
		reader.collapse()
		lines = []
		for _ in range(_MAX_CHUNKS):
			if reader.move(textInfos.UNIT_READINGCHUNK, 1, endPoint="end") <= 0:
				break
			sequences = getTextInfoSpeech(
				reader,
				useCache=state,
				unit=textInfos.UNIT_READINGCHUNK,
				reason=controlTypes.OutputReason.SAYALL,
			)
			text = recording.speechText(list(sequences))
			if text:
				lines.append(text)
			reader.collapse(end=True)
		return lines

	def _step(self) -> None:
		if not self.running:
			return
		try:
			self._nextStep()
		except Exception:
			log.exception("gent: a page recording step failed")
			# Translators: Why a gent page recording ended.
			self.stop(_("Something went wrong partway through, so the recording stopped there."))

	def _nextStep(self) -> None:
		"""Writes down what the last key made NVDA say, then presses Tab again or stops."""
		if time.monotonic() - self._lastSpeech < _QUIET_SECONDS:
			core.callLater(_SETTLE_MS, self._step)
			return
		said = " ".join(self._said)
		self._said.clear()
		# Translators: In a gent page recording, the step before any Tab is pressed.
		key = f"Tab {len(self._steps)}" if self._steps else _("Start, top of the page")
		self._steps.append(Step(key, said))
		focus = api.getFocusObject()
		if self._steps[1:] and focus.treeInterceptor is not self.doc:
			# Translators: Why a gent page recording ended.
			self.stop(_("Tab left the page."))
			return
		if len(self._steps) == 2:
			self._first = focus
		elif len(self._steps) > 2 and _same(focus, self._first):
			# Translators: Why a gent page recording ended.
			self.stop(_("Tab came back round to the first item."))
			return
		if len(self._steps) > _MAX_TABS:
			# Translators: Why a gent page recording ended.
			self.stop(_("Stopped after {count} presses of Tab.").format(count=_MAX_TABS))
			return
		KeyboardInputGesture.fromName("tab").send()
		core.callLater(_WAIT_MS, self._step)


def _same(a, b) -> bool:
	try:
		return a is not None and b is not None and a == b
	except Exception:  # noqa: BLE001
		return False


def _safe(get):
	try:
		return get()
	except Exception:  # noqa: BLE001
		log.debugWarning("gent: couldn't read a page property for a recording", exc_info=True)
		return None


def _appName(doc) -> str:
	app = _safe(lambda: doc.rootNVDAObject.appModule)
	name = getattr(app, "productName", None) or getattr(app, "appName", None) or ""
	version = getattr(app, "productVersion", None) or ""
	return f"{name} {version}".strip() or "a web browser"
