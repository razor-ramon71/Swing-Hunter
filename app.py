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

# =========================================================
# 🥇 GOLDEN SCANNER V3
# =========================================================

st.divider()
st.header("🥇 Golden Scanner")

st.write(
    "Scans a starter universe of liquid stocks and ETFs "
    "for 1–2 week swing candidates."
)

# ---------------------------------------------------------
# STARTER UNIVERSE
# ---------------------------------------------------------

scanner_symbols = [
    "AAPL",
    "MSFT",
    "NVDA",
    "AMZN",
    "META",
    "GOOGL",
    "TSLA",
    "AMD",
    "NFLX",
    "PLTR",
    "AVGO",
    "QQQ",
    "SPY",
    "IWM",
    "DIA",
    "V",
    "XOM",
    "DIS",
    "SOFI",
    "PYPL",
    "NKE",
    "MRNA",
    "BABA",
    "SNAP",
    "UBER",
    "KO",
    "DELL",
    "MRVL",
    "CRM",
    "ORCL",
    "CRWD",
    "MSTR",
    "NOW",
    "HOOD",
    "MA",
    "CVX",
    "NFLX",
    "COIN",
    "UNH",
    "COST",
    "SHOP",
    "ADBE",
    "PG",
    "PFE",
    "HD",
    "VZ",
    "BA",
    "NU"
]

scan_button = st.button(
    "🔍 RUN GOLDEN SCAN"
)

