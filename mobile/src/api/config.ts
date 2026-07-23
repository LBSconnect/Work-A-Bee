// Expo exposes any env var prefixed EXPO_PUBLIC_ to app code at build time.
// Point this at your local Flask dev server's LAN address (e.g.
// http://192.168.1.23:5000) when testing with Expo Go on a real phone, or at
// the deployed Render URL for production builds. Falls back to localhost for
// `expo start --web`, which shares the machine's network stack.
export const API_BASE_URL = process.env.EXPO_PUBLIC_API_BASE_URL || "http://localhost:5000";
