#!/usr/bin/env python3
"""Sync the API Reference cards in docs/index.html from the public OpenAPI spec.

Usage:
    python3 scripts/sync_reference.py [--spec URL_OR_FILE] [--write]

Default spec: https://prod.sportsvisio-api.com/api-docs/public-json
Without --write it prints the plan and leaves index.html untouched.

What it touches (API Reference section only, the hand-written guides are left alone):
  - every endpoint card's summary, description, parameters, request body,
    response-code chips and search index are regenerated from the spec
  - existing example response bodies are kept (they're real data); new cards
    get a schema-derived example
  - endpoints in the spec with no card get a new card appended to their tag
    group (new tag groups + sidebar links are created as needed)
  - tag counts and sidebar badges are recomputed
Cards whose endpoint is no longer in the spec are reported, not removed.
"""
import argparse
import html
import json
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INDEX = ROOT / "docs" / "index.html"
API_HOST = "https://api.sportsvisio-api.com"
DEFAULT_SPEC = "https://prod.sportsvisio-api.com/api-docs/public-json"
METHODS = ("get", "post", "put", "patch", "delete")
COLLAPSE_OVER = 10  # response bodies longer than this start collapsed (scripts.js truncates at 10)


# --------------------------------------------------------------------------- spec
def load_spec(src: str) -> dict:
    if re.match(r"^https?://", src):
        with urllib.request.urlopen(src, timeout=30) as r:
            return json.load(r)
    return json.loads(Path(src).read_text())


# Internal worker knobs the API's public spec still leaks (SPO-1459). They are
# never documented: dropped from parameters and request bodies before rendering.
INTERNAL_FIELDS = {"devMode", "renderFireball", "renderAiExternal"}


def strip_internal(spec):
    """Remove INTERNAL_FIELDS from every operation's parameters and request body. Returns the count removed."""
    removed = 0
    schemas = spec.get("components", {}).get("schemas", {})

    def walk(schema, seen):
        nonlocal removed
        if not isinstance(schema, dict):
            return
        if "$ref" in schema:
            name = schema["$ref"].split("/")[-1]
            if name not in seen:
                walk(schemas.get(name, {}), seen | {name})
            return
        props = schema.get("properties", {})
        for f in INTERNAL_FIELDS & set(props):
            del props[f]
            removed += 1
        if "required" in schema:
            schema["required"] = [r for r in schema["required"] if r not in INTERNAL_FIELDS]
        if isinstance(schema.get("example"), dict):
            for f in INTERNAL_FIELDS & set(schema["example"]):
                del schema["example"][f]
        for k in ("allOf", "oneOf", "anyOf"):
            for s in schema.get(k, []):
                walk(s, seen)
        for s in props.values():
            walk(s, seen)
        for k in ("items", "additionalProperties", "not"):
            walk(schema.get(k), seen)

    for _, _, op in iter_ops(spec):
        before = len(op.get("parameters", []))
        op["parameters"] = [p for p in op.get("parameters", []) if p.get("name") not in INTERNAL_FIELDS]
        removed += before - len(op["parameters"])
        try:
            walk(op["requestBody"]["content"]["application/json"]["schema"], frozenset())
        except (KeyError, TypeError):
            pass
    return removed


def iter_ops(spec):
    for path, methods in spec.get("paths", {}).items():
        for m in METHODS:
            if m in methods:
                yield m.upper(), path, methods[m]


def card_id(method, path):
    return method.lower() + "-" + re.sub(r"[{}]", "", path).strip("/").replace("/", "-")


def tag_slug(tag):
    return "tag-" + re.sub(r"[^a-z0-9]+", "-", tag.lower()).strip("-")


