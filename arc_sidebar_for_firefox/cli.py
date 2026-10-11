"""Command line entry point: arc-sidebar-install."""

import argparse
import subprocess
import sys
import time
from pathlib import Path

from . import __version__
from . import installer


def ask(question):
    """Ask a yes or no question. Answers no when there is no terminal."""
    if not sys.stdin.isatty():
        return False
    return input(f"{question} [y/N] ").strip().lower() in ("y", "yes")


def quit_firefox(profile):
    if sys.platform == "darwin":
        subprocess.run(["osascript", "-e", 'quit app "Firefox"'], capture_output=True)
        for _ in range(30):
            if not installer.firefox_running(profile):
                return
            time.sleep(1)


def build_parser():
    parser = argparse.ArgumentParser(
        prog="arc-sidebar-install",
        description="Install, update or remove the Arc-style Firefox setup.",
    )
    parser.add_argument("profile", nargs="?", help="profile folder (default: your main profile)")
    parser.add_argument("--extras", action="store_true", help="also apply the optional settings")
    parser.add_argument(
        "--no-login-start", action="store_true", help="do not start the pin and folder saver at login"
    )
    parser.add_argument("--uninstall", action="store_true", help="remove what was installed")
    parser.add_argument("--for", dest="major", metavar="MAJOR", help="use the files for this Firefox major version")
    parser.add_argument("--firefox", metavar="APP", help="Firefox app to read the version from")
    parser.add_argument("--version", action="version", version=__version__)
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        if args.profile:
            profile = Path(args.profile).expanduser()
        else:
            profile = installer.detect_profile()
            if profile is None:
                raise installer.InstallError(
                    "Could not find your Firefox profile. Pass its folder, "
                    "which you can find at about:profiles under Root Directory."
                )
            print(f"Using your default profile: {profile}")
        if not profile.is_dir():
            raise installer.InstallError(f"No such folder: {profile}")
        profile = profile.resolve()

        if installer.firefox_running(profile):
            if ask("Firefox is open. Quit it now? Your tabs are saved."):
                quit_firefox(profile)
            if installer.firefox_running(profile):
                raise installer.InstallError("Firefox is still open. Quit it with Cmd+Q, then run this again.")

        if args.uninstall:
            installer.uninstall(profile)
            return 0

        extras = args.extras or ask(
            "Also apply the optional settings (blank new tab, https-only, battery and privacy)?"
        )
        installer.install(
            profile,
            extras=extras,
            login_start=not args.no_login_start,
            major=args.major,
            app=args.firefox,
        )
    except installer.InstallError as error:
        print(error, file=sys.stderr)
        return 1
    return 0
