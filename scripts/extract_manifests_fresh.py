"""Statically extract MCP tool manifests (name, description, input schema) from source.
No third-party code is executed. Handles: Python FastMCP-style decorators (ast),
TypeScript/JavaScript server.tool()/registerTool() with zod, and raw {name,description,inputSchema} objects.
Extraction is best-effort; coverage is reported per repo so the limitation is measurable."""
import ast, json, re, sys, pathlib
ROOT = pathlib.Path(__file__).resolve().parent.parent
WORK = pathlib.Path.home() / "mcp-study-work"  # clones live outside the synced folder (fs there breaks git checkout)
SKIP = {"node_modules", ".git", "dist", "build", "venv", ".venv", "__pycache__", "tests", "test", "__tests__", "examples", "example", "docs"}
PYTYPE = {"str": "string", "int": "integer", "float": "number", "bool": "boolean", "list": "array", "dict": "object"}

def files(repo, exts):
    for p in repo.rglob("*"):
        if p.suffix in exts and p.is_file() and not (set(p.relative_to(repo).parts[:-1]) & SKIP) and p.stat().st_size < 400_000:
            yield p

def py_tools(path):
    try: tree = ast.parse(path.read_text(errors="ignore"))
    except Exception: return []
    out = []
    for fn in ast.walk(tree):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)): continue
        dec = None
        for d in fn.decorator_list:
            base = d.func if isinstance(d, ast.Call) else d
            if (isinstance(base, ast.Attribute) and base.attr == "tool") or (isinstance(base, ast.Name) and base.id == "tool"):
                dec = d; break
        if dec is None: continue
        name, desc = fn.name, ast.get_docstring(fn) or ""
        if isinstance(dec, ast.Call):
            for kw in dec.keywords:
                if kw.arg == "name" and isinstance(kw.value, ast.Constant): name = str(kw.value.value)
                if kw.arg == "description" and isinstance(kw.value, ast.Constant): desc = str(kw.value.value)
            if dec.args and isinstance(dec.args[0], ast.Constant) and isinstance(dec.args[0].value, str): name = dec.args[0].value
        props = {}
        args = fn.args.args + fn.args.kwonlyargs
        for a in args:
            if a.arg in ("self", "cls", "ctx", "context") : continue
            ann = ast.unparse(a.annotation) if a.annotation else ""
            if "Context" in ann: continue
            s = {"type": "string"}
            base = ann.split("[")[0].replace("Optional", "").strip("| ") or ann
            if ann.startswith("Literal["):
                try: s["enum"] = [ast.unparse(e) for e in getattr(ast.parse(ann, mode="eval").body.slice, "elts", [])] or ["?"]
                except Exception: s["enum"] = ["?"]
            elif re.search(r"\b(int)\b", ann): s = {"type": "integer"}
            elif re.search(r"\bfloat\b", ann): s = {"type": "number"}
            elif re.search(r"\bbool\b", ann): s = {"type": "boolean"}
            elif re.search(r"\b(list|List)\b", ann): s = {"type": "array"}
            elif re.search(r"\b(dict|Dict)\b", ann): s = {"type": "object"}
            elif ann and not re.search(r"\bstr\b", ann): s = {"type": "object"}
            props[a.arg] = s
        out.append(dict(name=name, description=desc, input_schema={"type": "object", "properties": props}, src=str(path)))
    return out

STR = r'(?:"((?:[^"\\]|\\.)*)"|\'((?:[^\'\\]|\\.)*)\'|`((?:[^`\\]|\\.)*)`)'
def lit(m): return next(g for g in m.groups() if g is not None)
def zod_props(block):
    props = {}
    for m in re.finditer(r"(\w+)\s*:\s*(?:z|zod)\s*\.\s*(string|number|boolean|enum|array|object|any|union|record)\s*\(([^)]*)\)([^,\n]*(?:\n\s*\.[^,\n]*)*)", block):
        key, kind, arg, chain = m.groups()
        s = {"type": {"string": "string", "number": "number", "boolean": "boolean", "array": "array", "enum": "string"}.get(kind, "object")}
        if kind == "enum": s["enum"] = ["?"]
        if re.search(r"\.regex\(|\.startsWith\(|\.endsWith\(|\.includes\(", chain): s["pattern"] = "?"
        if re.search(r"\.max\(|\.length\(", chain) and kind == "string": s["maxLength"] = 1
        if re.search(r"\.(url|email|uuid|datetime)\(", chain): s["format"] = "?"
        d = re.search(r"\.describe\(\s*" + STR, chain)
        if d: s["description"] = lit(d)
        props[key] = s
    return props
