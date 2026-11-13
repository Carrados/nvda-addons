// Page recordings: what NVDA said on a web page, which gent uploads only when the user says yes.
// Each one gets an unguessable link and is deleted after a week.
// Kept free of Workers APIs so it can be tested with node --test.

import { BadRequest } from "./gent.js";

// A long page read in full, plus a few hundred Tab presses, fits comfortably.
export const MAX_RECORDING = 512 * 1024;
export const KEEP_SECONDS = 7 * 24 * 60 * 60;
const INSTALL_ID = /^[A-Za-z0-9-]{8,64}$/;
// 128 random bits, as 32 lowercase hex characters.
export const RECORDING_ID = /^[0-9a-f]{32}$/;

// Validates the add-on's upload body and returns the parts the relay keeps.
export function parseRecordingBody(body) {
	if (typeof body !== "object" || body === null) throw new BadRequest("Body must be a JSON object.");
	const { install_id: installId, text } = body;
	if (typeof installId !== "string" || !INSTALL_ID.test(installId)) throw new BadRequest("Invalid install_id.");
	if (typeof text !== "string" || !text.trim()) throw new BadRequest("text must not be empty.");
	if (new TextEncoder().encode(text).length > MAX_RECORDING) {
		throw new BadRequest(`The recording is over ${MAX_RECORDING / 1024} KB.`);
	}
	return { installId, text };
}

export function newRecordingId(randomValues = (a) => crypto.getRandomValues(a)) {
	return Array.from(randomValues(new Uint8Array(16)), (b) => b.toString(16).padStart(2, "0")).join("");
}

// Where the recording can be read: /r/<id> on the relay's own address.
export function recordingUrl(requestUrl, id) {
	return new URL(`/r/${id}`, requestUrl).toString();
}
