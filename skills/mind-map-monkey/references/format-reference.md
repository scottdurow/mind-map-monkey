# Mind Map Monkey file format

This is the format that `scripts/validate_mmd.py` enforces. It comes from the Mind Map Monkey file format specification and the documented parser behaviour of the app. The app's parser source could not be retrieved, so open a new kind of file once in the app before relying on it.

## The whole file

- Raw UTF-8 text with the `.mmd` extension. There is no byte-order mark, no JSON, no Markdown code fence and no commentary around the map.
- Line 1 is exactly `mindmap`.
- Exactly one root, indented by two spaces and written `id((Title))`.
- Every deeper level adds exactly two spaces. Write spaces only. The parser counts a tab as four spaces, but the validator rejects tabs.
- Blank lines are allowed and ignored. Do not write `%%{` directives.

## Node lines

| Written as | Meaning |
|---|---|
| `id((Label))` | The root. Only the root uses this shape. |
| `id))Label((` | High importance. Use it on one to three nodes. |
| `id(Label)` | Medium importance. This is the normal case. |
| `id[Label]` | Low importance. Use it for supporting detail. |

- Every node has an explicit id that matches `^[A-Za-z0-9_](?:[A-Za-z0-9_-]{0,62}[A-Za-z0-9_])?$`. That is 1 to 64 letters, digits, underscores or hyphens, and it cannot start or end with a hyphen. Ids are unique in the file. `new_id()` makes ids in the app's style, such as `n3k9x0qa`.
- The parser also reads `{{…}}`, `)…(` and bare labels as medium. The validator rejects them so importance stays explicit.
- A label is one line. It contains no `(`, `)`, `[`, `]`, `{` or `}`. `sanitise_label()` turns those characters into spaces. Rephrase when the result reads badly.
- Keep labels to one to three words, five at most. Put the detail in descriptions.
- Write classes on their own line, never inline after `:::` on the node line.

## Metadata lines

Metadata sits immediately after its node, at the same indentation, in this order:

1. `::icon(lucide lucide-<key>)` (optional, at most one)
2. `:::color-<colour> size-<size>` (write it on every node)
3. `%% @tags a, b` (optional, at most one line)
4. `%% @link <targetId> | <label>` (optional, any number)
5. `%% description text` (optional, any number)

The app's writer puts `%% @at` and `%% @dir` between the class line and the tags line. This skill never writes them, so the app lays the map out itself. The validator rejects them.

### Values

- Colours: brand, sky, teal, emerald, lime, amber, orange, rose, fuchsia, violet, slate.
- Sizes: small, medium, large. Use large for the root, medium for branches and ordinary nodes, and small for fine detail.
- Icons: lightbulb, target, flag, star, book, users, rocket, heart, settings, calendar, code, globe, megaphone, shield, wallet. The parser also knows aliases such as `idea` or `team`. Write the canonical key.

### Tags

`normalise_tag()` does what the app does. It trims, drops one leading `#`, lower-cases, turns spaces into hyphens, keeps only letters, combining marks, digits, `-`, `_`, `.`, `+` and `/`, collapses runs of hyphens, cuts to 40 characters and trims hyphens from both ends. A tag that ends up empty is dropped. `normalise_tags()` also removes duplicates, sorts the list and keeps at most 24. Write one tags line per node with no colon after `@tags`.

### Association links

- `%% @link target_id | depends on` is written on the node the label reads from.
- The target must be another node in the same file. It cannot be the node itself, its parent or its child.
- One link per pair of nodes, in either direction.
- The label is optional, one line, single-spaced and at most 60 characters. Label every link the skill writes, and only with a relationship the source supports.

### Descriptions

- Each `%% text` line is one line of the description.
- Simple Markdown works: `**bold**`, `*italic*`, `` `code` `` and `[text](https://url)`. Only http, https and mailto links are clickable.
- When the text starts with `@` or `\`, add a backslash after `%% `, so `@owner` becomes `%% \@owner` and `\server` becomes `%% \\server`. `escape_description()` does this.

## Limits

| Limit | Value |
|---|---|
| Nodes, root included | 2,000 |
| Levels, root included | 64 |
| File size | 1,000,000 UTF-8 bytes |

When a map goes over a limit, ask the user to narrow the scope or approve separate maps. Never truncate.

## Validator output

```
python scripts/validate_mmd.py working/mmm/<file>.mmd
```

It prints JSON with `ok`, `stats` (bytes, nodes, depth, links, high_importance, top_level_branches), `errors` and `warnings`. Each entry has `line`, `code` and `message`. Exit code 0 means no errors, 1 means at least one error, and 2 means the file could not be read. Fix every error before uploading. Read the warnings and fix the ones that matter for the map's design.
