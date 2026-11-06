#!/usr/bin/env python3
"""Regenerate plans/INTENT_PROMPT_CALL_GRAPH.md from the current checkout.

Run from the repo root:  python3 tools/callgraph/build.py
Needs: Python 3.12 and Node 20+ with npm. The TypeScript parser comes from
looper-bot/node_modules when present. Otherwise the version pinned in
looper-bot/package-lock.json is downloaded once into ~/.cache/looper-callgraph
(outside the repo). Nothing is executed from the analysed code; both extractors
only parse files."""
import datetime, json, os, shutil, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
OUT = os.path.join(ROOT, "plans", "INTENT_PROMPT_CALL_GRAPH.md")
BOT_MODULES = os.path.join(ROOT, "looper-bot", "node_modules")
LOCKFILE = os.path.join(ROOT, "looper-bot", "package-lock.json")
CACHE = os.path.join(os.path.expanduser("~"), ".cache", "looper-callgraph")


class BuildError(Exception):
    """A problem the person running this can act on; shown without a traceback."""


def run(cmd, **kw):
    print("+", " ".join(os.path.relpath(c, ROOT) if os.path.isabs(c) and c.startswith(ROOT) else c for c in cmd))
    try:
        subprocess.run(cmd, check=True, cwd=ROOT, **kw)
    except subprocess.CalledProcessError as exc:
        raise BuildError(f"step failed with exit code {exc.returncode}: {os.path.basename(cmd[0])}") from exc


def pinned_typescript():
    try:
        with open(LOCKFILE, encoding="utf-8") as fh:
            return json.load(fh)["packages"]["node_modules/typescript"]["version"]
    except (OSError, ValueError, KeyError) as exc:
        raise BuildError(f"could not read the TypeScript version from {os.path.relpath(LOCKFILE, ROOT)}") from exc


def typescript_modules():
    """Return a node_modules folder that contains the TypeScript parser."""
    if os.path.isdir(os.path.join(BOT_MODULES, "typescript")):
        return BOT_MODULES
    version = pinned_typescript()
    prefix = os.path.join(CACHE, f"typescript-{version}")
    modules = os.path.join(prefix, "node_modules")
    if os.path.isdir(os.path.join(modules, "typescript")):
        return modules
    if not shutil.which("npm"):
        raise BuildError("npm was not found. Install Node 20+ from https://nodejs.org and run this again.")
    print(f"Downloading TypeScript {version} once into {prefix}")
    os.makedirs(prefix, exist_ok=True)
    run(["npm", "install", "--prefix", prefix, "--no-save", "--no-audit", "--no-fund",
         "--loglevel=error", f"typescript@{version}"])
    return modules


def main():
    if not shutil.which("node"):
        raise BuildError("node was not found. Install Node 20+ from https://nodejs.org and run this again.")
    tmp = tempfile.mkdtemp(prefix="looper-callgraph-")
    pyj, jsj = os.path.join(tmp, "py.json"), os.path.join(tmp, "js.json")
    run([sys.executable, "-I", os.path.join(HERE, "pycg.py"), ROOT, "backend,brain,tools,scripts,training", pyj])
    env = dict(os.environ)
    env["NODE_PATH"] = typescript_modules()
    run(["node", os.path.join(HERE, "jscg.js"), ROOT, "web,workers,looper-bot", jsj], env=env)
    sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip() or "unknown"
    today = datetime.date.today().isoformat()
    run([sys.executable, "-I", os.path.join(HERE, "render.py"), ROOT, pyj, jsj, os.path.join(HERE, "intent.md"), OUT, sha, today])
    print("ok:", os.path.relpath(OUT, ROOT))


if __name__ == "__main__":
    try:
        main()
    except BuildError as exc:
        sys.exit(f"build failed: {exc}")
