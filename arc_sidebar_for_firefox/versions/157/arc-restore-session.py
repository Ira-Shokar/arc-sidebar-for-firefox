#!/usr/bin/env python3
"""After Firefox quits, put pinned tabs and folders back into the session it will reopen."""

import fcntl
import json
import os
import struct
import sys
import time
from urllib.parse import parse_qsl, urlsplit, urlunsplit, urlencode

# The script lives in the profile folder it keeps tidy. ARC_PROFILE overrides that.
PROFILE = os.environ.get("ARC_PROFILE") or os.path.dirname(os.path.abspath(__file__))
SESSION = os.path.join(PROFILE, "sessionstore.jsonlz4")
LOCK = os.path.join(PROFILE, ".parentlock")


def lz4_decompress(data, usize):
    out = bytearray()
    index = 0
    size = len(data)
    while index < size and len(out) < usize:
        token = data[index]
        index += 1
        literal_length = token >> 4
        if literal_length == 15:
            while True:
                extra = data[index]
                index += 1
                literal_length += extra
                if extra != 255:
                    break
        out += data[index : index + literal_length]
        index += literal_length
        if len(out) >= usize or index >= size:
            break
        offset = data[index] | (data[index + 1] << 8)
        index += 2
        match_length = (token & 0x0F) + 4
        if token & 0x0F == 15:
            while True:
                extra = data[index]
                index += 1
                match_length += extra
                if extra != 255:
                    break
        start = len(out) - offset
        for _ in range(match_length):
            out.append(out[start])
            start += 1
    return bytes(out[:usize])


def lz4_compress(data):
    out = bytearray()
    remaining = len(data)
    token_at = len(out)
    out.append(0)
    if remaining < 15:
        out[token_at] = remaining << 4
    else:
        out[token_at] = 15 << 4
        remaining -= 15
        while remaining >= 255:
            out.append(255)
            remaining -= 255
        out.append(remaining)
    out += data
    return bytes(out)


def load_session(path):
    raw = open(path, "rb").read()
    if raw[:8] != b"mozLz40\x00":
        raise ValueError("not a Firefox session file")
    usize = struct.unpack_from("<I", raw, 8)[0]
    return json.loads(lz4_decompress(raw[12:], usize))


def save_session(path, state):
    payload = json.dumps(state, separators=(",", ":")).encode("utf-8")
    blob = b"mozLz40\x00" + struct.pack("<I", len(payload)) + lz4_compress(payload)
    if lz4_decompress(blob[12:], len(payload)) != payload:
        raise ValueError("session rewrite did not round-trip")
    temporary = path + ".arc-tmp"
    with open(temporary, "wb") as handle:
        handle.write(blob)
    os.replace(temporary, path)


def firefox_is_running():
    if not os.path.exists(LOCK):
        return False
    try:
        handle = open(LOCK, "a+")
    except OSError:
        return True
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        handle.close()
        return True
    fcntl.flock(handle, fcntl.LOCK_UN)
    handle.close()
    return False


def sidebar_is_saved(window):
    tabs = window.get("tabs") or []
    if any(tab.get("pinned") for tab in tabs):
        return True
    if window.get("groups"):
        return True
    return any(tab.get("groupId") for tab in tabs)


def tab_url(tab):
    entries = tab.get("entries") or []
    if not entries:
        return ""
    index = tab.get("index") or 1
    index = min(max(index, 1), len(entries)) - 1
    return entries[index].get("url") or ""


def pin_key(url):
    """One pin per page. Ignore the hash and tracking query args."""
    if not url:
        return ""
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https"):
        return url
    path = parts.path.rstrip("/") or "/"
    ignored = {"ref_type", "utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term"}
    query = urlencode(
        [(key, value) for key, value in parse_qsl(parts.query, keep_blank_values=True) if key not in ignored]
    )
    return urlunsplit((parts.scheme, parts.netloc.lower(), path, query, ""))


