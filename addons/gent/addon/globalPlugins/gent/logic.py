# Decisions that don't touch NVDA: when to act or ask, and how far to move a setting.
# No NVDA imports, so it can be tested outside NVDA.

# At or above this, gent acts without asking.
CONFIDENT = 0.7

# Pairs of actions that undo each other. Undoing a change and asking for its opposite
# have the same effect, so Jev splitting between the two is not real doubt.
_PAIRS = [
	("speechRateFaster", "speechRateSlower"),
	("rateBoostOn", "rateBoostOff"),
	("pitchHigher", "pitchLower"),
	("volumeLouder", "volumeQuieter"),
	("inflectionMore", "inflectionLess"),
	("nextVoice", "previousVoice"),
	("nextVariant", "previousVariant"),
	("punctuationMore", "punctuationLess"),
	("capPitchHigher", "capPitchLower"),
	("sayCapOn", "sayCapOff"),
	("beepForCapsOn", "beepForCapsOff"),
	("spellingOn", "spellingOff"),
	("delayedDescriptionsOn", "delayedDescriptionsOff"),
	("emojiOn", "emojiOff"),
	("autoLanguageOn", "autoLanguageOff"),
	("autoDialectOn", "autoDialectOff"),
	("reportLanguageOn", "reportLanguageOff"),
	("trustVoiceLanguageOn", "trustVoiceLanguageOff"),
	("normalizationOn", "normalizationOff"),
	("reportNormalizedOn", "reportNormalizedOff"),
	("userDictionaryOn", "userDictionaryOff"),
	("voiceDictionaryOn", "voiceDictionaryOff"),
	("typedCharactersOn", "typedCharactersOff"),
	("typedWordsOn", "typedWordsOff"),
	("commandKeysOn", "commandKeysOff"),
]
OPPOSITES = {a: b for a, b in _PAIRS} | {b: a for a, b in _PAIRS}


def plan(answer: dict, lastAction: str | None) -> tuple[str, str]:
	"""Returns ("act", action), ("ask", action) or ("none", "none")."""
	action = answer["action"]
	if action == "none":
		return ("none", "none")
	if answer["confidence"] >= CONFIDENT:
		return ("act", action)
	opposite = OPPOSITES.get(lastAction)
	if opposite is not None:
		sameEffect = {"undo", opposite}
		top = answer["alternatives"][:2]
		if {a["action"] for a in top} == sameEffect and sum(a["probability"] for a in top) >= CONFIDENT:
			return ("act", action)
	return ("ask", action)


def stepValue(value: int, up: bool, large: bool, low: int = 0, high: int = 100) -> int:
	"""Most voice settings run from 0 to 100. A big change moves further."""
	step = 25 if large else 10
	return max(low, min(high, value + (step if up else -step)))


def stepLevel(levels: list[int], current: int, more: bool, large: bool) -> int:
	"""Moves along an ordered list of levels. An unknown current level counts as the nearest one."""
	index = min(range(len(levels)), key=lambda i: abs(levels[i] - current))
	index += (2 if large else 1) * (1 if more else -1)
	return levels[max(0, min(len(levels) - 1, index))]
