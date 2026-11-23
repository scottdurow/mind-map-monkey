#!/usr/bin/env python3
"""Validate a Mind Map Monkey .mmd file before it is uploaded.

Standard library only. The checks follow the Mind Map Monkey file format
(the Mind Map Monkey format specification) and the parser behaviour recorded in the existing
mind-map skill. The app's own parser source was not available when this was
written, so a file that passes here should still be opened once in the app.

Usage:
    python validate_mmd.py path/to/map.mmd          # JSON report on stdout
    python validate_mmd.py - < map.mmd               # read from stdin

Exit codes: 0 = no errors (warnings allowed), 1 = at least one error,
2 = the file could not be read.

Helpers for the generator (import this module):
    normalise_tag(text)        -> the app's normalised tag, or "" to drop it
    normalise_tags(iterable)   -> de-duplicated, sorted list, at most 24 tags
    sanitise_label(text)       -> one-line label with no brackets or braces
    escape_description(text)   -> description text safe to put after "%% "
    safe_filename(title)       -> a descriptive OneDrive-safe .mmd file name
    new_id(existing)           -> a fresh id like the app's, unique in `existing`
"""
from __future__ import annotations

import json
import re
import secrets
import string
import sys
import unicodedata

# ---------------------------------------------------------------- limits
MAX_NODES = 2000
MAX_DEPTH = 64           # levels, including the root
_META_LABEL = re.compile(r"(sources?\s+(differ|disagree|notes?|comparison|check)|where\s+.*sources|methodology|\bmeta\b|about\s+th(is|ese)\s+sources?)", re.I)
MAX_BYTES = 1_000_000    # UTF-8 bytes
MAX_TAGS_PER_NODE = 24
MAX_TAG_CHARS = 40
MAX_LINK_LABEL = 60

ID_RE = re.compile(r"^[A-Za-z0-9_](?:[A-Za-z0-9_-]{0,62}[A-Za-z0-9_])?$")
COLOURS = ("brand", "sky", "teal", "emerald", "lime", "amber", "orange",
           "rose", "fuchsia", "violet", "slate")
SIZES = ("small", "medium", "large")
ICONS = ("lightbulb", "target", "flag", "star", "book", "users", "rocket",
         "heart", "settings", "calendar", "code", "globe", "megaphone",
         "shield", "wallet")
ICON_ALIASES = {
    "idea": "lightbulb", "bulb": "lightbulb", "goal": "target",
    "bullseye": "target", "milestone": "flag", "favorite": "star",
    "read": "book", "docs": "book", "people": "users", "team": "users",
    "group": "users", "launch": "rocket", "love": "heart", "cog": "settings",
    "gear": "settings", "date": "calendar", "schedule": "calendar",
    "dev": "code", "terminal": "code", "world": "globe", "web": "globe",
    "bullhorn": "megaphone", "marketing": "megaphone", "security": "shield",
    "lock": "shield", "money": "wallet", "budget": "wallet",
    "dollar": "wallet",
}
BRACKETS = "()[]{}"

# Metadata line kinds, in the order the app writes them.
ORDER = {"icon": 0, "class": 1, "tags": 2, "link": 3, "desc": 4}
ONCE = {"icon", "class", "tags"}

SHAPES = (
    # (kind, regex). Root form first so "((x))" is not read as medium "(x)".
    ("root", re.compile(r"^(?P<id>[^\s()\[\]{}]*)\(\((?P<label>.*)\)\)$")),
    ("high", re.compile(r"^(?P<id>[^\s()\[\]{}]*)\)\)(?P<label>.*)\(\($")),
    ("medium", re.compile(r"^(?P<id>[^\s()\[\]{}]*)\((?P<label>.*)\)$")),
    ("low", re.compile(r"^(?P<id>[^\s()\[\]{}]*)\[(?P<label>.*)\]$")),
)
NONCANONICAL = (
    re.compile(r"^[^\s()\[\]{}]*\{\{.*\}\}$"),
    re.compile(r"^[^\s()\[\]{}]*\).*\($"),
)


# ---------------------------------------------------------------- helpers
def _tag_char_ok(ch: str) -> bool:
    if ch in "-_.+/":
        return True
    cat = unicodedata.category(ch)
    return cat[0] in ("L", "M") or cat == "Nd"


