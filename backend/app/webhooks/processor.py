from dataclasses import dataclass
from decimal import Decimal
from datetime import datetime
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
