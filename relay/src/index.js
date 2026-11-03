// NVDA gent relay: holds the TypeSafe key, asks Jev the one gent question,
// and limits use per install, per IP address and per day. It never logs what users type.
import { DurableObject } from "cloudflare:workers";
import { BadRequest, buildJevRequest, parseDecideBody, readJevAnswer } from "./gent.js";

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

export default {
	async fetch(request, env) {
		const { pathname } = new URL(request.url);
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
		return json(readJevAnswer(await upstream.json()));
	},
};
