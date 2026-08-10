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

### Submitting straight to the App Store

The workflow's `auto_submit` input (iOS + `production` profile only) chains
`eas build` straight into `eas submit`, using `eas.json`'s
`submit.production.ios` config - already pointed at this app's App Store
Connect record (`ascAppId: "6799530913"`, `appleTeamId: "F9JJ9GMS26"`, both
plain identifiers, not secrets). Actually authenticating that submission needs
an App Store Connect API Key, via three repository secrets (Settings ->
Secrets and variables -> Actions), from App Store Connect -> Users and Access
-> Integrations -> Keys:

| Secret name | Value |
|---|---|
| `APPLE_ASC_KEY_ID` | the key's Key ID |
| `APPLE_ASC_ISSUER_ID` | the Issuer ID shown above the key list |
| `APPLE_ASC_API_KEY` | the full contents of the downloaded `.p8` file |

Without `auto_submit=yes`, the workflow only builds - the finished `.ipa`
sits in your Expo dashboard for you to submit by hand (`eas submit -p ios`)
or review before it goes anywhere near App Review.

There's no Play Store equivalent wired up yet (would need a Google Play
service account key) - Android builds are build-only for now.