if scan_button:

    results = []

    progress = st.progress(0)

    status_text = st.empty()

    for index, scan_symbol in enumerate(
        scanner_symbols
    ):

        status_text.write(
            f"Scanning {scan_symbol}..."
        )

        try:

            scan_end = date.today()

            scan_start = (
                scan_end
                - timedelta(days=450)
            )

            response = requests.get(
                "https://sandbox.tradier.com/v1/markets/history",
                params={
                    "symbol": scan_symbol,
                    "interval": "daily",
                    "start":
                        scan_start.isoformat(),
                    "end":
                        scan_end.isoformat()
                },
                headers=headers,
                timeout=10
            )

            if response.status_code != 200:
                continue

            history_data = response.json()

            scan_history = (
                history_data
                .get("history", {})
                .get("day", [])
            )

            if not scan_history:
                continue

            sdf = pd.DataFrame(
                scan_history
            )

            for column in [
                "open",
                "high",
                "low",
                "close",
                "volume"
            ]:

                sdf[column] = pd.to_numeric(
                    sdf[column],
                    errors="coerce"
                )

            sdf = (
                sdf
                .dropna()
                .sort_values("date")
                .reset_index(drop=True)
            )

            if len(sdf) < 200:
                continue

            close_s = sdf["close"]
            high_s = sdf["high"]
            low_s = sdf["low"]
            volume_s = sdf["volume"]

            # -------------------------------------------------
            # MOVING AVERAGES
            # -------------------------------------------------

            ema20_s = close_s.ewm(
                span=20,
                adjust=False
            ).mean()

            ema50_s = close_s.ewm(
                span=50,
                adjust=False
            ).mean()

            ema200_s = close_s.ewm(
                span=200,
                adjust=False
            ).mean()

            # -------------------------------------------------
            # RSI
            # -------------------------------------------------

            change_s = close_s.diff()

            gain_s = change_s.clip(
                lower=0
            )

            loss_s = -change_s.clip(
                upper=0
            )

            avg_gain_s = gain_s.rolling(
                14
            ).mean()

            avg_loss_s = loss_s.rolling(
                14
            ).mean()

            rs_s = (
                avg_gain_s
                / avg_loss_s.replace(
                    0,
                    np.nan
                )
            )

            rsi_s = (
                100
                - (
                    100
                    / (1 + rs_s)
                )
            )

            # -------------------------------------------------
            # MACD
            # -------------------------------------------------

            ema12_s = close_s.ewm(
                span=12,
                adjust=False
            ).mean()

            ema26_s = close_s.ewm(
                span=26,
                adjust=False
            ).mean()

            macd_s = (
                ema12_s
                - ema26_s
            )

            macd_signal_s = (
                macd_s.ewm(
                    span=9,
                    adjust=False
                ).mean()
            )

            # -------------------------------------------------
            # VOLUME
            # -------------------------------------------------

            volume_avg_s = (
                volume_s
                .rolling(20)
                .mean()
            )

            latest_s = sdf.iloc[-1]

            current_price = float(
                latest_s["close"]
            )

            current_ema20 = float(
                ema20_s.iloc[-1]
            )

            current_ema50 = float(
                ema50_s.iloc[-1]
            )

            current_ema200 = float(
                ema200_s.iloc[-1]
            )

            current_rsi = float(
                rsi_s.iloc[-1]
            )

            current_macd = float(
                macd_s.iloc[-1]
            )

            current_signal = float(
                macd_signal_s.iloc[-1]
            )

            current_volume = float(
                latest_s["volume"]
            )

            average_volume = float(
                volume_avg_s.iloc[-1]
            )

            volume_ratio_s = (
                current_volume
                / average_volume
                if average_volume > 0
                else 1
            )

            # -------------------------------------------------
            # TREND SCORE
            # -------------------------------------------------

            if (
                current_price > current_ema20
                and current_ema20 > current_ema50
                and current_ema50 > current_ema200
            ):

                trend = 100
                trend_direction = "Bullish"

            elif (
                current_price < current_ema20
                and current_ema20 < current_ema50
                and current_ema50 < current_ema200
            ):

                trend = 100
                trend_direction = "Bearish"

            elif (
                current_price > current_ema20
                and current_ema20 > current_ema50
            ):

                trend = 85
                trend_direction = "Bullish"

            elif (
                current_price < current_ema20
                and current_ema20 < current_ema50
            ):

                trend = 85
                trend_direction = "Bearish"

            else:

                trend = 50

                if current_price >= current_ema50:
                    trend_direction = "Bullish"
                else:
                    trend_direction = "Bearish"

            # -------------------------------------------------
            # MOMENTUM SCORE
            # -------------------------------------------------

            if (
                current_rsi >= 55
                and current_rsi <= 70
                and current_macd > current_signal
            ):

                momentum = 100

            elif (
                current_rsi > 50
                and current_macd > current_signal
            ):

                momentum = 85

            elif (
                current_rsi <= 45
                and current_macd < current_signal
            ):

                momentum = 100

            elif (
                current_rsi < 50
                and current_macd < current_signal
            ):

                momentum = 85

            else:

                momentum = 50

            # -------------------------------------------------
            # VOLUME SCORE
            # -------------------------------------------------

            if volume_ratio_s >= 1.5:

                volume_score_s = 100

            elif volume_ratio_s >= 1.2:

                volume_score_s = 85

            elif volume_ratio_s >= 1.0:

                volume_score_s = 70

            else:

                volume_score_s = 45

            # -------------------------------------------------
            # STRUCTURE
            # -------------------------------------------------

            recent_s = sdf.tail(20)

            older_s = sdf.iloc[-40:-20]

            recent_high_s = (
                recent_s["high"].max()
            )

            recent_low_s = (
                recent_s["low"].min()
            )

            older_high_s = (
                older_s["high"].max()
            )

            older_low_s = (
                older_s["low"].min()
            )

            if (
                trend_direction == "Bullish"
                and recent_high_s > older_high_s
                and recent_low_s > older_low_s
            ):

                structure = 100

            elif (
                trend_direction == "Bearish"
                and recent_high_s < older_high_s
                and recent_low_s < older_low_s
            ):

                structure = 100

            else:

                structure = 60

            # -------------------------------------------------
            # SUPPORT / RESISTANCE
            # -------------------------------------------------

            range_size = (
                recent_high_s
                - recent_low_s
            )

            if range_size > 0:

                position_in_range = (
                    current_price
                    - recent_low_s
                ) / range_size

            else:

                position_in_range = 0.5

            if trend_direction == "Bullish":

                if position_in_range <= 0.35:

                    sr_score = 95
                    setup = "Pullback"

                elif position_in_range >= 0.85:

                    sr_score = 70
                    setup = "Breakout Watch"

                else:

                    sr_score = 80
                    setup = "Continuation"

            else:

                if position_in_range >= 0.65:

                    sr_score = 95
                    setup = "Rally / Resistance"

                elif position_in_range <= 0.15:

                    sr_score = 70
                    setup = "Breakdown Watch"

                else:

                    sr_score = 80
                    setup = "Continuation"

            # -------------------------------------------------
            # HIGHER TIMEFRAME
            # -------------------------------------------------

            if (
                trend_direction == "Bullish"
                and current_price > current_ema200
            ):

                higher_tf = 90

            elif (
                trend_direction == "Bearish"
                and current_price < current_ema200
            ):

                higher_tf = 90

            else:

                higher_tf = 55

            # -------------------------------------------------
            # FINAL SCORE
            # -------------------------------------------------

            final_score = (

                trend * 0.20
                + momentum * 0.20
                + volume_score_s * 0.15
                + structure * 0.15
                + sr_score * 0.15
                + higher_tf * 0.15
            )

            final_score = round(
                final_score,
                1
            )

            # -------------------------------------------------
            # GRADE
            # -------------------------------------------------

            if final_score >= 90:
                grade_s = "A+"

            elif final_score >= 85:
                grade_s = "A"

            elif final_score >= 80:
                grade_s = "B+"

            elif final_score >= 75:
                grade_s = "B"

            else:
                grade_s = "C"

            # -------------------------------------------------
            # OPTION DIRECTION
            # -------------------------------------------------

            if trend_direction == "Bullish":

                option_type_s = "CALL"

            else:

                option_type_s = "PUT"

            # -------------------------------------------------
            # SAVE RESULT
            # -------------------------------------------------

            results.append({

                "Rank Score":
                    final_score,

                "Symbol":
                    scan_symbol,

                "Setup":
                    setup,

                "Bias":
                    trend_direction,

                "Grade":
                    grade_s,

                "RSI":
                    round(
                        current_rsi,
                        1
                    ),

                "Volume":
                    f"{volume_ratio_s:.2f}x",

                "Option":
                    option_type_s
            })

        except Exception:
            continue

        progress.progress(
            (index + 1)
            / len(scanner_symbols)
        )

    status_text.empty()

    progress.empty()

    # ---------------------------------------------------------
    # DISPLAY RESULTS
    # ---------------------------------------------------------

    if results:

        results_df = pd.DataFrame(
            results
        )

        results_df = (
            results_df
            .sort_values(
                "Rank Score",
                ascending=False
            )
            .reset_index(drop=True)
        )

        results_df.index += 1

        results_df.index.name = "Rank"

        st.success(
            f"🟢 Scan complete — "
            f"{len(results_df)} candidates found."
        )

        st.subheader(
            "🏆 Golden Scanner Rankings"
        )

        st.dataframe(
            results_df,
            use_container_width=True
        )

        # -----------------------------------------------------
        # BEST CANDIDATE
        # -----------------------------------------------------

        best = results_df.iloc[0]

        st.subheader(
            "🥇 Top Candidate"
        )

        st.success(
            f"{best['Symbol']} — "
            f"{best['Grade']} — "
            f"{best['Rank Score']}/100 — "
            f"{best['Bias']} — "
            f"{best['Setup']} — "
            f"{best['Option']}"
        )