class Resolver:
    def __init__(self, spec):
        self.spec = spec

    def deref(self, schema):
        while isinstance(schema, dict) and "$ref" in schema:
            name = schema["$ref"].split("/")[-1]
            schema = self.spec["components"]["schemas"].get(name, {})
        return schema

    def example(self, schema, depth=0, seen=()):
        if not isinstance(schema, dict):
            return None
        if "$ref" in schema:
            name = schema["$ref"].split("/")[-1]
            if name in seen or depth > 8:
                return {}
            return self.example(self.deref(schema), depth + 1, seen + (name,))
        if "example" in schema:
            return schema["example"]
        if "allOf" in schema:
            merged = {}
            for s in schema["allOf"]:
                v = self.example(s, depth + 1, seen)
                if isinstance(v, dict):
                    merged.update(v)
            return merged
        for k in ("oneOf", "anyOf"):
            if k in schema and schema[k]:
                return self.example(schema[k][0], depth + 1, seen)
        t = schema.get("type")
        if t is None and "properties" in schema:
            t = "object"
        if t == "object":
            return {k: self.example(v, depth + 1, seen) for k, v in schema.get("properties", {}).items()}
        if t == "array":
            return [self.example(schema.get("items", {}), depth + 1, seen)]
        if t == "string":
            if schema.get("enum"):
                return schema["enum"][0]
            fmt = schema.get("format", "")
            if fmt == "uuid":
                return "7a5e7bf4-ad48-4a01-b64b-46f515de2c86"
            if fmt == "date-time":
                return "2026-01-15T10:00:00Z"
            if fmt == "date":
                return "2026-01-15"
            return "string"
        if t in ("number", "integer"):
            return 0
        if t == "boolean":
            return True
        return None

    def type_name(self, schema):
        schema = self.deref(schema) if isinstance(schema, dict) else {}
        t = schema.get("type", "object" if "properties" in schema else "string")
        if t == "array":
            return "array"
        return t


# --------------------------------------------------------------------------- rendering
def esc(s):
    return html.escape(str(s or ""), quote=True)


def inline_md(s):
    """Escape, then `code` and **bold**."""
    s = esc(s)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
    return s


def md_to_html(text):
    """Minimal markdown: paragraphs, '- ' bullets, '1. ' numbered lists."""
    out, para, items, kind = [], [], [], None

    def flush():
        nonlocal para, items, kind
        if para:
            out.append("<p>" + "<br>".join(para) + "</p>")
            para = []
        if items:
            out.append(f"<{kind}>" + "".join(f"<li>{i}</li>" for i in items) + f"</{kind}>")
            items, kind = [], None

    for line in (text or "").strip().split("\n"):
        line = line.rstrip()
        if not line.strip():
            flush()
            continue
        m_ul = re.match(r"^\s*[-*] (.*)", line)
        m_ol = re.match(r"^\s*\d+[.)] (.*)", line)
        if m_ul or m_ol:
            want = "ul" if m_ul else "ol"
            if para or (items and kind != want):
                flush()
            kind = want
            items.append(inline_md((m_ul or m_ol).group(1)))
        else:
            if items:
                flush()
            para.append(inline_md(line))
    flush()
    return "".join(out)


def first_sentence(text):
    t = (text or "").strip().split("\n")[0]
    return re.sub(r"[`*]", "", t)


def param_row(p, res):
    typ = res.type_name(p.get("schema", {}))
    return (f'<tr><td><span class="param-name">{esc(p["name"])}</span></td>'
            f'<td><span class="param-in">{esc(p.get("in"))}</span></td>'
            f'<td><span class="param-type">{esc(typ)}</span></td>'
            f'<td>{inline_md(p.get("description", ""))}</td></tr>')


def table(rows):
    return ('<table class="param-table"><thead><tr><th>Name</th><th>In</th><th>Type</th><th>Description</th></tr></thead><tbody>\n'
            + "\n".join(rows) + "\n</tbody></table>")


