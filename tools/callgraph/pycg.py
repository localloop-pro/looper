#!/usr/bin/env python3
"""pycg.py ROOT DIR1,DIR2,... OUT.json
Function-level call graph for Python sources (ast based, no execution)."""
import ast, json, os, re, sys

ROOT, DIRS, OUT = sys.argv[1], sys.argv[2].split(","), sys.argv[3]
EXCLUDE = {".venv", "venv", "node_modules", "__pycache__", "tests", "test", "dist", "build"}
TRIVIAL = set("""len str int float bool dict list set tuple isinstance issubclass print range enumerate zip
map filter sorted reversed min max sum abs round any all getattr setattr hasattr repr format type id hash iter
next open super vars object bytes bytearray frozenset slice divmod pow chr ord bin hex oct callable staticmethod
classmethod property Exception ValueError TypeError KeyError RuntimeError IndexError AttributeError
NotImplementedError StopIteration OSError IOError PermissionError FileNotFoundError ZeroDivisionError
AssertionError LookupError SystemExit KeyboardInterrupt UnicodeDecodeError""".split())
ROUTE_RE = re.compile(r"^(?:\w+\.)?(?:router|app|api|\w*_router)\.(get|post|put|delete|patch|head|options|websocket|api_route)\(\s*(['\"])(.*?)\2")

def files():
    for d in DIRS:
        base = os.path.join(ROOT, d)
        if os.path.isfile(base):
            yield base
            continue
        for dp, dns, fns in os.walk(base):
            dns[:] = sorted(x for x in dns if x not in EXCLUDE and not x.startswith("."))
            for fn in sorted(fns):
                if fn.endswith(".py") and not fn.startswith("test_") and fn != "conftest.py":
                    yield os.path.join(dp, fn)

def modname(path):
    rel = os.path.relpath(path, ROOT)[:-3].replace(os.sep, "/").replace("/", ".").lstrip(".")
    if rel.endswith(".__init__"):
        rel = rel[:-9]
    return rel

def dotted(n):
    if isinstance(n, ast.Name):
        return n.id
    if isinstance(n, ast.Attribute):
        b = dotted(n.value)
        return f"{b}.{n.attr}" if b else None
    if isinstance(n, ast.Call):
        b = dotted(n.func)
        return f"{b}()" if b else None
    if isinstance(n, ast.Subscript):
        b = dotted(n.value)
        return f"{b}[]" if b else None
    return None

def const_str(n):
    return n.value if isinstance(n, ast.Constant) and isinstance(n.value, str) else None

mods = {}
nodes = {}   # (mod, qual) -> ast node

def collect_defs(m, info, body, prefix, cls):
    for node in body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            q = f"{prefix}{node.name}"
            decos = [ast.unparse(d) for d in node.decorator_list]
            route = None
            for d in decos:
                mt = ROUTE_RE.match(d)
                if mt:
                    route = f"{mt.group(1).upper()} {mt.group(3)}"
            info["functions"][q] = {"line": node.lineno, "end": node.end_lineno,
                                    "async": isinstance(node, ast.AsyncFunctionDef),
                                    "decorators": decos, "route": route, "class": cls,
                                    "args": [a.arg for a in node.args.args if a.arg not in ("self", "cls")]}
            nodes[(m, q)] = node
            collect_defs(m, info, node.body, q + ".", cls)
        elif isinstance(node, ast.ClassDef):
            q = f"{prefix}{node.name}"
            info["classes"][q] = {"line": node.lineno, "bases": [ast.unparse(b) for b in node.bases],
                                  "decorators": [ast.unparse(d) for d in node.decorator_list]}
            collect_defs(m, info, node.body, q + ".", q)
        else:
            for b in (getattr(node, "body", None), getattr(node, "orelse", None), getattr(node, "finalbody", None)):
                if isinstance(b, list):
                    collect_defs(m, info, b, prefix, cls)
            for h in getattr(node, "handlers", []) or []:
                collect_defs(m, info, h.body, prefix, cls)

