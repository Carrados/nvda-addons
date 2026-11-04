// The gent question: the actions Jev may choose from, and the request and
// response shapes. Kept free of Workers APIs so it can be tested with node --test.

// Each action is a Choice option. Descriptions are what Jev reads, so they say
// what the user wants to happen, not what NVDA calls the setting.
const ACTIONS_V1 = {
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

const HELP = "Asks what gent can do, what can be changed, or for help using gent.";

// Version 3: everything on NVDA 2026.2's Speech settings panel, plus typing echo and command keys.
const ACTIONS_V3 = {
	speechRateFaster: "Make speech faster.",
	speechRateSlower: "Make speech slower.",
	rateBoostOn: "Turn on rate boost, for speech much faster than the normal maximum.",
	rateBoostOff: "Turn off rate boost.",
	pitchHigher: "Make the voice higher pitched, for example because it sounds too deep or too low.",
	pitchLower: "Make the voice lower or deeper, for example because it sounds too high, squeaky or like a chipmunk.",
	volumeLouder: "Make speech louder.",
	volumeQuieter: "Make speech quieter.",
	inflectionMore: "Give the voice more inflection or expression, so it sounds less flat.",
	inflectionLess: "Give the voice less inflection, so it sounds flatter and more even.",
	nextVoice: "Switch to a different voice, or the next voice.",
	previousVoice: "Go back to the previous voice in the list.",
	nextVariant: "Switch to a different variant of the current voice.",
	previousVariant: "Go back to the previous variant of the current voice.",
	nextSynth: "Switch to a different speech synthesizer or speech engine.",
	punctuationMore: "Read out more punctuation and symbols.",
	punctuationLess: "Read out less punctuation and fewer symbols.",
	punctuationNone: "Read no punctuation or symbols at all.",
	punctuationAll: "Read out all punctuation and every symbol.",
	capPitchHigher: "Raise the voice's pitch more for capital letters, so capitals stand out more.",
	capPitchLower: "Raise the voice's pitch less for capital letters, so capitals stand out less.",
	sayCapOn: "Say \"cap\" before capital letters.",
	sayCapOff: "Stop saying \"cap\" before capital letters.",
	beepForCapsOn: "Beep for capital letters.",
	beepForCapsOff: "Stop beeping for capital letters.",
	spellingOn: "Use the voice's own spelling when spelling out words.",
	spellingOff: "Stop using the voice's own spelling when spelling out words.",
	delayedDescriptionsOn: "After a pause on a character, describe it, for example \"a, alpha\".",
	delayedDescriptionsOff: "Stop describing characters after a pause.",
	emojiOn: "Read emoji and symbols by name, using Unicode Consortium data.",
	emojiOff: "Stop reading emoji and Unicode symbols by name.",
	autoLanguageOn: "Switch the voice's language automatically when the text changes language, for example reading French text with a French voice.",
	autoLanguageOff: "Stop switching the voice's language or accent automatically when the text is in another language, such as French.",
	autoDialectOn: "Switch between dialects of the same language automatically, for example between British and American English.",
	autoDialectOff: "Stop switching between dialects of the same language, such as British and American English.",
	reportLanguageOn: "Announce when the language changes while reading.",
	reportLanguageOff: "Stop announcing language changes while reading.",
	unsupportedLanguageSpeak: "Say so when the voice can't speak a language in the text.",
	unsupportedLanguageBeep: "Beep when the voice can't speak a language in the text.",
	unsupportedLanguageOff: "Say nothing when the voice can't speak a language in the text.",
	trustVoiceLanguageOn: "Use the voice's language when reading characters and symbols.",
	trustVoiceLanguageOff: "Use NVDA's interface language, not the voice's, when reading characters and symbols.",
	normalizationOn: "Turn on Unicode normalization, so unusual or decorated letters are read as plain letters.",
	normalizationOff: "Turn off Unicode normalization.",
	reportNormalizedOn: "Say \"normalized\" when moving onto a character that was normalized.",
	reportNormalizedOff: "Stop saying \"normalized\" when moving by character.",
	userDictionaryOn: "Use my own pronunciation dictionary, the default speech dictionary that applies to every voice.",
	userDictionaryOff: "Stop using my own pronunciation dictionary, the default speech dictionary that applies to every voice.",
	voiceDictionaryOn: "Use the separate speech dictionary that belongs only to the current voice.",
	voiceDictionaryOff: "Stop using the separate speech dictionary that belongs only to the current voice.",
	typedCharactersOn: "Speak each character as it is typed.",
	typedCharactersOff: "Stop speaking each character as it is typed.",
	typedWordsOn: "Speak each word after it is typed.",
	typedWordsOff: "Stop speaking each word after it is typed.",
	commandKeysOn: "Tell me which keys I press, including shortcuts like Control+C and keys like the arrows, Tab and Escape.",
	commandKeysOff: "Stop telling me which keys and shortcuts I press.",
	undo: "Undo the last change, or put things back to how they were before.",
	help: HELP,
	none: "None of the above: the request is about something else, is unclear, or asks for something not listed.",
};

// Add-ons send the version they understand, so older installs never get an action they can't handle.
export const ACTIONS_BY_VERSION = {
	1: ACTIONS_V1,
	2: { ...ACTIONS_V1, help: HELP },
	3: ACTIONS_V3,
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
	const actions = Object.hasOwn(ACTIONS_BY_VERSION, version) ? ACTIONS_BY_VERSION[version] : null;
	if (!actions) throw new BadRequest(`actions_version must be one of ${Object.keys(ACTIONS_BY_VERSION).join(", ")}.`);
	if (typeof installId !== "string" || !INSTALL_ID.test(installId)) throw new BadRequest("Invalid install_id.");
	if (typeof text !== "string" || !text.trim() || text.length > MAX_TEXT) {
		throw new BadRequest(`text must be 1 to ${MAX_TEXT} characters.`);
	}
	const isChange = (a) => Object.hasOwn(actions, a) && !["none", "undo", "help"].includes(a);
	if (!Array.isArray(recent) || recent.length > MAX_RECENT || !recent.every(isChange)) {
		throw new BadRequest(`recent must be up to ${MAX_RECENT} action names.`);
	}
	return { installId, text: text.trim(), recent, version };
}

// Builds the POST body for https://api.typesafe.ai/v1/systemone.
// Both questions run in parallel; the add-on uses size only for adjustable settings.
export function buildJevRequest({ text, recent, version }, model) {
	return {
		model,
		state: { request: text, recent_changes: recent },
		questions: {
			action: {
				type: "choice",
				instructions:
					"A screen reader user typed `request` to gent, a helper inside the NVDA screen reader that " +
					"changes NVDA's settings when asked in plain words. " +
					"`recent_changes` lists changes just made, most recent first; use it to resolve words like " +
					"\"now\", \"that\", \"again\" or \"how it was before\". Which action does the user want?",
				criteria: ACTIONS_BY_VERSION[version],
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
export function readJevAnswer(jev, version) {
	const { action, size } = jev.answers;
	const alternatives = Object.entries(action.probabilities)
		.sort(([, a], [, b]) => b - a)
		.slice(0, 3)
		.map(([name, probability]) => ({ action: name, probability }));
	return {
		actions_version: version,
		action: action.choice,
		confidence: action.confidence,
		alternatives,
		size: size.choice,
	};
}
