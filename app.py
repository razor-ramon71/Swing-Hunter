# ============================================================
# 🥇 GOLDEN SCANNER — GOLDEN QOD
# Streamlit + Tradier
#
# ONE APP / ONE SCANNER
#
# Purpose:
#   Find short-term, liquid stock-option opportunities using
#   multiple technical confluences.
#
# QOD-inspired — NOT a reproduction of any proprietary formula.
# ============================================================

import os
import math
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import requests
import streamlit as st


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="🥇 Golden Scanner",
    page_icon="🥇",
    layout="wide",
)


# ============================================================
# CONFIGURATION
# ============================================================

MIN_STOCK_PRICE = 10.00
MIN_AVG_VOLUME = 500_000
MIN_MARKET_CAP = 2_000_000_000

MIN_SCORE = 76
GOLDEN_SCORE = 90
MAX_RESULTS = 15

MIN_DTE = 2
MAX_DTE = 14

MIN_DELTA = 0.35
MAX_DELTA = 0.70

MIN_OPEN_INTEREST = 100
MIN_OPTION_VOLUME = 10
MAX_SPREAD_PCT = 0.20

# Preferred stock risk model
PREFERRED_R = 1.50
MIN_R = 1.25
MAX_R = 1.75

ATR_STOP_MULTIPLE = 1.25

HISTORY_DAYS = 420


# ============================================================
# BROAD ESTABLISHED COMPANY UNIVERSE
# ============================================================

UNIVERSE = """
AAPL MSFT AMZN GOOGL GOOG META NVDA AVGO ORCL CRM ADBE AMD INTC QCOM
TXN AMAT MU LRCX KLAC ADI CSCO IBM NOW INTU PANW CRWD PLTR ACN
ADP PAYX

WMT COST TGT HD LOW TJX ROST NKE MCD SBUX CMG YUM
KO PEP MDLZ KHC GIS HSY PG CL KMB EL UL

JNJ PFE MRK ABBV LLY UNH CVS CI HUM BMY AMGN GILD REGN ISRG
SYK MDT BSX ABT DHR TMO

JPM BAC WFC C C GS MS BLK SCHW AXP USB PNC COF
V MA JPM

CAT DE HON GE RTX LMT NOC GD ETN EMR PH
UPS FDX UNP CSX NSC

XOM CVX COP EOG OXY SLB HAL MPC PSX VLO
OKE KMI WMB

NEE DUK SO AEP EXC XEL ED PEG

T VZ TMUS CHTR CMCSA DIS NFLX
SPOT

BKNG ABNB MAR HLT DAL UAL LUV AAL
GM F F

SHOP SQ PYPL COIN HOOD
SNOW DDOG MDB NET
"""

DEFAULT_SYMBOLS = sorted(set(UNIVERSE.split()))


# ============================================================
# HELPERS
# ============================================================

def num(value: Any, default: float = 0.0) -> float:
    try:
        x = float(value)
        if math.isfinite(x):
            return x
    except Exception:
        pass
    return default


def safe_last(series: pd.Series, default: float = 0.0) -> float:
    if series is None or len(series) == 0:
        return default

    value = series.iloc[-1]

    if pd.isna(value):
        return default

    return num(value, default)


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


# ============================================================
# TRADIER CLIENT
# ============================================================

class TradierError(Exception):
    pass


class TradierClient:

    def __init__(self, token: str, sandbox: bool = False):
        self.token = token.strip()

        self.base_url = (
            "https://sandbox.tradier.com/v1"
            if sandbox
            else "https://api.tradier.com/v1"
        )

        self.session = requests.Session()

        self.session.headers.update(
            {
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/json",
            }
        )

    def get(self, endpoint: str, params: Optional[dict] = None):

        url = self.base_url + endpoint

        response = self.session.get(
            url,
            params=params,
            timeout=30,
        )

        if response.status_code != 200:
            raise TradierError(
                f"Tradier HTTP {response.status_code}: "
                f"{response.text[:300]}"
            )

        try:
            return response.json()
        except Exception:
            raise TradierError("Tradier returned invalid JSON.")

    def quotes(self, symbols: List[str]) -> Dict[str, dict]:

        if not symbols:
            return {}

        data = self.get(
            "/markets/quotes",
            {
                "symbols": ",".join(symbols),
                "greeks": "true",
            },
        )

        quotes = data.get("quotes", {}).get("quote", [])

        if isinstance(quotes, dict):
            quotes = [quotes]

        result = {}

        for q in quotes:
            symbol = q.get("symbol")

            if symbol:
                result[str(symbol).upper()] = q

        return result

    def history(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
    ) -> pd.DataFrame:

        data = self.get(
            "/markets/history",
            {
                "symbol": symbol,
                "interval": "daily",
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
            },
        )

        history = data.get("history", {})

        if not history:
            return pd.DataFrame()

        rows = history.get("day", [])

        if isinstance(rows, dict):
            rows = [rows]

        if not rows:
            return pd.DataFrame()

        df = pd.DataFrame(rows)

        rename = {
            "date": "Date",
            "open": "Open",
            "high": "High",
            "low": "Low",
            "close": "Close",
            "volume": "Volume",
        }

        df = df.rename(columns=rename)

        required = [
            "Date",
            "Open",
            "High",
            "Low",
            "Close",
            "Volume",
        ]

        for col in required:
            if col not in df.columns:
                return pd.DataFrame()

        df["Date"] = pd.to_datetime(df["Date"])

        for col in [
            "Open",
            "High",
            "Low",
            "Close",
            "Volume",
        ]:
            df[col] = pd.to_numeric(
                df[col],
                errors="coerce",
            )

        df = df.dropna(
            subset=[
                "Open",
                "High",
                "Low",
                "Close",
            ]
        )

        df = df.sort_values("Date")
        df = df.reset_index(drop=True)

        return df

    def option_expirations(
        self,
        symbol: str,
    ) -> List[str]:

        data = self.get(
            "/markets/options/expirations",
            {
                "symbol": symbol,
                "includeAllRoots": "true",
                "strikes": "false",
            },
        )

        expirations = (
            data
            .get("expirations", {})
            .get("date", [])
        )

        if isinstance(expirations, str):
            expirations = [expirations]

        return expirations or []

    def option_chain(
        self,
        symbol: str,
        expiration: str,
    ) -> List[dict]:

        data = self.get(
            "/markets/options/chains",
            {
                "symbol": symbol,
                "expiration": expiration,
                "greeks": "true",
            },
        )

        options = (
            data
            .get("options", {})
            .get("option", [])
        )

        if isinstance(options, dict):
            options = [options]

        return options or []