def normalise_tag(text: str) -> str:
    """Return the tag as the app stores it, or "" when nothing is left.

    Trim, drop one leading '#', lower-case, turn inner whitespace into '-',
    remove every disallowed character, collapse runs of hyphens, cut to 40
    characters and trim hyphens from both ends.
    """
    t = (text or "").strip()
    if t.startswith("#"):
        t = t[1:]
    t = t.lower()
    t = re.sub(r"\s+", "-", t)
    t = "".join(ch for ch in t if _tag_char_ok(ch))
    t = re.sub(r"-{2,}", "-", t)
    t = t[:MAX_TAG_CHARS]
    return t.strip("-")


def normalise_tags(tags) -> list:
    """Normalise, drop empties, de-duplicate, sort and cap at 24."""
    out = sorted({normalise_tag(t) for t in tags} - {""})
    return out[:MAX_TAGS_PER_NODE]


def sanitise_label(text: str) -> str:
    """Make a one-line label: brackets and braces become spaces, any line
    break or tab becomes a space, runs of spaces collapse, ends are trimmed."""
    t = (text or "").replace("<br>", " ").replace("<br/>", " ")
    t = "".join(" " if ch in BRACKETS else ch for ch in t)
    t = re.sub(r"\s+", " ", t)
    return t.strip()


def escape_description(text: str) -> str:
    """Prefix a backslash when a description line starts with '@' or '\\'."""
    t = (text or "").replace("\r", " ").replace("\n", " ")
    if t.startswith("@") or t.startswith("\\"):
        return "\\" + t
    return t


_BAD_NAME_CHARS = re.compile(r'[\\/:*?"<>|#%\x00-\x1f]')


def safe_filename(title: str, max_len: int = 80) -> str:
    """A descriptive lower-case .mmd file name that OneDrive accepts."""
    t = unicodedata.normalize("NFC", title or "").strip().lower()
    t = _BAD_NAME_CHARS.sub(" ", t)
    t = "".join(" " if ch in BRACKETS else ch for ch in t)
    t = re.sub(r"[\s_]+", "-", t)
    t = re.sub(r"-{2,}", "-", t).strip("-.")
    t = t[:max_len].strip("-.") or "mind-map"
    return t + ".mmd"


def new_id(existing=()) -> str:
    """An id in the app's own style: 'n' plus seven lower-case letters/digits."""
    alphabet = string.ascii_lowercase + string.digits
    taken = set(existing)
    while True:
        cand = "n" + "".join(secrets.choice(alphabet) for _ in range(7))
        if cand not in taken:
            return cand


# ---------------------------------------------------------------- validator
class _Report:
    def __init__(self):
        self.errors = []
        self.warnings = []

    def err(self, line, code, msg):
        self.errors.append({"line": line, "code": code, "message": msg})

    def warn(self, line, code, msg):
        self.warnings.append({"line": line, "code": code, "message": msg})


def _parse_node(content: str):
    """Return (kind, id, label) or None when no canonical shape matches."""
    for kind, rx in SHAPES:
        m = rx.match(content)
        if m:
            return kind, m.group("id"), m.group("label")
    return None