def is_login_bounce(url):
    lowered = (url or "").lower()
    return any(token in lowered for token in ("oauth", "oauth2callback", "/login", "signin", "accounts.google.com"))


def dedupe_pins(tabs):
    """Keep the newest pin for each page and drop login bounces."""
    kept = []
    pinned_at = {}
    changed = False
    for tab in tabs:
        if not tab.get("pinned"):
            kept.append(tab)
            continue
        url = tab_url(tab)
        key = pin_key(url)
        if not key or is_login_bounce(url):
            changed = True
            continue
        previous = pinned_at.get(key)
        if previous is None:
            pinned_at[key] = len(kept)
            kept.append(tab)
            continue
        changed = True
        if (tab.get("lastAccessed") or 0) >= (kept[previous].get("lastAccessed") or 0):
            kept[previous] = tab
    pinned = [tab for tab in kept if tab.get("pinned")]
    unpinned = [tab for tab in kept if not tab.get("pinned")]
    ordered = pinned + unpinned
    if [id(tab) for tab in ordered] != [id(tab) for tab in tabs]:
        changed = True
    return ordered, changed, {pin_key(tab_url(tab)) for tab in pinned}


FOLDERS_GROUP_ID = "arc-folders-section"
ANCHOR_TITLE = "arc-folder-anchor"
PLACEHOLDER_TITLES = ("Folders", "arc-folders-placeholder")


def tab_title(tab):
    entries = tab.get("entries") or []
    if not entries:
        return ""
    return entries[0].get("title") or ""


def is_anchor_tab(tab):
    return not tab.get("pinned") and not tab.get("groupId") and tab_title(tab) == ANCHOR_TITLE


def is_placeholder_tab(tab, group_id):
    return (
        tab.get("groupId") == group_id
        and tab_url(tab) == "about:blank"
        and tab_title(tab) in PLACEHOLDER_TITLES
    )


def ensure_folders_section(window):
    """Keep a Folders row under the pins, and a blank tab in front of it.

    Firefox cannot put a folder inside a folder. The Folders group is only
    the section header. A new folder is inserted before the first unpinned
    tab, so that tab must not already sit inside Folders or the new folder
    is created inside the header and never shows up.
    """
    groups = list(window.get("groups") or [])
    tabs = list(window.get("tabs") or [])
    header = next(
        (
            group
            for group in groups
            if group.get("id") == FOLDERS_GROUP_ID or group.get("name") == "Folders"
        ),
        None,
    )
    changed = False
    if header is None:
        header = {
            "id": FOLDERS_GROUP_ID,
            "name": "Folders",
            "color": "gray",
            "collapsed": False,
            "saveOnWindowClose": False,
        }
        groups.insert(0, header)
        changed = True
    elif header.get("saveOnWindowClose"):
        header["saveOnWindowClose"] = False
        changed = True
    group_id = header.get("id")

    anchors = [tab for tab in tabs if is_anchor_tab(tab)]
    placeholders = [tab for tab in tabs if is_placeholder_tab(tab, group_id)]
    body = [
        tab
        for tab in tabs
        if not is_anchor_tab(tab) and not is_placeholder_tab(tab, group_id)
    ]
    anchor = anchors[0] if anchors else session_tab("about:blank", ANCHOR_TITLE, False, 0)
    anchor.pop("groupId", None)
    anchor["pinned"] = False
    anchor["hidden"] = False
    placeholder = (
        placeholders[0]
        if placeholders
        else session_tab("about:blank", "arc-folders-placeholder", False, 0, group_id)
    )
    placeholder["groupId"] = group_id
    placeholder["pinned"] = False
    placeholder["hidden"] = False

    pinned = 0
    for tab in body:
        if not tab.get("pinned"):
            break
        pinned += 1
    last_in_group = None
    for index, tab in enumerate(body):
        if tab.get("groupId") == group_id:
            last_in_group = index
    with_anchor = body[:pinned] + [anchor] + body[pinned:]
    if last_in_group is None:
        ordered = with_anchor[: pinned + 1] + [placeholder] + with_anchor[pinned + 1 :]
    else:
        last_in_group += 1
        ordered = with_anchor[: last_in_group + 1] + [placeholder] + with_anchor[last_in_group + 1 :]

    if ordered != tabs:
        selected = window.get("selected") or 1
        target = None
        if isinstance(selected, int) and 1 <= selected <= len(tabs):
            target = tabs[selected - 1]
        if (
            target is not None
            and not is_anchor_tab(target)
            and not is_placeholder_tab(target, group_id)
            and target in ordered
        ):
            window["selected"] = ordered.index(target) + 1
        elif any(tab.get("pinned") for tab in ordered):
            window["selected"] = next(index for index, tab in enumerate(ordered, 1) if tab.get("pinned"))
        changed = True
        window["tabs"] = ordered
    if changed:
        window["groups"] = groups
    return changed


