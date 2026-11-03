# The Making of gent

*A Blind Ant note on building an NVDA add-on by agentic coding, not vibe coding.*

This afternoon I typed one line into Claude Code:

> can you look at nvda repos on github

By the evening, gent was running inside my copy of NVDA.

I press NVDA+G. I type "way too slow, speed it right up". NVDA speeds up. I type "undo that". It goes back. I type "describe this image". It politely tells me it can't do that yet.

That sounds like a vibe-coding story. It isn't one, and the difference is the point of this post.

## Vibe coding and agentic coding

Vibe coding is when you describe what you want, an AI writes something that looks plausible, and you run it and hope. If it breaks, you paste the error back and hope again. Nobody reads the code. Nobody checks the platform it targets. It's fine for a toy.

It is not fine for a screen reader. For the people who rely on NVDA, it is how they use their computer. An add-on that crashes it, silently changes the wrong setting, or quietly sends what I type somewhere unexpected is not a toy. It's a locked door.

Agentic coding is different. The agent doesn't just write code. It works the way a careful developer works: it reads the real source, checks its assumptions, runs tests, deploys infrastructure, finds problems in the real world, and stops to ask me when a decision is mine.

Here is what that looked like.

## It read NVDA before it wrote for NVDA

The first thing Claude did was look at what NV Access actually publishes on GitHub: the screen reader itself, the add-on store, and the official add-on template.

When I said I only wanted to write add-ons, it set up a local workspace from that official template, wrote small scripts to create, build and install add-ons, and built a throwaway test add-on to prove the pipeline worked before deleting it.

Even that test caught something. The starter command it generated gave the test add-on the key NVDA+Shift+S, which is NVDA's own sleep mode. Claude changed the template so new add-ons don't claim any key by default.

Later, before writing a line of gent, it read NVDA's source code for my exact version, 2026.2, not the development version:

* the configuration file that defines every setting NVDA saves;
* the code behind NVDA's own commands for punctuation and typing echo;
* the dialog functions NVDA wants add-ons to use.

That mattered. "Key echo" turns out not to be on or off. NVDA stores three values: off, only in edit controls, and always. Punctuation is a scale with its own numbers. An add-on written from memory would have got both wrong.

It also checked that NVDA+G isn't already used by NVDA. (I first asked for NVDA+J, then changed my mind halfway through its turn. It picked that up.)

## It fact-checked me

Before any code, I gave Claude my two design-fiction posts, NVDA Commander and NVDA gent, and asked what it thought.

It checked my claims against TypeSafe's documentation, OpenAI's developer docs and NVDA's user guide. Most held up. One didn't: I had estimated that £50 of inference would buy "tens of thousands" of decisions. At Jev's published price, it's closer to two million. I was out by about a hundredfold, and that changes what my "Jevons test" would actually measure.

It also pointed out that an AI image-description add-on for NVDA already exists, and that Sign in with ChatGPT is a preview limited to paid plans. That's why the first version of gent uses Jev alone.

A vibe coder agrees with you. An agent with access to the sources sometimes tells you you're wrong.

## A real architecture, not a script

gent has three parts.

**The add-on**, in Python, inside NVDA. It opens a text box when you press NVDA+G, sends what you typed, then makes the change itself using ordinary NVDA code. It remembers its last five changes so it can undo them.

**The relay**, a Cloudflare Worker. It sits between the add-on and the AI so that my TypeSafe key never ships inside the add-on. It also:

* builds the question it sends to Jev itself, so nobody can use it as a free gateway to Jev for something else;
* limits each install to 20 requests a minute and each internet address to 60;
* caps the whole service at 20,000 requests a day, so my credit can't drain overnight;
* keeps no logs of what anyone types.

**Jev**, TypeSafe's decision model. It never writes text. It is given the list of things gent can do, and what the user typed, and it returns one choice with a probability. It cannot invent a setting that isn't on the list.

The add-on and the relay are versioned. When I asked for a help overview, the relay learned to offer "help" only to add-ons that understand it. An older copy of gent can never be handed an action it doesn't know.

## The secret key stayed mine

At one point I said: the API key is on my clipboard.

Claude wouldn't touch it. It said keys are mine to enter, deployed the relay without one, and told me exactly where in the Cloudflare dashboard to paste it as an encrypted secret. Then it confirmed the secret was there without ever seeing it.

