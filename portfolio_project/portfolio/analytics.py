from django.db.models import Sum

from .models import HistoricalPrice, Stock, Transaction


def get_portfolio_holdings(portfolio):
    """
    Returns dict: { stock_id: net_quantity }
    net_quantity = BUY - SELL
    """
    stock_ids = (
        Transaction.objects
        .filter(portfolio=portfolio)
        .values_list("stock_id", flat=True)
        .distinct()
    )

    holdings = {}
    for stock_id in stock_ids:
        buy_qty = (
            Transaction.objects
            .filter(portfolio=portfolio, stock_id=stock_id, transaction_type="BUY")
            .aggregate(total=Sum("quantity"))["total"] or 0
        )
        sell_qty = (
            Transaction.objects
            .filter(portfolio=portfolio, stock_id=stock_id, transaction_type="SELL")
            .aggregate(total=Sum("quantity"))["total"] or 0
        )

        net_qty = buy_qty - sell_qty
        if net_qty > 0:
            holdings[stock_id] = net_qty

    return holdings


def get_latest_adjusted_close(stock_id):
    """
    Returns latest adjusted close price for a stock (float or None)
    """
    return (
        HistoricalPrice.objects
        .filter(stock_id=stock_id)
        .order_by("-date")
        .values_list("adjusted_close_price", flat=True)
        .first()
    )


def calculate_portfolio_value(portfolio):
    """
    Total portfolio value using latest adjusted close prices
    """
    holdings = get_portfolio_holdings(portfolio)
    total_value = 0.0

    for stock_id, qty in holdings.items():
        latest = get_latest_adjusted_close(stock_id)
        if latest is not None:
            total_value += float(latest) * float(qty)

    return round(total_value, 2)


def get_owned_quantity(portfolio, stock, exclude_tx_id=None):
    """
    Net owned quantity for a given stock in a portfolio.
    Used for validation (e.g., prevent SELL > owned).
    """
    qs = Transaction.objects.filter(portfolio=portfolio, stock=stock)
    if exclude_tx_id:
        qs = qs.exclude(id=exclude_tx_id)

    buy = qs.filter(transaction_type="BUY").aggregate(s=Sum("quantity"))["s"] or 0
    sell = qs.filter(transaction_type="SELL").aggregate(s=Sum("quantity"))["s"] or 0
    return buy - sell


def moving_average(values, window=10):
    """
    Simple moving average (SMA). Returns list same length as values.
    """
    if window <= 1:
        return values

    out = []
    for i in range(len(values)):
        start = max(0, i - window + 1)
        chunk = values[start:i + 1]
        out.append(sum(chunk) / len(chunk))
    return out


def calculate_rsi(prices, period=14):
    """
    Basic RSI calculation.
    Returns latest RSI value or None if insufficient data.
    """
    if not prices or len(prices) <= period:
        return None

    gains = []
    losses = []

    for i in range(1, len(prices)):
        change = prices[i] - prices[i - 1]
        gains.append(max(change, 0))
        losses.append(abs(min(change, 0)))

    if len(gains) < period:
        return None

    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period

    if avg_loss == 0:
        return 100.0

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return round(rsi, 2)


def calculate_volatility(prices):
    """
    Simple daily-return volatility in percent.
    Returns volatility or None if insufficient data.
    """
    if not prices or len(prices) < 2:
        return None

    returns = []
    for i in range(1, len(prices)):
        prev_price = prices[i - 1]
        curr_price = prices[i]
        if prev_price != 0:
            returns.append((curr_price - prev_price) / prev_price)

    if not returns:
        return None

    mean_return = sum(returns) / len(returns)
    variance = sum((r - mean_return) ** 2 for r in returns) / len(returns)
    volatility = (variance ** 0.5) * 100
    return round(volatility, 2)


def forecast_next_day(prices, window=5):
    """
    Very simple forecast using recent moving average.
    Returns forecast price and direction.
    """
    if not prices:
        return None, "N/A"

    recent = prices[-window:] if len(prices) >= window else prices
    forecast = sum(recent) / len(recent)
    latest = prices[-1]

    if forecast > latest:
        direction = "Up"
    elif forecast < latest:
        direction = "Down"
    else:
        direction = "Flat"

    return round(forecast, 2), direction