def reattach_saved_groups(window, saved_groups):
    """Put saved folders back on the open window.

    Folders were marked to leave the window when it closed. A later launch
    that still had pinned tabs skipped them, so the sidebar looked empty.
    """
    existing_ids = {group.get("id") for group in (window.get("groups") or [])}
    groups = list(window.get("groups") or [])
    tabs = list(window.get("tabs") or [])
    present = {tab_url(tab) for tab in tabs}
    remaining = []
    changed = False
    for saved_group in saved_groups:
        group_id = saved_group.get("id")
        if not group_id or group_id in existing_ids:
            if group_id in existing_ids:
                changed = True
            else:
                remaining.append(saved_group)
            continue
        groups.append(
            {
                "id": group_id,
                "name": saved_group.get("name") or "Folder",
                "color": saved_group.get("color") or "blue",
                "collapsed": bool(saved_group.get("collapsed")),
                "saveOnWindowClose": False,
            }
        )
        existing_ids.add(group_id)
        for saved_tab in saved_group.get("tabs") or []:
            tab = json.loads(json.dumps(saved_tab.get("state") or {}))
            tab["pinned"] = False
            tab["hidden"] = False
            tab["groupId"] = group_id
            url = tab_url(tab)
            if url and url in present:
                continue
            tabs.append(tab)
            if url:
                present.add(url)
        changed = True
    window["groups"] = groups
    window["tabs"] = tabs
    return remaining, changed


def strip_closed_pins(closed):
    """Drop every pinned tab stored on closed windows.

    Those windows are older copies. Leaving them in place makes the next
    launch add pins that are no longer in the sidebar.
    """
    remaining = []
    changed = False
    for window in closed:
        original = window.get("tabs") or []
        tabs = [tab for tab in original if not tab.get("pinned")]
        if len(tabs) != len(original):
            changed = True
        if not tabs:
            changed = True
            continue
        if tabs != original:
            window = dict(window)
            window["tabs"] = tabs
        remaining.append(window)
    return remaining, changed


