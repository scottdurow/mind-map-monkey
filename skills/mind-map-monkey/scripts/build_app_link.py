#!/usr/bin/env python3
"""Build the link that opens a OneDrive .mmd file in Mind Map Monkey.

Standard library only. The link contract is:

    <app-address>?file=<encoded-file-id>&path=<encoded-drive-relative-path>

Each value is encoded exactly once with urllib.parse.urlencode(...,
quote_via=quote, safe=''), so '!' becomes %21, '/' becomes %2F, a space
becomes %20, and '#', '&', '%', '+', apostrophes and non-ASCII characters are
percent-encoded as UTF-8.

Usage:
    python build_app_link.py --app-address <play address from AppGet> \
        --file-id <id returned by the upload or GetDriveItem> \
        --path /Mindmaps/project-review.mmd

    # Or derive the path from GetDriveItem's parent path and the file name:
    python build_app_link.py --app-address ... --file-id ... \
        --parent-path "/drive/root:/Mindmaps" --name project-review.mmd

Add --literal-percent only when the id or path really contains a '%' followed
by two hex digits as part of its name. Without the flag such a value is
refused, because it is probably encoded already and would be double-encoded.

Prints JSON: {"ok": true, "url": ..., "file": ..., "path": ...}. Exit 1 on a
refused value, 2 on a usage error.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from urllib.parse import quote, urlencode, urlsplit

ENCODED_RE = re.compile(r"%[0-9A-Fa-f]{2}")
# Case-sensitive. A OneDrive folder that happens to share one of these names
# is refused too, so rename such a folder or pass the path through a reviewer.
LOCAL_PREFIXES = ("/mnt/", "/home/", "/tmp/", "/Users/", "/var/", "/private/",  # nosec B108
                  "/workspace/", "/opt/")
WORKSPACE_PREFIXES = ("working/", "cloud/", "input/", "output/", "./", "../", "~")
NON_DRIVE_PREFIXES = ("/personal/", "/drives/", "/drive/root", "/me/drive", "/:")
SHARING_HOST_HINTS = ("sharepoint.com", "1drv.ms", "onedrive.live.com",
                      "onedrive.com", "sharepoint-df.com")


class LinkError(ValueError):
    """A value was refused. The message says why and what to do instead."""


def drive_relative_path(parent_path: str, name: str) -> str:
    """Turn GetDriveItem's parent path plus the file name into '/Folder/name'.

    Accepts '/drive/root:', '/drive/root:/Mindmaps',
    '/drives/<id>/root:/Mindmaps' and a plain '/Mindmaps'.
    """
    if not name or "/" in name or "\\" in name:
        raise LinkError("The file name must be a plain name such as 'map.mmd'.")
    p = (parent_path or "").strip()
    m = re.match(r"^/drives?/(?:[^/]+/)?root:(.*)$", p)
    if m:
        p = m.group(1)
    elif p.startswith("/drive/root"):
        p = p[len("/drive/root"):]
    p = p.rstrip("/")
    if p and not p.startswith("/"):
        p = "/" + p
    return f"{p}/{name}"


def check_path(path: str, literal_percent: bool = False) -> str:
    if not isinstance(path, str) or not path.strip():
        raise LinkError("The drive-relative path is empty.")
    if path != path.strip():
        raise LinkError("The path has spaces at its ends. Use the path exactly as OneDrive reports it.")
    low = path.lower()
    if "://" in low or low.startswith(("http:", "https:", "file:")) or any(h in low for h in SHARING_HOST_HINTS):
        raise LinkError("The path looks like a URL or a sharing link. Use the OneDrive-relative "
                        "path, such as /Mindmaps/project-review.mmd.")
    if re.match(r"^[A-Za-z]:[\\/]", path) or path.startswith("\\") or "\\" in path:
        raise LinkError("The path looks like a local Windows path. Use the OneDrive-relative path.")
    if low.startswith(WORKSPACE_PREFIXES):
        raise LinkError("The path is a workspace path. Use the OneDrive-relative path from GetDriveItem.")
    if not path.startswith("/"):
        raise LinkError("The drive-relative path must start with '/', such as /Mindmaps/map.mmd.")
    if path.startswith(LOCAL_PREFIXES):
        raise LinkError("The path looks like a local file-system path. Use the OneDrive-relative path.")
    if path.startswith(NON_DRIVE_PREFIXES):
        raise LinkError("The path is a Graph or SharePoint path. Strip it to the folder path from the "
                        "OneDrive root (use --parent-path and --name).")
    segments = path.split("/")[1:]
    if any(s in ("", ".", "..") for s in segments):
        raise LinkError("The path has an empty, '.' or '..' segment.")
    if ENCODED_RE.search(path) and not literal_percent:
        raise LinkError("The path already contains percent-encoding such as %20. Pass the decoded "
                        "path, or add --literal-percent if '%xx' is really part of the name.")
    return path


def check_file_id(file_id: str, literal_percent: bool = False) -> str:
    if not isinstance(file_id, str) or not file_id.strip():
        raise LinkError("The file id is empty. Use the id returned by the upload or by GetDriveItem.")
    if file_id != file_id.strip() or re.search(r"\s", file_id):
        raise LinkError("The file id contains whitespace.")
    if "://" in file_id or file_id.lower().startswith(("http", "www.")):
        raise LinkError("The file id looks like a URL. Use the drive item id, never a sharing link.")
    if "/" in file_id or "\\" in file_id:
        raise LinkError("The file id contains a slash. That looks like a path, not an item id.")
    if ENCODED_RE.search(file_id) and not literal_percent:
        raise LinkError("The file id already contains percent-encoding such as %21. Pass the id "
                        "exactly as the tool returned it, or add --literal-percent if that is the id.")
    return file_id


def check_app_address(addr: str) -> str:
    if not isinstance(addr, str) or not addr.strip():
        raise LinkError("The app address is empty. Use the play address returned by AppGet.")
    parts = urlsplit(addr.strip())
    if parts.scheme != "https" or not parts.netloc:
        raise LinkError("The app address must be an https URL.")
    if parts.query or parts.fragment:
        raise LinkError("The app address must not already carry a query string or fragment.")
    return addr.strip()


def build_app_link(app_address: str, file_id: str, path: str,
                   literal_percent: bool = False) -> dict:
    app = check_app_address(app_address)
    fid = check_file_id(file_id, literal_percent)
    p = check_path(path, literal_percent)
    query = urlencode({"file": fid, "path": p}, quote_via=quote, safe="")
    return {"ok": True, "url": f"{app}?{query}", "file": fid, "path": p}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Build a Mind Map Monkey open link.")
    ap.add_argument("--app-address", required=True)
    ap.add_argument("--file-id", required=True)
    ap.add_argument("--path")
    ap.add_argument("--parent-path")
    ap.add_argument("--name")
    ap.add_argument("--literal-percent", action="store_true",
                    help="the id or path really contains '%%xx' as part of its name")
    a = ap.parse_args(argv)
    try:
        if a.path:
            path = a.path
        elif a.parent_path is not None and a.name:
            path = drive_relative_path(a.parent_path, a.name)
        else:
            raise LinkError("Give --path, or --parent-path with --name.")
        out = build_app_link(a.app_address, a.file_id, path, a.literal_percent)
    except LinkError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