def generate_ai_signal(prices, short_window=5, long_window=20):
    """
    prices: list of floats (chronological: oldest -> newest)
    Returns explainable analytics summary for dashboard.
    """
    if not prices or len(prices) < long_window:
        return {
            "trend": "Insufficient data",
            "signal": "N/A",
            "short_ma": None,
            "long_ma": None,
            "confidence": None,
            "risk_level": "N/A",
            "volatility": None,
            "rsi": None,
            "rsi_state": "N/A",
            "forecast_next": None,
            "forecast_direction": "N/A",
            "explanation": "Not enough historical data to generate AI insight.",
            "alerts": [],
        }

    short_ma = sum(prices[-short_window:]) / short_window
    long_ma = sum(prices[-long_window:]) / long_window
    latest_price = prices[-1]

    if latest_price > long_ma:
        trend = "Uptrend"
    elif latest_price < long_ma:
        trend = "Downtrend"
    else:
        trend = "Neutral"

    if short_ma > long_ma:
        signal = "BUY"
    elif short_ma < long_ma:
        signal = "SELL"
    else:
        signal = "HOLD"

    diff = abs(short_ma - long_ma)
    base = max(abs(long_ma), 1e-9)
    confidence = min(100.0, round((diff / base) * 1000, 2))

    volatility = calculate_volatility(prices)
    if volatility is None:
        risk_level = "N/A"
    elif volatility < 1.0:
        risk_level = "Low"
    elif volatility < 2.5:
        risk_level = "Medium"
    else:
        risk_level = "High"

    rsi = calculate_rsi(prices)
    if rsi is None:
        rsi_state = "N/A"
    elif rsi >= 70:
        rsi_state = "Overbought"
    elif rsi <= 30:
        rsi_state = "Oversold"
    else:
        rsi_state = "Neutral"

    forecast_next, forecast_direction = forecast_next_day(prices)

    reasons = []

    if signal == "BUY":
        reasons.append("MA(5) is above MA(20), indicating stronger short-term momentum")
    elif signal == "SELL":
        reasons.append("MA(5) is below MA(20), indicating weakening short-term momentum")
    else:
        reasons.append("MA(5) is close to MA(20), indicating no strong directional signal")

    if trend == "Uptrend":
        reasons.append("latest price is above the long-term moving average")
    elif trend == "Downtrend":
        reasons.append("latest price is below the long-term moving average")

    if rsi_state == "Overbought":
        reasons.append("RSI suggests the stock may be overbought")
    elif rsi_state == "Oversold":
        reasons.append("RSI suggests the stock may be oversold")

    if volatility is not None:
        reasons.append(f"recent daily volatility is {volatility}%")

    reasons.append(f"signal confidence is {confidence}%")

    explanation = " | ".join(reasons) + "."

    alerts = []
    if confidence >= 30 and signal in ["BUY", "SELL"]:
        alerts.append(f"Strong {signal} signal detected (confidence {confidence}%).")
    if trend == "Downtrend":
        alerts.append("Downtrend detected: consider risk management.")
    if trend == "Uptrend":
        alerts.append("Uptrend detected: momentum appears positive.")
    if rsi_state == "Overbought":
        alerts.append("RSI alert: stock may be overbought.")
    if rsi_state == "Oversold":
        alerts.append("RSI alert: stock may be oversold.")
    if risk_level == "High":
        alerts.append("High volatility detected: price swings are elevated.")

    return {
        "trend": trend,
        "signal": signal,
        "short_ma": round(short_ma, 2),
        "long_ma": round(long_ma, 2),
        "confidence": confidence,
        "risk_level": risk_level,
        "volatility": volatility,
        "rsi": rsi,
        "rsi_state": rsi_state,
        "forecast_next": forecast_next,
        "forecast_direction": forecast_direction,
        "explanation": explanation,
        "alerts": alerts,
    }


def build_dashboard_data(portfolio, chart_days=60, ma_window=10, selected_stock_id=None):
    holdings_dict = get_portfolio_holdings(portfolio)

    rows = []
    total_value = 0.0

    for stock_id, qty in holdings_dict.items():
        stock = Stock.objects.get(id=stock_id)
        latest = get_latest_adjusted_close(stock_id)

        value = None
        if latest is not None:
            value = float(latest) * float(qty)
            total_value += value

        rows.append({
            "stock_id": stock_id,
            "stock_symbol": stock.symbol,
            "stock_name": stock.company_name,
            "quantity": qty,
            "latest_price": round(float(latest), 2) if latest is not None else None,
            "value": round(float(value), 2) if value is not None else None,
        })

    rows.sort(key=lambda x: x["stock_symbol"])

    stock_options = [
        {"id": r["stock_id"], "symbol": r["stock_symbol"], "name": r["stock_name"]}
        for r in rows
    ]

    if rows:
        available_ids = {r["stock_id"] for r in rows}
        if selected_stock_id and selected_stock_id in available_ids:
            chart_stock_id = selected_stock_id
        else:
            chart_stock_id = rows[0]["stock_id"]
    else:
        chart_stock_id = None

    chart = {"labels": [], "prices": [], "ma": [], "symbol": "", "window": ma_window}
    prices = []

    if chart_stock_id:
        stock_obj = Stock.objects.get(id=chart_stock_id)
        chart["symbol"] = stock_obj.symbol

        qs = (
            HistoricalPrice.objects
            .filter(stock_id=chart_stock_id)
            .order_by("-date")[:chart_days]
        )
        data = list(qs)[::-1]
        cleaned = [p for p in data if p.adjusted_close_price is not None]

        chart["labels"] = [p.date.strftime("%Y-%m-%d") for p in cleaned]
        prices = [float(p.adjusted_close_price) for p in cleaned]
        chart["prices"] = prices

        ma = moving_average(prices, window=ma_window)
        chart["ma"] = [round(x, 4) for x in ma]

    ai = generate_ai_signal(prices)

    return {
        "portfolio": portfolio,
        "total_value": round(total_value, 2),
        "holdings": rows,
        "chart": chart,
        "ai": ai,
        "stock_options": stock_options,
        "selected_stock_id": chart_stock_id,
    }