// NVDA gent relay: holds the TypeSafe key, asks Jev the one gent question,
// and limits use per install, per IP address and per day. It never logs what users type.
// It also keeps page recordings the user chose to share, for a week, behind an unguessable link.
import { DurableObject } from "cloudflare:workers";
import { BadRequest, buildJevRequest, parseDecideBody, readJevAnswer } from "./gent.js";
import {
	KEEP_SECONDS,
	MAX_RECORDING,
	RECORDING_ID,
	newRecordingId,
	parseRecordingBody,
	recordingUrl,
} from "./recordings.js";

const JEV_URL = "https://api.typesafe.ai/v1/systemone";
const MAX_BODY = 4096;

function json(data, status = 200) {
	return Response.json(data, { status });
}

// One global counter, so the daily cap holds across all Cloudflare locations.
export class DailyCounter extends DurableObject {
	async take(day, cap) {
		const used = (await this.ctx.storage.get(day)) ?? 0;
		if (used >= cap) return false;
		await this.ctx.storage.put(day, used + 1);
		return true;
	}
}

// One page recording. Its alarm deletes it a week after it was saved.
export class Recording extends DurableObject {
	async save(text, keepSeconds) {
		await this.ctx.storage.put("text", text);
		await this.ctx.storage.setAlarm(Date.now() + keepSeconds * 1000);
	}

	async read() {
		return (await this.ctx.storage.get("text")) ?? null;
	}

	async alarm() {
		await this.ctx.storage.deleteAll();
	}
}

// Uploads allowed per day across all users.
const DAILY_RECORDINGS = 2000;

async function limited(request, env, installId) {
	const ip = request.headers.get("CF-Connecting-IP") ?? "unknown";
	const checks = [env.IP_LIMITER.limit({ key: ip })];
	if (installId) checks.push(env.INSTALL_LIMITER.limit({ key: installId }));
	return (await Promise.all(checks)).some((r) => !r.success);
}

async function saveRecording(request, env) {
	if (request.method !== "POST") return json({ error: "Use POST." }, 405);
	const raw = await request.text();
	// JSON escaping can roughly double the text, so the exact limit is checked after parsing.
	if (raw.length > MAX_RECORDING * 2 + 1024) return json({ error: "Recording too large." }, 413);
	let parsed;
	try {
		parsed = parseRecordingBody(JSON.parse(raw));
	} catch (e) {
		if (e instanceof SyntaxError) return json({ error: "Body must be JSON." }, 400);
		if (e instanceof BadRequest) return json({ error: e.message }, 400);
		throw e;
	}
	if (await limited(request, env, parsed.installId)) return json({ error: "Too many requests. Try again in a minute." }, 429);
	const day = new Date().toISOString().slice(0, 10);
	const counter = env.DAILY_COUNTER.get(env.DAILY_COUNTER.idFromName("global"));
	if (!(await counter.take(`recordings-${day}`, DAILY_RECORDINGS))) {
		return json({ error: "gent has stored as many recordings as it can today. Try again tomorrow." }, 503);
	}
	const id = newRecordingId();
	await env.RECORDINGS.get(env.RECORDINGS.idFromName(id)).save(parsed.text, KEEP_SECONDS);
	const expires = new Date(Date.now() + KEEP_SECONDS * 1000).toISOString();
	return json({ url: recordingUrl(request.url, id), expires });
}

async function readRecording(request, env, id) {
	if (request.method !== "GET") return json({ error: "Use GET." }, 405);
	if (await limited(request, env)) return json({ error: "Too many requests. Try again in a minute." }, 429);
	const text = RECORDING_ID.test(id) ? await env.RECORDINGS.get(env.RECORDINGS.idFromName(id)).read() : null;
	if (text === null) {
		return new Response("This recording doesn't exist, or it was deleted after a week.\n", {
			status: 404,
			headers: { "Content-Type": "text/plain; charset=utf-8" },
		});
	}
	return new Response(text, {
		headers: {
			"Content-Type": "text/plain; charset=utf-8",
			"Cache-Control": "no-store",
			"X-Robots-Tag": "noindex",
		},
	});
}

export default {
	async fetch(request, env) {
		const { pathname } = new URL(request.url);
		if (pathname === "/v1/recordings") return saveRecording(request, env);
		if (pathname.startsWith("/r/")) return readRecording(request, env, pathname.slice(3));
		if (pathname !== "/v1/decide") return json({ error: "Not found." }, 404);
		if (request.method !== "POST") return json({ error: "Use POST." }, 405);

		const raw = await request.text();
		if (raw.length > MAX_BODY) return json({ error: "Request too large." }, 413);
		let parsed;
		try {
			parsed = parseDecideBody(JSON.parse(raw));
		} catch (e) {
			if (e instanceof SyntaxError) return json({ error: "Body must be JSON." }, 400);
			if (e instanceof BadRequest) return json({ error: e.message }, 400);
			throw e;
		}

		const ip = request.headers.get("CF-Connecting-IP") ?? "unknown";
		const [byInstall, byIp] = await Promise.all([
			env.INSTALL_LIMITER.limit({ key: parsed.installId }),
			env.IP_LIMITER.limit({ key: ip }),
		]);
		if (!byInstall.success || !byIp.success) return json({ error: "Too many requests. Try again in a minute." }, 429);

		const day = new Date().toISOString().slice(0, 10);
		const counter = env.DAILY_COUNTER.get(env.DAILY_COUNTER.idFromName("global"));
		if (!(await counter.take(day, Number(env.DAILY_CAP)))) {
			return json({ error: "gent has reached today's limit. Try again tomorrow." }, 503);
		}

		if (!env.TYPESAFE_API_KEY) return json({ error: "Relay is not configured." }, 503);
		let upstream;
		try {
			upstream = await fetch(JEV_URL, {
				method: "POST",
				headers: { Authorization: `Bearer ${env.TYPESAFE_API_KEY}`, "Content-Type": "application/json" },
				body: JSON.stringify(buildJevRequest(parsed, env.TYPESAFE_MODEL)),
				signal: AbortSignal.timeout(5000),
			});
		} catch {
			return json({ error: "Could not reach the decision model." }, 502);
		}
		if (!upstream.ok) return json({ error: `Decision model returned ${upstream.status}.` }, 502);
		return json(readJevAnswer(await upstream.json(), parsed.version));
	},
};