def validate_bytes(data: bytes) -> dict:
    rep = _Report()
    stats = {"bytes": len(data), "nodes": 0, "depth": 0, "links": 0,
             "high_importance": 0, "top_level_branches": 0}

    if len(data) > MAX_BYTES:
        rep.err(None, "too-large",
                f"The file is {len(data):,} bytes, over the {MAX_BYTES:,}-byte limit. "
                "Ask the user to narrow the scope or approve separate maps. Never truncate.")
    if data.startswith(b"\xef\xbb\xbf"):
        rep.err(1, "bom", "Remove the UTF-8 byte-order mark. The file must start with 'mindmap'.")
        data = data[3:]
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        rep.err(None, "not-utf8", f"The file is not valid UTF-8 ({exc}).")
        return _result(rep, stats)

    stripped = text.lstrip()
    if stripped.startswith("{") or stripped.startswith("["):
        rep.err(1, "json", "The file looks like JSON. Save raw Mermaid mindmap text.")
        return _result(rep, stats)
    if "\r" in text:
        rep.warn(None, "crlf", "Use LF line endings. Carriage returns were found.")
        text = text.replace("\r\n", "\n").replace("\r", "\n")

    lines = text.split("\n")
    for i, ln in enumerate(lines, 1):
        if ln.lstrip().startswith("```"):
            rep.err(i, "code-fence", "Remove the Markdown code fence. Save the mindmap text only.")
    if any(e["code"] == "code-fence" for e in rep.errors):
        return _result(rep, stats)

    if not lines or lines[0] != "mindmap":
        rep.err(1, "header", "The first line must be exactly 'mindmap'.")
        return _result(rep, stats)

    nodes = {}          # id -> dict(line, depth, parent, kind)
    order = []          # ids in file order
    stack = []          # list of (indent, id)
    current = None      # id of the node whose metadata we are reading
    cur_indent = None
    cur_last = -1       # last metadata ORDER value seen for current node
    cur_seen = set()
    pending_links = []  # (line, source, target, label)
    root_id = None
    root_indent = None

    for i, raw in enumerate(lines[1:], 2):
        if raw.strip() == "":
            continue
        if "\t" in raw[: len(raw) - len(raw.lstrip())]:
            rep.err(i, "tab-indent", "Indent with spaces only (two per level), never tabs.")
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        content = raw.strip(" ")
        if raw != raw.rstrip():
            rep.warn(i, "trailing-space", "Remove trailing whitespace.")
            content = content.rstrip()
        if indent % 2:
            rep.err(i, "odd-indent", "Indentation must be a multiple of two spaces.")
            continue

        # ---- metadata lines -------------------------------------------
        kind = None
        if content.startswith("%%{"):
            rep.warn(i, "directive", "Mermaid directive line found. This skill should not write directives.")
            continue
        if content.startswith("::icon("):
            kind = "icon"
        elif content.startswith(":::"):
            kind = "class"
        elif content.startswith("%%"):
            body = content[2:]
            body_s = body[1:] if body.startswith(" ") else body
            low = body_s.lower()
            if re.match(r"@tags(?![^\s:])", low):
                kind = "tags"
            elif re.match(r"@link(?!\S)", low):
                kind = "link"
            elif re.match(r"@(at|dir)(?!\S)", low):
                rep.err(i, "positioning", "Omit '@at' and '@dir' lines so the app lays the map out itself.")
                continue
            else:
                kind = "desc"

        if kind is not None:
            if current is None:
                rep.err(i, "orphan-metadata", "Metadata appears before any node.")
                continue
            if indent != cur_indent:
                rep.err(i, "metadata-indent",
                        f"Metadata must sit at the same indentation as its node ({cur_indent} spaces).")
            rank = ORDER[kind]
            if kind in ONCE and kind in cur_seen:
                rep.err(i, "metadata-repeat", f"Only one {kind} line is allowed per node.")
            elif rank < cur_last:
                rep.err(i, "metadata-order",
                        "Metadata order is: icon, class, tags, links, then description lines.")
            cur_last = max(cur_last, rank)
            cur_seen.add(kind)
            _check_meta(rep, i, kind, content, current, pending_links)
            continue

        # ---- node line --------------------------------------------------
        if ":::" in content:
            rep.err(i, "inline-class", "Write the ':::color-… size-…' classes on their own line.")
            content = content.split(":::", 1)[0].rstrip()
        parsed = _parse_node(content)
        if parsed is None:
            if any(rx.match(content) for rx in NONCANONICAL):
                rep.err(i, "shape", "Use one of the four shapes: id((root)), id))high((, id(medium), id[low].")
            else:
                rep.err(i, "shape", "This line is not a node with an id and a supported shape.")
            continue
        shape, nid, label = parsed
        if not nid:
            rep.err(i, "missing-id", "Every node needs an explicit id before its shape.")
            continue
        if not ID_RE.match(nid):
            rep.err(i, "bad-id",
                    f"Id '{nid}' must be 1-64 letters, digits, '_' or '-', not starting or ending with '-'.")
        if nid in nodes:
            rep.err(i, "duplicate-id", f"Id '{nid}' is already used on line {nodes[nid]['line']}.")
        _check_label(rep, i, label)

        # hierarchy
        if root_id is None:
            if indent != 2:
                rep.err(i, "root-indent", "The root node must be indented by exactly two spaces.")
            if shape != "root":
                rep.err(i, "root-shape", "The root must be written as id((Title)).")
            root_id, root_indent = nid, indent
            depth, parent = 1, None
            stack = [(indent, nid)]
        else:
            if shape == "root":
                rep.err(i, "root-shape-reused", "Only the root may use the ((…)) shape.")
            if indent <= root_indent:
                rep.err(i, "second-root", "A mindmap has exactly one root. This node is at root level.")
                continue
            while stack and stack[-1][0] >= indent:
                stack.pop()
            parent_indent, parent = stack[-1]
            if indent != parent_indent + 2:
                rep.err(i, "indent-jump",
                        f"A child must be indented exactly two spaces deeper than its parent ({parent_indent + 2}).")
            depth = nodes[parent]["depth"] + 1 if parent in nodes else len(stack) + 1
            stack.append((indent, nid))
            if parent == root_id:
                stats["top_level_branches"] += 1
        if shape == "high":
            stats["high_importance"] += 1
        if nid not in nodes:
            nodes[nid] = {"line": i, "depth": depth, "parent": parent, "kind": shape, "label": label}
            order.append(nid)
        stats["depth"] = max(stats["depth"], depth)
        if current is not None and "class" not in cur_seen:
            rep.warn(nodes[current]["line"], "no-class",
                     f"Node '{current}' has no ':::color-… size-…' line. Write one on every node.")
        current, cur_indent, cur_last, cur_seen = nid, indent, -1, set()

    if current is not None and "class" not in cur_seen:
        rep.warn(nodes[current]["line"], "no-class",
                 f"Node '{current}' has no ':::color-… size-…' line. Write one on every node.")
    if root_id is None:
        rep.err(None, "no-root", "The file has no root node.")

    stats["nodes"] = len(nodes)
    if stats["nodes"] > MAX_NODES:
        rep.err(None, "too-many-nodes",
                f"{stats['nodes']} nodes is over the {MAX_NODES}-node limit. "
                "Ask the user to narrow the scope or approve separate maps.")
    if stats["depth"] > MAX_DEPTH:
        rep.err(None, "too-deep",
                f"{stats['depth']} levels is over the {MAX_DEPTH}-level limit (root included). "
                "Ask the user to narrow the scope or approve separate maps.")

    # ---- links -----------------------------------------------------------
    pairs = {}
    for line, src, tgt, _label in pending_links:
        if tgt not in nodes:
            rep.err(line, "link-target-missing", f"Link target '{tgt}' is not a node in this file.")
            continue
        if tgt == src:
            rep.err(line, "link-self", "A node cannot link to itself.")
            continue
        if nodes[src]["parent"] == tgt or nodes[tgt]["parent"] == src:
            rep.err(line, "link-parent-child", "Do not link a node to its own parent or child.")
            continue
        key = frozenset((src, tgt))
        if key in pairs:
            rep.err(line, "link-duplicate-pair",
                    f"Nodes '{src}' and '{tgt}' are already linked on line {pairs[key]}. One link per pair.")
            continue
        pairs[key] = line
    stats["links"] = len(pairs)

    # ---- design warnings ----------------------------------------------------
    if stats["high_importance"] > 3:
        rep.warn(None, "too-many-high", "Keep high importance for one to three nodes.")
    if root_id and stats["nodes"] >= 30 and stats["depth"] < 6:
        rep.warn(None, "shallow",
                 f"The map goes {stats['depth'] - 1} levels below the root. Readers can collapse "
                 "branches, so go at least five levels deep where the source has the detail.")
    for nid, info in nodes.items():
        if info["parent"] == root_id and _META_LABEL.search(info.get("label", "")):
            rep.warn(info["line"], "meta-branch",
                     "This main branch looks like a note about the sources. Keep the map on its "
                     "subject and put source notes on the nodes they qualify.")
    if root_id and not (3 <= stats["top_level_branches"] <= 7):
        rep.warn(None, "branch-count",
                 f"{stats['top_level_branches']} main branches. Three to seven read best.")
    return _result(rep, stats)


