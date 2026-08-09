import traceback

import requests

import config

EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"


def _headers():
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    if config.EXPO_ACCESS_TOKEN:
        headers["Authorization"] = f"Bearer {config.EXPO_ACCESS_TOKEN}"
    return headers


def send_push(tokens, title, body, data=None):
    """Best-effort push to one or more Expo push tokens for a single
    notification. Never raises - same contract as notify_email.send_email: a
    missing/misbehaving push provider must not break the in-app action
    (shift claimed, PTO decided, new message, ...) that triggered it.

    Returns the subset of `tokens` Expo reported as no longer registered
    (uninstalled app, revoked permission, ...), so the caller can prune them
    from push_tokens instead of retrying them forever.
    """
    tokens = [t for t in (tokens or []) if t]
    if not tokens:
        return []
    try:
        resp = requests.post(
            EXPO_PUSH_URL,
            headers=_headers(),
            json=[{"to": t, "title": title, "body": body, "data": data or {}} for t in tokens],
            timeout=10,
        )
        resp.raise_for_status()
        tickets = resp.json().get("data", [])
        return [
            token for token, ticket in zip(tokens, tickets)
            if ticket.get("status") == "error"
            and ticket.get("details", {}).get("error") == "DeviceNotRegistered"
        ]
    except Exception:
        print("WARNING: push notification delivery failed. Traceback:")
        traceback.print_exc()
        return []
