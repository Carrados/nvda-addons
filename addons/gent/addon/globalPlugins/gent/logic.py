# Decisions that don't touch NVDA: when to act or ask, and how far to move a setting.
# No NVDA imports, so it can be tested outside NVDA.

# At or above this, gent acts without asking.
CONFIDENT = 0.7

# The opposite of each action. Undoing a change and asking for its opposite
# have the same effect, so Jev splitting between the two is not real doubt.
OPPOSITES = {
	"speechRateFaster": "speechRateSlower",
	"speechRateSlower": "speechRateFaster",
	"punctuationMore": "punctuationLess",
	"punctuationLess": "punctuationMore",
	"typedCharactersOn": "typedCharactersOff",
	"typedCharactersOff": "typedCharactersOn",
	"typedWordsOn": "typedWordsOff",
	"typedWordsOff": "typedWordsOn",
}


def plan(answer: dict, lastAction: str | None) -> tuple[str, str]:
	"""Returns ("act", action), ("ask", action) or ("none", "none")."""
	action = answer["action"]
	if action == "none":
		return ("none", "none")
	if answer["confidence"] >= CONFIDENT:
		return ("act", action)
	if lastAction is not None:
		sameEffect = {"undo", OPPOSITES[lastAction]}
		top = answer["alternatives"][:2]
		if {a["action"] for a in top} == sameEffect and sum(a["probability"] for a in top) >= CONFIDENT:
			return ("act", action)
	return ("ask", action)


def stepRate(rate: int, faster: bool, large: bool) -> int:
	"""NVDA rates run from 0 to 100."""
	step = 25 if large else 10
	return max(0, min(100, rate + (step if faster else -step)))


def stepLevel(levels: list[int], current: int, more: bool, large: bool) -> int:
	"""Moves along an ordered list of levels. An unknown current level counts as the nearest one."""
	index = min(range(len(levels)), key=lambda i: abs(levels[i] - current))
	index += (2 if large else 1) * (1 if more else -1)
	return levels[max(0, min(len(levels) - 1, index))]
