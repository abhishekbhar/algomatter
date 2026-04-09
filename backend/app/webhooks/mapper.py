from decimal import Decimal

from jsonpath_ng import parse

from app.webhooks.schemas import StandardSignal


def apply_mapping(payload: dict, template: dict) -> StandardSignal:
    """Resolve a template of JSONPath expressions + literals against a payload,
    returning a validated StandardSignal."""
    resolved: dict = {}
    for field, expr in template.items():
        if isinstance(expr, str) and expr.startswith("$."):
            matches = parse(expr).find(payload)
            if not matches:
                continue  # skip; Pydantic raises for required fields, optional fields get None default
            resolved[field] = matches[0].value
        else:
            resolved[field] = expr

    # Validate required fields are present
    required = {"symbol", "exchange", "action", "quantity", "order_type", "product_type"}
    missing = required - resolved.keys()
    if missing:
        raise ValueError(f"Required field(s) missing from payload: {', '.join(sorted(missing))}")

    # Normalize
    resolved["action"] = str(resolved["action"]).upper()
    if resolved.get("order_type"):
        resolved["order_type"] = str(resolved["order_type"]).upper()
    resolved["quantity"] = Decimal(str(resolved["quantity"]))
    for decimal_field in ("price", "trigger_price", "take_profit", "stop_loss"):
        if resolved.get(decimal_field):
            resolved[decimal_field] = Decimal(str(resolved[decimal_field]))
    if resolved.get("leverage") is not None:
        resolved["leverage"] = int(resolved["leverage"])

    return StandardSignal(**resolved)
