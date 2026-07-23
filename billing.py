from datetime import datetime

import stripe

import config
import plans
from models import get_db

stripe.api_key = config.STRIPE_SECRET_KEY


def create_checkout_session(org_id, plan_key, admin_email, success_url, cancel_url):
    """Creates a Stripe Checkout session that collects a card and starts a
    90-day-trial subscription for the given org. Returns the session's URL."""
    session = stripe.checkout.Session.create(
        mode="subscription",
        line_items=[{"price": plans.stripe_price_id(plan_key), "quantity": 1}],
        subscription_data={
            "trial_period_days": plans.PROMO_DAYS,
            "metadata": {"org_id": str(org_id)},
        },
        customer_email=admin_email,
        client_reference_id=str(org_id),
        metadata={"org_id": str(org_id), "plan": plan_key},
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


def handle_checkout_completed(session):
    org_id = int(session["client_reference_id"])
    subscription = stripe.Subscription.retrieve(session["subscription"])
    with get_db() as conn:
        conn.execute(
            "UPDATE organizations SET stripe_customer_id=%s WHERE id=%s",
            (session["customer"], org_id),
        )
        _sync_subscription_to_org(conn, org_id, subscription)
        conn.commit()


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
        handle_checkout_completed(obj)
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
