"""Offline tests for the Mind Map Monkey skill scripts.

Run from the skill folder:
    python -m unittest discover -s tests -v
Standard library only. No network and no OneDrive access.
"""
import json
import os
import re
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
FIX = os.path.join(HERE, "fixtures")
SRC = os.path.join(FIX, "sources")
sys.path.insert(0, os.path.join(SKILL, "scripts"))

import validate_mmd as v  # noqa: E402
import build_app_link as b  # noqa: E402

APP = "https://example.invalid/apps/00000000-0000-0000-0000-000000000000"


def read(*parts):
    with open(os.path.join(*parts), encoding="utf-8") as fh:
        return fh.read()


def codes(result):
    return {e["code"] for e in result["errors"]}


def base_map(extra=""):
    return ("mindmap\n"
            "  r((Root))\n"
            "  :::color-brand size-large\n"
            "    a(Alpha)\n"
            "    :::color-sky size-medium\n"
            "      a1[Alpha one]\n"
            "      :::color-sky size-small\n"
            "    b(Beta)\n"
            "    :::color-teal size-medium\n"
            "    c(Gamma)\n"
            "    :::color-amber size-medium\n" + extra)


class ValidMaps(unittest.TestCase):
    def check_valid(self, name):
        res = v.validate_file(os.path.join(FIX, name))
        self.assertTrue(res["ok"], res["errors"])
        return res, read(FIX, name)

    def test_document_map_with_page_refs(self):
        res, text = self.check_valid("document_map.mmd")
        source = read(SRC, "pilot-proposal.txt")
        pages = set(re.findall(r"p\. (\d+)", text))
        self.assertTrue(pages, "page references expected in descriptions")
        for p in pages:  # every cited page exists in the source
            self.assertIn(f"[Page {p}]", source)
        self.assertIn("*Inference:*", text)  # inference marked apart from source statements

    def test_video_transcript_map(self):
        res, text = self.check_valid("video_map.mmd")
        source = read(SRC, "video-transcript.txt")
        stamps = re.findall(r"\b\d\d:\d\d:\d\d\b", text)
        self.assertTrue(stamps)
        for s in stamps:  # no invented timestamps
            self.assertIn(f"[{s}]", source)
        self.assertIn("Transcript only", text)
        self.assertIn("visual content may be missing", text)

    def test_teams_transcript_map(self):
        res, text = self.check_valid("teams_map.mmd")
        source = read(SRC, "teams-transcript.txt")
        for branch in ("(Topics)", "(Decisions)", "(Actions)", "(Risks)", "(Open questions)"):
            self.assertIn(branch, text)
        owners = re.findall(r"Owner: ([^.]+)\.", text)
        self.assertIn("not stated", owners)
        for owner in owners:  # owners only when stated in the transcript
            if owner != "not stated":
                self.assertIn(f"{owner}: I will", source)
        for due in re.findall(r"Due: ([^.]+)\.", text):
            if due != "not stated":
                self.assertIn(due, source)
        for s in re.findall(r"\b\d\d:\d\d:\d\d\b", text):
            self.assertIn(f"[{s}]", source)

    def test_multiple_sources_with_conflict(self):
        res, text = self.check_valid("multi_source_map.mmd")
        self.assertIn("https://example.com/field-notes/rollout", text)
        self.assertIn("%% @tags conflict", text)
        self.assertIn("contradicts", text)
        self.assertIn("The sources disagree", text)
        self.assertIn("%% \\@vendor", text)  # escaped description line is accepted

    def test_spec_example_is_valid(self):
        example = ("mindmap\n  root((Project review))\n  :::color-brand size-large\n"
                   "    decision))Approve pilot((\n    :::color-teal size-medium\n"
                   "    %% @tags decision, pilot\n    %% Source: meeting transcript, 00:12:08.\n"
                   "    action(Prepare pilot plan)\n    :::color-amber size-medium\n"
                   "    %% @tags action\n    %% @link decision | implements\n")
        res = v.validate_text(example)
        self.assertTrue(res["ok"], res["errors"])

    def test_cli_exit_codes(self):
        script = os.path.join(SKILL, "scripts", "validate_mmd.py")
        ok = subprocess.run([sys.executable, script, os.path.join(FIX, "document_map.mmd")],
                            capture_output=True, text=True)
        self.assertEqual(ok.returncode, 0)
        self.assertTrue(json.loads(ok.stdout)["ok"])
        bad = subprocess.run([sys.executable, script, "-"], input=b"not a map",
                             capture_output=True)
        self.assertEqual(bad.returncode, 1)


