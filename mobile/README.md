# Work-A-Beez mobile app

Expo (managed workflow) React Native app. Phase A: employee login + clock in/out, talking to the new `/api/v1` endpoints on the Flask backend (`../api/`).

## Running locally

```
npm install
EXPO_PUBLIC_API_BASE_URL=http://<your-machine-LAN-IP>:5000 npx expo start
```

Scan the QR code with Expo Go on your Android phone. The phone and your dev machine need to be on the same network, and `EXPO_PUBLIC_API_BASE_URL` must be a LAN address (not `localhost`) since `localhost` on the phone means the phone itself.

For logic-only smoke testing without a phone: `npx expo start --web`.

Push notifications (see below) won't actually deliver in Expo Go - Expo removed
remote push support from Expo Go in SDK 53+. `registerForPushNotificationsAsync`
degrades to returning `null` there (no crash, just no token), so the rest of the
app works normally; to see a real push end-to-end you need an EAS development
build (`eas build --profile development`) or the production app.

## Push notifications

Employees/admins are registered for push on sign-in (`src/auth/AuthContext.tsx`
calls `registerForPushNotificationsAsync` + `POST /api/v1/{employee,admin}/push-token`)
and unregistered on sign-out. The Flask backend sends through Expo's push API
whenever it would otherwise create an in-app notification or send a
notification email (see `notifications.py` / `notify_push.py` on the backend) -
shift claimed, PTO decided, new message, etc.

## Building for the Play Store / App Store

`eas.json` has build profiles for development/preview/production. Trigger a
cloud build via the "EAS Build (mobile)" GitHub Actions workflow
(`.github/workflows/eas-build.yml`, manual `workflow_dispatch` only) or locally
with `eas build --platform android --profile preview`. Either way requires
being authenticated with Expo - locally via `eas login`, in CI via an
`EXPO_TOKEN` repository secret (see the workflow file for where to create one).
No local Android SDK or Xcode install is required; EAS builds in the cloud and
can also manage signing (keystore / distribution certificate) for you.

### Submitting straight to a store

The workflow's `auto_submit` input (`production` profile, one platform at a
time - not `all`) chains `eas build` straight into `eas submit`, using
`eas.json`'s `submit.production.<platform>` config. There's also a separate
"EAS Submit" workflow (`.github/workflows/eas-submit.yml`) for submitting a
build that's already finished in EAS, without triggering a new one.

Without `auto_submit=yes`, EAS Build only builds - the finished binary sits
in your Expo dashboard for you to submit by hand or review before it goes
anywhere near either store's review queue.

**iOS** - `submit.production.ios` is already pointed at this app's App Store
Connect record (`ascAppId: "6799530913"`, `appleTeamId: "F9JJ9GMS26"`, both
plain identifiers, not secrets). Authenticating the actual submission needs
an App Store Connect API Key, via three repository secrets (Settings ->
Secrets and variables -> Actions), from App Store Connect -> Users and Access
-> Integrations -> Keys:

| Secret name | Value |
|---|---|
| `APPLE_ASC_KEY_ID` | the key's Key ID |
| `APPLE_ASC_ISSUER_ID` | the Issuer ID shown above the key list |
| `APPLE_ASC_API_KEY` | the full contents of the downloaded `.p8` file |

**Android** - `submit.production.android` uploads to the `internal` testing
track as a `draft` release rather than `production`, since a brand-new Play
Console listing won't have its store listing/content rating/target audience
setup tasks finished yet (Google won't allow a production release until
those are done, and - separately - new Play Developer accounts must run a
closed test with 20+ testers for 14 days before their first production
release, regardless of what's uploaded). Promote the draft to whichever
track you want once the listing is ready. Needs one repository secret, from
a Google Service Account key (exact steps: https://expo.fyi/creating-google-
service-account - enable the Google Play Android Developer API in Google
Cloud Console, create a service account + JSON key there, then invite that
service account's email in Play Console's Users and permissions with
release/store-listing permissions):

| Secret name | Value |
|---|---|
| `GOOGLE_PLAY_SERVICE_ACCOUNT_KEY` | the full contents of the downloaded JSON key |

The app listing itself (name, package, store listing) has to be created by
hand in Play Console first - the Play Developer API can't create a brand-new
app, only act on one that already exists there.
