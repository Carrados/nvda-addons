"""Build an add-on in addons/ with SCons, and optionally install it into NVDA.

Usage: python build.py <addonName> [--install]
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SCONS = ROOT / ".venv" / "Scripts" / "scons.exe"


def main() -> None:
	parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
	parser.add_argument("name", help="folder name under addons/")
	parser.add_argument("--install", action="store_true", help="open the built file so NVDA offers to install it")
	args = parser.parse_args()

	addonDir = ROOT / "addons" / args.name
	if not addonDir.is_dir():
		sys.exit(f"No add-on folder at {addonDir}")
	if not SCONS.is_file():
		sys.exit("Build tools missing. Run setup.ps1 first.")

	result = subprocess.run([str(SCONS)], cwd=addonDir)
	if result.returncode:
		sys.exit(result.returncode)

	built = max(addonDir.glob("*.nvda-addon"), key=lambda p: p.stat().st_mtime)
	print(f"Built {built.relative_to(ROOT)}")
	if args.install:
		# NVDA is registered for .nvda-addon files and asks whether to install, then to restart.
		os.startfile(built)


if __name__ == "__main__":
	main()
