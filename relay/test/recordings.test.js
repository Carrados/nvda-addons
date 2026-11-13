import assert from "node:assert/strict";
import { test } from "node:test";
import { BadRequest } from "../src/gent.js";
import {
	MAX_RECORDING,
	RECORDING_ID,
	newRecordingId,
	parseRecordingBody,
	recordingUrl,
} from "../src/recordings.js";

const valid = { install_id: "abcd1234-ef56", text: "gent page recording\nTab 1: Search, edit" };

test("accepts a recording", () => {
	assert.deepEqual(parseRecordingBody(valid), { installId: "abcd1234-ef56", text: valid.text });
});

test("rejects bad recordings", () => {
	for (const body of [
		null,
		{ ...valid, install_id: "x" },
		{ ...valid, text: "   " },
		{ ...valid, text: 42 },
		{ ...valid, text: "a".repeat(MAX_RECORDING + 1) },
		// Counted in bytes: 3 bytes each in UTF-8.
		{ ...valid, text: "€".repeat(MAX_RECORDING / 3 + 1) },
	]) {
		assert.throws(() => parseRecordingBody(body), BadRequest);
	}
});

test("ids are 128 random bits in hex", () => {
	const id = newRecordingId();
	assert.match(id, RECORDING_ID);
	assert.notEqual(id, newRecordingId());
	assert.equal(newRecordingId((a) => a.fill(255)), "f".repeat(32));
});

test("links point at the relay's own address", () => {
	assert.equal(
		recordingUrl("https://nvda-gent-relay.example.workers.dev/v1/recordings", "0".repeat(32)),
		`https://nvda-gent-relay.example.workers.dev/r/${"0".repeat(32)}`,
	);
});

test("ids that aren't ours are refused before any lookup", () => {
	for (const id of ["", "../v1/decide", "ABCDEF".repeat(6), "0".repeat(31)]) assert.doesNotMatch(id, RECORDING_ID);
});
