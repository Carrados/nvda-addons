// The gent question: the actions Jev may choose from, and the request and
// response shapes. Kept free of Workers APIs so it can be tested with node --test.

export const ACTIONS_VERSION = "1";

// Each action is a Choice option. Descriptions are what Jev reads, so they say
// what the user wants to happen, not what NVDA calls the setting.
export const ACTIONS = {
	speechRateFaster: "Make speech faster.",
	speechRateSlower: "Make speech slower.",
	punctuationMore: "Read out more punctuation and symbols.",
	punctuationLess: "Read out less punctuation and fewer symbols.",
	typedCharactersOn: "Speak each character as it is typed.",
	typedCharactersOff: "Stop speaking each character as it is typed.",
	typedWordsOn: "Speak each word after it is typed.",
	typedWordsOff: "Stop speaking each word after it is typed.",
	undo: "Undo the last change, or put things back to how they were before.",
	none: "None of the above: the request is about something else, is unclear, or asks for something not listed.",
};

const SIZES = {
	small: "A small change, or no amount was mentioned, for example \"a bit faster\", \"slightly quieter\" or just \"faster\".",
	large: "A big change, for example \"much faster\", \"a lot quieter\" or \"way too slow\".",
};

const MAX_TEXT = 300;
const MAX_RECENT = 5;
const INSTALL_ID = /^[A-Za-z0-9-]{8,64}$/;

export class BadRequest extends Error {}

// Validates the add-on's request body and returns the parts the relay uses.
export function parseDecideBody(body) {
	if (typeof body !== "object" || body === null) throw new BadRequest("Body must be a JSON object.");
	const { install_id: installId, text, recent = [], actions_version: version } = body;
	if (version !== ACTIONS_VERSION) throw new BadRequest(`actions_version must be "${ACTIONS_VERSION}".`);
	if (typeof installId !== "string" || !INSTALL_ID.test(installId)) throw new BadRequest("Invalid install_id.");
	if (typeof text !== "string" || !text.trim() || text.length > MAX_TEXT) {
		throw new BadRequest(`text must be 1 to ${MAX_TEXT} characters.`);
	}
	if (!Array.isArray(recent) || recent.length > MAX_RECENT || !recent.every((a) => a in ACTIONS && a !== "none")) {
		throw new BadRequest(`recent must be up to ${MAX_RECENT} action names.`);
	}
	return { installId, text: text.trim(), recent };
}

// Builds the POST body for https://api.typesafe.ai/v1/systemone.
// Both questions run in parallel; the add-on uses size only for adjustable settings.
export function buildJevRequest({ text, recent }, model) {
	return {
		model,
		state: { request: text, recent_changes: recent },
		questions: {
			action: {
				type: "choice",
				instructions:
					"A screen reader user typed `request` to NVDA, asking it to change how it behaves. " +
					"`recent_changes` lists changes just made, most recent first; use it to resolve words like " +
					"\"now\", \"that\", \"again\" or \"how it was before\". Which action does the user want?",
				criteria: ACTIONS,
			},
			size: {
				type: "choice",
				instructions: "If `request` asks for a setting to change, how big a change does the user want?",
				criteria: SIZES,
			},
		},
	};
}

// Turns Jev's response into what the add-on needs: the action, how sure Jev is,
// the runners-up for "did you mean...?", and the size of change.
export function readJevAnswer(jev) {
	const { action, size } = jev.answers;
	const alternatives = Object.entries(action.probabilities)
		.sort(([, a], [, b]) => b - a)
		.slice(0, 3)
		.map(([name, probability]) => ({ action: name, probability }));
	return {
		actions_version: ACTIONS_VERSION,
		action: action.choice,
		confidence: action.confidence,
		alternatives,
		size: size.choice,
	};
}
