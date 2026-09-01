import streamlit as st
import pandas as pd
import requests
import numpy as np
from datetime import datetime, date, timedelta

st.set_page_config(
    page_title="Swing Hunter",
    page_icon="🦅",
    layout="wide"
)

st.title("🦅 SWING HUNTER")
st.subheader("1–2 Week Stock & Options Swing Scanner")

st.info(
    "V2 TEST MODE — Tradier market data powers the technical engine. "
    "No trades are placed."
)

# =========================================================
# SETTINGS
# =========================================================

st.sidebar.header("Scanner Settings")

account_size = st.sidebar.selectbox(
    "Account Size",
    [2000, 2500, 3000, 3500, 4000, 4500, 5000],
    index=3
)

symbol = st.sidebar.text_input(
    "Test Symbol",
    "AAPL"
).upper().strip()

timeframe = st.sidebar.selectbox(
    "Analysis Timeframe",
    ["daily", "weekly"]
)

# =========================================================
# TRADIER AUTHENTICATION
# =========================================================

try:
    token = st.secrets["TRADIER_SANDBOX_TOKEN"]

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json"
    }

except Exception:

    st.error(
        "🔴 Tradier secret not found. "
        "Check Streamlit Secrets."
    )

    st.stop()

# =========================================================
# HISTORICAL DATA
# =========================================================

st.header("📊 Technical Analysis")

try:

    end_date = date.today()
    start_date = end_date - timedelta(days=450)

    history_response = requests.get(
        "https://sandbox.tradier.com/v1/markets/history",
        params={
            "symbol": symbol,
            "interval": "daily",
            "start": start_date.isoformat(),
            "end": end_date.isoformat()
        },
        headers=headers,
        timeout=10
    )

    if history_response.status_code != 200:

        st.error(
            f"Historical data request failed: "
            f"HTTP {history_response.status_code}"
        )

        st.code(history_response.text)

        st.stop()

    history_data = history_response.json()

    history = (
        history_data
        .get("history", {})
        .get("day", [])
    )

    if not history:

        st.warning(
            f"No historical data returned for {symbol}."
        )

        st.stop()

    df = pd.DataFrame(history)

    df["date"] = pd.to_datetime(df["date"])

    numeric_columns = [
        "open",
        "high",
        "low",
        "close",
        "volume"
    ]

    for column in numeric_columns:

        df[column] = pd.to_numeric(
            df[column],
            errors="coerce"
        )

    df = (
        df
        .dropna()
        .sort_values("date")
        .reset_index(drop=True)
    )

except Exception as e:

    st.error(
        "🔴 Historical data engine failed."
    )

    st.code(str(e))

    st.stop()

# =========================================================
# INDICATORS
# =========================================================

close = df["close"]
high = df["high"]
low = df["low"]
volume = df["volume"]

df["EMA20"] = close.ewm(
    span=20,
    adjust=False
).mean()

df["EMA50"] = close.ewm(
    span=50,
    adjust=False
).mean()

df["EMA200"] = close.ewm(
    span=200,
    adjust=False
).mean()

# ---------------------------------------------------------
# RSI
# ---------------------------------------------------------

delta = close.diff()

gain = delta.clip(
    lower=0
)

loss = -delta.clip(
    upper=0
)

avg_gain = gain.rolling(14).mean()
avg_loss = loss.rolling(14).mean()

rs = avg_gain / avg_loss.replace(
    0,
    np.nan
)

df["RSI"] = 100 - (
    100 / (1 + rs)
)

# ---------------------------------------------------------
# MACD
# ---------------------------------------------------------

ema12 = close.ewm(
    span=12,
    adjust=False
).mean()

ema26 = close.ewm(
    span=26,
    adjust=False
).mean()

df["MACD"] = ema12 - ema26

df["MACD_signal"] = df["MACD"].ewm(
    span=9,
    adjust=False
).mean()

# ---------------------------------------------------------
# ATR
# ---------------------------------------------------------

