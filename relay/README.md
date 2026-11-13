# gent relay

A Cloudflare Worker between the gent NVDA add-on and TypeSafe's Jev model. It also keeps page recordings that users choose to share, for 7 days.

The add-on sends what the user typed. The relay asks Jev which of gent's actions the user means and returns Jev's choice. The add-on then makes the change itself, with ordinary NVDA code.

## Why there is a relay

* **The TypeSafe API key stays secret.** It is stored as an encrypted Worker secret and never ships inside the add-on.
* **It only asks one question.** The relay builds the Jev request itself, from the action list in [src/gent.js](src/gent.js). Callers send only their text, so the relay can't be used as a free gateway to Jev for anything else.
* **Spending is capped.** Each install may make 20 requests a minute and each IP address 60. A daily cap across everyone (20,000 requests) is enforced by a Durable Object, so it holds across all Cloudflare locations.
* **Nothing is kept, except recordings people share.** Worker logging is off. The relay doesn't store what anyone types to gent. A page recording is stored only after the user says yes to sharing it, and its own Durable Object deletes it after 7 days.

## The request

`POST /v1/decide`, with a JSON body:

```json
{
	"install_id": "a random ID the add-on makes once",
	"text": "make it talk a bit faster",
	"recent": ["punctuationLess"],
	"actions_version": "2"
}
```

* `text`: up to 300 characters.
* `recent`: up to five of gent's latest changes, most recent first, so Jev can understand "now", "that" or "how it was before".
* `actions_version`: which action list the add-on understands. Older add-ons keep getting the list they were built for.

The answer:

```json
{
	"actions_version": "2",
	"action": "speechRateFaster",
	"confidence": 1,
	"alternatives": [{ "action": "speechRateFaster", "probability": 1 }],
	"size": "small"
}
```

Requests must send a `User-Agent`. Cloudflare blocks Python's default one, so the add-on sends `nvda-gent/<version>`.

## Page recordings

`POST /v1/recordings`, with a JSON body:

```json
{ "install_id": "a random ID the add-on makes once", "text": "gent page recording\n..." }
```

* `text`: up to 512 KB of UTF-8.

The answer:

```json
{ "url": "https://<relay>/r/<32 hex characters>", "expires": "2026-11-20T21:00:00.000Z" }
```

`GET /r/<id>` returns the recording as plain text, until it is deleted. Each ID is 128 random bits, so links can't be guessed. Uploads share the per-install and per-IP limits, with a separate daily cap of 2,000.

## Running your own

You need a Cloudflare account and a [TypeSafe](https://typesafe.ai) API key with credit.

1. `npm install`, then `npm test`.
2. `npx wrangler deploy`. The rate-limit `namespace_id` values in [wrangler.jsonc](wrangler.jsonc) must be unique within your Cloudflare account.
3. `npx wrangler secret put TYPESAFE_API_KEY`, and paste your key when asked.
4. Change `RELAY_URL` in the add-on's [relay.py](../addons/gent/addon/globalPlugins/gent/relay.py) to your Worker's address, and rebuild the add-on.

`npm run dev` runs the relay on your own computer. Without a key it answers "Relay is not configured", which is enough to test validation and rate limits.
