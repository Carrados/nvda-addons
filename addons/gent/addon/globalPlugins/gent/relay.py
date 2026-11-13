# Talks to the gent relay, which asks Jev which action the user means.
# No NVDA imports, so it can be tested outside NVDA.

import json
import urllib.error
import urllib.request

RELAY = "https://nvda-gent-relay.charlijotyrer.workers.dev"
RELAY_URL = RELAY + "/v1/decide"
RECORDINGS_URL = RELAY + "/v1/recordings"
ACTIONS_VERSION = "3"
# Cloudflare blocks Python's default user agent, so gent always sends its own.
USER_AGENT = "nvda-gent/{version}"


class RelayError(Exception):
	"""A failure the user should hear about. The message is from the relay or is a plain fallback."""


def decide(installId: str, text: str, recent: list[str], version: str, timeout: float = 8) -> dict:
	"""Returns the relay's answer: action, confidence, alternatives and size."""
	body = {"install_id": installId, "text": text, "recent": recent, "actions_version": ACTIONS_VERSION}
	return _post(RELAY_URL, body, version, timeout)


def shareRecording(installId: str, text: str, version: str, timeout: float = 20) -> dict:
	"""Uploads a page recording the user chose to share. Returns its link ("url") and when it is deleted ("expires")."""
	return _post(RECORDINGS_URL, {"install_id": installId, "text": text}, version, timeout)


def _post(url: str, body: dict, version: str, timeout: float) -> dict:
	request = urllib.request.Request(
		url,
		data=json.dumps(body).encode("utf-8"),
		headers={"Content-Type": "application/json", "User-Agent": USER_AGENT.format(version=version)},
	)
	try:
		with urllib.request.urlopen(request, timeout=timeout) as response:
			return json.load(response)
	except urllib.error.HTTPError as e:
		try:
			message = json.load(e)["error"]
		except (ValueError, KeyError, TypeError):
			message = f"gent's service returned an error ({e.code})."
		raise RelayError(message) from e
	except (urllib.error.URLError, TimeoutError) as e:
		raise RelayError("Couldn't reach gent's service. Check your internet connection.") from e
