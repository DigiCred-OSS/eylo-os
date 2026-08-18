"""Curated Stripe tool implementations for the `integrations_v2` pipeline."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from eylo.modules.integrations_v2.domain.enums import ToolEffect

from ...contracts import VendorToolContext, VendorToolError
from ...registry import curated_tool
from .definition import vendor

# Currencies Stripe stores without a fractional part. Everything else is
# hundredths. https://stripe.com/docs/currencies#zero-decimal
_ZERO_DECIMAL = frozenset(
    {
        "bif",
        "clp",
        "djf",
        "gnf",
        "jpy",
        "kmf",
        "krw",
        "mga",
        "pyg",
        "rwf",
        "ugx",
        "vnd",
        "vuv",
        "xaf",
        "xof",
        "xpf",
    }
)
# Stored in thousandths rather than hundredths.
_THREE_DECIMAL = frozenset({"bhd", "jod", "kwd", "omr", "tnd"})


class FindCustomerInput(BaseModel):
    email: str = Field(min_length=1, description="Customer's email address.")


class ListPaymentsInput(BaseModel):
    customer_email: str = Field(min_length=1)
    limit: int = Field(default=10, ge=1, le=50)


class ListSubscriptionsInput(BaseModel):
    customer_email: str = Field(min_length=1)
    include_cancelled: bool = Field(default=False)


class ListInvoicesInput(BaseModel):
    customer_email: str = Field(min_length=1)
    limit: int = Field(default=10, ge=1, le=50)


class GetPaymentInput(BaseModel):
    payment_id: str = Field(
        min_length=1, description="A payment intent id, starting pi_."
    )


@curated_tool(
    vendor=vendor.vendor,
    name="find_customer",
    display_name="Find Stripe Customer",
    description=(
        "Look a customer up by email and report their id, name, balance, "
        "default currency, and when they were created. The id is what Stripe "
        "indexes everything else by, though the other tools here take the "
        "email directly."
    ),
    input_model=FindCustomerInput,
    effect=ToolEffect.READ,
)
async def find_customer(
    payload: FindCustomerInput, ctx: VendorToolContext
) -> dict[str, Any]:
    customers = await _customers(ctx, payload.email)
    if not customers:
        return {"found": False, "email": payload.email}
    customer = customers[0]
    currency = str(customer.get("currency") or "usd")
    return {
        "found": True,
        "id": customer.get("id"),
        "name": customer.get("name"),
        "email": customer.get("email"),
        "currency": currency.upper(),
        "balance": _money(customer.get("balance"), currency),
        "delinquent": customer.get("delinquent"),
        "created_at": _moment(customer.get("created")),
        "duplicate_accounts": len(customers) - 1,
    }


@curated_tool(
    vendor=vendor.vendor,
    name="list_payments",
    display_name="List Stripe Payments",
    description=(
        "List a customer's payments, most recent first, with each amount "
        "converted from Stripe's minor units into real money. Reports what "
        "succeeded, what failed and why, and how much of each was refunded — "
        "which is what 'did my refund go through' actually needs."
    ),
    input_model=ListPaymentsInput,
    effect=ToolEffect.READ,
)
async def list_payments(
    payload: ListPaymentsInput, ctx: VendorToolContext
) -> dict[str, Any]:
    customer = await _customer_or_none(ctx, payload.customer_email)
    if customer is None:
        return {"payments": [], "count": 0, "customer_found": False}

    response = await ctx.read(
        "/charges",
        query={"customer": customer.get("id"), "limit": payload.limit},
    )
    charges = _data(response.data)
    return {
        "customer_id": customer.get("id"),
        "customer_found": True,
        "payments": [
            {
                "id": charge.get("id"),
                "amount": _money(charge.get("amount"), charge.get("currency")),
                "status": charge.get("status"),
                "paid": charge.get("paid"),
                "refunded": charge.get("refunded"),
                "amount_refunded": _money(
                    charge.get("amount_refunded"), charge.get("currency")
                ),
                "description": charge.get("description"),
                "failure_message": charge.get("failure_message"),
                "card_last4": (
                    (charge.get("payment_method_details") or {}).get("card") or {}
                ).get("last4"),
                "receipt_url": charge.get("receipt_url"),
                "created_at": _moment(charge.get("created")),
            }
            for charge in charges
        ],
        "count": len(charges),
    }


@curated_tool(
    vendor=vendor.vendor,
    name="list_subscriptions",
    display_name="List Stripe Subscriptions",
    description=(
        "List a customer's subscriptions with the plan name, what it costs per "
        "period, whether it is active, and when it next renews or ends. "
        "Cancelled subscriptions are hidden unless asked for."
    ),
    input_model=ListSubscriptionsInput,
    effect=ToolEffect.READ,
)
async def list_subscriptions(
    payload: ListSubscriptionsInput, ctx: VendorToolContext
) -> dict[str, Any]:
    customer = await _customer_or_none(ctx, payload.customer_email)
    if customer is None:
        return {"subscriptions": [], "count": 0, "customer_found": False}

    query: dict[str, Any] = {"customer": customer.get("id"), "limit": 20}
    if payload.include_cancelled:
        query["status"] = "all"
    response = await ctx.read("/subscriptions", query=query)
    subscriptions = _data(response.data)
    return {
        "customer_id": customer.get("id"),
        "customer_found": True,
        "subscriptions": [_subscription_view(item) for item in subscriptions],
        "count": len(subscriptions),
    }


@curated_tool(
    vendor=vendor.vendor,
    name="list_invoices",
    display_name="List Stripe Invoices",
    description=(
        "List a customer's invoices with their totals, whether they are paid, "
        "and links to view or download them. Amounts are converted into real "
        "money."
    ),
    input_model=ListInvoicesInput,
    effect=ToolEffect.READ,
)
async def list_invoices(
    payload: ListInvoicesInput, ctx: VendorToolContext
) -> dict[str, Any]:
    customer = await _customer_or_none(ctx, payload.customer_email)
    if customer is None:
        return {"invoices": [], "count": 0, "customer_found": False}

    response = await ctx.read(
        "/invoices", query={"customer": customer.get("id"), "limit": payload.limit}
    )
    invoices = _data(response.data)
    return {
        "customer_id": customer.get("id"),
        "customer_found": True,
        "invoices": [
            {
                "id": invoice.get("id"),
                "number": invoice.get("number"),
                "status": invoice.get("status"),
                "total": _money(invoice.get("total"), invoice.get("currency")),
                "amount_due": _money(
                    invoice.get("amount_due"), invoice.get("currency")
                ),
                "amount_paid": _money(
                    invoice.get("amount_paid"), invoice.get("currency")
                ),
                "due_at": _moment(invoice.get("due_date")),
                "created_at": _moment(invoice.get("created")),
                "hosted_url": invoice.get("hosted_invoice_url"),
                "pdf_url": invoice.get("invoice_pdf"),
            }
            for invoice in invoices
        ],
        "count": len(invoices),
    }


@curated_tool(
    vendor=vendor.vendor,
    name="get_payment",
    display_name="Get Stripe Payment",
    description=(
        "Read one payment by its id, including what it was for, whether it "
        "succeeded, the reason if it did not, and every refund against it with "
        "amounts and reasons."
    ),
    input_model=GetPaymentInput,
    effect=ToolEffect.READ,
)
async def get_payment(
    payload: GetPaymentInput, ctx: VendorToolContext
) -> dict[str, Any]:
    identifier = payload.payment_id.strip()
    path = "/charges" if identifier.startswith("ch_") else "/payment_intents"
    response = await ctx.read(f"{path}/{identifier}")
    payment = _object(response.data)
    currency = payment.get("currency")
    view: dict[str, Any] = {
        "id": payment.get("id"),
        "amount": _money(payment.get("amount"), currency),
        "status": payment.get("status"),
        "description": payment.get("description"),
        "customer_id": payment.get("customer"),
        "created_at": _moment(payment.get("created")),
        "receipt_url": payment.get("receipt_url"),
    }
    error = payment.get("last_payment_error") or {}
    if isinstance(error, dict) and error:
        view["failure_reason"] = error.get("message")
    if payment.get("failure_message"):
        view["failure_reason"] = payment.get("failure_message")

    refunds = _data(payment.get("refunds"))
    view["refunds"] = [
        {
            "id": refund.get("id"),
            "amount": _money(refund.get("amount"), refund.get("currency") or currency),
            "status": refund.get("status"),
            "reason": refund.get("reason"),
            "created_at": _moment(refund.get("created")),
        }
        for refund in refunds
    ]
    view["fully_refunded"] = bool(payment.get("refunded"))
    return view


async def _customers(ctx: VendorToolContext, email: str) -> list[dict[str, Any]]:
    response = await ctx.read("/customers", query={"email": email.strip(), "limit": 5})
    return _data(response.data)


async def _customer_or_none(
    ctx: VendorToolContext, email: str
) -> dict[str, Any] | None:
    found = await _customers(ctx, email)
    return found[0] if found else None


def _subscription_view(subscription: dict[str, Any]) -> dict[str, Any]:
    items = _data(subscription.get("items"))
    first = items[0] if items else {}
    price = first.get("price") or {}
    product = price.get("product")
    return {
        "id": subscription.get("id"),
        "status": subscription.get("status"),
        "active": subscription.get("status") in {"active", "trialing"},
        "plan": price.get("nickname")
        or (product if isinstance(product, str) else None),
        "amount": _money(price.get("unit_amount"), price.get("currency")),
        "interval": (price.get("recurring") or {}).get("interval"),
        "quantity": first.get("quantity"),
        "current_period_end": _moment(subscription.get("current_period_end")),
        "cancel_at_period_end": subscription.get("cancel_at_period_end"),
        "cancelled_at": _moment(subscription.get("canceled_at")),
        "trial_ends_at": _moment(subscription.get("trial_end")),
    }


def _money(amount: Any, currency: Any) -> dict[str, Any] | None:
    """Convert Stripe's minor units into real money.

    Getting this wrong is the difference between £49.99 and £4,999, and the raw
    integer gives no hint which it is — the exponent depends on the currency.
    """
    if not isinstance(amount, int):
        return None
    code = str(currency or "usd").casefold()
    if code in _ZERO_DECIMAL:
        exponent = 0
    elif code in _THREE_DECIMAL:
        exponent = 3
    else:
        exponent = 2
    value = amount / (10**exponent)
    return {
        "value": value,
        "currency": code.upper(),
        "formatted": f"{value:,.{exponent}f} {code.upper()}",
        "minor_units": amount,
    }


def _moment(value: Any) -> str | None:
    """Stripe timestamps are Unix epochs; nobody can read those."""
    if not isinstance(value, int):
        return None
    return datetime.fromtimestamp(value, tz=timezone.utc).isoformat()


def _data(payload: Any) -> list[dict[str, Any]]:
    if payload is None:
        return []
    body = _object(payload)
    return [item for item in body.get("data") or [] if isinstance(item, dict)]


def _object(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise VendorToolError(
            "vendor_response_invalid", "Stripe returned a non-object response."
        )
    error = payload.get("error")
    if isinstance(error, dict):
        raise VendorToolError(
            "vendor_rejected",
            str(error.get("message", "Stripe rejected the request."))[:500],
        )
    return payload


__all__ = [
    "find_customer",
    "get_payment",
    "list_invoices",
    "list_payments",
    "list_subscriptions",
]
