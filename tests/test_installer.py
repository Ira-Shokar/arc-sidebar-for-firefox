import os
import plistlib
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from arc_sidebar_for_firefox import installer  # noqa: E402


def quiet(*_args, **_kwargs):
    pass


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.profile = self.root / "profile"
        (self.profile / "chrome").mkdir(parents=True)
        (self.profile / "user.js").write_text('user_pref("mine", 1);\n')
        (self.profile / "chrome" / "userChrome.css").write_text("/* mine */\n")

    def tearDown(self):
        self.tmp.cleanup()

    def run_install(self, **kwargs):
        kwargs.setdefault("major", "157")
        kwargs.setdefault("login_start", False)
        installer.install(self.profile, home=self.root, out=quiet, **kwargs)

    def test_install_keeps_existing_content_and_is_repeatable(self):
        self.run_install()
        self.run_install()
        user_js = (self.profile / "user.js").read_text()
        css = (self.profile / "chrome" / "userChrome.css").read_text()
        self.assertIn('user_pref("mine", 1);', user_js)
        self.assertIn("/* mine */", css)
        self.assertEqual(user_js.count(installer.BEGIN_JS), 1)
        self.assertEqual(css.count(installer.BEGIN_CSS), 1)
        self.assertTrue((self.profile / "arc-restore-session.py").is_file())
        self.assertTrue((self.profile / "customKeys.json").is_file())
        self.assertEqual(len(list(self.profile.glob("arc-backup-*"))), 2)

    def test_extras_are_optional(self):
        self.run_install()
        self.assertNotIn("translations.enable", (self.profile / "user.js").read_text())
        self.run_install(extras=True)
        self.assertIn("translations.enable", (self.profile / "user.js").read_text())

    def test_uninstall_restores_own_content(self):
        self.run_install()
        installer.uninstall(self.profile, home=self.root, out=quiet)
        self.assertEqual((self.profile / "user.js").read_text(), 'user_pref("mine", 1);\n')
        self.assertEqual((self.profile / "chrome" / "userChrome.css").read_text(), "/* mine */\n")
        self.assertFalse((self.profile / "arc-restore-session.py").exists())

    def test_version_fallback_uses_nearest_older(self):
        folder, warning = installer.choose_version("157")
        self.assertEqual(folder.name, "157")
        self.assertIsNone(warning)
        folder, warning = installer.choose_version("999")
        self.assertEqual(folder.name, "157")
        self.assertIn("999", warning)
        with self.assertRaises(installer.InstallError):
            installer.choose_version("1")

    @unittest.skipUnless(sys.platform == "darwin", "login start is macOS only")
    def test_login_agent_is_written_and_removed(self):
        self.run_install(login_start=True)
        plists = list((self.root / "Library" / "LaunchAgents").glob("*.plist"))
        self.assertEqual(len(plists), 1)
        data = plistlib.loads(plists[0].read_bytes())
        self.assertEqual(data["ProgramArguments"][-1], "--watch")
        self.assertTrue(data["RunAtLoad"])
        installer.uninstall(self.profile, home=self.root, out=quiet)
        self.assertEqual(list((self.root / "Library" / "LaunchAgents").glob("*.plist")), [])

    def test_detect_profile_prefers_install_section(self):
        base = installer.firefox_dir(self.root)
        (base / "Profiles" / "abc.default-release").mkdir(parents=True)
        (base / "profiles.ini").write_text(
            "[Profile1]\nName=default\nIsRelative=1\nPath=Profiles/zzz.default\nDefault=1\n\n"
            "[Profile0]\nName=default-release\nIsRelative=1\nPath=Profiles/abc.default-release\n\n"
            "[Install2656FF1E876E9973]\nDefault=Profiles/abc.default-release\nLocked=1\n"
        )
        self.assertEqual(installer.detect_profile(self.root), base / "Profiles" / "abc.default-release")

    def test_detect_profile_falls_back_to_default_flag(self):
        base = installer.firefox_dir(self.root)
        base.mkdir(parents=True)
        (base / "profiles.ini").write_text(
            "[Profile1]\nName=default\nIsRelative=1\nPath=Profiles/zzz.default\nDefault=1\n"
        )
        self.assertEqual(installer.detect_profile(self.root), base / "Profiles" / "zzz.default")

    def test_detect_profile_none_without_ini(self):
        self.assertIsNone(installer.detect_profile(self.root))


if __name__ == "__main__":
    unittest.main()
