import streamlit as st
import pandas as pd
import requests
from datetime import datetime, date

st.set_page_config(
    page_title="Swing Hunter",
    page_icon="🦅",
    layout="wide"
)

# =========================================================
# SWING HUNTER
# =========================================================

st.title("🦅 SWING HUNTER")
st.subheader("1–2 Week Stock & Options Swing Scanner")

st.info(
    "LIVE DATA TEST MODE — Market and option data are being "
    "retrieved from the Tradier sandbox. No trades are placed."
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

horizon = st.sidebar.selectbox(
    "Swing Horizon",
    ["7–14 Days", "5–10 Days"]
)

mode = st.sidebar.selectbox(
    "Scanner Mode",
    ["Balanced", "Conservative", "Aggressive"]
)

symbol = st.sidebar.text_input(
    "Test Symbol",
    "AAPL"
).upper().strip()

# =========================================================
# PROTOTYPE CANDIDATES
# =========================================================

prototype_data = [
    ["NVDA", "🟢 Bullish", 94, "+7.2%", "A+"],
    ["AMD", "🟢 Bullish", 91, "+6.8%", "A"],
    ["PLTR", "🟢 Bullish", 87, "+5.9%", "B+"],
    ["TSLA", "🔴 Bearish", 89, "-6.4%", "A-"],
    ["QQQ", "🟢 Bullish", 86, "+4.7%", "A-"],
    ["META", "🔴 Bearish", 83, "-5.3%", "B"]
]

prototype_columns = [
    "Symbol",
    "Bias",
    "Swing Score",
    "Expected Move",
    "Grade"
]

prototype_df = pd.DataFrame(
    prototype_data,
    columns=prototype_columns
)

# =========================================================
# PROTOTYPE DASHBOARD
# =========================================================

st.header("🔥 Prototype Opportunities")

c1, c2, c3, c4 = st.columns(4)

c1.metric(
    "Candidates",
    len(prototype_df)
)

c2.metric(
    "A / A+",
    len(
        prototype_df[
            prototype_df["Grade"].isin(
                ["A+", "A", "A-"]
            )
        ]
    )
)

c3.metric(
    "Mode",
    mode
)

c4.metric(
    "Account",
    f"${account_size:,}"
)

st.dataframe(
    prototype_df,
    use_container_width=True,
    hide_index=True
)

# =========================================================
# TRADIER CONNECTION
# =========================================================

st.divider()
st.header("📡 Tradier Market Data Connection")

quote = None

try:

    token = st.secrets["TRADIER_SANDBOX_TOKEN"]

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json"
    }

    quote_response = requests.get(
        "https://sandbox.tradier.com/v1/markets/quotes",
        params={
            "symbols": symbol,
            "greeks": "false"
        },
        headers=headers,
        timeout=10
    )

    if quote_response.status_code == 200:

        quote_data = quote_response.json()

        quote = (
            quote_data
            .get("quotes", {})
            .get("quote")
        )

        if isinstance(quote, list):
            quote = quote[0]

        if quote:

            st.success(
                "🟢 Tradier Market Data Connection Successful"
            )

            st.write(
                f"**Symbol:** {quote.get('symbol')}"
            )

            st.write(
                f"**Last Price:** "
                f"${quote.get('last')}"
            )

            st.write(
                f"**Volume:** "
                f"{quote.get('volume')}"
            )

        else:

            st.error(
                "Tradier connected, but no quote was returned."
            )

    else:

        st.error(
            f"🔴 Tradier returned HTTP "
            f"{quote_response.status_code}"
        )

        st.code(quote_response.text)

except Exception as e:

    st.error(
        "🔴 Tradier connection failed."
    )

    st.code(str(e))

# =========================================================
# OPTIONS ENGINE
# =========================================================

st.divider()
st.header("🧮 Swing Hunter Options Engine")

