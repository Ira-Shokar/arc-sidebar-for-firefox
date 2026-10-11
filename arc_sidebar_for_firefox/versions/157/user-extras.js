// Optional settings. Install them with ./install.sh <profile> --extras
// Chatbots listed in the sidebar chatbot menu. One is open at a time.
user_pref("browser.ml.chat.providers", "claude,chatgpt,copilot,gemini,huggingchat,lechat");
// Videos keep playing in the background when you switch tabs. Pop one out yourself with the button on it.
user_pref("media.videocontrols.picture-in-picture.enable-when-switching-tabs.enabled", false);
// Hold a link to preview it before opening it.
user_pref("browser.ml.linkPreview.enabled", true);
user_pref("browser.ml.linkPreview.longPress", true);
user_pref("browser.ml.linkPreview.longPressMs", 600);
// New tabs are blank, like Arc, with no shortcut tiles or sponsored content.
user_pref("browser.newtabpage.enabled", false);
// Use https whenever a site offers it, and warn before loading plain http.
user_pref("dom.security.https_only_mode", true);
// Battery: no silent autoplaying videos, no pre-loading pages you may never open.
user_pref("media.autoplay.default", 5);
user_pref("network.prefetch-next", false);
user_pref("network.dns.disablePrefetch", true);
user_pref("network.predictor.enabled", false);
user_pref("browser.urlbar.speculativeConnect.enabled", false);
// Save the session every 30 seconds instead of every 15, so the disk wakes less.
user_pref("browser.sessionstore.interval", 30000);
// Less background work: no AI tab suggestions, sponsored address bar results,
// studies, or usage reporting.
user_pref("browser.tabs.groups.smart.enabled", false);
user_pref("browser.urlbar.quicksuggest.enabled", false);
user_pref("browser.urlbar.suggest.quicksuggest.sponsored", false);
user_pref("browser.urlbar.suggest.quicksuggest.nonsponsored", false);
user_pref("browser.urlbar.suggest.trending", false);
user_pref("app.normandy.enabled", false);
user_pref("app.shield.optoutstudies.enabled", false);
user_pref("browser.discovery.enabled", false);
user_pref("datareporting.healthreport.uploadEnabled", false);
user_pref("toolkit.telemetry.unified", false);
user_pref("toolkit.telemetry.enabled", false);
// Cap drawing at 60 frames a second. On a 120Hz screen this halves the work for
// animations and scrolling at a small cost in smoothness.
user_pref("layout.frame_rate", 60);
// Offer to translate pages in other languages, on this device.
user_pref("browser.translations.enable", true);
user_pref("browser.translations.automaticallyPopup", true);