# ============================================================
# TECHNICAL INDICATORS
# ============================================================

def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(
        span=period,
        adjust=False,
    ).mean()


def rsi(series: pd.Series, period: int = 14) -> pd.Series:

    delta = series.diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(
        alpha=1 / period,
        adjust=False,
    ).mean()

    avg_loss = loss.ewm(
        alpha=1 / period,
        adjust=False,
    ).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)

    result = 100 - (100 / (1 + rs))

    return result.fillna(50)


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:

    previous_close = df["Close"].shift(1)

    tr = pd.concat(
        [
            df["High"] - df["Low"],
            (df["High"] - previous_close).abs(),
            (df["Low"] - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1)

    return tr.ewm(
        alpha=1 / period,
        adjust=False,
    ).mean()


def macd(
    series: pd.Series,
) -> Tuple[pd.Series, pd.Series, pd.Series]:

    fast = ema(series, 12)
    slow = ema(series, 26)

    line = fast - slow
    signal = ema(line, 9)

    histogram = line - signal

    return line, signal, histogram


def stochastic(
    df: pd.DataFrame,
    period: int = 14,
) -> Tuple[pd.Series, pd.Series]:

    low = df["Low"].rolling(period).min()
    high = df["High"].rolling(period).max()

    denominator = (high - low).replace(0, np.nan)

    k = 100 * (
        (df["Close"] - low) /
        denominator
    )

    d = k.rolling(3).mean()

    return k.fillna(50), d.fillna(50)


# ============================================================
# TECHNICAL ENGINE
# ============================================================

def add_indicators(df: pd.DataFrame) -> pd.DataFrame:

    d = df.copy()

    d["EMA20"] = ema(d["Close"], 20)
    d["EMA50"] = ema(d["Close"], 50)
    d["EMA200"] = ema(d["Close"], 200)

    d["RSI"] = rsi(d["Close"])

    (
        d["MACD"],
        d["MACDSignal"],
        d["MACDHist"],
    ) = macd(d["Close"])

    d["ATR"] = atr(d)

    d["ATR_PCT"] = (
        d["ATR"] / d["Close"]
    )

    d["VolumeAvg20"] = (
        d["Volume"]
        .rolling(20)
        .mean()
    )

    d["VolumeRatio"] = (
        d["Volume"] /
        d["VolumeAvg20"].replace(0, np.nan)
    )

    d["SMA20"] = (
        d["Close"]
        .rolling(20)
        .mean()
    )

    d["ROC5"] = (
        d["Close"]
        .pct_change(5)
    )

    d["ROC10"] = (
        d["Close"]
        .pct_change(10)
    )

    (
        d["StochK"],
        d["StochD"],
    ) = stochastic(d)

    # Approximate daily VWAP using typical price.
    typical_price = (
        d["High"] +
        d["Low"] +
        d["Close"]
    ) / 3

    cumulative_volume = d["Volume"].cumsum()

    d["VWAP"] = (
        typical_price * d["Volume"]
    ).cumsum() / cumulative_volume

    # Previous 20-day levels.
    d["Prior20High"] = (
        d["High"]
        .rolling(20)
        .max()
        .shift(1)
    )

    d["Prior20Low"] = (
        d["Low"]
        .rolling(20)
        .min()
        .shift(1)
    )

    # Support / resistance.
    d["Support10"] = (
        d["Low"]
        .rolling(10)
        .min()
        .shift(1)
    )

    d["Resistance10"] = (
        d["High"]
        .rolling(10)
        .max()
        .shift(1)
    )

    return d


# ============================================================
# CANDLESTICK / PRICE ACTION
# ============================================================

def price_action_signal(
    df: pd.DataFrame,
) -> Tuple[str, List[str], int]:

    if len(df) < 3:
        return "NEUTRAL", [], 0

    prev = df.iloc[-2]
    cur = df.iloc[-1]

    reasons = []

    bullish = 0
    bearish = 0

    prev_body = abs(
        prev["Close"] - prev["Open"]
    )

    cur_body = abs(
        cur["Close"] - cur["Open"]
    )

    cur_range = max(
        cur["High"] - cur["Low"],
        0.0001,
    )

    upper_wick = (
        cur["High"] -
        max(cur["Open"], cur["Close"])
    )

    lower_wick = (
        min(cur["Open"], cur["Close"]) -
        cur["Low"]
    )

    # Bullish engulfing
    if (
        prev["Close"] < prev["Open"]
        and cur["Close"] > cur["Open"]
        and cur["Open"] <= prev["Close"]
        and cur["Close"] >= prev["Open"]
    ):
        bullish += 2
        reasons.append("bullish engulfing")

    # Bearish engulfing
    if (
        prev["Close"] > prev["Open"]
        and cur["Close"] < cur["Open"]
        and cur["Open"] >= prev["Close"]
        and cur["Close"] <= prev["Open"]
    ):
        bearish += 2
        reasons.append("bearish engulfing")

    # Hammer
    if (
        lower_wick >= cur_body * 2
        and upper_wick <= cur_body
        and cur["Close"] > cur["Open"]
    ):
        bullish += 2
        reasons.append("hammer")

    # Shooting star
    if (
        upper_wick >= cur_body * 2
        and lower_wick <= cur_body
        and cur["Close"] < cur["Open"]
    ):
        bearish += 2
        reasons.append("shooting star")

    # Strong body
    if cur_body / cur_range >= 0.65:

        if cur["Close"] > cur["Open"]:
            bullish += 1
            reasons.append("strong bullish body")

        elif cur["Close"] < cur["Open"]:
            bearish += 1
            reasons.append("strong bearish body")

    if bullish > bearish:
        return "BULL", reasons, bullish

    if bearish > bullish:
        return "BEAR", reasons, bearish

    return "NEUTRAL", reasons, 0


# ============================================================
# TECHNICAL SCORING
# ============================================================

def analyze_direction(
    df: pd.DataFrame,
    direction: str,
    spy: Optional[pd.DataFrame],
) -> Dict[str, Any]:

    if len(df) < 210:
        return {
            "score": 0,
            "confluences": [],
            "reasons": [],
            "setup": "NO SETUP",
        }

    x = df.iloc[-1]

    p = num(x["Close"])
    e20 = num(x["EMA20"])
    e50 = num(x["EMA50"])
    e200 = num(x["EMA200"])

    r = num(x["RSI"], 50)

    macd_value = num(x["MACD"])
    macd_signal = num(x["MACDSignal"])
    macd_hist = num(x["MACDHist"])

    volume_ratio = num(
        x["VolumeRatio"],
        1,
    )

    stoch_k = num(x["StochK"], 50)
    stoch_d = num(x["StochD"], 50)

    vwap = num(x["VWAP"], p)

    atr_pct = num(x["ATR_PCT"], 0.03)

    score = 0

    confluences = []
    reasons = []

    setup_scores = {
        "BREAKOUT": 0,
        "BREAKDOWN": 0,
        "20 EMA REACTION": 0,
        "20 EMA REJECTION": 0,
        "MOMENTUM": 0,
    }

    # --------------------------------------------------------
    # 1. TREND
    # --------------------------------------------------------

    if direction == "CALL":

        if p > e20:
            score += 8
            confluences.append("Price > EMA20")

        if e20 > e50:
            score += 7
            confluences.append("EMA20 > EMA50")

        if e50 > e200:
            score += 5
            confluences.append("EMA50 > EMA200")

        if p > vwap:
            score += 4
            confluences.append("Price > VWAP")

    else:

        if p < e20:
            score += 8
            confluences.append("Price < EMA20")

        if e20 < e50:
            score += 7
            confluences.append("EMA20 < EMA50")

        if e50 < e200:
            score += 5
            confluences.append("EMA50 < EMA200")

        if p < vwap:
            score += 4
            confluences.append("Price < VWAP")

    # --------------------------------------------------------
    # 2. MOMENTUM
    # --------------------------------------------------------

    if direction == "CALL":

        if 52 <= r <= 72:
            score += 6
            confluences.append("Bullish RSI")

        if macd_value > macd_signal:
            score += 5
            confluences.append("MACD bullish")

        if macd_hist > 0:
            score += 3
            confluences.append("MACD histogram positive")

        if stoch_k > stoch_d:
            score += 3
            confluences.append("Stochastic bullish")

        if num(x["ROC5"]) > 0:
            score += 3
            confluences.append("5-day momentum positive")

    else:

        if 28 <= r <= 48:
            score += 6
            confluences.append("Bearish RSI")

        if macd_value < macd_signal:
            score += 5
            confluences.append("MACD bearish")

        if macd_hist < 0:
            score += 3
            confluences.append("MACD histogram negative")

        if stoch_k < stoch_d:
            score += 3
            confluences.append("Stochastic bearish")

        if num(x["ROC5"]) < 0:
            score += 3
            confluences.append("5-day momentum negative")

    # --------------------------------------------------------
    # 3. RELATIVE STRENGTH
    # --------------------------------------------------------

    rs = 0.0

    if spy is not None and len(spy) >= 25:

        stock_start = num(
            df["Close"].iloc[-21],
            p,
        )

        spy_start = num(
            spy["Close"].iloc[-21],
            num(spy["Close"].iloc[-1]),
        )

        stock_return = (
            p / stock_start - 1
            if stock_start
            else 0
        )

        spy_return = (
            num(spy["Close"].iloc[-1])
            / spy_start - 1
            if spy_start
            else 0
        )

        rs = stock_return - spy_return

    if direction == "CALL" and rs > 0.03:
        score += 8
        confluences.append("Relative strength vs SPY")

    if direction == "PUT" and rs < -0.03:
        score += 8
        confluences.append("Relative weakness vs SPY")

    # --------------------------------------------------------
    # 4. VOLUME
    # --------------------------------------------------------

    if volume_ratio >= 1.25:
        score += 8
        confluences.append("Volume expansion")

    elif volume_ratio >= 1.05:
        score += 4
        confluences.append("Above-average volume")

    # --------------------------------------------------------
    # 5. PRICE ACTION
    # --------------------------------------------------------

    pa_direction, pa_reasons, pa_strength = (
        price_action_signal(df)
    )

    if direction == "CALL" and pa_direction == "BULL":

        score += 6
        confluences.append("Bullish price action")
        reasons.extend(pa_reasons)

    elif direction == "PUT" and pa_direction == "BEAR":

        score += 6
        confluences.append("Bearish price action")
        reasons.extend(pa_reasons)

    # --------------------------------------------------------
    # 6. SETUP TYPE
    # --------------------------------------------------------

    prior20_high = num(
        x["Prior20High"],
        float("inf"),
    )

    prior20_low = num(
        x["Prior20Low"],
        float("-inf"),
    )

    near_ema = (
        abs(p - e20) / p <= 0.025
        if p > 0
        else False
    )

    if direction == "CALL":

        if p > prior20_high:
            score += 10
            setup_scores["BREAKOUT"] = 10
            reasons.append("20-day breakout")
            confluences.append("20-day breakout")
            setup = "BREAKOUT"

        elif near_ema and p >= e50:
            score += 10
            setup_scores["20 EMA REACTION"] = 10
            reasons.append("20 EMA reaction")
            confluences.append("20 EMA reaction")
            setup = "20 EMA REACTION"

        else:
            setup = "MOMENTUM"
            setup_scores["MOMENTUM"] = 5

    else:

        if p < prior20_low:
            score += 10
            setup_scores["BREAKDOWN"] = 10
            reasons.append("20-day breakdown")
            confluences.append("20-day breakdown")
            setup = "BREAKDOWN"

        elif near_ema and p <= e50:
            score += 10
            setup_scores["20 EMA REJECTION"] = 10
            reasons.append("20 EMA rejection")
            confluences.append("20 EMA rejection")
            setup = "20 EMA REJECTION"

        else:
            setup = "MOMENTUM"
            setup_scores["MOMENTUM"] = 5

    # --------------------------------------------------------
    # 7. VOLATILITY SANITY
    # --------------------------------------------------------

    if 0.015 <= atr_pct <= 0.10:
        score += 4
        confluences.append("Healthy volatility")

    # Avoid chasing extremely extended moves.
    if direction == "CALL":

        if p > e20 + 1.5 * num(x["ATR"], p * 0.02):
            score -= 5
            reasons.append("extended above EMA20")

    else:

        if p < e20 - 1.5 * num(x["ATR"], p * 0.02):
            score -= 5
            reasons.append("extended below EMA20")

    score = clamp(score, 0, 100)

    # Remove duplicate confluences.
    confluences = list(
        dict.fromkeys(confluences)
    )

    # Independent confluence count.
    confluence_count = len(confluences)

    return {
        "score": round(score, 1),
        "confluences": confluences,
        "confluence_count": confluence_count,
        "reasons": reasons,
        "setup": setup,
        "rs": rs,
        "price_action": pa_direction,
        "atr_pct": atr_pct,
    }


# ============================================================
# RISK / TARGET ENGINE
# ============================================================

def risk_plan(
    df: pd.DataFrame,
    direction: str,
) -> Dict[str, Any]:

    p = num(
        df["Close"].iloc[-1],
        0,
    )

    a = num(
        df["ATR"].iloc[-1],
        max(p * 0.02, 0.01),
    )

    recent_low = num(
        df["Low"].tail(10).min(),
        p,
    )

    recent_high = num(
        df["High"].tail(10).max(),
        p,
    )

    if direction == "CALL":

        atr_stop = (
            p -
            ATR_STOP_MULTIPLE * a
        )

        structure_stop = recent_low

        stop = min(
            structure_stop,
            atr_stop,
        )

        if stop <= 0 or stop >= p:
            stop = atr_stop

        risk = p - stop

        target = (
            p +
            PREFERRED_R * risk
        )

    else:

        atr_stop = (
            p +
            ATR_STOP_MULTIPLE * a
        )

        structure_stop = recent_high

        stop = max(
            structure_stop,
            atr_stop,
        )

        if stop <= p:
            stop = atr_stop

        risk = stop - p

        target = (
            p -
            PREFERRED_R * risk
        )

    if risk <= 0:
        return {
            "valid": False,
        }

    stop_pct = abs(
        stop / p - 1
    )

    target_pct = abs(
        target / p - 1
    )

    actual_r = (
        abs(target - p) / risk
    )

    # Keep projected stock movement reasonable.
    valid = (
        0.025 <= target_pct <= 0.18
        and MIN_R <= actual_r <= MAX_R
    )

    return {
        "valid": valid,
        "stock_entry": p,
        "stock_stop": stop,
        "stock_target": target,
        "risk": risk,
        "stop_pct": stop_pct,
        "target_pct": target_pct,
        "r_multiple": actual_r,
    }


# ============================================================
# OPTION ENGINE
# ============================================================

def get_greek(
    option: dict,
    name: str,
) -> float:

    greeks = option.get("greeks")

    if isinstance(greeks, dict):
        return num(
            greeks.get(name),
            0,
        )

    return num(
        option.get(name),
        0,
    )


def option_mid(
    option: dict,
) -> float:

    bid = num(option.get("bid"))
    ask = num(option.get("ask"))
    last = num(
        option.get("lastPrice"),
        num(option.get("last")),
    )

    if bid > 0 and ask > 0:
        return (bid + ask) / 2

    if last > 0:
        return last

    return 0


def choose_expiration(
    expirations: List[str],
) -> Optional[Tuple[str, int]]:

    today = date.today()

    candidates = []

    for expiration in expirations:

        try:
            d = datetime.strptime(
                expiration[:10],
                "%Y-%m-%d",
            ).date()
        except Exception:
            continue

        dte = (
            d - today
        ).days

        if MIN_DTE <= dte <= MAX_DTE:

            # Prefer roughly 7 DTE.
            candidates.append(
                (
                    abs(dte - 7),
                    dte,
                    expiration[:10],
                )
            )

    if not candidates:
        return None

    candidates.sort()

    _, dte, expiration = candidates[0]

    return expiration, dte


def option_contract_score(
    option: dict,
    direction: str,
) -> float:

    bid = num(option.get("bid"))
    ask = num(option.get("ask"))

    mid = option_mid(option)

    if mid <= 0:
        return -1_000_000

    if bid <= 0 or ask <= 0:
        return -1_000_000

    spread_pct = (
        (ask - bid) / mid
        if mid > 0
        else 1
    )

    oi = num(
        option.get("open_interest")
    )

    volume = num(
        option.get("volume")
    )

    delta = get_greek(
        option,
        "delta",
    )

    abs_delta = abs(delta)

    if (
        abs_delta < MIN_DELTA
        or abs_delta > MAX_DELTA
    ):
        return -1_000_000

    if oi < MIN_OPEN_INTEREST:
        return -1_000_000

    if volume < MIN_OPTION_VOLUME:
        return -1_000_000

    if spread_pct > MAX_SPREAD_PCT:
        return -1_000_000

    if direction == "CALL" and delta <= 0:
        return -1_000_000

    if direction == "PUT" and delta >= 0:
        return -1_000_000

    score = 0

    # Prefer ~0.50 delta.
    score += max(
        0,
        10 -
        abs(abs_delta - 0.50) * 25
    )

    # Liquidity.
    score += min(
        10,
        math.log10(max(oi, 1)) * 2,
    )

    score += min(
        8,
        math.log10(max(volume, 1)) * 2,
    )

    # Tight spread.
    score += max(
        0,
        10 -
        spread_pct * 40,
    )

    return score


def choose_option(
    client: TradierClient,
    symbol: str,
    direction: str,
    stock_price: float,
    stock_stop: float,
    stock_target: float,
) -> Optional[Dict[str, Any]]:

    try:
        expirations = (
            client.option_expirations(symbol)
        )

        chosen = choose_expiration(
            expirations
        )

        if not chosen:
            return None

        expiration, dte = chosen

        chain = client.option_chain(
            symbol,
            expiration,
        )

        if not chain:
            return None

    except Exception:
        return None

    best = None
    best_score = -1_000_000

    for option in chain:

        option_type = str(
            option.get("option_type")
            or option.get("type")
            or ""
        ).lower()

        if direction == "CALL":
            if option_type not in (
                "call",
                "c",
            ):
                continue

        else:
            if option_type not in (
                "put",
                "p",
            ):
                continue

        strike = num(
            option.get("strike")
        )

        if strike <= 0:
            continue

        score = option_contract_score(
            option,
            direction,
        )

        if score > best_score:

            best_score = score
            best = option

    if best is None:
        return None

    entry = option_mid(best)

    if entry <= 0:
        return None

    delta = get_greek(
        best,
        "delta",
    )

    # --------------------------------------------------------
    # Approximate option stop / target.
    #
    # This is a planning estimate based on delta. It is NOT
    # a guaranteed option price prediction.
    # --------------------------------------------------------

    stock_move_to_stop = abs(
        stock_stop - stock_price
    )

    stock_move_to_target = abs(
        stock_target - stock_price
    )

    option_stop = max(
        0.05,
        entry -
        abs(delta) *
        stock_move_to_stop,
    )

    option_target = (
        entry +
        abs(delta) *
        stock_move_to_target
    )

    # Round to realistic cents.
    entry = round(entry, 2)
    option_stop = round(
        option_stop,
        2,
    )
    option_target = round(
        option_target,
        2,
    )

    return {
        "expiration": expiration,
        "dte": dte,
        "strike": strike,
        "option_type": (
            "CALL"
            if direction == "CALL"
            else "PUT"
        ),
        "option_symbol": best.get(
            "symbol",
            "",
        ),
        "bid": num(
            best.get("bid")
        ),
        "ask": num(
            best.get("ask")
        ),
        "entry": entry,
        "delta": delta,
        "open_interest": int(
            num(
                best.get(
                    "open_interest"
                )
            )
        ),
        "option_volume": int(
            num(
                best.get("volume")
            )
        ),
        "option_stop": option_stop,
        "option_target": option_target,
        "contract_score": round(
            best_score,
            1,
        ),
    }


# ============================================================
# FULL SYMBOL ANALYSIS
# ============================================================

def analyze_symbol(
    client: TradierClient,
    symbol: str,
    quote: dict,
    spy: Optional[pd.DataFrame],
    include_options: bool = True,
) -> Optional[Dict[str, Any]]:

    price = num(
        quote.get("last")
        or quote.get("close")
    )

    avg_volume = num(
        quote.get("average_volume")
        or quote.get("avg_volume")
        or quote.get("volume")
    )

    market_cap = num(
        quote.get("market_cap")
        or quote.get("marketCap")
    )

    # --------------------------------------------------------
    # Basic stock filters
    # --------------------------------------------------------

    if price < MIN_STOCK_PRICE:
        return None

    if avg_volume and avg_volume < MIN_AVG_VOLUME:
        return None

    if market_cap and market_cap < MIN_MARKET_CAP:
        return None

    try:

        end_date = date.today()

        start_date = (
            end_date -
            timedelta(
                days=HISTORY_DAYS
            )
        )

        df = client.history(
            symbol,
            start_date,
            end_date,
        )

    except Exception:

        return None

    if df.empty or len(df) < 210:
        return None

    df = add_indicators(df)

    # --------------------------------------------------------
    # Evaluate BOTH directions.
    # --------------------------------------------------------

    call = analyze_direction(
        df,
        "CALL",
        spy,
    )

    put = analyze_direction(
        df,
        "PUT",
        spy,
    )

    if call["score"] >= put["score"]:

        direction = "CALL"
        analysis = call

    else:

        direction = "PUT"
        analysis = put

    score = analysis["score"]

    # --------------------------------------------------------
    # Minimum score.
    # --------------------------------------------------------

    if score < MIN_SCORE:
        return None

    # --------------------------------------------------------
    # Minimum independent confluence.
    # --------------------------------------------------------

    if analysis[
        "confluence_count"
    ] < 3:

        return None

    # --------------------------------------------------------
    # Risk plan.
    # --------------------------------------------------------

    plan = risk_plan(
        df,
        direction,
    )

    if not plan.get("valid"):
        return None

    option = None

    if include_options:

        option = choose_option(
            client,
            symbol,
            direction,
            plan["stock_entry"],
            plan["stock_stop"],
            plan["stock_target"],
        )

        # A stock can be technically good but still fail
        # the option liquidity test.
        if option is None:
            return None

    golden = (
        score >= GOLDEN_SCORE
        and analysis[
            "confluence_count"
        ] >= 5
        and plan["r_multiple"] >= 1.45
    )

    x = df.iloc[-1]

    result = {
        "ticker": symbol,
        "score": round(score, 1),
        "grade": grade(score),
        "golden": golden,
        "direction": direction,
        "setup": analysis["setup"],
        "price": round(
            price,
            2,
        ),
        "rsi": round(
            num(x["RSI"], 50),
            1,
        ),
        "atr": round(
            num(x["ATR"]),
            2,
        ),
        "atr_pct": round(
            num(x["ATR_PCT"]) * 100,
            2,
        ),
        "volume_ratio": round(
            num(x["VolumeRatio"], 1),
            2,
        ),
        "relative_strength": round(
            analysis["rs"] * 100,
            2,
        ),
        "confluence_count": analysis[
            "confluence_count"
        ],
        "confluences": analysis[
            "confluences"
        ],
        "reasons": list(
            dict.fromkeys(
                analysis["reasons"]
            )
        )[:10],
        "stock_stop": round(
            plan["stock_stop"],
            2,
        ),
        "stock_target": round(
            plan["stock_target"],
            2,
        ),
        "r_multiple": round(
            plan["r_multiple"],
            2,
        ),
        "stop_pct": round(
            plan["stop_pct"] * 100,
            2,
        ),
        "target_pct": round(
            plan["target_pct"] * 100,
            2,
        ),
        "option": option,
    }

    return result


# ============================================================
# GRADING
# ============================================================

def grade(score: float) -> str:

    if score >= 95:
        return "A+"

    if score >= 90:
        return "A"

    if score >= 85:
        return "A-"

    if score >= 80:
        return "B+"

    if score >= 76:
        return "B"

    if score >= 70:
        return "C+"

    return "C"


# ============================================================
# QOD FORMATTER
# ============================================================

def month_week_label(
    expiration: str,
) -> str:

    d = datetime.strptime(
        expiration[:10],
        "%Y-%m-%d",
    ).date()

    week = (
        (d.day - 1) // 7
    ) + 1

    return (
        f"{d.strftime('%B')} "
        f"Week {week}"
    )


def format_trade(
    trade: Dict[str, Any],
) -> str:

    option = trade["option"]

    expiration = option[
        "expiration"
    ]

    contract = (
        f"({trade['ticker']}) "
        f"{month_week_label(expiration)} "
        f"({datetime.strptime(expiration[:10], '%Y-%m-%d').strftime('%m/%d')}) "
        f"{option['strike']:g} "
        f"{option['option_type'].title()}"
    )

    return (
        "NEW TRADE:\n\n"
        "Buy-to-Open the\n"
        f"{contract} at "
        f"{option['entry']:.2f} or less.\n\n"
        f"Apply a stop of "
        f"{option['option_stop']:.2f}\n"
        f"Target to "
        f"{option['option_target']:.2f} "
        "or more in Full position."
    )


# ============================================================
# STREAMLIT DISPLAY
# ============================================================

def display_trade_card(
    trade: Dict[str, Any],
    rank: int,
):

    option = trade["option"]

    title = (
        "🥇 GOLDEN QOD"
        if trade["golden"]
        else f"#{rank} QUALIFIED SETUP"
    )

    st.markdown(
        f"## {title}"
    )

    st.markdown(
        f"### {trade['ticker']} "
        f"— {trade['direction']}"
    )

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        st.metric(
            "Score",
            f"{trade['score']:.1f}",
        )

    with c2:
        st.metric(
            "Grade",
            trade["grade"],
        )

    with c3:
        st.metric(
            "Confluences",
            trade["confluence_count"],
        )

    with c4:
        st.metric(
            "Risk / Reward",
            f"{trade['r_multiple']:.2f}R",
        )

    st.write(
        f"**Setup:** {trade['setup']}"
    )

    st.write(
        f"**Stock:** ${trade['price']:.2f}"
    )

    st.write(
        f"**Stock Stop:** ${trade['stock_stop']:.2f}  "
        f" |  **Stock Target:** ${trade['stock_target']:.2f}"
    )

    st.write(
        f"**Option:** "
        f"{option['strike']:g} "
        f"{option['option_type']}  "
        f"exp. {option['expiration']} "
        f"({option['dte']} DTE)"
    )

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        st.metric(
            "Entry",
            f"${option['entry']:.2f}",
        )

    with c2:
        st.metric(
            "Option Stop",
            f"${option['option_stop']:.2f}",
        )

    with c3:
        st.metric(
            "Option Target",
            f"${option['option_target']:.2f}",
        )

    with c4:
        st.metric(
            "Delta",
            f"{option['delta']:.2f}",
        )

    st.write(
        f"**Option Volume:** "
        f"{option['option_volume']:,}"
        f"  |  **Open Interest:** "
        f"{option['open_interest']:,}"
    )

    st.write(
        f"**RSI:** {trade['rsi']:.1f}"
        f"  |  **ATR:** ${trade['atr']:.2f}"
        f"  |  **Volume Ratio:** "
        f"{trade['volume_ratio']:.2f}x"
    )

    st.write(
        "**Confluence:** "
        + ", ".join(
            trade["confluences"]
        )
    )

    with st.expander(
        "📋 QOD TRADE ALERT"
    ):

        st.code(
            format_trade(trade),
            language=None,
        )

    st.divider()


# ============================================================
# MAIN STREAMLIT APPLICATION
# ============================================================

def main():

    st.title(
        "🥇 GOLDEN SCANNER"
    )

    st.subheader(
        "Golden QOD Short-Term Options Scanner"
    )

    st.caption(
        "Established companies • $10+ stocks • "
        "2–14 DTE • CALL & PUT • "
        "3+ confluences • 1.25–1.75R risk model"
    )

    # --------------------------------------------------------
    # SIDEBAR
    # --------------------------------------------------------

    st.sidebar.header(
        "⚙️ Scanner Settings"
    )

    token = None

    # Streamlit Cloud secrets first.
    try:

        token = st.secrets.get(
            "TRADIER_TOKEN"
        )

    except Exception:

        token = None

    # Environment variable fallback.
    if not token:

        token = os.getenv(
            "TRADIER_TOKEN"
        )

    if not token:

        st.warning(
            "⚠️ Tradier API token not found."
        )

        st.info(
            "Add TRADIER_TOKEN to your "
            "Streamlit secrets or environment variables."
        )

        st.code(
            'TRADIER_TOKEN = "YOUR_TRADIER_TOKEN"',
            language="toml",
        )

        st.stop()

    max_results = st.sidebar.slider(
        "Maximum results",
        min_value=1,
        max_value=15,
        value=MAX_RESULTS,
    )

    min_score = st.sidebar.slider(
        "Minimum score",
        min_value=70,
        max_value=95,
        value=MIN_SCORE,
    )

    include_options = st.sidebar.checkbox(
        "Require qualifying option contract",
        value=True,
    )

    custom_symbols = st.sidebar.text_area(
        "Optional custom symbols",
        placeholder=(
            "WMT, V, HD, COST, MSFT, AAPL"
        ),
    )

    if custom_symbols.strip():

        symbols = [
            x.strip().upper()
            for x in custom_symbols.split(",")
            if x.strip()
        ]

    else:

        symbols = DEFAULT_SYMBOLS

    st.sidebar.write(
        f"Universe: **{len(symbols)} stocks**"
    )

    st.sidebar.markdown(
        """
**Stock filters**

• Minimum price: $10  
• Established companies  
• Minimum avg volume: 500K  
• Minimum market cap: $2B  

**Options**

• 2–14 DTE  
• Delta 0.35–0.70  
• OI ≥ 100  
• Volume ≥ 10  
• Spread ≤ 20%  

**Risk**

• Minimum 1.25R  
• Preferred 1.50R  
• Maximum 1.75R
"""
    )

    # --------------------------------------------------------
    # RUN BUTTON
    # --------------------------------------------------------

    run_scan = st.button(
        "🚀 RUN GOLDEN SCANNER",
        type="primary",
        use_container_width=True,
    )

    if not run_scan:
        st.info(
            "Ready. Click **RUN GOLDEN SCANNER** "
            "to scan the market."
        )

        st.markdown(
            """
### What this scanner is looking for

🥇 **Golden QOD**

The scanner is looking for short-duration setups with
multiple independent pieces of confirmation:

1. **Trend**
2. **Momentum**
3. **MACD**
4. **EMA structure**
5. **VWAP**
6. **Relative strength vs SPY**
7. **Volume**
8. **Stochastic**
9. **Price action / candlestick**
10. **Breakout, breakdown or EMA reaction**

It will **not force a trade** when the market does not
produce a qualifying setup.
"""
        )

        return

    # --------------------------------------------------------
    # RUN SCAN
    # --------------------------------------------------------

    client = TradierClient(
        token
    )

    progress = st.progress(0)

    status = st.empty()

    candidates = []

    # --------------------------------------------------------
    # SPY BENCHMARK
    # --------------------------------------------------------

    status.write(
        "Loading SPY benchmark..."
    )

    try:

        spy = client.history(
            "SPY",
            date.today()
            - timedelta(
                days=HISTORY_DAYS
            ),
            date.today(),
        )

    except Exception:

        spy = None

    if spy is not None and not spy.empty:

        spy = add_indicators(
            spy
        )

    # --------------------------------------------------------
    # QUOTES
    # --------------------------------------------------------

    status.write(
        f"Loading quotes for "
        f"{len(symbols)} stocks..."
    )

    try:

        # Tradier accepts batches, so process
        # in manageable groups.
        quotes = {}

        batch_size = 100

        for start in range(
            0,
            len(symbols),
            batch_size,
        ):

            batch = symbols[
                start:start + batch_size
            ]

            try:

                quotes.update(
                    client.quotes(batch)
                )

            except Exception:

                continue

    except Exception as e:

        st.error(
            f"Unable to load Tradier quotes: {e}"
        )

        return

    # --------------------------------------------------------
    # ANALYSIS
    # --------------------------------------------------------

    total_symbols = len(symbols)

    for index, symbol in enumerate(
        symbols,
        start=1,
    ):

        status.write(
            f"Analyzing {symbol} "
            f"({index}/{total_symbols})..."
        )

        quote = quotes.get(
            symbol
        )

        if not quote:
            progress.progress(
                index / total_symbols
            )
            continue

        try:

            result = analyze_symbol(
                client,
                symbol,
                quote,
                spy,
                include_options=include_options,
            )

            if result:

                if result["score"] >= min_score:

                    candidates.append(
                        result
                    )

        except Exception:
            pass

        progress.progress(
            index / total_symbols
        )

    status.empty()
    progress.empty()

    # --------------------------------------------------------
    # SORT
    # --------------------------------------------------------

    candidates.sort(
        key=lambda x: (
            x["golden"],
            x["score"],
            x["confluence_count"],
            (
                x["option"][
                    "option_volume"
                ]
                if x.get("option")
                else 0
            ),
        ),
        reverse=True,
    )

    candidates = candidates[
        :max_results
    ]

    # --------------------------------------------------------
    # NO TRADE
    # --------------------------------------------------------

    if not candidates:

        st.error(
            "🚫 NO QUALIFYING GOLDEN QOD SETUPS"
        )

        st.warning(
            "The scanner did not find a setup "
            "meeting the current technical, "
            "confluence, risk and option-liquidity "
            "requirements."
        )

        st.info(
            "That is intentional — the scanner "
            "will NOT force a trade."
        )

        return

    # --------------------------------------------------------
    # SUMMARY
    # --------------------------------------------------------

    golden_trades = [
        x for x in candidates
        if x["golden"]
    ]

    st.success(
        f"Found {len(candidates)} "
        f"qualifying setup(s)."
    )

    if golden_trades:

        st.success(
            f"🥇 {len(golden_trades)} "
            f"GOLDEN QOD setup(s) detected."
        )

    else:

        st.info(
            "No setup reached the special "
            "GOLDEN QOD threshold."
        )

    # --------------------------------------------------------
    # TOP GOLDEN SETUP
    # --------------------------------------------------------

    if golden_trades:

        st.markdown(
            "# 🥇 GOLDEN QOD — TOP SETUP"
        )

        display_trade_card(
            golden_trades[0],
            1,
        )

    # --------------------------------------------------------
    # ALL RESULTS
    # --------------------------------------------------------

    st.markdown(
        "# 📊 QUALIFYING SETUPS"
    )

    table_rows = []

    for rank, trade in enumerate(
        candidates,
        start=1,
    ):

        option = trade.get(
            "option"
        )

        table_rows.append(
            {
                "Rank": rank,
                "Ticker": trade[
                    "ticker"
                ],
                "Score": trade[
                    "score"
                ],
                "Grade": trade[
                    "grade"
                ],
                "Golden": (
                    "🥇"
                    if trade[
                        "golden"
                    ]
                    else ""
                ),
                "Direction": trade[
                    "direction"
                ],
                "Setup": trade[
                    "setup"
                ],
                "Stock": trade[
                    "price"
                ],
                "Option": (
                    f"{option['strike']:g} "
                    f"{option['option_type']}"
                    if option
                    else "-"
                ),
                "DTE": (
                    option["dte"]
                    if option
                    else "-"
                ),
                "Entry": (
                    option["entry"]
                    if option
                    else "-"
                ),
                "Stop": (
                    option["option_stop"]
                    if option
                    else "-"
                ),
                "Target": (
                    option["option_target"]
                    if option
                    else "-"
                ),
                "Confluences": trade[
                    "confluence_count"
                ],
                "R": trade[
                    "r_multiple"
                ],
            }
        )

    result_df = pd.DataFrame(
        table_rows
    )

    st.dataframe(
        result_df,
        use_container_width=True,
        hide_index=True,
    )

    # --------------------------------------------------------
    # DETAILED CARDS
    # --------------------------------------------------------

    st.markdown(
        "# 🔎 TRADE DETAILS"
    )

    displayed_golden = (
        golden_trades[0]["ticker"]
        if golden_trades
        else None
    )

    detail_rank = 1

    for trade in candidates:

        # Don't display the top Golden twice.
        if (
            displayed_golden
            and trade["ticker"]
            == displayed_golden
        ):
            continue

        display_trade_card(
            trade,
            detail_rank,
        )

        detail_rank += 1

    # --------------------------------------------------------
    # DISCLAIMER
    # --------------------------------------------------------

    st.caption(
        "Educational/analytical tool only. "
        "Technical scores and option targets are estimates, "
        "not guarantees of future performance, fills, or profit. "
        "Option prices can move rapidly and implied volatility "
        "can materially affect results."
    )


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    main()
