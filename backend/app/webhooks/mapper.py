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
                raise ValueError(
                    f"Failed to resolve JSONPath '{expr}' for field '{field}'"
                )
            resolved[field] = matches[0].value
        else:
            resolved[field] = expr

    # Normalize
    resolved["action"] = str(resolved["action"]).upper()
    resolved["quantity"] = Decimal(str(resolved["quantity"]))
    if resolved.get("price"):
        resolved["price"] = Decimal(str(resolved["price"]))
    if resolved.get("trigger_price"):
        resolved["trigger_price"] = Decimal(str(resolved["trigger_price"]))

    return StandardSignal(**resolved)