# =========================================================
# 🏆 GOLDEN TRADE ENGINE
# =========================================================

st.divider()
st.header("🏆 Golden Trade Engine")

st.write(
    "The highest-ranked scanner candidates are now "
    "evaluated for 7–14 DTE options."
)
# =========================================================
# 🥇 GOLDEN QOD SETTINGS
# =========================================================

GOLDEN_MIN_SCORE = 85
GOLDEN_MIN_CONFLUENCES = 3

QOD_MIN_DTE = 2
QOD_MAX_DTE = 14

QOD_MIN_DELTA = 0.35
QOD_MAX_DELTA = 0.70

QOD_MIN_OPTION_VOLUME = 10
QOD_MIN_OPEN_INTEREST = 100

QOD_MAX_SPREAD_PERCENT = 20

QOD_MIN_RR = 1.25
QOD_PREFERRED_RR = 1.50
QOD_MAX_RR = 1.75

QOD_ATR_STOP = 1.25
# ---------------------------------------------------------
# TRADE ENGINE SETTINGS
# ---------------------------------------------------------

max_risk_pct = st.slider(
    "Maximum account risk per trade (%)",
    1.0,
    5.0,
    2.0,
    0.5
)

max_risk_dollars = (
    account_size * max_risk_pct / 100
)