if quote:

    try:

        stock_price = float(
            quote.get("last")
        )

        # -------------------------------------------------
        # GET EXPIRATIONS
        # -------------------------------------------------

        expiration_response = requests.get(
            "https://sandbox.tradier.com/v1/markets/options/expirations",
            params={
                "symbol": symbol,
                "includeAllRoots": "true"
            },
            headers=headers,
            timeout=10
        )

        if expiration_response.status_code != 200:

            st.error(
                f"Expiration request failed: "
                f"HTTP {expiration_response.status_code}"
            )

            st.code(
                expiration_response.text
            )

        else:

            expiration_data = (
                expiration_response.json()
            )

            expiration_dates = (
                expiration_data
                .get("expirations", {})
                .get("date", [])
            )

            if isinstance(
                expiration_dates,
                str
            ):

                expiration_dates = [
                    expiration_dates
                ]

            today = date.today()

            preferred = []

            for expiration in expiration_dates:

                try:

                    expiration_date = (
                        datetime.strptime(
                            expiration,
                            "%Y-%m-%d"
                        ).date()
                    )

                    dte = (
                        expiration_date - today
                    ).days

                    if 7 <= dte <= 14:

                        preferred.append(
                            (
                                expiration,
                                dte
                            )
                        )

                except Exception:

                    continue

            # -------------------------------------------------
            # EXPIRATION SELECTION
            # -------------------------------------------------

            st.subheader(
                "📅 Preferred Swing Expirations"
            )

            if not preferred:

                st.warning(
                    "No 7–14 DTE expiration was "
                    "returned by Tradier."
                )

            else:

                # Prefer approximately 10 DTE
                preferred.sort(
                    key=lambda x: abs(
                        x[1] - 10
                    )
                )

                selected_expiration = (
                    preferred[0][0]
                )

                selected_dte = (
                    preferred[0][1]
                )

                st.success(
                    f"🟢 Selected expiration: "
                    f"{selected_expiration} "
                    f"({selected_dte} DTE)"
                )

                st.write(
                    "Available preferred expirations: "
                    + ", ".join(
                        f"{d} ({dte} DTE)"
                        for d, dte in preferred
                    )
                )

                # -------------------------------------------------
                # OPTION CHAIN
                # -------------------------------------------------

                chain_response = requests.get(
                    "https://sandbox.tradier.com/v1/markets/options/chains",
                    params={
                        "symbol": symbol,
                        "expiration":
                            selected_expiration,
                        "greeks": "true"
                    },
                    headers=headers,
                    timeout=10
                )

                if chain_response.status_code != 200:

                    st.error(
                        f"Option chain failed: "
                        f"HTTP {chain_response.status_code}"
                    )

                    st.code(
                        chain_response.text
                    )

                else:

                    chain_data = (
                        chain_response.json()
                    )

                    options = (
                        chain_data
                        .get("options", {})
                        .get("option", [])
                    )

                    if isinstance(
                        options,
                        dict
                    ):

                        options = [
                            options
                        ]

                    rows = []

                    one_percent_limit = (
                        stock_price * 0.01
                    )

                    for option in options:

                        strike = option.get(
                            "strike"
                        )

                        bid = option.get(
                            "bid"
                        )

                        ask = option.get(
                            "ask"
                        )

                        option_type = option.get(
                            "option_type"
                        )

                        if (
                            strike is None
                            or bid is None
                            or ask is None
                        ):

                            continue

                        try:

                            strike = float(
                                strike
                            )

                            bid = float(
                                bid
                            )

                            ask = float(
                                ask
                            )

                            mid = (
                                bid + ask
                            ) / 2

                            # Intrinsic value
                            if option_type == "call":

                                intrinsic = max(
                                    stock_price
                                    - strike,
                                    0
                                )

                            else:

                                intrinsic = max(
                                    strike
                                    - stock_price,
                                    0
                                )

                            # Time value
                            time_value = max(
                                mid
                                - intrinsic,
                                0
                            )

                            # Hughes 1% rule
                            if (
                                time_value
                                < one_percent_limit
                            ):

                                rule = "PASS"

                            else:

                                rule = "FAIL"

                            rows.append({

                                "Type":
                                    option_type,

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

                                "Intrinsic":
                                    round(
                                        intrinsic,
                                        2
                                    ),

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
                                    rule
                            })

                        except Exception:

                            continue

                    if rows:

                        option_df = pd.DataFrame(
                            rows
                        )

                        # Closest strikes to current price
                        option_df["Distance"] = (
                            abs(
                                option_df["Strike"]
                                - stock_price
                            )
                        )

                        option_df = (
                            option_df
                            .sort_values(
                                "Distance"
                            )
                            .drop(
                                columns=[
                                    "Distance"
                                ]
                            )
                            .head(30)
                        )

                        st.subheader(
                            "🎯 7–14 DTE Option Candidates"
                        )

                        st.write(
                            f"Underlying "
                            f"{symbol}: "
                            f"**${stock_price:.2f}**"
                        )

                        st.write(
                            f"Hughes 1% maximum "
                            f"time value: "
                            f"**${one_percent_limit:.2f}**"
                        )

                        st.dataframe(
                            option_df,
                            use_container_width=True,
                            hide_index=True
                        )

                    else:

                        st.warning(
                            "No usable option "
                            "contracts returned."
                        )

    except Exception as e:

        st.error(
            "🔴 Options engine failed."
        )

        st.code(
            str(e)
        )

