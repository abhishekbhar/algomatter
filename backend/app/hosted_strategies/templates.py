"""Built-in strategy templates.

Each template provides a ready-to-use strategy that users can clone and
customise.  The ``code`` string is valid Python that imports from the
strategy SDK and subclasses ``AlgoMatterStrategy``.
"""

TEMPLATES: list[dict] = [
    # ------------------------------------------------------------------
    # 1. SMA Crossover
    # ------------------------------------------------------------------
    {
        "name": "SMA Crossover",
        "description": "Buy when price crosses above the simple moving average, sell when it drops below.",
        "params": {"sma_period": 20},
        "code": (
            'from strategy_sdk import AlgoMatterStrategy, Candle\n'
            '\n'
            '\n'
            'class Strategy(AlgoMatterStrategy):\n'
            '    """Simple Moving Average crossover strategy.\n'
            '\n'
            '    Buys when the closing price rises above the SMA and sells\n'
            '    when it drops below.\n'
            '    """\n'
            '\n'
            '    def on_init(self) -> None:\n'
            '        self.state.setdefault("prices", [])\n'
            '        self.state.setdefault("position", None)\n'
            '\n'
            '    def on_candle(self, candle: Candle) -> None:\n'
            '        period = self.params.get("sma_period", 20)\n'
            '        self.state["prices"].append(candle.close)\n'
            '        # Keep only as many prices as we need\n'
            '        self.state["prices"] = self.state["prices"][-period:]\n'
            '\n'
            '        if len(self.state["prices"]) < period:\n'
            '            return  # Not enough data yet\n'
            '\n'
            '        sma = sum(self.state["prices"]) / period\n'
            '\n'
            '        if candle.close > sma and self.state["position"] != "long":\n'
            '            self.buy(symbol=candle.symbol, quantity=1)\n'
            '            self.state["position"] = "long"\n'
            '        elif candle.close < sma and self.state["position"] == "long":\n'
            '            self.sell(symbol=candle.symbol, quantity=1)\n'
            '            self.state["position"] = None\n'
        ),
    },
    # ------------------------------------------------------------------
    # 2. RSI Mean Reversion
    # ------------------------------------------------------------------
    {
        "name": "RSI Mean Reversion",
        "description": "Buy when RSI falls below the oversold threshold and sell when it rises above the overbought threshold.",
        "params": {"rsi_period": 14, "oversold": 30, "overbought": 70},
        "code": (
            'from strategy_sdk import AlgoMatterStrategy, Candle\n'
            '\n'
            '\n'
            'class Strategy(AlgoMatterStrategy):\n'
            '    """RSI mean-reversion strategy.\n'
            '\n'
            '    Enters long when RSI < oversold and exits when RSI > overbought.\n'
            '    """\n'
            '\n'
            '    def on_init(self) -> None:\n'
            '        self.state.setdefault("prices", [])\n'
            '        self.state.setdefault("position", None)\n'
            '\n'
            '    def _compute_rsi(self, period: int) -> float | None:\n'
            '        prices = self.state["prices"]\n'
            '        if len(prices) < period + 1:\n'
            '            return None\n'
            '        deltas = [prices[i] - prices[i - 1] for i in range(-period, 0)]\n'
            '        gains = [d for d in deltas if d > 0]\n'
            '        losses = [-d for d in deltas if d < 0]\n'
            '        avg_gain = sum(gains) / period if gains else 0.0\n'
            '        avg_loss = sum(losses) / period if losses else 0.0\n'
            '        if avg_loss == 0:\n'
            '            return 100.0\n'
            '        rs = avg_gain / avg_loss\n'
            '        return 100.0 - (100.0 / (1.0 + rs))\n'
            '\n'
            '    def on_candle(self, candle: Candle) -> None:\n'
            '        period = self.params.get("rsi_period", 14)\n'
            '        oversold = self.params.get("oversold", 30)\n'
            '        overbought = self.params.get("overbought", 70)\n'
            '\n'
            '        self.state["prices"].append(candle.close)\n'
            '        self.state["prices"] = self.state["prices"][-(period + 50):]\n'
            '\n'
            '        rsi = self._compute_rsi(period)\n'
            '        if rsi is None:\n'
            '            return\n'
            '\n'
            '        if rsi < oversold and self.state["position"] != "long":\n'
            '            self.buy(symbol=candle.symbol, quantity=1)\n'
            '            self.state["position"] = "long"\n'
            '        elif rsi > overbought and self.state["position"] == "long":\n'
            '            self.sell(symbol=candle.symbol, quantity=1)\n'
            '            self.state["position"] = None\n'
        ),
    },
    # ------------------------------------------------------------------
    # 3. MACD Momentum
    # ------------------------------------------------------------------
    {
        "name": "MACD Momentum",
        "description": "Trade MACD line crossovers with the signal line for momentum entries and exits.",
        "params": {"fast_period": 12, "slow_period": 26, "signal_period": 9},
        "code": (
            'from strategy_sdk import AlgoMatterStrategy, Candle\n'
            '\n'
            '\n'
            'class Strategy(AlgoMatterStrategy):\n'
            '    """MACD momentum strategy.\n'
            '\n'
            '    Enters long when the MACD line crosses above the signal line\n'
            '    and exits when it crosses below.\n'
            '    """\n'
            '\n'
            '    def on_init(self) -> None:\n'
            '        self.state.setdefault("prices", [])\n'
            '        self.state.setdefault("position", None)\n'
            '\n'
            '    @staticmethod\n'
            '    def _ema(values: list[float], period: int) -> float:\n'
            '        """Compute an exponential moving average over *values*."""\n'
            '        if not values:\n'
            '            return 0.0\n'
            '        k = 2 / (period + 1)\n'
            '        ema = values[0]\n'
            '        for v in values[1:]:\n'
            '            ema = v * k + ema * (1 - k)\n'
            '        return ema\n'
            '\n'
            '    def on_candle(self, candle: Candle) -> None:\n'
            '        fast = self.params.get("fast_period", 12)\n'
            '        slow = self.params.get("slow_period", 26)\n'
            '        sig = self.params.get("signal_period", 9)\n'
            '\n'
            '        self.state["prices"].append(candle.close)\n'
            '        self.state["prices"] = self.state["prices"][-(slow + sig + 50):]\n'
            '\n'
            '        prices = self.state["prices"]\n'
            '        if len(prices) < slow + sig:\n'
            '            return\n'
            '\n'
            '        # Build MACD series\n'
            '        macd_series: list[float] = []\n'
            '        for i in range(sig + 1):\n'
            '            end = len(prices) - sig + i\n'
            '            fast_ema = self._ema(prices[:end], fast)\n'
            '            slow_ema = self._ema(prices[:end], slow)\n'
            '            macd_series.append(fast_ema - slow_ema)\n'
            '\n'
            '        signal_val = self._ema(macd_series, sig)\n'
            '        macd_val = macd_series[-1]\n'
            '        prev_macd = macd_series[-2]\n'
            '        prev_signal = self._ema(macd_series[:-1], sig)\n'
            '\n'
            '        # Crossover detection\n'
            '        if prev_macd <= prev_signal and macd_val > signal_val:\n'
            '            if self.state["position"] != "long":\n'
            '                self.buy(symbol=candle.symbol, quantity=1)\n'
            '                self.state["position"] = "long"\n'
            '        elif prev_macd >= prev_signal and macd_val < signal_val:\n'
            '            if self.state["position"] == "long":\n'
            '                self.sell(symbol=candle.symbol, quantity=1)\n'
            '                self.state["position"] = None\n'
        ),
    },
    # ------------------------------------------------------------------
    # 4. Bollinger Band Breakout
    # ------------------------------------------------------------------
    {
        "name": "Bollinger Band Breakout",
        "description": "Buy when price breaks above the upper Bollinger Band and sell when it drops below the lower band.",
        "params": {"bb_period": 20, "bb_std": 2.0},
        "code": (
            'from strategy_sdk import AlgoMatterStrategy, Candle\n'
            'import math\n'
            '\n'
            '\n'
            'class Strategy(AlgoMatterStrategy):\n'
            '    """Bollinger Band breakout strategy.\n'
            '\n'
            '    Buys when price exceeds the upper band and sells when it\n'
            '    falls below the lower band.\n'
            '    """\n'
            '\n'
            '    def on_init(self) -> None:\n'
            '        self.state.setdefault("prices", [])\n'
            '        self.state.setdefault("position", None)\n'
            '\n'
            '    def on_candle(self, candle: Candle) -> None:\n'
            '        period = self.params.get("bb_period", 20)\n'
            '        num_std = self.params.get("bb_std", 2.0)\n'
            '\n'
            '        self.state["prices"].append(candle.close)\n'
            '        self.state["prices"] = self.state["prices"][-period:]\n'
            '\n'
            '        if len(self.state["prices"]) < period:\n'
            '            return\n'
            '\n'
            '        prices = self.state["prices"]\n'
            '        sma = sum(prices) / period\n'
            '        variance = sum((p - sma) ** 2 for p in prices) / period\n'
            '        std = math.sqrt(variance)\n'
            '        upper = sma + num_std * std\n'
            '        lower = sma - num_std * std\n'
            '\n'
            '        if candle.close > upper and self.state["position"] != "long":\n'
            '            self.buy(symbol=candle.symbol, quantity=1)\n'
            '            self.state["position"] = "long"\n'
            '        elif candle.close < lower and self.state["position"] == "long":\n'
            '            self.sell(symbol=candle.symbol, quantity=1)\n'
            '            self.state["position"] = None\n'
        ),
    },
    # ------------------------------------------------------------------
    # 5. Blank Template
    # ------------------------------------------------------------------
    {
        "name": "Blank Template",
        "description": "A minimal skeleton strategy with comments explaining the AlgoMatter strategy API.",
        "params": {},
        "code": (
            'from strategy_sdk import AlgoMatterStrategy, Candle\n'
            '\n'
            '\n'
            'class Strategy(AlgoMatterStrategy):\n'
            '    """Your custom strategy.\n'
            '\n'
            '    Lifecycle:\n'
            '        on_init()   -- Called once when the strategy starts.\n'
            '                       Use self.state (a dict) to store persistent\n'
            '                       values across candles.\n'
            '        on_candle() -- Called for every new candle.  Inspect the\n'
            '                       candle data and call self.buy() / self.sell()\n'
            '                       to place orders.\n'
            '\n'
            '    Useful attributes:\n'
            '        self.params  -- dict of user-supplied parameters\n'
            '        self.state   -- persistent state dict (survives restarts)\n'
            '\n'
            '    Order helpers:\n'
            '        self.buy(symbol, quantity)   -- place a buy order\n'
            '        self.sell(symbol, quantity)  -- place a sell order\n'
            '    """\n'
            '\n'
            '    def on_init(self) -> None:\n'
            '        # Initialise any state you need\n'
            '        self.state.setdefault("trade_count", 0)\n'
            '\n'
            '    def on_candle(self, candle: Candle) -> None:\n'
            '        # Access candle fields: candle.symbol, candle.open,\n'
            '        # candle.high, candle.low, candle.close, candle.volume\n'
            '        pass\n'
        ),
    },
]