# ---- pass 1: defs + imports
trees = {}
for p in files():
    try:
        src = open(p, encoding="utf-8").read()
        tree = ast.parse(src, p)
    except SyntaxError as e:
        print("skip", p, e, file=sys.stderr)
        continue
    m = modname(p)
    is_pkg = p.endswith("__init__.py")
    pkg = m if is_pkg else (m.rsplit(".", 1)[0] if "." in m else "")
    info = {"path": os.path.relpath(p, ROOT).replace(os.sep, "/"), "imports": {}, "functions": {}, "classes": {},
            "env": [], "lines": src.count("\n") + 1, "doc": (ast.get_docstring(tree) or "").strip().split("\n")[0][:160]}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                info["imports"][a.asname or a.name.split(".")[0]] = a.name
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = pkg
                for _ in range(node.level - 1):
                    base = base.rsplit(".", 1)[0] if "." in base else ""
                target = f"{base}.{node.module}" if node.module else base
            else:
                target = node.module or ""
            for a in node.names:
                info["imports"][a.asname or a.name] = f"{target}.{a.name}" if target else a.name
    collect_defs(m, info, tree.body, "", None)
    info["functions"]["<module>"] = {"line": 1, "end": info["lines"], "async": False, "decorators": [],
                                     "route": None, "class": None, "args": []}
    nodes[(m, "<module>")] = tree
    mods[m] = info
    trees[m] = tree

defs = {}
for m, info in mods.items():
    for q in info["functions"]:
        defs[f"{m}:{q}"] = "function"
    for q in info["classes"]:
        defs[f"{m}:{q}"] = "class"

def resolve(m, info, name, cls, scope):
    if not name:
        return None
    name = name.replace("()", "").replace("[]", "")
    parts = name.split(".")
    head = parts[0]
    if head in ("self", "cls") and len(parts) >= 2:
        if cls:
            cand = f"{m}:{cls}.{parts[1]}"
            if cand in defs:
                return cand
            for b in info["classes"].get(cls, {}).get("bases", []):
                cand = f"{m}:{b}.{parts[1]}"
                if cand in defs:
                    return cand
        return None
    # lexical scopes (nested defs), innermost first
    sc = scope
    while sc and sc != "<module>":
        cand = f"{m}:{sc}.{name}"
        if cand in defs and cand != f"{m}:{scope}":
            return cand
        sc = sc.rsplit(".", 1)[0] if "." in sc else ""
    cand = f"{m}:{name}"
    if cand in defs:
        return cand
    if head in info["imports"]:
        full = ".".join([info["imports"][head]] + parts[1:])
        segs = full.split(".")
        for i in range(len(segs), 0, -1):
            modp, qual = ".".join(segs[:i]), ".".join(segs[i:])
            real = canon_mod(m, modp)
            if real:
                if qual and f"{real}:{qual}" in defs:
                    return f"{real}:{qual}"
                if qual and f"{real}:{qual}" not in defs and real in mods and qual.split(".")[0] in mods[real]["imports"]:
                    return None  # re-exported third-party name
                return f"{real}:{qual}" if qual else f"{real}:<module>"
    return None

def canon_mod(m, modp):
    """Map an import path to a scanned module: exact, or relative to the current package
    (backend code is run with its own folder on sys.path, so `from models import x` means backend.models)."""
    if modp in mods:
        return modp
    parts = m.split(".")
    for i in range(len(parts) - 1, 0, -1):
        cand = ".".join(parts[:i] + [modp])
        if cand in mods:
            return cand
    tail = [k for k in mods if k.endswith("." + modp)]
    return tail[0] if len(tail) == 1 else None

class Collector(ast.NodeVisitor):
    def __init__(self):
        self.calls, self.refs, self.env, self.includes = [], [], [], []
        self.env_params = []          # parameter names passed to os.getenv / os.environ.get
        self.router_prefix = None
    def visit_FunctionDef(self, node):   # nested defs are their own entries
        for d in node.decorator_list:
            self.visit(d)
    visit_AsyncFunctionDef = visit_FunctionDef
    def visit_ClassDef(self, node):
        pass
    def visit_Lambda(self, node):
        self.generic_visit(node)
    def visit_Call(self, node):
        name = dotted(node.func)
        arg0 = const_str(node.args[0]) if node.args else None
        if name in ("os.getenv", "os.environ.get") and node.args:
            if arg0:
                self.env.append(arg0)
            elif isinstance(node.args[0], ast.Name):
                self.env_params.append(node.args[0].id)
        if name and name.endswith("APIRouter"):
            self.router_prefix = next((const_str(k.value) for k in node.keywords if k.arg == "prefix"), None)
        if name and name.endswith("include_router") and node.args:
            prefix = next((const_str(k.value) for k in node.keywords if k.arg == "prefix"), None)
            self.includes.append((dotted(node.args[0]), prefix))
        consts = [const_str(a) for a in node.args]
        kwconsts = {k.arg: const_str(k.value) for k in node.keywords if k.arg}
        self.calls.append((name, arg0, node.lineno, consts, kwconsts))
        for a in list(node.args) + [k.value for k in node.keywords]:
            if isinstance(a, ast.Starred):
                a = a.value
            if not isinstance(a, ast.Call):
                d = dotted(a)
                if d:
                    self.refs.append(d)
        self.generic_visit(node)
    def visit_Subscript(self, node):
        if dotted(node.value) == "os.environ" and const_str(node.slice):
            self.env.append(const_str(node.slice))
        self.generic_visit(node)

