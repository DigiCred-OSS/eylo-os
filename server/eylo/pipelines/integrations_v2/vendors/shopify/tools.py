"""Curated Shopify tool implementations for the `integrations_v2` pipeline."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from eylo.modules.integrations_v2.domain.enums import ToolEffect

from ...contracts import VendorToolContext, VendorToolError
from ...registry import curated_tool
from .definition import vendor

MAX_LINE_ITEMS = 50
_ORDER_STATUS = ("open", "closed", "cancelled", "any")


class FindCustomerInput(BaseModel):
    email: str | None = Field(default=None, description="Customer's email address.")
    phone: str | None = Field(default=None, description="Customer's phone number.")
    name: str | None = Field(default=None, description="Customer's name.")


class ListOrdersInput(BaseModel):
    customer_email: str | None = Field(
        default=None, description="Only this customer's orders. Resolved here."
    )
    status: str = Field(default="any", description="open, closed, cancelled, or any.")
    created_after: str | None = Field(default=None, description="ISO 8601 timestamp.")
    limit: int = Field(default=20, ge=1, le=50)


class GetOrderInput(BaseModel):
    order_id: int = Field(ge=1, description="Numeric order id, not the order number.")


class CheckProductStockInput(BaseModel):
    title_contains: str = Field(min_length=1, description="Part of the product title.")
    limit: int = Field(default=10, ge=1, le=25)


class TagOrderInput(BaseModel):
    order_id: int = Field(ge=1)
    add_tags: list[str] | None = Field(default=None, description="Tags to add.")
    note: str | None = Field(
        default=None, description="Internal note. Replaces any existing note."
    )


@curated_tool(
    vendor=vendor.vendor,
    name="find_customer",
    display_name="Find Shopify Customer",
    description=(
        "Look a customer up by email, phone, or name. Returns their id, "
        "contact details, order count, and lifetime spend, so a follow-up "
        "lookup is rarely needed."
    ),
    input_model=FindCustomerInput,
    effect=ToolEffect.READ,
)
async def find_customer(
    payload: FindCustomerInput, ctx: VendorToolContext
) -> dict[str, Any]:
    terms = []
    if payload.email:
        terms.append(f"email:{payload.email}")
    if payload.phone:
        terms.append(f"phone:{payload.phone}")
    if payload.name:
        terms.append(payload.name)
    if not terms:
        raise VendorToolError(
            "search_unbounded", "Give an email, phone number, or name to search for."
        )
    customers = await _customers(ctx, " ".join(terms))
    return {
        "customers": [_customer_view(item) for item in customers],
        "count": len(customers),
    }


@curated_tool(
    vendor=vendor.vendor,
    name="list_orders",
    display_name="List Shopify Orders",
    description=(
        "List orders, optionally only a given customer's — name them by email "
        "and the customer lookup happens here. Each order reports its number, "
        "total, financial status, and whether it has been fulfilled."
    ),
    input_model=ListOrdersInput,
    effect=ToolEffect.READ,
)
async def list_orders(
    payload: ListOrdersInput, ctx: VendorToolContext
) -> dict[str, Any]:
    query: dict[str, Any] = {
        "status": _one_of(payload.status, _ORDER_STATUS, "status"),
        "limit": payload.limit,
    }
    customer_id = None
    if payload.customer_email:
        matches = await _customers(ctx, f"email:{payload.customer_email}")
        if not matches:
            return {
                "orders": [],
                "count": 0,
                "customer_found": False,
                "customer_email": payload.customer_email,
            }
        customer_id = matches[0].get("id")
        query["customer_id"] = customer_id
    if payload.created_after:
        query["created_at_min"] = payload.created_after

    response = await ctx.read("/orders.json", query=query)
    orders = _collection(response.data, "orders")
    return {
        "orders": [_order_view(order) for order in orders],
        "count": len(orders),
        "customer_id": customer_id,
        "customer_found": customer_id is not None if payload.customer_email else None,
    }


@curated_tool(
    vendor=vendor.vendor,
    name="get_order",
    display_name="Get Shopify Order",
    description=(
        "Read one order in full: what was bought, what it cost, where it is "
        "going, and what has actually shipped. Fulfillment is summarised into "
        "a plain status and tracking numbers rather than the nested shape the "
        "API returns."
    ),
    input_model=GetOrderInput,
    effect=ToolEffect.READ,
)
async def get_order(payload: GetOrderInput, ctx: VendorToolContext) -> dict[str, Any]:
    response = await ctx.read(f"/orders/{payload.order_id}.json")
    order = _object(response.data).get("order")
    if not isinstance(order, dict):
        raise VendorToolError("order_not_found", "That order does not exist.")

    view = _order_view(order)
    items = [i for i in order.get("line_items") or [] if isinstance(i, dict)][
        :MAX_LINE_ITEMS
    ]
    view["line_items"] = [
        {
            "title": item.get("title"),
            "variant": item.get("variant_title"),
            "sku": item.get("sku"),
            "quantity": item.get("quantity"),
            "price": item.get("price"),
        }
        for item in items
    ]
    shipping = order.get("shipping_address")
    if isinstance(shipping, dict):
        view["shipping_address"] = {
            "name": shipping.get("name"),
            "city": shipping.get("city"),
            "province": shipping.get("province"),
            "country": shipping.get("country"),
            "zip": shipping.get("zip"),
        }
    fulfillments = [f for f in order.get("fulfillments") or [] if isinstance(f, dict)]
    view["shipments"] = [
        {
            "status": f.get("status"),
            "tracking_company": f.get("tracking_company"),
            "tracking_numbers": f.get("tracking_numbers") or [],
            "shipped_at": f.get("created_at"),
        }
        for f in fulfillments
    ]
    view["note"] = order.get("note")
    view["customer_email"] = order.get("email")
    return view


@curated_tool(
    vendor=vendor.vendor,
    name="check_product_stock",
    display_name="Check Shopify Product Stock",
    description=(
        "Find products by title and report how many are in stock. Shopify "
        "tracks inventory per variant, so this reports each variant and the "
        "total across them — the number someone asking 'do you have any left' "
        "actually wants."
    ),
    input_model=CheckProductStockInput,
    effect=ToolEffect.READ,
)
async def check_product_stock(
    payload: CheckProductStockInput, ctx: VendorToolContext
) -> dict[str, Any]:
    response = await ctx.read(
        "/products.json",
        query={"title": payload.title_contains, "limit": payload.limit},
    )
    products = _collection(response.data, "products")
    shaped = []
    for product in products:
        variants = [v for v in product.get("variants") or [] if isinstance(v, dict)]
        quantities = [
            int(v.get("inventory_quantity") or 0)
            for v in variants
            if isinstance(v.get("inventory_quantity"), int)
        ]
        shaped.append(
            {
                "id": product.get("id"),
                "title": product.get("title"),
                "status": product.get("status"),
                "total_in_stock": sum(quantities),
                "variants": [
                    {
                        "title": v.get("title"),
                        "sku": v.get("sku"),
                        "price": v.get("price"),
                        "in_stock": v.get("inventory_quantity"),
                    }
                    for v in variants
                ],
            }
        )
    return {"products": shaped, "count": len(shaped)}


@curated_tool(
    vendor=vendor.vendor,
    name="tag_order",
    display_name="Tag Shopify Order",
    description=(
        "Add tags to an order, or set its internal note. Tags are merged with "
        "the existing ones rather than replacing them, since Shopify's own "
        "update would otherwise silently drop whatever was already there. The "
        "note does replace what was there."
    ),
    input_model=TagOrderInput,
    effect=ToolEffect.MUTATION,
)
async def tag_order(payload: TagOrderInput, ctx: VendorToolContext) -> dict[str, Any]:
    if not payload.add_tags and payload.note is None:
        raise VendorToolError(
            "no_change_requested", "Give tags to add or a note to set."
        )
    update: dict[str, Any] = {"id": payload.order_id}

    if payload.add_tags:
        # Shopify replaces the whole tag string, so the existing tags have to
        # be read first or they are lost.
        current = _object((await ctx.read(f"/orders/{payload.order_id}.json")).data)
        order = current.get("order")
        existing = str((order or {}).get("tags") or "")
        tags = [tag.strip() for tag in existing.split(",") if tag.strip()]
        for tag in payload.add_tags:
            if tag.strip() and tag.strip() not in tags:
                tags.append(tag.strip())
        update["tags"] = ", ".join(tags)
    if payload.note is not None:
        update["note"] = payload.note

    response = await ctx.mutate(
        f"/orders/{payload.order_id}.json", method="PUT", json={"order": update}
    )
    updated = _object(response.data).get("order") or {}
    return {
        "order_id": payload.order_id,
        "tags": [
            tag.strip()
            for tag in str(updated.get("tags") or "").split(",")
            if tag.strip()
        ],
        "note": updated.get("note"),
    }


async def _customers(ctx: VendorToolContext, query: str) -> list[dict[str, Any]]:
    response = await ctx.read("/customers/search.json", query={"query": query})
    return _collection(response.data, "customers")


def _one_of(value: str, allowed: tuple[str, ...], field: str) -> str:
    candidate = value.strip().casefold()
    if candidate not in allowed:
        raise VendorToolError(
            f"{field}_invalid", f"{field} must be one of: {', '.join(allowed)}."
        )
    return candidate


def _customer_view(customer: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": customer.get("id"),
        "name": " ".join(
            part
            for part in (customer.get("first_name"), customer.get("last_name"))
            if part
        )
        or None,
        "email": customer.get("email"),
        "phone": customer.get("phone"),
        "orders_count": customer.get("orders_count"),
        "total_spent": customer.get("total_spent"),
        "created_at": customer.get("created_at"),
    }


def _order_view(order: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": order.get("id"),
        "order_number": order.get("name"),
        "created_at": order.get("created_at"),
        "total": order.get("total_price"),
        "currency": order.get("currency"),
        "financial_status": order.get("financial_status"),
        "fulfillment_status": order.get("fulfillment_status") or "unfulfilled",
        "cancelled_at": order.get("cancelled_at"),
        "tags": [
            tag.strip()
            for tag in str(order.get("tags") or "").split(",")
            if tag.strip()
        ],
    }


def _collection(payload: Any, key: str) -> list[dict[str, Any]]:
    body = _object(payload)
    return [item for item in body.get(key) or [] if isinstance(item, dict)]


def _object(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise VendorToolError(
            "vendor_response_invalid", "Shopify returned a non-object response."
        )
    errors = payload.get("errors")
    if errors is not None:
        raise VendorToolError("vendor_rejected", str(errors)[:500])
    return payload


__all__ = [
    "check_product_stock",
    "find_customer",
    "get_order",
    "list_orders",
    "tag_order",
]