CONSTS = {}
ANCHOR = re.compile(r"(?:registerTool|addTool|defineTool|definePageTool|\.tool)\s*\(\s*")
def collect_consts(t):
    for m in re.finditer(r"(?:const|let|var)\s+([A-Za-z_]\w*)\s*=\s*" + STR + r"\s*(?:as const)?\s*[;\n]", t):
        CONSTS[m.group(1)] = lit(re.match(r"^\w+\s*", "") or m) if False else next(g for g in m.groups()[1:] if g is not None)
def json_props(block):
    props = {}
    for pm in re.finditer(r"(\w+)\s*:\s*\{\s*type\s*:\s*['\"](\w+)['\"]([^{}]*)\}", block):
        k, ty, tail = pm.groups(); sc = {"type": ty}
        for f in ("enum", "pattern", "format", "maxLength"):
            if re.search(r"\b%s\s*:" % f, tail): sc[f] = "?"
        props[k] = sc
    return props
def ts_tools(path):
    t = path.read_text(errors="ignore"); out = []
    anchors = list(ANCHOR.finditer(t))
    for i, m in enumerate(anchors):
        end = anchors[i + 1].start() if i + 1 < len(anchors) else len(t)
        win = t[m.end(): min(end, m.end() + 4500)]
        name = desc = None
        if win.startswith("{"):
            nm = re.search(r"\bname\s*:\s*(?:" + STR + r"|([A-Za-z_]\w*))", win[:600])
            if nm:
                name = next((g for g in nm.groups()[:3] if g is not None), None) or CONSTS.get(nm.group(4))
        else:
            nm = re.match(r"(?:" + STR + r"|([A-Za-z_][\w.]*))\s*,", win)
            if nm:
                name = next((g for g in nm.groups()[:3] if g is not None), None) or CONSTS.get(nm.group(4))
        if not name: continue
        dm = re.match(r"(?:" + STR + r")\s*,\s*" + STR, win) if not win.startswith("{") else None
        if dm: desc = next(g for g in dm.groups()[3:] if g is not None)
        else:
            dd = re.search(r"description\s*:\s*" + STR, win)
            if dd: desc = lit(dd)
        if desc is None: continue
        props = zod_props(win); props.update({k: v for k, v in json_props(win).items() if k not in props})
        out.append(dict(name=name, description=desc, input_schema={"type": "object", "properties": props}, src=str(path)))
    # generic fallback: object literals pairing name + description with a schema-ish key nearby
    if re.search(r"modelcontextprotocol|FastMCP|McpServer|mcp-server|@mcp|fastmcp", t, re.I) or True:
        for dm in re.finditer(r"\bdescription\s*:\s*" + STR, t):
            around = t[max(0, dm.start() - 400): dm.start()]; after = t[dm.end(): dm.end() + 1800]
            nm = list(re.finditer(r"\bname\s*:\s*" + STR, around))
            nm2 = re.match(r"\s*,?\s*(?:\w+\s*:[^\n]*\n\s*)?name\s*:\s*" + STR, after)
            if nm: name = lit(nm[-1])
            elif nm2: name = lit(nm2)
            else: continue
            if not re.search(r"\b(inputSchema|input_schema|schema|parameters)\s*:", after[:1500] if not nm else (t[dm.start()-200:dm.end()+1500])): continue
            if not re.fullmatch(r"[A-Za-z0-9_.:/-]{2,80}", name): continue
            props = zod_props(after); props.update({k: v for k, v in json_props(after).items() if k not in props})
            out.append(dict(name=name, description=lit(dm), input_schema={"type": "object", "properties": props}, src=str(path)))
    return out

def main():
    corpus = json.loads((ROOT / "data" / "fresh_corpus.json").read_text())
    result = {}
    for name, meta in corpus.items():
        repo = WORK / "corpus2" / name.replace("/", "__")
        if not repo.exists(): continue
        tools = []
        for p in files(repo, {".py"}):
            try: tools += py_tools(p)
            except Exception: pass
        tsf = list(files(repo, {".ts", ".js", ".mjs", ".tsx"}))
        CONSTS.clear()
        for p in tsf:
            try: collect_consts(p.read_text(errors="ignore"))
            except Exception: pass
        for p in tsf:
            try: tools += ts_tools(p)
            except Exception: pass
        seen, uniq = set(), []
        for x in tools:
            k = (x["name"], x["description"][:60])
            if k not in seen: seen.add(k); uniq.append(x)
        result[name] = dict(meta=meta, tools=uniq)
        print(f"{name}: {len(uniq)} tools", flush=True)
    (ROOT / "data" / "manifests_fresh.json").write_text(json.dumps(result, indent=1))
main()