st.caption(
    f"Account: ${account_size:,.0f} | "
    f"Maximum planned risk: "
    f"${max_risk_dollars:,.2f}"
)

# ---------------------------------------------------------
# TOP CANDIDATES
# ---------------------------------------------------------

top_candidates = results_df.head(5)

trade_results = []

for _, candidate in top_candidates.iterrows():

    trade_symbol = candidate["Symbol"]

    try:

        # -------------------------------------------------
        # GET CURRENT QUOTE
        # -------------------------------------------------

        quote_response = requests.get(
            "https://sandbox.tradier.com/v1/markets/quotes",
            params={
                "symbols": trade_symbol,
                "greeks": "false"
            },
            headers=headers,
            timeout=10
        )

        if quote_response.status_code != 200:
            continue

        quote_json = quote_response.json()

        trade_quote = (
            quote_json
            .get("quotes", {})
            .get("quote")
        )

        if isinstance(trade_quote, list):
            trade_quote = trade_quote[0]

        if not trade_quote:
            continue

        trade_price = float(
            trade_quote.get("last")
        )

        # -------------------------------------------------
        # EXPIRATIONS
        # -------------------------------------------------

        expiration_response = requests.get(
            "https://sandbox.tradier.com/v1/markets/options/expirations",
            params={
                "symbol": trade_symbol,
                "includeAllRoots": "true"
            },
            headers=headers,
            timeout=10
        )

        if expiration_response.status_code != 200:
            continue

        expiration_json = (
            expiration_response.json()
        )

        expiration_list = (
            expiration_json
            .get("expirations", {})
            .get("date", [])
        )

        if isinstance(
            expiration_list,
            str
        ):
            expiration_list = [
                expiration_list
            ]

        today_trade = date.today()

        preferred_expirations = []

        for exp in expiration_list:

            try:

                exp_date = datetime.strptime(
                    exp,
                    "%Y-%m-%d"
                ).date()

                dte = (
                    exp_date
                    - today_trade
                ).days

                if 7 <= dte <= 14:

                    preferred_expirations.append(
                        (
                            exp,
                            dte
                        )
                    )

            except Exception:
                continue

        if not preferred_expirations:
            continue

        # Choose expiration closest to 10 DTE
        preferred_expirations.sort(
            key=lambda x: abs(
                x[1] - 10
            )
        )

        selected_expiration = (
            preferred_expirations[0][0]
        )

        selected_dte = (
            preferred_expirations[0][1]
        )

        # -------------------------------------------------
        # OPTION CHAIN
        # -------------------------------------------------

        chain_response = requests.get(
            "https://sandbox.tradier.com/v1/markets/options/chains",
            params={
                "symbol": trade_symbol,
                "expiration":
                    selected_expiration,
                "greeks": "true"
            },
            headers=headers,
            timeout=10
        )

        if chain_response.status_code != 200:
            continue

        chain_json = (
            chain_response.json()
        )

        option_list = (
            chain_json
            .get("options", {})
            .get("option", [])
        )

        if isinstance(
            option_list,
            dict
        ):
            option_list = [
                option_list
            ]

        # -------------------------------------------------
        # DETERMINE CALL / PUT
        # -------------------------------------------------

        if candidate["Bias"] == "Bullish":
            desired_type = "call"
        else:
            desired_type = "put"

        option_candidates = []

        # -------------------------------------------------
        # EVALUATE OPTIONS
        # -------------------------------------------------

        for option in option_list:

            if option.get(
                "option_type"
            ) != desired_type:
                continue

            strike = option.get(
                "strike"
            )

            bid = option.get(
                "bid"
            )

            ask = option.get(
                "ask"
            )

            volume_option = option.get(
                "volume",
                0
            )

            open_interest = option.get(
                "open_interest",
                0
            )

            greeks = option.get(
                "greeks",
                {}
            )

            if not isinstance(
                greeks,
                dict
            ):
                greeks = {}

            delta = greeks.get(
                "delta"
            )

            if (
                strike is None
                or bid is None
                or ask is None
            ):
                continue

            try:

                strike = float(strike)
                bid = float(bid)
                ask = float(ask)

                if bid < 0 or ask <= 0:
                    continue

                mid = (
                    bid + ask
                ) / 2

                spread = (
                    ask - bid
                )

                spread_pct = (
                    spread / mid * 100
                    if mid > 0
                    else 999
                )

                # -----------------------------------------
                # INTRINSIC VALUE
                # -----------------------------------------

                if desired_type == "call":

                    intrinsic = max(
                        trade_price
                        - strike,
                        0
                    )

                else:

                    intrinsic = max(
                        strike
                        - trade_price,
                        0
                    )

                # -----------------------------------------
                # TIME VALUE
                # -----------------------------------------

                time_value = max(
                    mid - intrinsic,
                    0
                )

                # -----------------------------------------
                # HUGHES 1% TEST
                # -----------------------------------------

                one_percent_limit = (
                    trade_price * 0.01
                )

                if (
                    time_value
                    <= one_percent_limit
                ):

                    hughes_pass = True

                else:

                    hughes_pass = False

                # -----------------------------------------
                # DELTA
                # -----------------------------------------

                if delta is not None:

                    delta = float(delta)

                else:

                    delta = np.nan

                abs_delta = (
                    abs(delta)
                    if not np.isnan(delta)
                    else 0
                )

                # -----------------------------------------
                # LIQUIDITY
                # -----------------------------------------

                try:
                    option_volume = float(
                        volume_option
                    )
                except Exception:
                    option_volume = 0

                try:
                    option_oi = float(
                        open_interest
                    )
                except Exception:
                    option_oi = 0

                if (
                    spread_pct <= 10
                    and (
                        option_volume >= 10
                        or option_oi >= 50
                    )
                ):

                    liquidity_score = 100

                elif spread_pct <= 15:

                    liquidity_score = 75

                else:

                    liquidity_score = 40

                # -----------------------------------------
                # DELTA SCORE
                # -----------------------------------------

                if 0.35 <= abs_delta <= 0.60:

                    delta_score = 100

                elif 0.25 <= abs_delta <= 0.70:

                    delta_score = 80

                elif abs_delta > 0:

                    delta_score = 60

                else:

                    delta_score = 40

                # -----------------------------------------
                # HUGHES SCORE
                # -----------------------------------------

                if hughes_pass:

                    rule_score = 100

                else:

                    rule_score = 25

                # -----------------------------------------
                # AFFORDABILITY
                # -----------------------------------------

                contract_cost = (
                    mid * 100
                )

                if (
                    contract_cost
                    <= max_risk_dollars
                ):

                    affordability_score = 100

                else:

                    affordability_score = 25

                # -----------------------------------------
                # APPROXIMATE 1-ATR TARGET
                # -----------------------------------------

                if desired_type == "call":

                    target_price = (
                        trade_price
                        + (
                            atr
                            if "atr" in locals()
                            else trade_price * 0.03
                        )
                    )

                    target_intrinsic = max(
                        target_price
                        - strike,
                        0
                    )

                else:

                    target_price = (
                        trade_price
                        - (
                            atr
                            if "atr" in locals()
                            else trade_price * 0.03
                        )
                    )

                    target_intrinsic = max(
                        strike
                        - target_price,
                        0
                    )

                estimated_profit_per_contract = (
                    max(
                        target_intrinsic
                        - mid,
                        0
                    ) * 100
                )

                estimated_risk = (
                    contract_cost
                )

                if estimated_risk > 0:

                    estimated_rr = (
                        estimated_profit_per_contract
                        / estimated_risk
                    )

                else:

                    estimated_rr = 0

            
                # -----------------------------------------
                # RISK / REWARD SCORE
                # -----------------------------------------

                if estimated_rr >= 3:

                    rr_score = 100

                elif estimated_rr >= 2:

                    rr_score = 85

                elif estimated_rr >= 1.5:

                    rr_score = 70

                elif estimated_rr >= 1:

                    rr_score = 50

                else:

                    rr_score = 25

                    
                # -----------------------------------------
                # FINAL OPTION SCORE
                # -----------------------------------------

                option_score = (

                    candidate["Rank Score"] * 0.30

                    + rule_score * 0.20

                    + delta_score * 0.15

                    + liquidity_score * 0.15

                    + rr_score * 0.10

                    + affordability_score * 0.10
                )

                option_score = round(
                    option_score,
                    1
                )

                # -----------------------------------------
                # TRADE STATUS
                # -----------------------------------------

                if (
                    option_score >= 90
                    and hughes_pass
                    and contract_cost
                    <= max_risk_dollars
                    and estimated_rr >= 2
                ):

                    trade_status = "🟢 READY TO REVIEW"

                elif option_score >= 80:

                    trade_status = "🟡 WATCH"

                else:

                    trade_status = "🔴 NO TRADE"

                option_candidates.append({

                    "Symbol":
                        trade_symbol,

                    "Stock Score":
                        candidate["Rank Score"],

                    "Setup":
                        candidate["Setup"],

                    "Bias":
                        candidate["Bias"],

                    "Option":
                        desired_type.upper(),

                    "DTE":
                        selected_dte,

                    "Strike":
                        strike,

                    "Bid":
                        bid,

                    "Ask":
                        ask,

                    "Mid":
                        round(
                            mid,
                            2
                        ),

                    "Delta":
                        round(
                            delta,
                            3
                        )
                        if not np.isnan(delta)
                        else "N/A",

                    "Time Value":
                        round(
                            time_value,
                            2
                        ),

                    "1% Limit":
                        round(
                            one_percent_limit,
                            2
                        ),

                    "Hughes 1%":
                        "✅ PASS"
                        if hughes_pass
                        else "❌ FAIL",

                    "Spread %":
                        round(
                            spread_pct,
                            1
                        ),

                    "R/R":
                        round(
                            estimated_rr,
                            2
                        ),

                    "Option Score":
                        option_score,

                    "Status":
                        trade_status
                })

            except Exception:
                continue

        # -------------------------------------------------
        # KEEP BEST OPTION FOR THIS STOCK
        # -------------------------------------------------

        if option_candidates:

            best_option = max(
                option_candidates,
                key=lambda x:
                    x["Option Score"]
            )

            trade_results.append(
                best_option
            )

    except Exception:
        continue