CHANNEL_TAILS = {"getenv", "add_task", "Header", "Query", "Path", "Depends", "execute", "mount", "on_event", "middleware", "get", "post", "put", "delete", "patch", "add_api_route", "info", "warning", "error", "exception", "debug", "Thread"}

for m, info in mods.items():
    for q, f in info["functions"].items():
        node = nodes[(m, q)]
        c = Collector()
        body = node.body if hasattr(node, "body") else []
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for d in node.args.defaults + [d for d in node.args.kw_defaults if d is not None]:
                c.visit(d)
        for st in body:
            c.visit(st)
        internal, external, uses, seen = [], [], [], set()
        f["_argcalls"] = []
        for name, arg0, ln, consts, kwconsts in c.calls:
            if not name:
                continue
            r = resolve(m, info, name, f["class"], q)
            if r and r in defs and (any(consts) or any(kwconsts.values())):
                f["_argcalls"].append((r, consts, kwconsts))
            if r:
                if r not in seen:
                    seen.add(r)
                    (internal if r in defs else uses).append(r)
            else:
                parts = name.split(".")
                if len(parts) == 1 and parts[0] in TRIVIAL:
                    continue
                tail = parts[-1].replace("()", "")
                label = name
                if arg0 is not None and tail in CHANNEL_TAILS and tail not in ("info", "warning", "error", "exception", "debug"):
                    label = f'{name}("{arg0[:60]}")'
                if label not in seen:
                    seen.add(label); external.append(label)
        refs = []
        for d in c.refs:
            r = resolve(m, info, d, f["class"], q)
            if r and r not in seen and r not in refs:
                seen.add(r)
                (refs if r in defs else uses).append(r)
        f["calls"] = internal
        f["external"] = external
        f["refs"] = refs
        f["uses"] = uses
        f["called_by"] = []
        if c.env:
            info["env"] = sorted(set(info["env"]) | set(c.env))
        if c.env_params:
            f["env_params"] = c.env_params
        if c.includes:
            f["includes"] = [{"router": r, "prefix": p} for r, p in c.includes]
        if c.router_prefix is not None:
            info["route_prefix"] = c.router_prefix

# env names that reach os.getenv through a helper parameter, e.g. _env_int("LOOPER_X", 0)
for m, info in mods.items():
    for q, f in info["functions"].items():
        for tgt, consts, kwconsts in f.pop("_argcalls", []):
            tm, _, tq = tgt.partition(":")
            callee = mods.get(tm, {}).get("functions", {}).get(tq)
            if not callee or not callee.get("env_params"):
                continue
            for pname in callee["env_params"]:
                if pname not in callee["args"]:
                    continue
                i = callee["args"].index(pname)
                val = consts[i] if i < len(consts) else None
                val = val or kwconsts.get(pname)
                if val:
                    for mod in {m, tm}:
                        mods[mod]["env"] = sorted(set(mods[mod]["env"]) | {val})

# callers
for m, info in mods.items():
    for q, f in info["functions"].items():
        for tgt in f["calls"] + f["refs"]:
            tm, _, tq = tgt.partition(":")
            if tm in mods and tq in mods[tm]["functions"]:
                mods[tm]["functions"][tq]["called_by"].append(f"{m}:{q}")

json.dump({"root": ROOT, "modules": mods}, open(OUT, "w"), indent=1)
nf = sum(len(i["functions"]) for i in mods.values())
ne = sum(len(f["calls"]) + len(f["refs"]) for i in mods.values() for f in i["functions"].values())
print(f"modules={len(mods)} functions={nf} internal_edges={ne} -> {OUT}")