else:

    st.info(
        "Waiting for a successful market-data "
        "connection before running the options engine."
    )

# =========================================================
# STATUS
# =========================================================

st.divider()

st.header("🚦 Swing Hunter Status")

st.success(
    "🟢 Prototype online — "
    "Tradier market-data connection active."
)

st.caption(
    "Swing Hunter V1 • Sandbox data • "
    "No trades are placed • Not financial advice"
)

# =========================================================
# SWING HUNTER STOCK SCORING ENGINE
# =========================================================

st.divider()
st.header("🧠 Swing Hunter Stock Score")

st.write(
    "Initial technical scoring model for 1–2 week swing setups."
)

# ---------------------------------------------------------
# Technical inputs
# ---------------------------------------------------------

trend_score = st.slider(
    "Trend",
    0,
    100,
    70
)

momentum_score = st.slider(
    "Momentum",
    0,
    100,
    70
)

volume_score = st.slider(
    "Volume Confirmation",
    0,
    100,
    60
)

structure_score = st.slider(
    "Market Structure",
    0,
    100,
    70
)

support_score = st.slider(
    "Support / Resistance",
    0,
    100,
    65
)

higher_tf_score = st.slider(
    "Higher-Timeframe Confirmation",
    0,
    100,
    70
)

# ---------------------------------------------------------
# Weighted score
# ---------------------------------------------------------

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

# ---------------------------------------------------------
# Grade
# ---------------------------------------------------------

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

# ---------------------------------------------------------
# Direction
# ---------------------------------------------------------

bullish_components = (
    trend_score
    + momentum_score
    + structure_score
)

bearish_components = (
    (100 - trend_score)
    + (100 - momentum_score)
    + (100 - structure_score)
)

if bullish_components >= bearish_components:

    direction = "🟢 BULLISH"
    preferred_option = "CALL"

else:

    direction = "🔴 BEARISH"
    preferred_option = "PUT"

# ---------------------------------------------------------
# Display
# ---------------------------------------------------------

col1, col2, col3, col4 = st.columns(4)

col1.metric(
    "Swing Score",
    f"{swing_score}/100"
)

col2.metric(
    "Grade",
    grade
)

col3.metric(
    "Direction",
    direction
)

col4.metric(
    "Option Bias",
    preferred_option
)

st.success(
    f"{status} — {symbol}"
)

# ---------------------------------------------------------
# Score breakdown
# ---------------------------------------------------------

st.subheader(
    "📊 Confluence Breakdown"
)

score_df = pd.DataFrame({

    "Factor": [
        "Trend",
        "Momentum",
        "Volume",
        "Structure",
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

st.caption(
    "Prototype scoring model — technical inputs will "
    "later be calculated automatically from market data."
)
