"""
GOLDEN QOD v2
---------------
Purpose:
Find ONE high-quality short-term swing setup.

Rules:
- Stocks $10+
- Broad market universe
- Minimum 3 independent confluences
- Price action + candle patterns included
- Trend + momentum + volume + relative strength
- Support/resistance + ATR
- Target approximately 1.25R - 1.75R
- Prefer 2-7 trading day holds
- NO TRADE if nothing qualifies

Data source:
Yahoo Finance via yfinance

Educational/research tool only.
"""

import warnings
warnings.filterwarnings("ignore")

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime

# ============================================================
# SETTINGS
# ============================================================

MIN_PRICE = 10
MIN_CONFLUENCE = 3

MIN_SCORE = 70

TARGET_R_MIN = 1.25
TARGET_R_MAX = 1.75

LOOKBACK = "6mo"
INTERVAL = "1d"

# Broad liquid universe
TICKERS = [
    "AAPL", "MSFT", "NVDA", "AMZN", "META", "GOOGL", "GOOG",
    "AVGO", "TSLA", "AMD", "NFLX", "CRM", "ORCL", "ADBE",
    "QCOM", "MU", "AMAT", "LRCX", "INTC", "TXN",
    "WMT", "COST", "HD", "LOW", "TGT", "MCD", "SBUX",
    "NKE", "KO", "PEP", "XOM", "CVX", "COP",
    "JPM", "BAC", "GS", "MS", "C", "WFC",
    "V", "MA", "PYPL",
    "UNH", "LLY", "JNJ", "ABBV", "MRK",
    "CAT", "DE", "GE", "HON", "UPS",
    "PLTR", "CRWD", "PANW", "NOW", "SNOW",
    "UBER", "ABNB", "SHOP", "SQ",
    "NFLX", "DIS", "CMCSA",
    "GEV", "CEG", "FSLR"
]

# ============================================================
# INDICATORS
# ============================================================

def add_indicators(df):

    df = df.copy()

    # Moving averages
    df["EMA20"] = df["Close"].ewm(span=20, adjust=False).mean()
    df["EMA50"] = df["Close"].ewm(span=50, adjust=False).mean()

    # RSI
    delta = df["Close"].diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(14).mean()
    avg_loss = loss.rolling(14).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)

    df["RSI"] = 100 - (100 / (1 + rs))

    # MACD
    ema12 = df["Close"].ewm(span=12, adjust=False).mean()
    ema26 = df["Close"].ewm(span=26, adjust=False).mean()

    df["MACD"] = ema12 - ema26
    df["MACD_SIGNAL"] = df["MACD"].ewm(span=9, adjust=False).mean()

    # Stochastic
    low14 = df["Low"].rolling(14).min()
    high14 = df["High"].rolling(14).max()

    df["STOCH"] = (
        (df["Close"] - low14) /
        (high14 - low14).replace(0, np.nan)
    ) * 100

    # ATR
    high_low = df["High"] - df["Low"]
    high_close = abs(df["High"] - df["Close"].shift())
    low_close = abs(df["Low"] - df["Close"].shift())

    true_range = pd.concat(
        [high_low, high_close, low_close],
        axis=1
    ).max(axis=1)

    df["ATR"] = true_range.rolling(14).mean()

    # Volume ratio
    df["AVG_VOLUME"] = df["Volume"].rolling(20).mean()

    df["VOLUME_RATIO"] = (
        df["Volume"] /
        df["AVG_VOLUME"].replace(0, np.nan)
    )

    # Recent high / low
    df["HIGH20"] = df["High"].rolling(20).max()
    df["LOW20"] = df["Low"].rolling(20).min()

    # Previous day high / low
    df["PDH"] = df["High"].shift(1)
    df["PDL"] = df["Low"].shift(1)

    return df


# ============================================================
# CANDLE PATTERNS
# ============================================================