# -----------------------------------------------------
# 🥇 GOLDEN QOD TRADE ALERT
# -----------------------------------------------------

golden_trade = trade_df.iloc[0]

st.subheader(
    "🥇 GOLDEN QOD — #1 TRADE CANDIDATE"
)

trade_symbol = golden_trade["Symbol"]
trade_bias = golden_trade["Bias"]
trade_option = golden_trade["Option"]
trade_strike = float(golden_trade["Strike"])
trade_dte = int(golden_trade["DTE"])
trade_entry = float(golden_trade["Mid"])

# ---------------------------------------------------------
# STOCK PRICE / ATR
# ---------------------------------------------------------

try:

    golden_quote_response = requests.get(
        "https://sandbox.tradier.com/v1/markets/quotes",
        params={
            "symbols": trade_symbol,
            "greeks": "false"
        },
        headers=headers,
        timeout=10
    )

    golden_quote_json = (
        golden_quote_response.json()
    )

    golden_quote = (
        golden_quote_json
        .get("quotes", {})
        .get("quote")
    )

    if isinstance(golden_quote, list):
        golden_quote = golden_quote[0]

    golden_stock_price = float(
        golden_quote.get("last")
    )

except Exception:

    golden_stock_price = float(
        trade_price
    )

# ---------------------------------------------------------
# STOCK STOP / TARGET
# ---------------------------------------------------------

