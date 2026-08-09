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

## Building for the Play Store

`eas.json` has build profiles for development/preview/production. Trigger a
cloud build via the "EAS Build (mobile)" GitHub Actions workflow
(`.github/workflows/eas-build.yml`, manual `workflow_dispatch` only) or locally
with `eas build --platform android --profile preview`. Either way requires
being authenticated with Expo - locally via `eas login`, in CI via an
`EXPO_TOKEN` repository secret (see the workflow file for where to create one).
No local Android SDK is required; EAS builds in the cloud and can also manage
the upload keystore.
