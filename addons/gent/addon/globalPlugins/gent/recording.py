# Turns what NVDA said on a web page into a transcript someone can read and check.
# No NVDA imports, so it can be tested outside NVDA. recorder.py does the recording.

from dataclasses import dataclass


@dataclass
class Step:
	# The key gent pressed, such as "Tab 3", or "Start" for moving to the top of the page.
	key: str
	# Everything NVDA said after that key, in order.
	said: str


def speechText(sequence) -> str:
	"""The words in an NVDA speech sequence. Commands such as pitch changes and pauses are left out."""
	words: list[str] = []

	def walk(items) -> None:
		for item in items:
			if isinstance(item, str):
				if item.strip():
					words.append(item.strip())
			elif isinstance(item, (list, tuple)):
				walk(item)

	walk(sequence)
	return " ".join(" ".join(words).split())


def transcript(
	title: str,
	url: str,
	when: str,
	about: str,
	reading: list[str],
	steps: list[Step],
	stopped: str,
) -> str:
	"""Plain text, one thing NVDA said per line, in sections someone can jump between."""
	lines = [
		"gent page recording",
		f"Page: {title or '(no title)'}",
		f"Address: {url or '(unknown)'}",
		f"Recorded: {when}",
		f"With: {about}",
		"",
		f"== Reading the page, as Say All would ({len(reading)} lines) ==",
		"",
	]
	lines.extend(reading or ["(Nothing was read.)"])
	lines += ["", f"== Pressing Tab from the top ({len(steps) - 1 if steps else 0} presses) ==", ""]
	for step in steps:
		lines.append(f"{step.key}: {step.said or '(said nothing)'}")
	lines += ["", f"Stopped: {stopped}", ""]
	return "\n".join(lines)