def candle_patterns(df):

    last = df.iloc[-1]

    o = last["Open"]
    h = last["High"]
    l = last["Low"]
    c = last["Close"]

    body = abs(c - o)
    candle_range = h - l

    if candle_range == 0:
        return []

    upper_wick = h - max(o, c)
    lower_wick = min(o, c) - l

    patterns = []

    # Bullish candle
    if c > o:
        patterns.append("Bullish Candle")

    # Strong body / energy candle
    if body / candle_range >= 0.65:
        patterns.append("Energy Candle")

    # Hammer
    if (
        lower_wick >= body * 2
        and upper_wick <= body
        and c > o
    ):
        patterns.append("Hammer")

    # Shooting star
    if (
        upper_wick >= body * 2
        and lower_wick <= body
        and c < o
    ):
        patterns.append("Shooting Star")

    # Bullish engulfing
    if len(df) >= 2:

        prev = df.iloc[-2]

        prev_o = prev["Open"]
        prev_c = prev["Close"]

        if (
            prev_c < prev_o
            and c > o
            and o <= prev_c
            and c >= prev_o
        ):
            patterns.append("Bullish Engulfing")

        # Bearish engulfing
        if (
            prev_c > prev_o
            and c < o
            and o >= prev_c
            and c <= prev_o
        ):
            patterns.append("Bearish Engulfing")

    return patterns


# ============================================================
# PRICE ACTION
# ============================================================

def analyze_price_action(df):

    last = df.iloc[-1]

    close = last["Close"]
    high20 = last["HIGH20"]

    signals = []

    # Breakout
    if close >= high20 * 0.995:
        signals.append("20-Day Breakout")

    # Pullback to EMA20
    distance_ema20 = abs(close - last["EMA20"]) / close

    if distance_ema20 <= 0.015:
        signals.append("EMA20 Pullback")

    # Bullish structure
    if (
        last["EMA20"] > last["EMA50"]
        and close > last["EMA20"]
    ):
        signals.append("Bullish Structure")

    # Momentum expansion
    if len(df) >= 4:

        previous_close = df.iloc[-4]["Close"]

        if close > previous_close:
            signals.append("Short-Term Higher High")

    return signals


# ============================================================
# RELATIVE STRENGTH
# ============================================================

def relative_strength(df, spy_df):

    stock_return = (
        df["Close"].iloc[-1] /
        df["Close"].iloc[-21] - 1
    )

    spy_return = (
        spy_df["Close"].iloc[-1] /
        spy_df["Close"].iloc[-21] - 1
    )

    return stock_return > spy_return


# ============================================================
# SCORE ONE STOCK
# ============================================================

def analyze_stock(ticker, spy_df):

    try:

        df = yf.download(
            ticker,
            period=LOOKBACK,
            interval=INTERVAL,
            auto_adjust=True,
            progress=False
        )

        if df.empty or len(df) < 60:
            return None

        # Flatten yfinance columns if necessary
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        df = add_indicators(df)

        last = df.iloc[-1]

        price = float(last["Close"])

        # ----------------------------------------------------
        # BASIC FILTER
        # ----------------------------------------------------

        if price < MIN_PRICE:
            return None

        if pd.isna(last["ATR"]):
            return None

        score = 0
        confluences = []

        # ----------------------------------------------------
        # 1. TREND
        # ----------------------------------------------------

        if (
            price > last["EMA20"]
            and last["EMA20"] > last["EMA50"]
        ):

            score += 15
            confluences.append("Trend")

        # ----------------------------------------------------
        # 2. RSI MOMENTUM
        # ----------------------------------------------------

        if 55 <= last["RSI"] <= 75:

            score += 10
            confluences.append("RSI Momentum")

        # ----------------------------------------------------
        # 3. MACD
        # ----------------------------------------------------

        if (
            last["MACD"] > last["MACD_SIGNAL"]
            and last["MACD"] > 0
        ):

            score += 10
            confluences.append("MACD")

        # ----------------------------------------------------
        # 4. STOCHASTIC
        # ----------------------------------------------------

        if last["STOCH"] > 50:

            score += 5
            confluences.append("Stochastic")

        # ----------------------------------------------------
        # 5. VOLUME
        # ----------------------------------------------------

        if last["VOLUME_RATIO"] >= 1.3:

            score += 15
            confluences.append("Volume Expansion")

        # ----------------------------------------------------
        # 6. PRICE ACTION
        # ----------------------------------------------------

        price_action = analyze_price_action(df)

        if price_action:

            score += 15
            confluences.append("Price Action")

        # ----------------------------------------------------
        # 7. CANDLE
        # ----------------------------------------------------

        candles = candle_patterns(df)

        bullish_candles = [
            "Bullish Candle",
            "Energy Candle",
            "Hammer",
            "Bullish Engulfing"
        ]

        candle_confirmed = any(
            x in candles for x in bullish_candles
        )

        if candle_confirmed:

            score += 10
            confluences.append("Candle Pattern")

        # ----------------------------------------------------
        # 8. RELATIVE STRENGTH
        # ----------------------------------------------------

        if relative_strength(df, spy_df):

            score += 10
            confluences.append("Relative Strength")

        # ----------------------------------------------------
        # 9. SUPPORT / STRUCTURE
        # ----------------------------------------------------

        ema_distance = abs(price - last["EMA20"])

        if ema_distance <= last["ATR"] * 1.0:

            score += 5
            confluences.append("Structure Support")

        # ----------------------------------------------------
        # MINIMUM CONFLUENCE
        # ----------------------------------------------------

        if len(confluences) < MIN_CONFLUENCE:
            return None

        # ----------------------------------------------------
        # RISK / REWARD
        # ----------------------------------------------------

        atr = float(last["ATR"])

        entry = price

        # Structure-based stop
        stop = min(
            float(last["EMA20"]) - atr * 0.35,
            price - atr * 0.75
        )

        risk = entry - stop

        if risk <= 0:
            return None

        # Favor realistic QOD-style targets
        target_r = 1.50

        target = entry + risk * target_r

        # ----------------------------------------------------
        # FINAL SCORE
        # ----------------------------------------------------

        if score < MIN_SCORE:
            return None

        return {
            "Ticker": ticker,
            "Price": round(price, 2),
            "Score": score,
            "Confluences": len(confluences),
            "Setup": ", ".join(confluences),
            "Candles": ", ".join(candles),
            "Entry": round(entry, 2),
            "Stop": round(stop, 2),
            "Target": round(target, 2),
            "R:R": f"1:{target_r:.2f}",
            "ATR": round(atr, 2),
            "RSI": round(float(last["RSI"]), 1),
            "Volume": round(float(last["VOLUME_RATIO"]), 2)
        }

    except Exception as e:

        print(f"{ticker}: skipped")

        return None


