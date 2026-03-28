import logging
from app.db.models import StrategyDeployment

logger = logging.getLogger(__name__)

ORDER_TYPE_MAP = {
    "market": "MARKET",
    "limit": "LIMIT",
    "stop": "SL-M",
    "stop_limit": "SL",
}

EXCHANGE1_UNSUPPORTED = {"stop", "stop_limit"}


def translate_order(order: dict, deployment: StrategyDeployment) -> dict | None:
    """Translate strategy order to broker format."""
    order_type = order.get("order_type", "market")

    # Reject unsupported order types for Exchange1
    if deployment.exchange == "exchange1" and order_type in EXCHANGE1_UNSUPPORTED:
        logger.warning(f"Exchange1 does not support {order_type} orders, rejecting")
        return None

    return {
        "symbol": deployment.symbol,
        "exchange": deployment.exchange,
        "product_type": deployment.product_type,
        "action": order["action"].upper(),  # BUY or SELL
        "quantity": order["quantity"],
        "order_type": ORDER_TYPE_MAP.get(order_type, "MARKET"),
        "price": order.get("price"),
        "trigger_price": order.get("trigger_price"),
    }


async def dispatch_orders(orders: list[dict], deployment: StrategyDeployment, session) -> list[dict]:
    """Route orders to the appropriate broker."""
    results = []
    for order in orders:
        translated = translate_order(order, deployment)
        if translated is None:
            results.append({"order_id": order["id"], "status": "rejected", "reason": "unsupported_order_type"})
            continue

        if deployment.mode == "paper":
            # Paper mode: just record the order, simulated fill
            results.append({"order_id": order["id"], "status": "submitted", "broker_order": translated})
        elif deployment.mode == "live":
            try:
                from app.crypto.encryption import decrypt_credentials
                from app.brokers.factory import get_broker
                from app.db.models import BrokerConnection

                bc = await session.get(BrokerConnection, deployment.broker_connection_id)
                if not bc:
                    results.append({"order_id": order["id"], "status": "rejected", "reason": "broker_not_found"})
                    continue

                credentials = decrypt_credentials(bc.tenant_id, bc.credentials)
                broker = await get_broker(bc.broker_type, credentials)
                try:
                    broker_result = await broker.place_order(translated)
                    results.append({"order_id": order["id"], "status": "submitted", "broker_result": broker_result})
                finally:
                    await broker.close()
            except Exception as e:
                logger.error(f"Failed to dispatch order: {e}")
                results.append({"order_id": order["id"], "status": "failed", "reason": str(e)})

    return results