def params_html(op, res, cid):
    params = op.get("parameters", [])
    req = [param_row(p, res) for p in params if p.get("required")]
    opt = [param_row(p, res) for p in params if not p.get("required")]
    out = ["<h4>Parameters</h4>"]
    if req and opt:
        r, o = f"req-{cid}", f"opt-{cid}"
        out += ['<div class="param-tabs">',
                f'<button class="param-tab active" onclick="switchParamTab(event, \'{r}\', \'{o}\')">Required</button>',
                f'<button class="param-tab" onclick="switchParamTab(event, \'{o}\', \'{r}\')">Optional</button>',
                "</div>",
                f'<div id="{r}" class="param-tab-content active">', table(req), "</div>",
                f'<div id="{o}" class="param-tab-content">', table(opt), "</div>"]
    elif req or opt:
        out.append(table(req or opt))
    else:
        out.append('<p class="endpoint-desc">No parameters.</p>')
    return "\n".join(out) + "\n"


def body_schema(op):
    try:
        return op["requestBody"]["content"]["application/json"]["schema"]
    except (KeyError, TypeError):
        return None


def json_text(value):
    return json.dumps(value, indent=2, ensure_ascii=False)


def request_body_html(op, res):
    schema = body_schema(op)
    if schema is None:
        return ""
    props = res.deref(schema).get("properties", {})
    required = set(res.deref(schema).get("required", []))
    rows = []
    for name, s in props.items():
        ds = res.deref(s)
        rows.append(f'<tr><td><span class="param-name">{esc(name)}</span></td>'
                    f'<td><span class="param-in">{"required" if name in required else "optional"}</span></td>'
                    f'<td><span class="param-type">{esc(res.type_name(s))}</span></td>'
                    f'<td>{inline_md(ds.get("description", ""))}</td></tr>')
    out = ["<h4>Request Body</h4>"]
    if rows:
        out.append(table(rows))
    out.append('<div class="code-block"><div class="code-block-header"><span>application/json</span>'
               '<button class="copy-btn" onclick="copyCode(this)">Copy</button></div>'
               f'<pre><code>{esc(json_text(res.example(schema)))}</code></pre></div>')
    return "\n".join(out) + "\n"


def response_codes_html(op):
    chips = []
    for code, r in op.get("responses", {}).items():
        cls = "success" if code.startswith("2") else "error"
        chips.append(f'<span class="response-code {cls}">{esc(code)} {esc(r.get("description", ""))}</span>')
    return '<div class="response-codes">' + "".join(chips) + "</div>"


def response_body_html(cid, code, value):
    text = json_text(value)
    lines = text.count("\n") + 1
    rid = f"{cid}-response-{code}"
    collapsed = " response-body-collapsed" if lines > COLLAPSE_OVER else ""
    return f'''<div class="response-body{collapsed}" id="{rid}" data-lines="{lines}">
<div class="response-body-header" onclick="toggleResponseBody(this)">
<span class="response-body-toggle"><span class="response-body-chevron">&#9654;</span> Response Body ({code})</span>
<div class="response-body-actions">
<button class="copy-btn" onclick="event.stopPropagation(); copyResponseBodyCode(this)">Copy</button>
<button class="response-body-link" onclick="copyResponseBodyLink('{rid}', event)" title="Copy link to this response">#</button>
</div>
</div>
<div class="response-body-content">
<div class="response-body-pre">
<div class="response-body-lines"></div>
<code class="response-body-code">{esc(text)}</code>
</div></div>
</div>
'''


def curl_html(method, path, op, res):
    lines = [f'curl -X {method} "{API_HOST}{path}"', '  -H "Authorization: Bearer YOUR_TOKEN"']
    schema = body_schema(op)
    if method in ("POST", "PUT", "PATCH"):
        lines.append('  -H "Content-Type: application/json"')
        body = json_text(res.example(schema)) if schema is not None else "{}"
        lines.append(f"  -d '{body}'")
    cmd = " \\\n".join(lines)
    return ('<div class="code-block"><div class="code-block-header"><span>curl</span>'
            '<button class="copy-btn" onclick="copyCode(this)">Copy</button></div>'
            f'<pre><code>{esc(cmd)}</code></pre></div>')