class InvalidMaps(unittest.TestCase):
    def assertError(self, text, code):
        res = v.validate_text(text) if isinstance(text, str) else v.validate_bytes(text)
        self.assertFalse(res["ok"])
        self.assertIn(code, codes(res), res["errors"])

    def test_base_map_is_valid(self):
        self.assertTrue(v.validate_text(base_map())["ok"])

    def test_header_missing(self):
        self.assertError(base_map().replace("mindmap\n", "graph TD\n", 1), "header")

    def test_duplicate_ids(self):
        self.assertError(base_map("    a(Again)\n    :::color-lime size-medium\n"), "duplicate-id")

    def test_bad_ids(self):
        for bad in ("-a", "a-", "a b", "a.b", "x" * 65):
            text = base_map(f"    {bad}(Bad)\n    :::color-lime size-medium\n")
            res = v.validate_text(text)
            self.assertFalse(res["ok"], bad)
        self.assertTrue(v.validate_text(base_map("    a_b-9(Ok)\n    :::color-lime size-medium\n"))["ok"])

    def test_missing_id(self):
        self.assertError(base_map("    (No id)\n    :::color-lime size-medium\n"), "missing-id")

    def test_brackets_in_labels(self):
        self.assertError(base_map("    d(Budget (Q3))\n    :::color-lime size-medium\n"), "label-brackets")
        self.assertError(base_map("    d[List [x]]\n    :::color-lime size-medium\n"), "label-brackets")
        self.assertError(base_map("    d(Set {a})\n    :::color-lime size-medium\n"), "label-brackets")

    def test_noncanonical_shape(self):
        self.assertError(base_map("    d{{Hex}}\n    :::color-lime size-medium\n"), "shape")
        self.assertError(base_map("    d(Odd)extra\n"), "shape")

    def test_two_roots(self):
        self.assertError(base_map("  r2((Other root))\n"), "second-root")

    def test_indentation(self):
        self.assertError(base_map("         z(Odd)\n"), "odd-indent")
        self.assertError(base_map("        z(Jump)\n        :::color-lime size-medium\n"), "indent-jump")
        self.assertError(base_map("\tz(Tab)\n"), "tab-indent")

    def test_bad_colour_size_icon(self):
        self.assertError(base_map("    d(D)\n    :::color-red size-medium\n"), "colour-unknown")
        self.assertError(base_map("    d(D)\n    :::color-sky size-huge\n"), "size-unknown")
        self.assertError(base_map("    d(D)\n    ::icon(lucide lucide-bug)\n    :::color-sky size-medium\n"),
                         "icon-unknown")
        self.assertError(base_map("    d(D)\n    ::icon(lucide lucide-idea)\n    :::color-sky size-medium\n"),
                         "icon-unknown")

    def test_metadata_order_and_indent(self):
        self.assertError(base_map("    d(D)\n    :::color-sky size-medium\n    ::icon(lucide lucide-star)\n"),
                         "metadata-order")
        self.assertError(base_map("    d(D)\n    %% text\n    %% @tags x\n"), "metadata-order")
        self.assertError(base_map("    d(D)\n      :::color-sky size-medium\n"), "metadata-indent")

    def test_link_rules(self):
        self.assertError(base_map("    %% @link nowhere | x\n"), "link-target-missing")
        self.assertError(base_map("    %% @link c | self\n"), "link-self")
        self.assertError(base_map().replace("      :::color-sky size-small\n",
                                            "      :::color-sky size-small\n      %% @link a | up\n"),
                         "link-parent-child")
        self.assertError(base_map().replace("    :::color-sky size-medium\n",
                                            "    :::color-sky size-medium\n    %% @link a1 | down\n"),
                         "link-parent-child")
        dup = base_map("    %% @link b | one\n").replace(
            "    :::color-teal size-medium\n", "    :::color-teal size-medium\n    %% @link c | two\n")
        self.assertError(dup, "link-duplicate-pair")
        self.assertError(base_map("    %% @link b | " + "x" * 61 + "\n"), "link-label-long")

    def test_tags(self):
        self.assertError(base_map("    %% @tags Decision\n"), "tag-not-normalised")
        self.assertError(base_map("    %% @tags open question\n"), "tag-not-normalised")
        self.assertError(base_map("    %% @tags b, a\n"), "tag-order")
        self.assertError(base_map("    %% @tags a, a\n"), "tag-duplicate")
        self.assertError(base_map("    %% @tags: a\n"), "tags-colon")
        many = ", ".join(sorted(f"t{i:02d}" for i in range(25)))
        self.assertError(base_map(f"    %% @tags {many}\n"), "too-many-tags")
        self.assertError(base_map("    %% @tags " + "a" * 41 + "\n"), "tag-too-long")

    def test_description_escaping(self):
        self.assertError(base_map("    %% @owner Priya\n"), "desc-unescaped-at")
        self.assertError(base_map("    %% \\server\\share\n"), "desc-unescaped-backslash")
        self.assertTrue(v.validate_text(base_map("    %% \\@owner Priya\n"))["ok"])
        self.assertTrue(v.validate_text(base_map("    %% \\\\server\\share\n"))["ok"])

    def test_positioning_directives(self):
        self.assertError(base_map("    %% @at 10,20\n"), "positioning")
        self.assertError(base_map("    %% @dir left\n"), "positioning")

    def test_code_fence_and_json(self):
        self.assertError("```mermaid\n" + base_map() + "```\n", "code-fence")
        self.assertError(json.dumps({"mindmap": "x"}), "json")
        self.assertError(b"\xef\xbb\xbf" + base_map().encode(), "bom")
        self.assertError(b"mindmap\n  r((Caf\xe9))\n", "not-utf8")

    def test_too_many_nodes(self):
        body = "".join(f"    n{i}(Node {i})\n    :::color-sky size-medium\n" for i in range(2000))
        res = v.validate_text("mindmap\n  r((Big))\n  :::color-brand size-large\n" + body)
        self.assertIn("too-many-nodes", codes(res))
        self.assertEqual(res["stats"]["nodes"], 2001)

    def test_exactly_2000_nodes_ok(self):
        body = "".join(f"    n{i}(Node {i})\n    :::color-sky size-medium\n" for i in range(1999))
        res = v.validate_text("mindmap\n  r((Big))\n  :::color-brand size-large\n" + body)
        self.assertNotIn("too-many-nodes", codes(res))

    def test_too_deep(self):
        lines = ["mindmap"]
        for d in range(65):
            lines.append("  " * (d + 1) + f"d{d}(Level {d})")
        res = v.validate_text("\n".join(lines) + "\n")
        self.assertIn("too-deep", codes(res))
        lines = lines[:65]  # 64 levels including the root
        self.assertNotIn("too-deep", codes(v.validate_text("\n".join(lines) + "\n")))

    def test_too_many_bytes(self):
        filler = "    %% " + "x" * 990 + "\n"
        text = base_map() + filler * 1011
        self.assertGreater(len(text.encode()), 1_000_000)
        self.assertError(text, "too-large")



