from dataclasses import dataclass
from decimal import Decimal
from datetime import date, datetime, timedelta, time
from zoneinfo import ZoneInfo
from app.webhooks.schemas import StandardSignal


@dataclass
class RuleResult:
    passed: bool
    reason: str = ""


def evaluate_rules(
    signal: StandardSignal,
    rules: dict,
    open_positions: int,
    signals_today: int,
    current_time_str: str | None = None,
) -> RuleResult:
    if not rules:
        return RuleResult(passed=True)

    # Symbol whitelist
    if wl := rules.get("symbol_whitelist"):
        if wl and signal.symbol not in wl:
            return RuleResult(False, f"Symbol {signal.symbol} not in whitelist")

    # Symbol blacklist
    if bl := rules.get("symbol_blacklist"):
        if signal.symbol in bl:
            return RuleResult(False, f"Symbol {signal.symbol} in blacklist")

    # Max open positions
    if max_pos := rules.get("max_open_positions"):
        if open_positions >= max_pos:
            return RuleResult(False, f"Max open positions ({max_pos}) reached")

    # Max position size
    if max_size := rules.get("max_position_size"):
        if signal.quantity > Decimal(str(max_size)):
            return RuleResult(False, f"Quantity {signal.quantity} exceeds max {max_size}")

    # Max signals per day
    if max_sig := rules.get("max_signals_per_day"):
        if signals_today >= max_sig:
            return RuleResult(False, f"Max signals per day ({max_sig}) reached")

    # Trading hours
    if hours := rules.get("trading_hours"):
        tz = ZoneInfo(hours.get("timezone", "Asia/Kolkata"))
        if current_time_str:
            now_time = datetime.strptime(current_time_str, "%H:%M").time()
        else:
            now_time = datetime.now(tz).time()
        start = datetime.strptime(hours["start"], "%H:%M").time()
        end = datetime.strptime(hours["end"], "%H:%M").time()
        if not (start <= now_time <= end):
            return RuleResult(False, f"Outside trading hours ({hours['start']}-{hours['end']})")

    return RuleResult(passed=True)


async def get_strategy_counts(redis, strategy_id: str) -> tuple[int, int]:
    """Return (open_positions, signals_today) for a strategy.

    Falls back to (0, 0) if Redis is unavailable.
    """
    try:
        today = date.today().strftime("%Y-%m-%d")
        positions_key = f"wh:positions:{strategy_id}"
        signals_key = f"wh:signals:{strategy_id}:{today}"
        positions, signals = await redis.mget(positions_key, signals_key)
        return (int(positions or 0), int(signals or 0))
    except Exception:
        return (0, 0)


async def increment_signals_today(redis, strategy_id: str) -> None:
    """Increment signals_today counter; auto-expires at midnight IST."""
    try:
        today = date.today().strftime("%Y-%m-%d")
        signals_key = f"wh:signals:{strategy_id}:{today}"
        await redis.incr(signals_key)

        # Set TTL to end of day in IST
        tz = ZoneInfo("Asia/Kolkata")
        now = datetime.now(tz)
        midnight = datetime.combine(
            now.date() + timedelta(days=1),
            time.min,
            tzinfo=tz,
        )
        await redis.expireat(signals_key, int(midnight.timestamp()))
    except Exception:
        pass  # Counter is best-effort; don't fail the webhook


async def update_position_count(redis, strategy_id: str, action: str) -> None:
    """Increment (BUY) or decrement (SELL, floor 0) the open_positions counter."""
    try:
        key = f"wh:positions:{strategy_id}"
        if action.upper() == "BUY":
            await redis.incr(key)
        elif action.upper() == "SELL":
            current = await redis.get(key)
            if current and int(current) > 0:
                await redis.decr(key)
    except Exception:
        pass  # Counter is best-effort; don't fail the webhook
