#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Install the sci-drawio skill into a target skills directory.

Usage:
    python install.py --target <skills-dir>
    python install.py --target ~/.agents/skills
    python install.py --target ./workspace/.user_skills

The script copies this whole folder (except .git / __pycache__) into
<target>/sci-drawio. If a sci-drawio folder already exists there it is
replaced (backup kept as sci-drawio.bak).
"""
import argparse
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(HERE)
SKILL_NAME = os.path.basename(SKILL_DIR)

SKIP = {".git", "__pycache__", ".DS_Store"}


def main():
    ap = argparse.ArgumentParser(description="install sci-drawio into a skills directory")
    ap.add_argument("--target", required=True, help="target skills root (skill will land in <target>/sci-drawio)")
    ap.add_argument("--yes", action="store_true", help="replace existing copy without asking")
    args = ap.parse_args()

    target = os.path.abspath(os.path.expanduser(args.target))
    if not os.path.isdir(target):
        print("Error: target directory does not exist: %s" % target)
        sys.exit(1)

    dest = os.path.join(target, SKILL_NAME)
    if os.path.exists(dest):
        if not args.yes:
            ans = input("'%s' already exists. Replace it? [y/N] " % dest).strip().lower()
            if ans != "y":
                print("aborted")
                sys.exit(0)
        backup = dest + ".bak"
        if os.path.exists(backup):
            shutil.rmtree(backup)
        os.rename(dest, backup)
        print("moved existing copy to %s" % backup)

    shutil.copytree(
        SKILL_DIR, dest,
        ignore=shutil.ignore_patterns(*SKIP),
    )
    print("installed skill to %s" % dest)
    print("done. The skill is ready to be picked up by your agent.")


if __name__ == "__main__":
    main()
