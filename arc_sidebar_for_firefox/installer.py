"""Install, update or remove the Arc-style Firefox setup for one profile."""

import configparser
import datetime
import hashlib
import os
import plistlib
import re
import shutil
import subprocess
import sys
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
VERSIONS_DIR = PACKAGE_DIR / "versions"

BEGIN_JS = "// >>> arc-sidebar-for-firefox"
END_JS = "// <<< arc-sidebar-for-firefox"
BEGIN_CSS = "/* >>> arc-sidebar-for-firefox */"
END_CSS = "/* <<< arc-sidebar-for-firefox */"

MAC_APP = Path("/Applications/Firefox.app")


class InstallError(Exception):
    """A problem the user can fix. The message is shown as is."""


def firefox_dir(home=None):
    home = Path(home) if home else Path.home()
    if sys.platform == "darwin":
        return home / "Library" / "Application Support" / "Firefox"
    if sys.platform.startswith("win"):
        appdata = os.environ.get("APPDATA")
        return (Path(appdata) if appdata else home / "AppData" / "Roaming") / "Mozilla" / "Firefox"
    return home / ".mozilla" / "firefox"


def detect_profile(home=None):
    """Return the profile folder Firefox uses by default, or None."""
    base = firefox_dir(home)
    ini = base / "profiles.ini"
    if not ini.is_file():
        return None
    parser = configparser.RawConfigParser()
    parser.optionxform = str
    parser.read(ini, encoding="utf-8")

    def resolve(path, relative=True):
        p = Path(path)
        return p if p.is_absolute() or not relative else base / p

    for section in parser.sections():
        if section.startswith("Install") and parser.has_option(section, "Default"):
            return resolve(parser.get(section, "Default"))
    for section in parser.sections():
        if parser.get(section, "Default", fallback="0") == "1" and parser.has_option(section, "Path"):
            relative = parser.get(section, "IsRelative", fallback="1") == "1"
            return resolve(parser.get(section, "Path"), relative)
    return None


def firefox_major(app=None):
    """Return the major version of the installed Firefox as a string."""
    if sys.platform == "darwin":
        plist = Path(app) / "Contents" / "Info.plist" if app else MAC_APP / "Contents" / "Info.plist"
        try:
            with open(plist, "rb") as handle:
                return plistlib.load(handle)["CFBundleShortVersionString"].split(".")[0]
        except (OSError, KeyError, plistlib.InvalidFileException):
            raise InstallError(
                f"Could not read the Firefox version from {plist.parent.parent}. "
                "Use --for <major> or --firefox <path to Firefox.app>."
            )
    try:
        out = subprocess.run(
            [str(app) if app else "firefox", "--version"], capture_output=True, text=True, timeout=20
        ).stdout
    except (OSError, subprocess.SubprocessError):
        out = ""
    match = re.search(r"(\d+)\.", out)
    if not match:
        raise InstallError("Could not read the Firefox version. Use --for <major>.")
    return match.group(1)


def available_versions():
    return sorted(int(p.name) for p in VERSIONS_DIR.iterdir() if p.is_dir() and p.name.isdigit())


def choose_version(major):
    """Return (folder, warning). Exact match, else the nearest older version."""
    versions = available_versions()
    wanted = int(major)
    if wanted in versions:
        return VERSIONS_DIR / str(wanted), None
    older = [v for v in versions if v <= wanted]
    if not older:
        raise InstallError(f"No files for Firefox {major} or older.")
    best = older[-1]
    return (
        VERSIONS_DIR / str(best),
        f"There are no files for Firefox {major}. Using {best}. Some parts may look wrong.",
    )


def strip_block(path, begin, end):
    path = Path(path)
    if not path.is_file():
        return
    kept, skipping = [], False
    for line in path.read_text(encoding="utf-8").splitlines(keepends=True):
        stripped = line.rstrip("\n")
        if stripped == begin:
            skipping = True
        if not skipping:
            kept.append(line)
        if stripped == end:
            skipping = False
    path.write_text("".join(kept), encoding="utf-8")


def append_block(path, begin, end, body):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = path.read_text(encoding="utf-8") if path.is_file() else ""
    if existing and not existing.endswith("\n"):
        existing += "\n"
    path.write_text(f"{existing}{begin}\n{body.rstrip(chr(10))}\n{end}\n", encoding="utf-8")