def restore_state(state):
    windows = [json.loads(json.dumps(item)) for item in (state.get("windows") or [])]
    closed = [json.loads(json.dumps(item)) for item in (state.get("_closedWindows") or [])]
    changed = False
    open_has_pins = any(sidebar_is_saved(window) for window in windows)

    if open_has_pins:
        window = windows[0]
        tabs, tabs_changed, seen_keys = dedupe_pins(window.get("tabs") or [])
        if tabs_changed:
            window["tabs"] = tabs
            changed = True
        closed, closed_changed = strip_closed_pins(closed)
        remaining, groups_changed = reattach_saved_groups(
            window, list(state.get("savedGroups") or [])
        )
        changed = changed or closed_changed or groups_changed or ensure_folders_section(window)
        if not changed:
            return False
        state["windows"] = windows
        state["_closedWindows"] = closed
        if groups_changed:
            state["savedGroups"] = remaining
        return True

    saved_groups = list(state.get("savedGroups") or [])
    source = next(
        (
            window
            for window in closed
            if not window.get("isPopup") and any(tab.get("pinned") for tab in (window.get("tabs") or []))
        ),
        None,
    )
    if source is None and not saved_groups:
        return False

    if windows:
        window = windows[0]
    elif source is not None:
        window = json.loads(json.dumps(source))
        window.pop("closedAt", None)
        window.pop("closedId", None)
        window.pop("title", None)
    else:
        window = {"tabs": [], "groups": [], "selected": 1}

    collected = []
    if source is not None:
        for tab in source.get("tabs") or []:
            if tab.get("pinned"):
                collected.append(json.loads(json.dumps(tab)))
    unpinned = [tab for tab in (window.get("tabs") or []) if not tab.get("pinned")]
    tabs, _, _seen_keys = dedupe_pins(collected + unpinned)

    window["tabs"] = tabs
    remaining_groups, _groups_changed = reattach_saved_groups(window, saved_groups)
    ensure_folders_section(window)
    window["selected"] = 1
    closed, _ = strip_closed_pins(closed)
    state["windows"] = [window]
    state["selectedWindow"] = 1
    state["savedGroups"] = remaining_groups
    state["_closedWindows"] = closed
    return True


ARC_SIDEBAR = os.path.expanduser("~/Library/Application Support/Arc/StorableSidebar.json")
IMPORT_STAMP = os.path.join(PROFILE, "arc-imported-urls.json")
GROUP_COLORS = ["blue", "purple", "yellow", "green", "orange", "pink", "cyan", "red"]


def load_arc_sidebar():
    data = json.load(open(ARC_SIDEBAR))
    container = data["sidebar"]["containers"][1]
    raw_items = container["items"]
    items = {raw_items[index]: raw_items[index + 1] for index in range(0, len(raw_items), 2)}
    raw_spaces = container["spaces"]
    spaces = [raw_spaces[index + 1] for index in range(0, len(raw_spaces), 2)]
    return items, spaces


def arc_context(space):
    if (space.get("profile") or {}).get("custom"):
        return 0
    return 1


def arc_container_ids(space):
    pinned_id = None
    unpinned_id = None
    mode = None
    for entry in space.get("newContainerIDs") or []:
        if isinstance(entry, dict):
            if "pinned" in entry:
                mode = "pinned"
            elif "unpinned" in entry:
                mode = "unpinned"
        elif isinstance(entry, str):
            if mode == "pinned":
                pinned_id = entry
            elif mode == "unpinned":
                unpinned_id = entry
    return pinned_id, unpinned_id


def walk_arc(items, item_id, folder_name=None):
    item = items.get(item_id)
    if not item:
        return
    data = item.get("data") or {}
    children = item.get("childrenIds") or []
    if "itemContainer" in data or "splitView" in data:
        for child_id in children:
            yield from walk_arc(items, child_id, folder_name)
        return
    if "list" in data:
        name = item.get("title") or "Folder"
        for child_id in children:
            yield from walk_arc(items, child_id, name)
        return
    tab = data.get("tab") or {}
    url = tab.get("savedURL") or ""
    if not url.startswith(("http://", "https://", "file://")):
        return
    title = tab.get("savedTitle") or item.get("title") or url
    if folder_name:
        yield ("folder", url, title, folder_name)
    else:
        yield ("loose", url, title, None)


def arc_sections():
    items, spaces = load_arc_sidebar()
    # Work space first, then Personal, so work pins stay next to the ones already open.
    ordered = sorted(spaces, key=lambda space: 0 if arc_context(space) == 0 else 1)
    sections = []
    for space in ordered:
        pinned_id, unpinned_id = arc_container_ids(space)
        context = arc_context(space)
        pins = []
        folder_order = []
        folder_pages = {}
        if pinned_id:
            for kind, url, title, folder_name in walk_arc(items, pinned_id):
                if kind == "folder":
                    if folder_name not in folder_pages:
                        folder_pages[folder_name] = []
                        folder_order.append(folder_name)
                    folder_pages[folder_name].append((url, title))
                else:
                    pins.append((url, title))
        loose = []
        if unpinned_id:
            for _kind, url, title, _folder_name in walk_arc(items, unpinned_id):
                loose.append((url, title))
        sections.append((context, pins, [(name, folder_pages[name]) for name in folder_order], loose))
    return sections


