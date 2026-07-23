# Work-A-Beez mobile app

Expo (managed workflow) React Native app. Phase A: employee login + clock in/out, talking to the new `/api/v1` endpoints on the Flask backend (`../api/`).

## Running locally

```
npm install
EXPO_PUBLIC_API_BASE_URL=http://<your-machine-LAN-IP>:5000 npx expo start
```

Scan the QR code with Expo Go on your Android phone. The phone and your dev machine need to be on the same network, and `EXPO_PUBLIC_API_BASE_URL` must be a LAN address (not `localhost`) since `localhost` on the phone means the phone itself.

For logic-only smoke testing without a phone: `npx expo start --web`.

## Building for the Play Store

Handled later by EAS Build (`eas.json` not yet added - see Phase E of the mobile/API plan). No local Android SDK is required; EAS builds in the cloud and can also manage the upload keystore.
