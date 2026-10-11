# Arc Sidebar for Firefox

Make Firefox look and feel like Arc.

Arc is no longer getting new features. In 2025 The Browser Company said it had
stopped building them and would only keep Arc maintained, with Chromium updates
and security fixes, while it works on a new browser, Dia. Atlassian then
acquired the company. If you liked Arc's sidebar and want to keep that way of
working, this is a way to get most of it in Firefox.

- [Letter to Arc members](https://browsercompany.substack.com/p/letter-to-arc-members-2025), The Browser Company, May 2025
- [The Browser Company explains why it stopped developing Arc](https://www.theverge.com/news/674603/arc-browser-development-stopped-dia-browser-company), The Verge
- [Atlassian completes acquisition of The Browser Company](https://www.businesswire.com/news/home/20251021473486/en/Atlassian-Completes-Acquisition-of-The-Browser-Company-of-New-York), October 2025

It is an Arc-style sidebar for Firefox on macOS, built from `userChrome.css`, a
few Firefox settings and a small helper that keeps your pins and folders. It is
not an extension and it does not change the Firefox app.

Not affiliated with The Browser Company or Mozilla.

## What you get

- Vertical tabs with a hover sidebar that covers the page. Cmd+B docks it, and
  the page resizes beside it.
- The address field inside the sidebar. Cmd+T focuses it.
- Pinned tabs as a grid of square tiles. The column count follows the sidebar width.
- Tab groups as folders under a collapsible "Folders" section.
- A dark indigo gradient sidebar with rounded corners, blue folder icons and
  quieter rows.
- Back, forward, reload and an extensions button in the sidebar.
- Optional settings for blank new tabs, https-only mode, battery use and privacy.

## Requirements

- macOS and Firefox from mozilla.org (release channel).
- Python 3, for the helper. It comes with the Xcode command line tools.

Tested on macOS with Firefox 157 only. Other versions and platforms are untested.

## Other platforms

I will only be developing this for macOS. Contributions for Linux and Windows
are welcome. The styles may already work on other systems, but the installer
and the folder helper assume macOS, so those parts need porting. Please open a
pull request or an issue.

## Install

With [pipx](https://pipx.pypa.io), which installs command line tools in their own environment:

```sh
pipx install git+https://github.com/Ira-Shokar/arc-sidebar-for-firefox.git
arc-sidebar-install
```

Or with pip, in a virtual environment: `pip install git+https://github.com/Ira-Shokar/arc-sidebar-for-firefox.git`.

Once it is on PyPI this becomes `pipx install arc-sidebar-for-firefox`.

Or without installing anything, from a clone or an unzipped download:

```sh
git clone https://github.com/Ira-Shokar/arc-sidebar-for-firefox.git
cd arc-sidebar-for-firefox
./install.sh
```

The installer:

- finds your main Firefox profile for you,
- offers to quit Firefox if it is open,
- asks whether you also want the optional settings,
- sets the pin and folder helper to start at login,
- tells you when to reopen Firefox.

Firefox reads `userChrome.css` only at startup, so quit and reopen it after any change.

Options: pass a profile folder for a specific profile (find it at
`about:profiles`, **Root Directory**), `--extras` to apply the optional settings
without being asked, `--no-login-start` to skip the login helper, and
`--uninstall` to remove everything it installed.

Your own `user.js` and `userChrome.css` are kept. The installer adds one marked
block to each and replaces only that block when you run it again. It also saves
a copy of anything it replaces in `arc-backup-<time>` inside the profile.

### Updating and removing

Upgrading the package does not change your Firefox. Run `arc-sidebar-install`
again afterwards to apply the new files. Your own settings are kept.

```sh
pipx upgrade arc-sidebar-for-firefox
arc-sidebar-install
```

To remove it, run `arc-sidebar-install --uninstall`, then `pipx uninstall arc-sidebar-for-firefox`.

### Keeping pins and folders

In this setup Firefox did not reliably keep folders and pins after a Cmd+Q. The
helper `arc-restore-session.py` puts them back after Firefox closes. The
installer starts it at every login, from your next login. Until then, or with
`--no-login-start`, start it yourself with
`python3 <profile folder>/arc-restore-session.py --watch` and leave it running.
Without it your pins and folders may not survive a quit.

## Versions

Each Firefox major version has its own folder under `arc_sidebar_for_firefox/versions/`. The installer
reads the version of the installed Firefox and uses the matching folder. If
there is none, it warns you and uses the nearest older one. Use `--for <major>`
to choose one yourself.

Firefox changes its internal layout between releases, so the styles can break.
To add a version, copy the latest folder, fix what looks wrong, and send a pull request.

## Roadmap

- **Split view:** side-by-side tabs are planned and are not part of this yet.
  Firefox has early built-in support for it. This project does not style it or
  make it work with the sidebar layout, so do not expect it to look right.

## Known limits

- Dragging tiles in the pin grid may not work. Ctrl+Shift+Page Up or Down should move a pin, but that is untested.
- Dragging an open tab onto a folder may snap back. Right-click the tab and use
  **Move tab to group** instead.
- The footer icons are drawn by Firefox. Their spacing is approximate.
- Firefox profiles are separate windows. This does not give you Arc-style spaces.

## Feature requests and bugs

Feature requests are welcome. Open an issue and choose **Feature request**. Say
what you want and, if it exists in Arc or another browser, how it works there.
I'll tell you honestly whether Firefox can do it. Some things it can't, such as
real workspaces with separate logins in one window.

For bugs, choose **Bug report** and include your Firefox version and a screenshot.
Firefox reads the styles only at startup, so quit it with Cmd+Q and reopen it
first.

I can't promise to build every request. Pull requests are welcome too.

## Developing

```sh
python3 -m unittest discover -s tests
python3 -m build        # needs: pip install build
```

The installer uses only the Python standard library. To publish a release, bump
`version` in `pyproject.toml` and `arc_sidebar_for_firefox/__init__.py`, then
upload the build with `twine upload dist/*`.

## Back up

`./backup.sh` saves your current files into `backups/`. `./backup.sh restore <folder>`
puts them back. Quit Firefox first.

## Licence

MIT. See `LICENSE`.