def search_index(method, path, op):
    words = [method, re.sub(r"[{}/]", " ", path), op.get("summary", ""), first_sentence(op.get("description", ""))]
    words += [p["name"] for p in op.get("parameters", [])]
    toks, seen = [], set()
    for w in re.findall(r"[a-z0-9-]+", " ".join(words).lower()):
        if w not in seen:
            seen.add(w)
            toks.append(w)
    return " ".join(toks)


def success_response_example(op, res):
    for code, r in op.get("responses", {}).items():
        if code.startswith("2"):
            try:
                return code, res.example(r["content"]["application/json"]["schema"])
            except (KeyError, TypeError):
                continue
    return None, None


def render_card(method, path, op, res):
    cid = card_id(method, path)
    code, example = success_response_example(op, res)
    body = response_body_html(cid, code, example) if code else ""
    return f'''<div class="endpoint-card" id="{cid}" data-search="{esc(search_index(method, path, op))}">
<div class="endpoint-header" onclick="toggleEndpoint(this)">
<span class="method-badge {method.lower()}">{method}</span>
<span class="endpoint-path">{esc(path)}</span>
<span class="endpoint-summary">{esc(op.get("summary", ""))}</span>
<button class="endpoint-link-btn" onclick="event.stopPropagation(); copyEndpointLink('{cid}')" title="Copy link to this endpoint">#</button>
<span class="endpoint-chevron">&#9654;</span>
</div>
<div class="endpoint-body">
<div class="endpoint-desc">{md_to_html(op.get("description", ""))}</div>
{params_html(op, res, cid)}{request_body_html(op, res)}
<h4>Responses</h4>
{response_codes_html(op)}
{body}
{curl_html(method, path, op, res)}
</div></div>
'''


# --------------------------------------------------------------------------- html surgery
CARD_RE = re.compile(r'<div class="endpoint-card" id="([^"]+)"')
GROUP_RE = re.compile(r'<div class="tag-group" id="([^"]+)">')


def card_span(doc, cid):
    m = re.search(rf'<div class="endpoint-card" id="{re.escape(cid)}"', doc)
    if not m:
        return None
    nxt = re.compile(r'<div class="endpoint-card" id=|<div class="tag-group" id=|</section>').search(doc, m.end())
    return m.start(), nxt.start()


def update_card(doc, method, path, op, res):
    cid = card_id(method, path)
    span = card_span(doc, cid)
    s, e = span
    card = doc[s:e]
    card = re.sub(r'data-search="[^"]*"', f'data-search="{esc(search_index(method, path, op))}"', card, count=1)
    card = re.sub(r'<span class="endpoint-summary">.*?</span>', f'<span class="endpoint-summary">{esc(op.get("summary", ""))}</span>', card, count=1, flags=re.S)
    card = re.sub(r'<(p|div) class="endpoint-desc">.*?</\1>\n', f'<div class="endpoint-desc">{md_to_html(op.get("description", ""))}</div>\n', card, count=1, flags=re.S)
    # parameters (+ request body) block runs from <h4>Parameters</h4> to <h4>Responses</h4>
    card = re.sub(r'<h4>Parameters</h4>.*?(?=<h4>Responses</h4>)', lambda _: params_html(op, res, cid) + request_body_html(op, res) + "\n", card, count=1, flags=re.S)
    card = re.sub(r'<div class="response-codes">.*?</div>\n', lambda _: response_codes_html(op) + "\n", card, count=1, flags=re.S)
    # curl: fill an empty -d '{}' with the spec's example body
    schema = body_schema(op)
    if schema is not None and "-d '{}'" in card:
        card = card.replace("-d '{}'", "-d '" + esc(json_text(res.example(schema))) + "'", 1)
    return doc[:s] + card + doc[e:]