class ScopeAndDepth(unittest.TestCase):
    """Design warnings for map scope and depth."""

    def wcodes(self, text):
        return {w["code"] for w in v.validate_text(text)["warnings"]}

    def test_meta_branch_is_flagged(self):
        text = base_map("    meta(Where the sources differ)\n    :::color-slate size-medium\n")
        self.assertIn("meta-branch", self.wcodes(text))

    def test_subject_branch_is_not_flagged(self):
        self.assertNotIn("meta-branch", self.wcodes(base_map()))

    def chain(self, depth, siblings):
        lines = ["mindmap", "  r((Root))", "  :::color-brand size-large"]
        for b in range(3):
            for s in range(siblings):
                for d in range(1, depth):
                    ind = "  " * (d + 1)
                    nid = f"b{b}s{s}d{d}"
                    lines += [f"{ind}{nid}(Node {b} {s} {d})", f"{ind}:::color-sky size-medium"]
        return "\n".join(lines) + "\n"

    def test_shallow_large_map_is_flagged(self):
        text = self.chain(depth=3, siblings=6)          # 37 nodes, 2 levels below root
        self.assertIn("shallow", self.wcodes(text))

    def test_deep_map_is_not_flagged(self):
        text = self.chain(depth=6, siblings=2)          # 31 nodes, 5 levels below root
        self.assertNotIn("shallow", self.wcodes(text))

    def test_small_map_may_be_shallow(self):
        self.assertNotIn("shallow", self.wcodes(base_map()))

