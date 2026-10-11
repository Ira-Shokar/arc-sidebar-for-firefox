// Needed so userChrome.css is read, and for the vertical sidebar.
user_pref("toolkit.legacyUserProfileCustomizations.stylesheets", true);
user_pref("sidebar.revamp", true);
user_pref("sidebar.verticalTabs", true);
// Collapse vertical tabs to the left edge and expand them on hover.
// Cmd+B pins them open. Cmd+B again returns them to hover.
user_pref("sidebar.visibility", "expand-on-hover");
// Wait a beat on hover, then slide open. Cmd+B still pins it immediately.
user_pref("sidebar.animation.expand-on-hover.delay-duration-ms", 160);
user_pref("sidebar.animation.expand-on-hover.duration-ms", 260);
user_pref("sidebar.animation.enabled", true);
// Enter in the address field opens a new tab. Option-Return stays on this tab.
user_pref("browser.urlbar.openintab", true);
// Named folders in the sidebar. Right-click a tab and choose New Group.
user_pref("browser.tabs.groups.enabled", true);
// Reopen pinned tabs and folders from the last session.
user_pref("browser.startup.page", 3);
user_pref("browser.sessionstore.resume_from_crash", true);
// Closing the last tab keeps the window, so its pins stay in the session.
user_pref("browser.tabs.closeWindowWithLastTab", false);
// New tabs go to the bottom of the sidebar, including links opened from a pin.
user_pref("browser.tabs.insertRelatedAfterCurrent", false);
user_pref("browser.tabs.insertAfterCurrent", false);
// Two-finger swipe moves back and forward through the page.
user_pref("browser.gesture.swipe.left", "Browser:BackOrBackDuplicate");
user_pref("browser.gesture.swipe.right", "Browser:ForwardOrForwardDuplicate");
// No thumbnail card when the pointer rests on a tab.
user_pref("browser.tabs.hoverPreview.enabled", false);
user_pref("browser.tabs.hoverPreview.showThumbnails", false);
user_pref("browser.tabs.groups.hoverPreview.enabled", false);