def session_tab(url, title, pinned, context, group_id=None):
    tab = {
        "entries": [{"url": url, "title": title or url}],
        "index": 1,
        "pinned": bool(pinned and not group_id),
        "hidden": False,
        "userContextId": context,
        "lastAccessed": int(time.time() * 1000),
    }
    if group_id:
        tab["groupId"] = group_id
    return tab


def import_arc_sidebar(state):
    """Copy Arc pins, folders, and open tabs in once. Later quits do not put them back."""
    if os.environ.get("FIREFOX_ARC_IMPORT") != "1" or not os.path.exists(ARC_SIDEBAR):
        return False
    windows = state.get("windows") or []
    if not windows:
        return False
    window = windows[0]
    already = set()
    if os.path.exists(IMPORT_STAMP):
        already = set(json.load(open(IMPORT_STAMP)).get("urls") or [])
    present = {tab_url(tab) for tab in (window.get("tabs") or [])}
    new_pins = []
    new_groups = []
    new_group_tabs = []
    new_loose = []
    seen = set(already)
    color_index = len(window.get("groups") or [])
    imported = False
    for context, pins, folders, loose in arc_sections():
        for url, title in pins:
            seen.add(url)
            if url in present or url in already:
                continue
            present.add(url)
            new_pins.append(session_tab(url, title, True, context))
            imported = True
        for name, pages in folders:
            pages_to_add = []
            for url, title in pages:
                seen.add(url)
                if url in present or url in already:
                    continue
                present.add(url)
                pages_to_add.append((url, title))
            if not pages_to_add:
                continue
            group_id = "arc-%d-%d" % (int(time.time() * 1000), color_index)
            new_groups.append(
                {
                    "id": group_id,
                    "name": name,
                    "color": GROUP_COLORS[color_index % len(GROUP_COLORS)],
                    "collapsed": False,
                    "saveOnWindowClose": False,
                }
            )
            color_index += 1
            for url, title in pages_to_add:
                new_group_tabs.append(session_tab(url, title, False, context, group_id))
            imported = True
        for url, title in loose:
            seen.add(url)
            if url in present or url in already:
                continue
            present.add(url)
            new_loose.append(session_tab(url, title, False, context))
            imported = True
    if not imported:
        return False
    tabs = window.get("tabs") or []
    pinned_tabs = [tab for tab in tabs if tab.get("pinned")]
    other_tabs = [tab for tab in tabs if not tab.get("pinned")]
    window["tabs"] = pinned_tabs + new_pins + other_tabs + new_group_tabs + new_loose
    window["groups"] = list(window.get("groups") or []) + new_groups
    state["_arcImportUrls"] = sorted(seen)
    return True


def restore_session_file():
    if firefox_is_running() or not os.path.exists(SESSION):
        return False
    state = load_session(SESSION)
    changed = restore_state(state)
    imported = import_arc_sidebar(state)
    imported_urls = state.pop("_arcImportUrls", None)
    if not changed and not imported:
        return False
    save_session(SESSION, state)
    if imported_urls is not None:
        with open(IMPORT_STAMP, "w") as handle:
            json.dump({"urls": imported_urls}, handle)
    return True


def watch():
    # Check often only after Firefox has quit. While it runs, wake rarely to save battery.
    while True:
        try:
            restore_session_file()
        except Exception:
            pass
        time.sleep(2.0 if firefox_is_running() else 0.4)


def main():
    if "--watch" in sys.argv:
        watch()
        return
    if "--now" not in sys.argv:
        time.sleep(1.5)
    restore_session_file()


if __name__ == "__main__":
    main()
