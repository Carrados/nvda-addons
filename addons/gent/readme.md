# gent

Press NVDA+G, then Space. Type what you want NVDA to change in plain words, and press Enter.

For example:

* "Talk a bit faster", or "way too slow".
* "Stop reading so much punctuation".
* "Stop saying every letter I type", or "tell me what keys I'm pressing".
* "Make the voice deeper", or "beep for capitals".
* "Undo that", or "go back to how it was before".

gent works out which setting you mean and changes it, then tells you what it did.
If it isn't sure, it asks "Did you mean...?" first.
If it can't do what you asked, it says so.

## What gent can change

Everything on NVDA's Speech settings panel, plus typing and keys:

* Speed: faster or slower, by a little or a lot, and rate boost.
* Pitch, volume and inflection.
* Voice, variant and synthesizer. gent never switches to "No speech".
* Punctuation and symbols: more, less, none or all, and whether emoji and Unicode symbols are read by name.
* Capitals: saying "cap", beeping, and how much the pitch rises.
* Languages: automatic language and dialect switching, announcing language changes, what happens when the voice can't speak a language, and which language is used for symbols.
* Characters: delayed descriptions such as "a, alpha", Unicode normalization, and reporting "normalized".
* Speech dictionaries: your default dictionary and the voice's dictionary.
* Typing and keys: speaking typed characters, typed words and command keys.
* Undo: puts back the last change gent made. It remembers the last five.

Settings on the voice, such as pitch or capitals, apply to the synthesizer you're using, as they do in NVDA's own settings.

Type "help", or ask something like "what can I change?", to open an overview of what gent can do and your current settings.
Read it with the arrow keys and close it with Escape.

## When a form won't submit

On a web page in Chrome, Edge or Firefox, press NVDA+G, then F. You can also press NVDA+G, then Space, and type something like "form help" or "what have I missed?".

gent goes through every field on the page and lists:

* **Problems:** what's stopping the form. These are fields the page says are wrong, error messages such as "This field is required", and required fields that are empty or not ticked.
* **Things to check:** tickboxes that aren't ticked, questions with nothing chosen and empty boxes. Some of these may be fine to leave.

Choose one and press Enter to go straight to it. Escape closes the list.

Some sites only show their error messages as text on the page, without telling NVDA which field is wrong. gent reads the text after each field as well, so it finds those too.

The form check happens on your computer. Nothing on the form, and nothing you've typed into it, is sent anywhere.

## Privacy

The first time you use gent, it asks before sending anything.
What you type into gent (except asking it to check a form), and the names of gent's last few changes, go to Blind Ant's relay and on to TypeSafe's Jev model, which picks the setting you mean.
Nothing else on your computer is sent. The relay keeps no logs.
gent also sends a random ID, made when it is first used, so that the relay can stop any one install from sending too many requests.

## Commands

Press NVDA+G and gent says "gent", then waits for one key:

* Space or Enter: type what you want, in your own words.
* F: check the form on this web page.
* H: help.
* U: undo gent's last change.
* Escape: leave without doing anything. Any other key beeps and leaves.

You can change NVDA+G, or give the form check a key of its own, in NVDA's Input gestures dialog, under "gent".

gent is a Blind Ant design-fiction experiment.