golden_atr = float(
    atr
)

if trade_bias == "Bullish":

    stock_stop = (
        golden_stock_price
        - golden_atr * QOD_ATR_STOP
    )

    stock_risk = (
        golden_stock_price
        - stock_stop
    )

    stock_target = (
        golden_stock_price
        + stock_risk * QOD_PREFERRED_RR
    )

else:

    stock_stop = (
        golden_stock_price
        + golden_atr * QOD_ATR_STOP
    )

    stock_risk = (
        stock_stop
        - golden_stock_price
    )

    stock_target = (
        golden_stock_price
        - stock_risk * QOD_PREFERRED_RR
    )

# ---------------------------------------------------------
# OPTION STOP / TARGET
# ---------------------------------------------------------

trade_delta = golden_trade["Delta"]

try:

    trade_delta = abs(
        float(trade_delta)
    )

except Exception:

    trade_delta = 0.50

option_risk = (
    trade_entry
    * 0.40
)

option_stop = max(
    0.05,
    trade_entry - option_risk
)

option_target = (
    trade_entry
    + (
        trade_entry
        - option_stop
    )
    * QOD_PREFERRED_RR
)

# ---------------------------------------------------------
# GOLDEN QOD STATUS
# ---------------------------------------------------------

golden_score = float(
    golden_trade["Option Score"]
)