class Helpers(unittest.TestCase):
    def test_normalise_tag(self):
        self.assertEqual(v.normalise_tag("  #Open Question "), "open-question")
        self.assertEqual(v.normalise_tag("Owner/Alex"), "owner/alex")
        self.assertEqual(v.normalise_tag("--a---b--"), "a-b")
        self.assertEqual(v.normalise_tag("Q3!!"), "q3")
        self.assertEqual(v.normalise_tag("Café"), "café")
        self.assertEqual(v.normalise_tag("!!!"), "")
        self.assertEqual(len(v.normalise_tag("x" * 60)), 40)
        self.assertEqual(v.normalise_tags(["B", "a", "A", " "]), ["a", "b"])
        self.assertEqual(len(v.normalise_tags([f"t{i}" for i in range(30)])), 24)

    def test_sanitise_label(self):
        self.assertEqual(v.sanitise_label("Budget (Q3) [draft]\n{x}"), "Budget Q3 draft x")
        self.assertEqual(v.sanitise_label("a<br>b"), "a b")

    def test_escape_description(self):
        self.assertEqual(v.escape_description("@tags x"), "\\@tags x")
        self.assertEqual(v.escape_description("\\path"), "\\\\path")
        self.assertEqual(v.escape_description("plain"), "plain")

    def test_safe_filename_and_ids(self):
        self.assertEqual(v.safe_filename("Project Review: Q3 (draft)"), "project-review-q3-draft.mmd")
        self.assertEqual(v.safe_filename("???"), "mind-map.mmd")
        ids = {v.new_id() for _ in range(50)}
        self.assertEqual(len(ids), 50)
        self.assertTrue(all(v.ID_RE.match(i) for i in ids))


