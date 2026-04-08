import logging
from datetime import datetime, timezone

from app.db.models import StrategyDeployment, DeploymentTrade

logger = logging.getLogger(__name__)

ORDER_TYPE_MAP = {
    "market": "MARKET",
    "limit": "LIMIT",
    "stop": "SL-M",
    "stop_limit": "SL",
    "sl-m": "SL-M",
    "sl": "SL",
}


def translate_order(order: dict, deployment: StrategyDeployment) -> dict | None:
    """Translate strategy order to broker format."""
    order_type = order.get("order_type", "market")
    return {
        "symbol": deployment.symbol,
        "exchange": deployment.exchange,
        "product_type": deployment.product_type,
        "action": order["action"].upper(),
        "quantity": order["quantity"],
        "order_type": ORDER_TYPE_MAP.get(order_type.lower(), "MARKET"),
        "price": order.get("price"),
        "trigger_price": order.get("trigger_price"),
        "leverage": order.get("leverage"),
        "position_model": order.get("position_model"),
        "position_side": order.get("position_side"),
        "take_profit": order.get("take_profit"),
        "stop_loss": order.get("stop_loss"),
    }


async def dispatch_orders(orders: list[dict], deployment: StrategyDeployment, session) -> list[dict]:
    """Route orders to the appropriate broker and record DeploymentTrade rows."""
    results = []
    for order in orders:
        order_type_raw = order.get("order_type", "market")
        translated = translate_order(order, deployment)

        # Create trade record for every order attempt
        trade = DeploymentTrade(
            tenant_id=deployment.tenant_id,
            deployment_id=deployment.id,
            order_id=order["id"],
            action=order["action"].upper(),
            quantity=order["quantity"],
            order_type=ORDER_TYPE_MAP.get(order_type_raw, "MARKET"),
            price=order.get("price"),
            trigger_price=order.get("trigger_price"),
            status="submitted",
            is_manual=False,
        )
        session.add(trade)

        if translated is None:
            trade.status = "rejected"
            results.append({"order_id": order["id"], "status": "rejected", "reason": "unsupported_order_type"})
            continue

        if deployment.mode == "paper":
            trade.status = "filled"
            trade.fill_price = order.get("price") or translated.get("price")
            trade.fill_quantity = order["quantity"]
            trade.filled_at = datetime.now(timezone.utc)
            results.append({"order_id": order["id"], "status": "submitted", "broker_order": translated})
        elif deployment.mode == "live":
            try:
                from app.crypto.encryption import decrypt_credentials
                from app.brokers.factory import get_broker
                from app.db.models import BrokerConnection

                bc = await session.get(BrokerConnection, deployment.broker_connection_id)
                if not bc:
                    trade.status = "rejected"
                    results.append({"order_id": order["id"], "status": "rejected", "reason": "broker_not_found"})
                    continue

                credentials = decrypt_credentials(bc.tenant_id, bc.credentials)
                broker = await get_broker(bc.broker_type, credentials)
                try:
                    from app.brokers.base import OrderRequest
                    from decimal import Decimal as _D
                    order_req = OrderRequest(
                        symbol=translated["symbol"],
                        exchange=translated["exchange"],
                        action=translated["action"],
                        quantity=_D(str(translated["quantity"])),
                        order_type=translated["order_type"],
                        price=_D(str(translated.get("price") or 0)),
                        product_type=translated["product_type"],
                        trigger_price=_D(str(translated["trigger_price"])) if translated.get("trigger_price") else None,
                        leverage=translated.get("leverage"),
                        position_model=translated.get("position_model"),
                        position_side=translated.get("position_side"),
                        take_profit=_D(str(translated["take_profit"])) if translated.get("take_profit") else None,
                        stop_loss=_D(str(translated["stop_loss"])) if translated.get("stop_loss") else None,
                    )
                    broker_result = await broker.place_order(order_req)
                    trade.status = broker_result.status if broker_result.status in ("filled", "open") else "failed"
                    trade.fill_price = float(broker_result.fill_price) if broker_result.fill_price else None
                    trade.fill_quantity = float(broker_result.fill_quantity) if broker_result.fill_quantity else None
                    trade.broker_order_id = broker_result.order_id
                    if trade.status == "filled":
                        trade.filled_at = datetime.now(timezone.utc)
                    results.append({"order_id": order["id"], "status": "submitted", "broker_order_id": broker_result.order_id})
                finally:
                    await broker.close()
            except Exception as e:
                logger.error(f"Failed to dispatch order: {e}")
                trade.status = "failed"
                results.append({"order_id": order["id"], "status": "failed", "reason": str(e)})

    return results
