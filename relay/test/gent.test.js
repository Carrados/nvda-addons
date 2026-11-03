import assert from "node:assert/strict";
import { test } from "node:test";
import { ACTIONS, BadRequest, buildJevRequest, parseDecideBody, readJevAnswer } from "../src/gent.js";

const valid = { install_id: "abcd1234-ef56", text: " Make it talk a bit faster ", recent: [], actions_version: "1" };

test("accepts a valid request and trims the text", () => {
	assert.deepEqual(parseDecideBody(valid), { installId: "abcd1234-ef56", text: "Make it talk a bit faster", recent: [] });
});

test("rejects bad requests", () => {
	for (const body of [
		null,
		{ ...valid, actions_version: "2" },
		{ ...valid, install_id: "x" },
		{ ...valid, text: "   " },
		{ ...valid, text: "a".repeat(301) },
		{ ...valid, recent: ["deleteEverything"] },
		{ ...valid, recent: ["none"] },
		{ ...valid, recent: Array(6).fill("undo") },
	]) {
		assert.throws(() => parseDecideBody(body), BadRequest);
	}
});

test("builds a Jev request offering every action", () => {
	const req = buildJevRequest({ text: "faster", recent: ["speechRateSlower"] }, "jev-latest");
	assert.equal(req.model, "jev-latest");
	assert.deepEqual(req.state, { request: "faster", recent_changes: ["speechRateSlower"] });
	assert.deepEqual(Object.keys(req.questions.action.criteria), Object.keys(ACTIONS));
	assert.equal(req.questions.action.type, "choice");
});

test("reads Jev's answer with the top three alternatives", () => {
	const answer = readJevAnswer({
		answers: {
			action: {
				choice: "punctuationLess",
				confidence: 0.8,
				probabilities: { punctuationLess: 0.85, punctuationMore: 0.05, none: 0.07, undo: 0.03 },
			},
			size: { choice: "small", confidence: 0.9, probabilities: { small: 0.9, large: 0.1 } },
		},
	});
	assert.equal(answer.action, "punctuationLess");
	assert.deepEqual(answer.alternatives.map((a) => a.action), ["punctuationLess", "none", "punctuationMore"]);
	assert.equal(answer.size, "small");
});
