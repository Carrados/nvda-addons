"""Create a new NVDA add-on under addons/ from the vendored template.

Usage: python new_addon.py <addonName> "<Summary shown in NVDA>" [--kind globalPlugin|appModule]
"""

import argparse
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TEMPLATE = ROOT / "template"
ADDONS = ROOT / "addons"

# Files and folders the template README says to copy into a new add-on.
COPY = [
	"site_scons",
	"buildVars.py",
	"manifest.ini.tpl",
	"manifest-translated.ini.tpl",
	"sconstruct",
	".gitignore",
	".gitattributes",
	"COPYING.txt",
	"style.css",
]

AUTHOR = "Carrados <200772005+Carrados@users.noreply.github.com>"
MIN_NVDA = "2025.1"
LAST_TESTED_NVDA = "2026.2"

GLOBAL_PLUGIN = '''import globalPluginHandler
import ui
from scriptHandler import script

import addonHandler

addonHandler.initTranslation()


class GlobalPlugin(globalPluginHandler.GlobalPlugin):
	@script(
		# Translators: Describes the command in NVDA's Input gestures dialog.
		description=_("Announces that {name} is running"),
		# Translators: Category for this add-on's commands in NVDA's Input gestures dialog.
		category=_("{summary}"),
	)
	def script_hello(self, gesture):
		# Translators: Spoken when the command is used.
		ui.message(_("{summary} is running"))
'''

APP_MODULE = '''import appModuleHandler
import ui
from scriptHandler import script

import addonHandler

addonHandler.initTranslation()


# Rename this file to the executable name of the app, e.g. notepad.py for notepad.exe.
class AppModule(appModuleHandler.AppModule):
	@script(
		# Translators: Describes the command in NVDA's Input gestures dialog.
		description=_("Announces that {name} is running"),
		# Translators: Category for this add-on's commands in NVDA's Input gestures dialog.
		category=_("{summary}"),
	)
	def script_hello(self, gesture):
		# Translators: Spoken when the command is used.
		ui.message(_("{summary} is running"))
'''

README = """# {summary}

Describe what this add-on does and list its commands here.
This file becomes the add-on help shown from NVDA's Add-on Store.

## Commands

This add-on has no keys assigned by default.
Assign them from the NVDA menu, Preferences, Input gestures, under "{summary}".

* Announce that the add-on is running.
"""


def setVar(text: str, key: str, value: str) -> str:
	# Replace `key=<anything up to the end of the line>` in buildVars.py.
	return re.sub(rf"^(\t{key}=).*$", lambda m: m.group(1) + value + ",", text, count=1, flags=re.M)


def main() -> None:
	parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
	parser.add_argument("name", help="internal camelCase identifier, e.g. sayTime")
	parser.add_argument("summary", help="name users see in NVDA, e.g. \"Say Time\"")
	parser.add_argument("--kind", choices=["globalPlugin", "appModule"], default="globalPlugin")
	args = parser.parse_args()

	if not re.fullmatch(r"[a-z][A-Za-z0-9]*", args.name):
		sys.exit("Name must be camelCase letters and digits, starting with a lower-case letter.")
	dest = ADDONS / args.name
	if dest.exists():
		sys.exit(f"{dest} already exists.")

	dest.mkdir(parents=True)
	for item in COPY:
		src = TEMPLATE / item
		if src.is_dir():
			shutil.copytree(src, dest / item, ignore=shutil.ignore_patterns("__pycache__"))
		else:
			shutil.copy2(src, dest / item)

	buildVars = (dest / "buildVars.py").read_text(encoding="utf-8")
	for key, value in {
		"addon_name": repr(args.name),
		"addon_summary": f"_({args.summary!r})",
		"addon_version": repr("0.1.0"),
		"addon_author": repr(AUTHOR),
		"addon_minimumNVDAVersion": repr(MIN_NVDA),
		"addon_lastTestedNVDAVersion": repr(LAST_TESTED_NVDA),
		"addon_license": repr("GPL v2"),
		"addon_licenseURL": repr("https://www.gnu.org/licenses/gpl-2.0.html"),
	}.items():
		buildVars = setVar(buildVars, key, value)
	folder = "globalPlugins" if args.kind == "globalPlugin" else "appModules"
	buildVars = buildVars.replace(
		"pythonSources: list[str] = []",
		f'pythonSources: list[str] = ["addon/{folder}/*.py"]',
	)
	(dest / "buildVars.py").write_text(buildVars, encoding="utf-8")

	code = GLOBAL_PLUGIN if args.kind == "globalPlugin" else APP_MODULE
	pluginDir = dest / "addon" / folder
	pluginDir.mkdir(parents=True)
	(pluginDir / f"{args.name}.py").write_text(
		code.format(name=args.name, summary=args.summary), encoding="utf-8"
	)
	(dest / "readme.md").write_text(README.format(summary=args.summary), encoding="utf-8")

	print(f"Created {dest.relative_to(ROOT)}")
	print(f"Code: {(pluginDir / f'{args.name}.py').relative_to(ROOT)}")
	print(f"Build and install with: python build.py {args.name} --install")


if __name__ == "__main__":
	main()