def group_span(doc, slug):
    m = re.search(rf'<div class="tag-group" id="{re.escape(slug)}">', doc)
    if not m:
        return None
    nxt = re.compile(r'<div class="tag-group" id=|</section>').search(doc, m.end())
    return m.start(), nxt.start()


def append_to_group(doc, slug, card_html):
    s, e = group_span(doc, slug)
    region = doc[s:e]
    close = region.rindex("\n</div>\n")  # the tag-group's own closing div
    region = region[:close] + "\n" + card_html + region[close:]
    return doc[:s] + region + doc[e:]


def create_group(doc, tag, after_slug):
    slug = tag_slug(tag)
    block = f'\n<!-- {esc(tag)} -->\n<div class="tag-group" id="{slug}">\n<div class="tag-group-header"><h3>{esc(tag)}</h3><span class="tag-count">0 endpoints</span></div>\n\n</div>\n'
    s, e = group_span(doc, after_slug)
    doc = doc[:e] + block + doc[e:]
    # sidebar link after the preceding group's link
    link = f'  <a href="#{slug}" class="sidebar-link" onclick="closeMobile()">{esc(tag)} <span class="link-badge mixed">0</span></a>\n'
    m = re.search(rf'  <a href="#{re.escape(after_slug)}"[^\n]*\n', doc)
    doc = doc[:m.end()] + link + doc[m.end():]
    return doc


def recount(doc, groups):
    """groups: slug -> list of methods"""
    for slug, methods in groups.items():
        n = len(methods)
        label = f"{n} endpoint{'s' if n != 1 else ''}"
        doc = re.sub(rf'(<div class="tag-group" id="{slug}">\n<div class="tag-group-header"><h3>[^<]*</h3><span class="tag-count">)[^<]*(</span>)', rf'\g<1>{label}\2', doc)
        kinds = {m.lower() for m in methods}
        badge = kinds.pop() if len(kinds) == 1 else "mixed"
        doc = re.sub(rf'(<a href="#{slug}"[^>]*>[^<]*<span class="link-badge )[a-z]+(">)\d+(</span>)', rf'\g<1>{badge}\g<2>{n}\3', doc)
    return doc


# --------------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", default=DEFAULT_SPEC)
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    spec = load_spec(args.spec)
    print(f"  internal fields stripped: {strip_internal(spec)}")
    res = Resolver(spec)
    doc = INDEX.read_text()
    existing = set(CARD_RE.findall(doc))
    ops = list(iter_ops(spec))

    spec_ids = {card_id(m, p) for m, p, _ in ops}
    stale = sorted(existing - spec_ids)
    groups = {}
    added, updated = [], []
    for method, path, op in ops:
        tag = (op.get("tags") or ["Other"])[0]
        slug = tag_slug(tag)
        groups.setdefault(slug, []).append(method)
        cid = card_id(method, path)
        if cid in existing:
            doc = update_card(doc, method, path, op, res)
            updated.append(cid)
        else:
            if group_span(doc, slug) is None:
                # new tag group goes after the last group that exists so far
                last = GROUP_RE.findall(doc)[-1]
                doc = create_group(doc, tag, last)
            doc = append_to_group(doc, slug, render_card(method, path, op, res))
            added.append(cid)
    doc = recount(doc, groups)

    print(f"spec: {args.spec}\n  operations in spec: {len(ops)}\n  cards updated: {len(updated)}\n  cards added: {len(added)}")
    for c in added:
        print(f"    + {c}")
    if stale:
        print(f"  cards with no spec operation (left in place, review by hand): {stale}")
    before = (doc.count("<div"), doc.count("</div>"))
    if before[0] != before[1]:
        print(f"  WARNING: unbalanced <div> ({before[0]} open / {before[1]} close)", file=sys.stderr)
    if args.write:
        INDEX.write_text(doc)
        print(f"  wrote {INDEX}")
    else:
        print("  dry run — pass --write to apply")


if __name__ == "__main__":
    main()