previous_close = close.shift(1)

true_range = pd.concat(
    [
        high - low,
        (high - previous_close).abs(),
        (low - previous_close).abs()
    ],
    axis=1
).max(axis=1)

df["ATR14"] = true_range.rolling(14).mean()

# ---------------------------------------------------------
# VOLUME
# ---------------------------------------------------------

df["VolumeAvg20"] = volume.rolling(20).mean()

latest = df.iloc[-1]

price = float(latest["close"])
ema20 = float(latest["EMA20"])
ema50 = float(latest["EMA50"])
ema200 = float(latest["EMA200"])
rsi = float(latest["RSI"])
macd = float(latest["MACD"])
macd_signal = float(latest["MACD_signal"])
atr = float(latest["ATR14"])
current_volume = float(latest["volume"])
average_volume = float(latest["VolumeAvg20"])

# =========================================================
# AUTOMATIC SCORING
# =========================================================

# ---------------------------------------------------------
# 1. TREND
# ---------------------------------------------------------

if (
    price > ema20
    and ema20 > ema50
    and ema50 > ema200
):

    trend_score = 100

elif (
    price > ema20
    and ema20 > ema50
):

    trend_score = 85

elif (
    price < ema20
    and ema20 < ema50
    and ema50 < ema200
):

    trend_score = 100

elif (
    price < ema20
    and ema20 < ema50
):

    trend_score = 85

else:

    trend_score = 50

# ---------------------------------------------------------
# 2. MOMENTUM
# ---------------------------------------------------------

if (
    rsi >= 55
    and rsi <= 70
    and macd > macd_signal
):

    momentum_score = 100

elif (
    rsi > 50
    and macd > macd_signal
):

    momentum_score = 85

elif (
    rsi <= 45
    and macd < macd_signal
):

    momentum_score = 100

elif (
    rsi < 50
    and macd < macd_signal
):

    momentum_score = 85

else:

    momentum_score = 50

# ---------------------------------------------------------
# 3. VOLUME
# ---------------------------------------------------------

volume_ratio = (
    current_volume / average_volume
    if average_volume > 0
    else 1
)

if volume_ratio >= 1.5:

    volume_score = 100

elif volume_ratio >= 1.2:

    volume_score = 85

elif volume_ratio >= 1.0:

    volume_score = 70

else:

    volume_score = 45

# ---------------------------------------------------------
# 4. MARKET STRUCTURE
# ---------------------------------------------------------

recent = df.tail(20)

recent_high = recent["high"].max()
recent_low = recent["low"].min()

older = df.iloc[-40:-20]

older_high = older["high"].max()
older_low = older["low"].min()

if (
    recent_high > older_high
    and recent_low > older_low
):

    structure_score = 100

elif (
    recent_high < older_high
    and recent_low < older_low
):

    structure_score = 100

else:

    structure_score = 55

# ---------------------------------------------------------
# 5. SUPPORT / RESISTANCE
# ---------------------------------------------------------

distance_from_low = (
    price - recent_low
)

distance_from_high = (
    recent_high - price
)

if (
    distance_from_low
    < distance_from_high
):

    support_score = 85

elif (
    distance_from_high
    < distance_from_low
):

    support_score = 85

else:

    support_score = 60

# ---------------------------------------------------------
# 6. HIGHER-TIMEFRAME CONFIRMATION
# ---------------------------------------------------------

if (
    price > ema50
    and ema50 > ema200
):

    higher_tf_score = 90

elif (
    price < ema50
    and ema50 < ema200
):

    higher_tf_score = 90

else:

    higher_tf_score = 55

# =========================================================
# FINAL SCORE
# =========================================================

swing_score = (

    trend_score * 0.20

    + momentum_score * 0.20

    + volume_score * 0.15

    + structure_score * 0.15

    + support_score * 0.15

    + higher_tf_score * 0.15

)

swing_score = round(
    swing_score,
    1
)

# =========================================================
# DIRECTION
# =========================================================