# ============================================================
# GOLDEN SCANNER
# ============================================================

def run_scanner():

    print("\n")
    print("=" * 65)
    print("             🥇 GOLDEN QOD SCANNER")
    print("=" * 65)

    print("\nScanning market...")

    # SPY benchmark
    spy = yf.download(
        "SPY",
        period=LOOKBACK,
        interval=INTERVAL,
        auto_adjust=True,
        progress=False
    )

    if isinstance(spy.columns, pd.MultiIndex):
        spy.columns = spy.columns.get_level_values(0)

    results = []

    for ticker in TICKERS:

        result = analyze_stock(
            ticker,
            spy
        )

        if result:
            results.append(result)

    # --------------------------------------------------------
    # NO TRADE
    # --------------------------------------------------------

    if not results:

        print("\n🛑 NO GOLDEN QOD TODAY")
        print(
            "No stock met the minimum "
            "confluence and score requirements."
        )

        return

    # --------------------------------------------------------
    # RANK
    # --------------------------------------------------------

    results = sorted(
        results,
        key=lambda x: (
            x["Score"],
            x["Confluences"]
        ),
        reverse=True
    )

    # ONE WINNER
    golden = results[0]

    # --------------------------------------------------------
    # DISPLAY
    # --------------------------------------------------------

    print("\n")
    print("=" * 65)
    print("                 🥇 GOLDEN QOD")
    print("=" * 65)

    print(f"\nTICKER:       {golden['Ticker']}")
    print(f"PRICE:        ${golden['Price']}")
    print(f"BIAS:         BULLISH")

    print("\n---------------- SETUP ----------------")

    print(f"Score:        {golden['Score']}/100")
    print(f"Confluence:   {golden['Confluences']}")

    print("\nCONFIRMATIONS:")

    for item in golden["Setup"].split(", "):
        print(f"  ✓ {item}")

    print("\nCANDLE:")
    print(f"  {golden['Candles']}")

    print("\n---------------- TRADE ----------------")

    print(f"Entry:        ${golden['Entry']}")
    print(f"Stop:         ${golden['Stop']}")
    print(f"Target:       ${golden['Target']}")
    print(f"Risk/Reward:  {golden['R:R']}")

    print("\n---------------- DATA -----------------")

    print(f"ATR:          ${golden['ATR']}")
    print(f"RSI:          {golden['RSI']}")
    print(f"Volume Ratio: {golden['Volume']}x")

    print("\n")
    print("=" * 65)
    print("             GOLDEN SETUP FOUND 🔥")
    print("=" * 65)

    # Show runners-up for research
    print("\nOther qualifying candidates:")
    
    for r in results[1:6]:

        print(
            f"  {r['Ticker']:5} | "
            f"Score {r['Score']:3} | "
            f"{r['Confluences']} confluences"
        )


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    run_scanner()