def _check_label(rep, i, label):
    if label.strip() == "":
        rep.err(i, "empty-label", "The label is empty.")
        return
    bad = sorted({ch for ch in label if ch in BRACKETS})
    if bad:
        rep.err(i, "label-brackets",
                f"Label contains {' '.join(bad)}. Replace brackets and braces with spaces (sanitise_label).")
    if "<br" in label.lower():
        rep.err(i, "label-multiline", "Keep labels on one line, with no <br>.")
    if label != label.strip():
        rep.warn(i, "label-space", "Trim spaces at the ends of the label.")
    if len(label.split()) > 5:
        rep.warn(i, "long-label", "Labels read best at one to three words, five at most.")


def _check_meta(rep, i, kind, content, current, pending_links):
    if kind == "icon":
        m = re.match(r"^::icon\(lucide lucide-([A-Za-z0-9_-]+)\)$", content)
        if not m:
            rep.err(i, "icon-syntax", "Write icons as ::icon(lucide lucide-<key>).")
        elif m.group(1) not in ICONS:
            hint = ICON_ALIASES.get(m.group(1).lower())
            extra = f" Use '{hint}'." if hint else f" Valid keys: {', '.join(ICONS)}."
            rep.err(i, "icon-unknown", f"Icon '{m.group(1)}' is not a supported key.{extra}")
    elif kind == "class":
        tokens = content[3:].split()
        seen = {}
        if not tokens:
            rep.err(i, "class-empty", "The class line is empty.")
        for tok in tokens:
            if tok.startswith("color-"):
                if tok[6:] not in COLOURS:
                    rep.err(i, "colour-unknown", f"Colour '{tok[6:]}' is not one of: {', '.join(COLOURS)}.")
                key = "color"
            elif tok.startswith("size-"):
                if tok[5:] not in SIZES:
                    rep.err(i, "size-unknown", f"Size '{tok[5:]}' is not small, medium or large.")
                key = "size"
            else:
                rep.err(i, "class-unknown", f"Unknown class '{tok}'. Use color-<name> and size-<name>.")
                continue
            if key in seen:
                rep.err(i, "class-repeat", f"More than one {key} class on one node.")
            seen[key] = tok
    elif kind == "tags":
        body = content[2:].lstrip()
        rest = body[5:]
        if rest.startswith(":"):
            rep.err(i, "tags-colon", "Write '%% @tags a, b' without a colon.")
            rest = rest[1:]
        raw = [t.strip() for t in rest.split(",")] if rest.strip() else []
        if not raw:
            rep.warn(i, "tags-empty", "An empty tags line has no effect. Remove it.")
            return
        for t in raw:
            if len(t) > MAX_TAG_CHARS:
                rep.err(i, "tag-too-long", f"Tag '{t[:20]}…' is over {MAX_TAG_CHARS} characters.")
            elif normalise_tag(t) != t:
                rep.err(i, "tag-not-normalised",
                        f"Tag '{t}' is not normalised. Write '{normalise_tag(t)}'.")
        if len(raw) != len(set(raw)):
            rep.err(i, "tag-duplicate", "Tags on one node must be unique.")
        if raw != sorted(raw):
            rep.err(i, "tag-order", "Sort the tags alphabetically, as the app writes them.")
        if len(raw) > MAX_TAGS_PER_NODE:
            rep.err(i, "too-many-tags", f"{len(raw)} tags is over the {MAX_TAGS_PER_NODE}-tag limit.")
    elif kind == "link":
        body = content[2:].lstrip()[5:].strip()
        target, sep, label = body.partition("|")
        target, label = target.strip(), label.strip()
        if not target:
            rep.err(i, "link-syntax", "Write links as '%% @link <targetId> | <label>'.")
            return
        if not ID_RE.match(target):
            rep.err(i, "link-target-id", f"'{target}' is not a valid node id.")
            return
        if sep and not label:
            rep.warn(i, "link-label-empty", "Remove the '|' or add a label.")
        if not sep:
            rep.warn(i, "link-unlabelled", "Label each link with the relationship, such as 'depends on'.")
        if len(label) > MAX_LINK_LABEL:
            rep.err(i, "link-label-long", f"Link label is {len(label)} characters, over {MAX_LINK_LABEL}.")
        if re.search(r"\s{2,}|\t", label):
            rep.err(i, "link-label-space", "Use single spaces between words in a link label.")
        pending_links.append((i, current, target, label))
    elif kind == "desc":
        body = content[2:]
        text = body[1:] if body.startswith(" ") else body
        if text.startswith("@"):
            rep.err(i, "desc-unescaped-at",
                    "A description line starting with '@' must be escaped as '\\@' (escape_description).")
        elif text.startswith("\\") and not (text.startswith("\\@") or text.startswith("\\\\")):
            rep.err(i, "desc-unescaped-backslash",
                    "A description line starting with '\\' must be escaped as '\\\\' (escape_description).")
        for url in re.findall(r"\]\(([^)\s]+)\)", text):
            if not re.match(r"^(https?:|mailto:)", url, re.I):
                rep.warn(i, "desc-link-scheme", f"Only http, https and mailto links are clickable: {url[:60]}")


def _result(rep, stats):
    return {"ok": not rep.errors, "stats": stats,
            "errors": rep.errors, "warnings": rep.warnings}


def validate_text(text: str) -> dict:
    return validate_bytes(text.encode("utf-8"))


def validate_file(path: str) -> dict:
    with open(path, "rb") as fh:
        return validate_bytes(fh.read())


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1 or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 2
    try:
        if argv[0] == "-":
            result = validate_bytes(sys.stdin.buffer.read())
        else:
            result = validate_file(argv[0])
    except OSError as exc:
        print(json.dumps({"ok": False, "errors": [{"line": None, "code": "io", "message": str(exc)}],
                          "warnings": []}))
        return 2
    result["file"] = argv[0]
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
