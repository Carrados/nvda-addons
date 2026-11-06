# NVDA add-ons

NVDA add-ons by [Blind Ant](https://blind-ant.com), one folder each under `addons`.

## gent

Press NVDA+G, then Space, type what you want NVDA to change in plain words, and press Enter. "Talk a bit faster", "stop reading so much punctuation", "undo that". gent works out which setting you mean and changes it. Press NVDA+G, then H, to hear what it can do.

When a web form won't submit, press NVDA+G, then F. gent lists what's stopping it and takes you to the field. The check happens on your computer; nothing on the form is sent anywhere.

* **Download:** the `.nvda-addon` file from the [latest release](https://github.com/Carrados/nvda-addons/releases/latest). Open it and NVDA offers to install it. It needs NVDA 2025.1 or later.
* **How it works and what it sends:** [addons/gent/readme.md](addons/gent/readme.md).
* **The add-on's code:** [addons/gent](addons/gent).
* **The relay it talks to:** [relay](relay), a Cloudflare Worker that asks TypeSafe's Jev model which action you mean.
* **The story of how it was built:** [The Making of gent](posts/making-of-gent.md).

gent is a Blind Ant design-fiction experiment.

## Layout

* `addons/<name>/`: one add-on. Its code is in `addon/globalPlugins` or `addon/appModules`, its details (version, summary, NVDA versions) in `buildVars.py`, and its help text in `readme.md`.
* `relay/`: the Cloudflare Worker that gent talks to.
* `posts/`: writing about these add-ons.
* `template/`: a copy of [nvaccess/AddonTemplate](https://github.com/nvaccess/AddonTemplate), used to create new add-ons. Don't edit it.
* `new_addon.py`: creates a new add-on from the template.
* `build.py`: builds an add-on, and can install it into NVDA.

## First-time setup

Run `.\setup.ps1` once. It creates `.venv` with SCons, Markdown and Ruff, using Python 3.13.

## Making an add-on

1. `python new_addon.py sayTime "Say Time"` creates `addons/sayTime` with a starter global plugin. Add `--kind appModule` for an add-on that only works in one program.
2. Edit the code in `addons/sayTime/addon/globalPlugins/sayTime.py`.
3. `python build.py sayTime --install` builds `addons/sayTime/sayTime-0.1.0.nvda-addon` and opens it, so NVDA asks to install it and restart.

During a build, "The system cannot find the file specified." means GNU gettext isn't installed. That's fine until you want translations.

If the add-on doesn't load or a command does nothing, check the NVDA log (NVDA+F1) for errors.

## Testing

* gent's decision logic, settings and form check: `python -m unittest discover addons/gent/tests`
* The relay: `npm test` in the `relay` folder.

## Releasing

Bump `addon_version` and `addon_changelog` in the add-on's `buildVars.py` before each build you share.

## Licence

GNU General Public License, version 2 or later. See [LICENSE.txt](LICENSE.txt). The add-on template in `template/` is by the NVDA add-on team contributors, under the same licence.