def firefox_running(profile=None):
    """True when Firefox is open. With a profile, an unused profile counts as closed."""
    if profile is not None:
        locks = [Path(profile) / name for name in (".parentlock", "parent.lock")]
        if not any(lock.exists() for lock in locks):
            return False
    try:
        if sys.platform.startswith("win"):
            out = subprocess.run(["tasklist"], capture_output=True, text=True).stdout
            return "firefox.exe" in out.lower()
        if sys.platform == "darwin":
            command = ["pgrep", "-f", "Firefox.app/Contents/MacOS/firefox"]
        else:
            command = ["pgrep", "-x", "firefox"]
        return subprocess.run(command, capture_output=True).returncode == 0
    except OSError:
        return False


def agent_paths(profile, home=None):
    home = Path(home) if home else Path.home()
    digest = hashlib.sha1(str(profile).encode()).hexdigest()[:8]
    label = f"com.arc-sidebar-for-firefox.session.{digest}"
    return label, home / "Library" / "LaunchAgents" / f"{label}.plist"


def write_login_agent(profile, home=None):
    label, plist = agent_paths(profile, home)
    plist.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "Label": label,
        "ProgramArguments": [
            os.path.realpath(sys.executable),
            str(Path(profile) / "arc-restore-session.py"),
            "--watch",
        ],
        "RunAtLoad": True,
        "KeepAlive": True,
    }
    with open(plist, "wb") as handle:
        plistlib.dump(data, handle)
    return plist


def uninstall(profile, home=None, out=print):
    profile = Path(profile)
    strip_block(profile / "user.js", BEGIN_JS, END_JS)
    strip_block(profile / "chrome" / "userChrome.css", BEGIN_CSS, END_CSS)
    (profile / "arc-restore-session.py").unlink(missing_ok=True)
    agent_paths(profile, home)[1].unlink(missing_ok=True)
    out("Removed. customKeys.json was left alone. Restore it from an arc-backup folder if you want.")


def install(profile, extras=False, login_start=True, major=None, app=None, home=None, out=print):
    profile = Path(profile)
    if not profile.is_dir():
        raise InstallError(f"No such folder: {profile}")
    if major is None:
        major = firefox_major(app)
    source, warning = choose_version(major)
    if warning:
        out(f"Warning: {warning}")
    out(f"Using {source.name} for Firefox {major}.")

    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = profile / f"arc-backup-{stamp}"
    counter = 1
    while backup.exists():
        counter += 1
        backup = profile / f"arc-backup-{stamp}-{counter}"
    (backup / "chrome").mkdir(parents=True)
    for name in ("user.js", "customKeys.json", "arc-restore-session.py", "chrome/userChrome.css"):
        existing = profile / name
        if existing.is_file():
            shutil.copy2(existing, backup / name)

    user_js = profile / "user.js"
    css = profile / "chrome" / "userChrome.css"
    strip_block(user_js, BEGIN_JS, END_JS)
    strip_block(css, BEGIN_CSS, END_CSS)
    prefs = (source / "user.js").read_text(encoding="utf-8")
    if extras:
        prefs += (source / "user-extras.js").read_text(encoding="utf-8")
    append_block(user_js, BEGIN_JS, END_JS, prefs)
    append_block(css, BEGIN_CSS, END_CSS, (source / "chrome" / "userChrome.css").read_text(encoding="utf-8"))
    shutil.copy2(source / "customKeys.json", profile / "customKeys.json")
    shutil.copy2(source / "arc-restore-session.py", profile / "arc-restore-session.py")
    out(f"Installed. Backup of anything replaced: {backup}")

    saver = profile / "arc-restore-session.py"
    if login_start and sys.platform == "darwin":
        write_login_agent(profile, home)
        out("The pin and folder saver will start at your next login.")
    else:
        if login_start:
            out("Starting the saver at login is only set up on macOS so far.")
        out("To keep pins and folders after quitting, start the saver and leave it running:")
        out(f'  {os.path.basename(sys.executable) or "python3"} "{saver}" --watch')
    out(
        "Done. Open Firefox. Reload button missing? Right-click the toolbar, "
        "choose Customize, and drag Reload next to Forward."
    )
