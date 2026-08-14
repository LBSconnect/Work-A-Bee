// Shared legal/support links surfaced in-app (Settings/More screens). Kept in
// one place so the mobile app and the web app can't drift onto different
// domains - both point at the same production site regardless of build
// profile, since a privacy policy link isn't the kind of thing that should
// ever resolve to a dev/staging URL.
export const PRIVACY_POLICY_URL = "https://www.workabeez.net/privacy";
export const SUPPORT_URL = "https://www.workabeez.net/support";
