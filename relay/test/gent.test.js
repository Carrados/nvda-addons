import assert from "node:assert/strict";
import { test } from "node:test";
import { ACTIONS_BY_VERSION, BadRequest, buildJevRequest, parseDecideBody, readJevAnswer } from "../src/gent.js";

const valid = { install_id: "abcd1234-ef56", text: " Make it talk a bit faster ", recent: [], actions_version: "2" };

test("accepts a valid request and trims the text", () => {
	assert.deepEqual(parseDecideBody(valid), {
		installId: "abcd1234-ef56",
		text: "Make it talk a bit faster",
		recent: [],
		version: "2",
	});
});

test("still accepts version 1 add-ons", () => {
	assert.equal(parseDecideBody({ ...valid, actions_version: "1" }).version, "1");
});

test("rejects bad requests", () => {
	for (const body of [
		null,
		{ ...valid, actions_version: "3" },
		{ ...valid, actions_version: "toString" },
		{ ...valid, install_id: "x" },
		{ ...valid, text: "   " },
		{ ...valid, text: "a".repeat(301) },
		{ ...valid, recent: ["deleteEverything"] },
		{ ...valid, recent: ["none"] },
		{ ...valid, recent: ["help"] },
		{ ...valid, recent: Array(6).fill("speechRateFaster") },
	]) {
		assert.throws(() => parseDecideBody(body), BadRequest);
	}
});

test("only version 2 offers help", () => {
	const v1 = buildJevRequest({ text: "help", recent: [], version: "1" }, "jev-latest");
	const v2 = buildJevRequest({ text: "help", recent: [], version: "2" }, "jev-latest");
	assert.ok(!("help" in v1.questions.action.criteria));
	assert.deepEqual(Object.keys(v2.questions.action.criteria), Object.keys(ACTIONS_BY_VERSION[2]));
	assert.ok("help" in v2.questions.action.criteria);
});

test("builds a Jev request with recent changes as state", () => {
	const req = buildJevRequest({ text: "faster", recent: ["speechRateSlower"], version: "2" }, "jev-latest");
	assert.equal(req.model, "jev-latest");
	assert.deepEqual(req.state, { request: "faster", recent_changes: ["speechRateSlower"] });
	assert.equal(req.questions.action.type, "choice");
});

test("reads Jev's answer with the top three alternatives", () => {
	const answer = readJevAnswer(
		{
			answers: {
				action: {
					choice: "punctuationLess",
					confidence: 0.8,
					probabilities: { punctuationLess: 0.85, punctuationMore: 0.05, none: 0.07, undo: 0.03 },
				},
				size: { choice: "small", confidence: 0.9, probabilities: { small: 0.9, large: 0.1 } },
			},
		},
		"2",
	);
	assert.equal(answer.action, "punctuationLess");
	assert.equal(answer.actions_version, "2");
	assert.deepEqual(answer.alternatives.map((a) => a.action), ["punctuationLess", "none", "punctuationMore"]);
	assert.equal(answer.size, "small");
});