That's a small moment, and it's the clearest difference from vibe coding I can think of. The agent knew where its job ended.

## It found problems in the real world

Tests on my own machine only prove so much. Once the relay was live, real problems appeared, and Claude found them by testing against the real thing.

* **Cloudflare blocked Python.** Every request from Python came back with error 1010, because Cloudflare's bot protection refuses Python's default identity. NVDA add-ons are Python, so gent would have failed for every user. The fix is that gent always announces itself as `nvda-gent`.
* **A first-start crash.** The very first live request failed while Cloudflare set up the relay's daily counter. Claude checked the configuration, retried, and confirmed it was a one-off rather than shipping a retry loop and hoping.
* **Uncertainty that wasn't really uncertainty.** "Undo that", after making things louder, split Jev between "undo" (59%) and "quieter" (41%). Both have the same effect. So gent now treats a split between undoing a change and asking for its opposite as agreement, and acts. Jev only asks "Did you mean…?" when the choices would actually do different things.

Fourteen real phrases went through the live system before I installed anything. Jev got all fourteen right, in 0.3 to 0.6 seconds each, for a tiny fraction of a cent in total.

## Tests, style checks, commits

Every change came with checks:

* tests for gent's decision logic, including the undo-or-opposite rule found above;
* tests for the relay's validation, versioning and answer handling;
* NV Access's own code-style checks, from the template;
* a build of the actual `.nvda-addon` file, opened to confirm what was inside it.

Everything went into git, committed under my own account with an honest note that Claude co-wrote it. I chose to work on the main branch. Claude asked first.

And it's all public. Both the add-on and the relay are open source, under the same GNU General Public License as NVDA's add-on template, on GitHub at [Carrados/nvda-addons](https://github.com/Carrados/nvda-addons). Nothing secret is in there. The key lives only in Cloudflare.

## What I actually did

I didn't write the Python, the JavaScript or the Cloudflare configuration.

I did:

* decide what gent is for, and what it should refuse;
* choose the name (it stayed lower-case gent even when the code still said Commander);
* choose the first three settings and the key;
* create the TypeSafe account and add the credit;
* paste the secret key;
* confirm NVDA's install prompt;
* press NVDA+G and say "omg it works".

That's the shape of agentic coding, at least as I've now experienced it. The person decides. The agent does the engineering, checks its work against reality, and hands back the decisions that belong to the person.

## From a prompt to an add-on

gent is still a design-fiction experiment. It changes three kinds of setting. It has been tested by exactly one person, me, in one afternoon.

But it is real. It reads NVDA's actual settings. It runs through actual infrastructure with actual limits. It keeps an actual secret. And it was built properly, not hoped into existence.

Type "help" and it will tell you what it can do.

It waits to be asked.

## Try it, read it, fork it

* **Download gent:** the `.nvda-addon` file is on the [latest release](https://github.com/Carrados/nvda-addons/releases/latest). Open it and NVDA offers to install it. It needs NVDA 2025.1 or later, and an internet connection. The first time you press NVDA+G, gent asks before it sends anything.
* **What gent sends, and why:** [the add-on's help page](https://github.com/Carrados/nvda-addons/blob/main/addons/gent/readme.md).
* **The add-on's code:** [addons/gent](https://github.com/Carrados/nvda-addons/tree/main/addons/gent). The part that decides when to act and when to ask is [logic.py](https://github.com/Carrados/nvda-addons/blob/main/addons/gent/addon/globalPlugins/gent/logic.py).
* **The relay:** [relay](https://github.com/Carrados/nvda-addons/tree/main/relay), with instructions for running your own with your own TypeSafe key. The list of things Jev can choose from is in [gent.js](https://github.com/Carrados/nvda-addons/blob/main/relay/src/gent.js).
* **The tools:** gent was built with [Claude Code](https://claude.com/claude-code), on NV Access's [add-on template](https://github.com/nvaccess/AddonTemplate), with [TypeSafe](https://typesafe.ai)'s Jev and [Cloudflare Workers](https://workers.cloudflare.com).

If you try it, tell me what you asked it that it couldn't do. That's the most useful thing this experiment can learn.