bullish_score = (
    trend_score
    + momentum_score
    + structure_score
)

bearish_score = (
    (100 - trend_score)
    + (100 - momentum_score)
    + (100 - structure_score)
)

if bullish_score >= bearish_score:

    direction = "🟢 BULLISH"
    option_bias = "CALL"

else:

    direction = "🔴 BEARISH"
    option_bias = "PUT"

# =========================================================
# GRADE
# =========================================================

if swing_score >= 90:

    grade = "A+"
    status = "🔥 HIGH-QUALITY SETUP"

elif swing_score >= 85:

    grade = "A"
    status = "🟢 STRONG SETUP"

elif swing_score >= 80:

    grade = "B+"
    status = "🟢 GOOD SETUP"

elif swing_score >= 75:

    grade = "B"
    status = "🟡 WATCH"

else:

    grade = "C"
    status = "⚪ WAIT"

# =========================================================
# DASHBOARD
# =========================================================

c1, c2, c3, c4 = st.columns(4)

c1.metric(
    "Swing Score",
    f"{swing_score}/100"
)

c2.metric(
    "Grade",
    grade
)

c3.metric(
    "Direction",
    direction
)

c4.metric(
    "Option Bias",
    option_bias
)

st.success(
    f"{status} — {symbol}"
)

# =========================================================
# MARKET DATA
# =========================================================

st.subheader(
    "📈 Market Snapshot"
)

m1, m2, m3, m4 = st.columns(4)

m1.metric(
    "Price",
    f"${price:.2f}"
)

m2.metric(
    "RSI",
    f"{rsi:.1f}"
)

m3.metric(
    "Volume Ratio",
    f"{volume_ratio:.2f}x"
)

m4.metric(
    "ATR",
    f"${atr:.2f}"
)

# =========================================================
# CONFLUENCE
# =========================================================

st.subheader(
    "🧠 Automatic Confluence"
)

score_df = pd.DataFrame({

    "Factor": [
        "Trend",
        "Momentum",
        "Volume",
        "Market Structure",
        "Support / Resistance",
        "Higher Timeframe"
    ],

    "Score": [
        trend_score,
        momentum_score,
        volume_score,
        structure_score,
        support_score,
        higher_tf_score
    ],

    "Weight": [
        "20%",
        "20%",
        "15%",
        "15%",
        "15%",
        "15%"
    ]
})

st.dataframe(
    score_df,
    use_container_width=True,
    hide_index=True
)

# =========================================================
# TECHNICAL DETAILS
# =========================================================

with st.expander(
    "🔎 Technical Details"
):

    st.write(
        f"20 EMA: ${ema20:.2f}"
    )

    st.write(
        f"50 EMA: ${ema50:.2f}"
    )

    st.write(
        f"200 EMA: ${ema200:.2f}"
    )

    st.write(
        f"MACD: {macd:.3f}"
    )

    st.write(
        f"MACD Signal: {macd_signal:.3f}"
    )

    st.write(
        f"Recent 20-Day High: "
        f"${recent_high:.2f}"
    )

    st.write(
        f"Recent 20-Day Low: "
        f"${recent_low:.2f}"
    )

# =========================================================
# STATUS
# =========================================================

st.divider()

st.header(
    "🚦 Swing Hunter Status"
)

if swing_score >= 85:

    st.success(
        f"🦅 {grade} SETUP — "
        f"{direction} — "
        f"{option_bias}"
    )

elif swing_score >= 75:

    st.warning(
        f"👀 WATCH — "
        f"{direction}"
    )

else:

    st.info(
        "⏳ WAIT — Setup does not currently "
        "meet the preferred score."
    )

st.caption(
    "Swing Hunter V2 • Tradier sandbox data • "
    "Automated technical scoring • "
    "No trades are placed • Not financial advice"
)

st.caption(
    "Swing Hunter V2 • Tradier sandbox data • "
    "Automated technical scoring • "
    "No trades are placed • Not financial advice"
)