class AppLink(unittest.TestCase):
    def test_special_characters_in_path(self):
        path = "/Mind maps/Q&A #1 50% + more's café.mmd"
        # '50% ' has no hex pair after '%', so it is a literal character and needs no flag.
        out = b.build_app_link(APP, "01ABCDEFGHIJKLMNOPQRSTUVWXYZ", path)
        q = out["url"].split("?", 1)[1]
        self.assertIn("path=%2FMind%20maps%2FQ%26A%20%231%2050%25%20%2B%20more%27s%20caf%C3%A9.mmd", q)
        self.assertEqual(q.count("&"), 1)  # the only raw '&' separates the two parameters
        self.assertNotIn("#", out["url"])

    def test_connector_id_with_bang(self):
        out = b.build_app_link(APP, "b!Xk3abc_DEF-ghi!01ABC", "/Mindmaps/project-review.mmd")
        self.assertEqual(out["url"], APP + "?file=b%21Xk3abc_DEF-ghi%2101ABC"
                                         "&path=%2FMindmaps%2Fproject-review.mmd")

    def test_bare_graph_item_id(self):
        out = b.build_app_link(APP, "01ABCDEF2GHIJKLMNOPQRSTUVWX3YZ", "/Mindmaps/x.mmd")
        self.assertIn("file=01ABCDEF2GHIJKLMNOPQRSTUVWX3YZ&path=%2FMindmaps%2Fx.mmd", out["url"])

    def test_double_encoding_refused(self):
        with self.assertRaises(b.LinkError):
            b.build_app_link(APP, "01ABC", "%2FMindmaps%2Fx.mmd")
        with self.assertRaises(b.LinkError):
            b.build_app_link(APP, "01ABC", "/Mind%20maps/x.mmd")
        with self.assertRaises(b.LinkError):
            b.build_app_link(APP, "b%21abc", "/Mindmaps/x.mmd")
        out = b.build_app_link(APP, "01ABC", "/Mindmaps/100%25 done.mmd", literal_percent=True)
        self.assertIn("path=%2FMindmaps%2F100%2525%20done.mmd", out["url"])

    def test_local_and_url_paths_refused(self):
        for bad in ("/mnt/workspace/working/x.mmd", "working/x.mmd", "cloud/x.mmd",
                    "C:\\Users\\user\\x.mmd", "Mindmaps/x.mmd",
                    "https://example-my.sharepoint.com/personal/user/Documents/x.mmd",
                    "https://1drv.ms/u/s!abc", "/personal/user/Documents/x.mmd",
                    "/drive/root:/Mindmaps/x.mmd", "/Mindmaps/../x.mmd", "/Mindmaps//x.mmd", ""):
            with self.assertRaises(b.LinkError, msg=bad):
                b.build_app_link(APP, "01ABC", bad)

    def test_bad_ids_and_app_address(self):
        for bad in ("", "a b", "https://contoso.sharepoint.com/x", "folder/id"):
            with self.assertRaises(b.LinkError, msg=bad):
                b.build_app_link(APP, bad, "/Mindmaps/x.mmd")
        for bad in ("http://example.com/app", APP + "?file=x", "", "not a url"):
            with self.assertRaises(b.LinkError, msg=bad):
                b.build_app_link(bad, "01ABC", "/Mindmaps/x.mmd")

    def test_drive_relative_path(self):
        self.assertEqual(b.drive_relative_path("/drive/root:/Mindmaps", "x.mmd"), "/Mindmaps/x.mmd")
        self.assertEqual(b.drive_relative_path("/drive/root:", "x.mmd"), "/x.mmd")
        self.assertEqual(b.drive_relative_path("/drives/b!abc/root:/A/B", "x.mmd"), "/A/B/x.mmd")
        self.assertEqual(b.drive_relative_path("/Mindmaps/", "x.mmd"), "/Mindmaps/x.mmd")

    def test_cli(self):
        script = os.path.join(SKILL, "scripts", "build_app_link.py")
        r = subprocess.run([sys.executable, script, "--app-address", APP, "--file-id", "b!a",
                            "--parent-path", "/drive/root:/Mindmaps", "--name", "a b.mmd"],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertTrue(json.loads(r.stdout)["url"].endswith("?file=b%21a&path=%2FMindmaps%2Fa%20b.mmd"))
        r = subprocess.run([sys.executable, script, "--app-address", APP, "--file-id", "b!a",
                            "--path", "/mnt/workspace/a.mmd"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 1)
        self.assertFalse(json.loads(r.stdout)["ok"])


class BehaviouralCasesFile(unittest.TestCase):
    def test_cases_cover_required_scenarios(self):
        with open(os.path.join(HERE, "behavioral_cases.json"), encoding="utf-8") as fh:
            data = json.load(fh)
        ids = {c["id"] for c in data["cases"]}
        for need in ("unavailable-source", "filename-collision", "upload-failure", "upload-timeout",
                     "app-discovery-multiple", "app-discovery-none", "bare-graph-id",
                     "prompt-injection-in-source"):
            self.assertIn(need, ids)


if __name__ == "__main__":
    unittest.main()