if (
    golden_score >= GOLDEN_MIN_SCORE
    and golden_trade["R/R"] >= QOD_PREFERRED_RR
):

    golden_status = "🥇 GOLDEN QOD"

else:

    golden_status = "🟢 QUALIFIED QOD"

# ---------------------------------------------------------
# DISPLAY
# ---------------------------------------------------------

st.success(
    f"{golden_status} — "
    f"{trade_symbol} — "
    f"{trade_bias}"
)

a1, a2, a3, a4 = st.columns(4)

a1.metric(
    "Stock Score",
    f"{golden_trade['Stock Score']:.1f}"
)

a2.metric(
    "Option Score",
    f"{golden_score:.1f}"
)

a3.metric(
    "Risk / Reward",
    f"{golden_trade['R/R']:.2f}R"
)

a4.metric(
    "Delta",
    str(golden_trade["Delta"])
)

# ---------------------------------------------------------
# QOD-STYLE ALERT
# ---------------------------------------------------------

month_name = datetime.strptime(
    str(date.today()),
    "%Y-%m-%d"
).strftime("%B")

qod_alert = f"""
NEW TRADE:

Buy-to-Open the
({trade_symbol}) {month_name} {trade_dte} DTE
{trade_strike:g} {trade_option.title()}
at {trade_entry:.2f} or less.

Apply a stop of {option_stop:.2f}
Target to {option_target:.2f} or more in Full position.
"""

st.subheader(
    "📣 QOD-STYLE TRADE ALERT"
)

st.code(
    qod_alert.strip(),
    language=None
)

# ---------------------------------------------------------
# TRADE PLAN
# ---------------------------------------------------------

st.subheader(
    "🎯 Golden QOD Trade Plan"
)

p1, p2, p3, p4 = st.columns(4)

p1.metric(
    "Entry",
    f"${trade_entry:.2f}"
)

p2.metric(
    "Stop",
    f"${option_stop:.2f}"
)

p3.metric(
    "Target",
    f"${option_target:.2f}"
)

p4.metric(
    "DTE",
    f"{trade_dte}"
)

st.write(
    f"**Underlying:** {trade_symbol} "
    f"at ${golden_stock_price:.2f}"
)

st.write(
    f"**Stock Stop:** ${stock_stop:.2f} "
    f"| **Stock Target:** ${stock_target:.2f}"
)

st.write(
    f"**Option:** {trade_strike:g} "
    f"{trade_option.upper()} "
    f"| **Delta:** {golden_trade['Delta']} "
    f"| **Spread:** {golden_trade['Spread %']}%"
)

st.write(
    f"**Hughes 1%:** {golden_trade['Hughes 1%']} "
    f"| **Option Score:** {golden_score:.1f}/100"
)

st.info(
        "⚠️ This is a research prototype. "
        "Option pricing, Greeks, fills, slippage, "
        "and future price movement are uncertain. "
        "Paper-test before risking real money."
  )

st.warning(
        "No option contracts currently meet "
        "the Golden Trade Engine requirements."
    )

 st.info(
        "Press 🔍 RUN GOLDEN SCAN to scan "
        "the starter stock/ETF universe."
    )
