from datetime import datetime

import stripe

import config
import plans
import signup_provision
from models import get_db

stripe.api_key = config.STRIPE_SECRET_KEY


def create_checkout_session(draft_token, plan_key, admin_email, success_url, cancel_url):
    """Creates a Stripe Checkout session that collects a card and starts a
    90-day-trial subscription for a signup that is NOT an organization yet -
    keyed by the signup draft's token rather than an org_id. The org itself is
    only created once checkout actually completes; see finalize_signup_checkout().
    Returns the session's URL."""
    session = stripe.checkout.Session.create(
        mode="subscription",
        line_items=[{"price": plans.stripe_price_id(plan_key), "quantity": 1}],
        subscription_data={
            "trial_period_days": plans.PROMO_DAYS,
            "metadata": {"signup_draft_token": draft_token},
        },
        customer_email=admin_email,
        client_reference_id=draft_token,
        metadata={"signup_draft_token": draft_token, "plan": plan_key},
        success_url=success_url + "?session_id={CHECKOUT_SESSION_ID}",
        cancel_url=cancel_url,
    )
    return session.url


def _org_id_from_subscription(subscription):
    org_id = (subscription.get("metadata") or {}).get("org_id")
    return int(org_id) if org_id else None


def _sync_subscription_to_org(conn, org_id, subscription):
    period_end = subscription.get("current_period_end")
    conn.execute(
        "UPDATE organizations SET stripe_subscription_id=%s, subscription_status=%s, "
        "cancel_at_period_end=%s, current_period_end=%s, status=%s WHERE id=%s",
        (
            subscription["id"],
            subscription["status"],
            bool(subscription.get("cancel_at_period_end")),
            datetime.fromtimestamp(period_end) if period_end else None,
            "active" if subscription["status"] in ("trialing", "active") else "suspended",
            org_id,
        ),
    )


def finalize_signup_checkout(session):
    """Idempotently ensures the organization for this checkout session exists -
    creating it from the signup draft on first call - and syncs its Stripe
    subscription status. Safe to call from both the webhook and the browser's
    success-page redirect, in either order or even concurrently: only one call
    will actually claim the draft and create the org (an atomic DELETE...RETURNING
    on signup_drafts is the race guard), the other gets None back and should treat
    the org as "being created by the other caller."

    Returns the dict from signup_provision.create_org_from_draft_data() (plus
    org_id) if this call created the org, or None if someone else already did.
    """
    customer_id = session.get("customer")
    subscription = stripe.Subscription.retrieve(session["subscription"])

    with get_db() as conn:
        existing = conn.execute(
            "SELECT id FROM organizations WHERE stripe_customer_id=%s", (customer_id,)
        ).fetchone()
        if existing:
            org_id = existing["id"]
            _sync_subscription_to_org(conn, org_id, subscription)
            conn.commit()
            return None

        token = session.get("client_reference_id")
        claimed = conn.execute(
            "DELETE FROM signup_drafts WHERE draft_token=%s RETURNING data", (token,)
        ).fetchone() if token else None

        if claimed is None:
            conn.commit()
            return None

        created = signup_provision.create_org_from_draft_data(conn, claimed["data"])
        org_id = created["org_id"]
        conn.execute("UPDATE organizations SET stripe_customer_id=%s WHERE id=%s", (customer_id, org_id))
        _sync_subscription_to_org(conn, org_id, subscription)
        conn.commit()

    # Subscription metadata carries org_id so future webhook events (subscription
    # updated/deleted) can find the org - it could only carry the draft token
    # at creation time, since the org didn't exist yet.
    stripe.Subscription.modify(subscription["id"], metadata={"org_id": str(org_id)})

    created["org_id"] = org_id
    return created


def handle_subscription_updated(subscription):
    org_id = _org_id_from_subscription(subscription)
    if org_id is None:
        return
    with get_db() as conn:
        _sync_subscription_to_org(conn, org_id, subscription)
        conn.commit()


def handle_subscription_deleted(subscription):
    org_id = _org_id_from_subscription(subscription)
    if org_id is None:
        return
    with get_db() as conn:
        conn.execute(
            "UPDATE organizations SET subscription_status='canceled', status='canceled' WHERE id=%s",
            (org_id,),
        )
        conn.commit()


def process_webhook_event(event):
    event_type = event["type"]
    obj = event["data"]["object"]
    if event_type == "checkout.session.completed":
        finalize_signup_checkout(obj)
    elif event_type in ("customer.subscription.updated", "customer.subscription.trial_will_end"):
        handle_subscription_updated(obj)
    elif event_type == "customer.subscription.deleted":
        handle_subscription_deleted(obj)


def cancel_at_period_end(subscription_id):
    subscription = stripe.Subscription.modify(subscription_id, cancel_at_period_end=True)
    with get_db() as conn:
        org_id = _org_id_from_subscription(subscription)
        if org_id is not None:
            conn.execute(
                "UPDATE organizations SET cancel_at_period_end=TRUE WHERE id=%s", (org_id,)
            )
            conn.commit()


def resume_subscription(subscription_id):
    subscription = stripe.Subscription.modify(subscription_id, cancel_at_period_end=False)
    with get_db() as conn:
        org_id = _org_id_from_subscription(subscription)
        if org_id is not None:
            conn.execute(
                "UPDATE organizations SET cancel_at_period_end=FALSE WHERE id=%s", (org_id,)
            )
            conn.commit()


def change_plan(subscription_id, new_plan_key):
    subscription = stripe.Subscription.retrieve(subscription_id)
    item_id = subscription["items"]["data"][0]["id"]
    updated = stripe.Subscription.modify(
        subscription_id,
        items=[{"id": item_id, "price": plans.stripe_price_id(new_plan_key)}],
        proration_behavior="create_prorations",
    )
    org_id = _org_id_from_subscription(updated)
    with get_db() as conn:
        if org_id is not None:
            conn.execute("UPDATE organizations SET plan=%s WHERE id=%s", (new_plan_key, org_id))
        conn.commit()
