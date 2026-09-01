import streamlit as st
import pandas as pd

st.set_page_config(
    page_title="Swing Hunter",
    page_icon="🦅",
    layout="wide"
)

# -----------------------------
# SWING HUNTER V1 PROTOTYPE
# -----------------------------

st.title("🦅 SWING HUNTER")
st.subheader("1–2 Week Stock & Options Swing Scanner")

st.info(
    "PROTOTYPE MODE — The numbers shown are simulated. "
    "This version is testing the scanner's logic and interface, "
    "not providing live trading signals."
)

# Sidebar
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

show_rule_fails = st.sidebar.checkbox(
    "Show options that fail 1% rule",
    True
)

# -----------------------------
# SAMPLE CANDIDATES
# -----------------------------

data = [
    ["NVDA", "🟢 Bullish", 94, "+7.2%", "Call", "10", "PASS", 91, "A+"],
    ["AMD", "🟢 Bullish", 91, "+6.8%", "Call", "12", "PASS", 88, "A"],
    ["PLTR", "🟢 Bullish", 87, "+5.9%", "Call", "14", "FAIL", 79, "B+"],
    ["TSLA", "🔴 Bearish", 89, "-6.4%", "Put", "9", "FAIL", 82, "B+"],
    ["QQQ", "🟢 Bullish", 86, "+4.7%", "Call", "10", "PASS", 85, "A-"],
    ["META", "🔴 Bearish", 83, "-5.3%", "Put", "12", "FAIL", 76, "B"],
]

columns = [
    "Symbol",
    "Bias",
    "Swing Score",
    "Expected Move",
    "Option",
    "DTE",
    "Hughes 1%",
    "Option Score",
    "Grade"
]

df = pd.DataFrame(data, columns=columns)

if not show_rule_fails:
    df = df[df["Hughes 1%"] == "PASS"]

# -----------------------------
# SUMMARY
# -----------------------------

col1, col2, col3, col4 = st.columns(4)

col1.metric(
    "Candidates",
    len(df)
)

col2.metric(
    "A / A+ Setups",
    len(df[df["Grade"].isin(["A+", "A", "A-"])])
)

col3.metric(
    "1% Rule PASS",
    len(df[df["Hughes 1%"] == "PASS"])
)

col4.metric(
    "Account",
    f"${account_size:,}"
)

# -----------------------------
# RANKED OPPORTUNITIES
# -----------------------------

st.header("🔥 Top Swing Opportunities")

st.dataframe(
    df,
    use_container_width=True,
    hide_index=True
)

# -----------------------------
# DETAIL VIEW
# -----------------------------

st.header("🔎 Candidate Analysis")

symbol = st.selectbox(
    "Select a candidate",
    df["Symbol"].tolist()
)

candidate = df[df["Symbol"] == symbol].iloc[0]

left, right = st.columns(2)

with left:

    st.markdown(
        f"## {candidate['Symbol']} {candidate['Bias']}"
    )

    st.metric(
        "Swing Score",
        f"{candidate['Swing Score']}/100"
    )

    st.metric(
        "Expected Move",
        candidate["Expected Move"]
    )

    st.write(
        f"Expected holding period: **{horizon}**"
    )

with right:

    st.markdown("## 🎯 Option Candidate")

    st.write(
        f"**{candidate['Option']}**"
    )

    st.write(
        f"Expiration: **{candidate['DTE']} DTE**"
    )

    st.write(
        f"Hughes 1% Rule: "
        f"**{candidate['Hughes 1%']}**"
    )

    st.write(
        f"Option Score: "
        f"**{candidate['Option Score']}/100**"
    )

    st.write(
        f"Overall Grade: **{candidate['Grade']}**"
    )

# -----------------------------
# WHY THIS TRADE?
# -----------------------------

st.header("🧠 Why This Setup?")

reasons = {
    "Trend": "Confirmed",
    "Momentum": "Strong",
    "Market Structure": "Potential breakout/breakdown",
    "Volume": "Above baseline",
    "Compression": "Developing",
    "Higher Timeframe": "Aligned"
}

for item, status in reasons.items():

    st.write(
        f"✅ **{item}:** {status}"
    )

# -----------------------------
# HUGHES 1% EXAMPLE
# -----------------------------

st.header("🧮 Hughes 1% Rule")

prototype_prices = {
    "NVDA": 180,
    "AMD": 150,
    "PLTR": 148,
    "TSLA": 325,
    "QQQ": 595,
    "META": 745
}

stock_price = prototype_prices.get(
    symbol,
    100
)

threshold = stock_price * 0.01

st.write(
    f"Prototype stock price: **${stock_price:.2f}**"
)

st.write(
    f"Maximum preferred time value "
    f"(1%): **${threshold:.2f}**"
)

if candidate["Hughes 1%"] == "PASS":

    st.success(
        "✅ PASS — The prototype option satisfies "
        "the Hughes 1% requirement."
    )

else:

    st.warning(
        "⚠️ RULE FAIL — This option does not satisfy "
        "the Hughes 1% requirement. It is shown only "
        "because you selected the alternative-option setting."
    )

# -----------------------------
# TRADE STATUS
# -----------------------------

st.header("🚦 Trade Status")

if candidate["Swing Score"] >= 90:

    st.success(
        "🔥 READY — High-quality prototype setup. REVIEW before trading."
    )

elif candidate["Swing Score"] >= 85:

    st.warning(
        "🟠 WATCH — Setup developing."
    )

else:

    st.info(
        "🟡 WATCH — More confirmation required."
    )

st.divider()

st.caption(
   # -----------------------------
# SWING HUNTER OPTIONS ENGINE
# 7–14 DTE + HUGHES 1% RULE
# -----------------------------

st.divider()
st.header("🧮 Swing Hunter Options Engine")

from datetime import datetime, date

try:
    token = st.secrets["TRADIER_SANDBOX_TOKEN"]

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json"
    }

    # Current underlying price
    stock_price = quote.get("last", None)

    if stock_price is None:
        st.error("Could not determine the AAPL stock price.")
    else:

        stock_price = float(stock_price)

        # --------------------------------
        # GET AVAILABLE EXPIRATIONS
        # --------------------------------

        exp_response = requests.get(
            "https://sandbox.tradier.com/v1/markets/options/expirations",
            params={
                "symbol": "AAPL",
                "includeAllRoots": "true"
            },
            headers=headers,
            timeout=10
        )

        if exp_response.status_code != 200:

            st.error(
                f"Expiration request failed: "
                f"HTTP {exp_response.status_code}"
            )

            st.code(exp_response.text)

        else:

            exp_data = exp_response.json()

            dates = exp_data["expirations"]["date"]

            if isinstance(dates, str):
                dates = [dates]

            today = date.today()

            expiration_candidates = []

            for d in dates:

                try:
                    exp_date = datetime.strptime(
                        d,
                        "%Y-%m-%d"
                    ).date()

                    dte = (exp_date - today).days

                    if 7 <= dte <= 14:
                        expiration_candidates.append(
                            (d, dte)
                        )

                except Exception:
                    continue

            # --------------------------------
            # DISPLAY AVAILABLE 7–14 DTE
            # --------------------------------

            st.subheader("📅 Preferred Swing Expirations")

            if not expiration_candidates:

                st.warning(
                    "No expiration between 7 and 14 DTE "
                    "was returned by Tradier."
                )

            else:

                expiration_candidates.sort(
                    key=lambda x: abs(x[1] - 10)
                )

                selected_expiration, selected_dte = (
                    expiration_candidates[0]
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
                        for d, dte in expiration_candidates
                    )
                )

                # --------------------------------
                # GET OPTION CHAIN
                # --------------------------------

                chain_response = requests.get(
                    "https://sandbox.tradier.com/v1/markets/options/chains",
                    params={
                        "symbol": "AAPL",
                        "expiration": selected_expiration,
                        "greeks": "true"
                    },
                    headers=headers,
                    timeout=10
                )

                if chain_response.status_code != 200:

                    st.error(
                        f"Option chain request failed: "
                        f"HTTP {chain_response.status_code}"
                    )

                    st.code(chain_response.text)

                else:

                    chain_data = chain_response.json()

                    options = (
                        chain_data
                        .get("options", {})
                        .get("option", [])
                    )

                    if isinstance(options, dict):
                        options = [options]

                    rows = []

                    # Hughes 1% threshold
                    one_percent_limit = stock_price * 0.01

                    for opt in options:

                        strike = opt.get("strike")
                        bid = opt.get("bid")
                        ask = opt.get("ask")
                        option_type = opt.get("option_type")

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

                            mid = (bid + ask) / 2

                            # Intrinsic value
                            if option_type == "call":

                                intrinsic = max(
                                    stock_price - strike,
                                    0
                                )

                            else:

                                intrinsic = max(
                                    strike - stock_price,
                                    0
                                )

                            # Time value
                            time_value = max(
                                mid - intrinsic,
                                0
                            )

                            # Hughes 1% test
                            rule = (
                                "PASS"
                                if time_value
                                < one_percent_limit
                                else "FAIL"
                            )

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
                                    round(mid, 2),

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

                        option_df = pd.DataFrame(rows)

                        # --------------------------------
                        # FIND CONTRACTS CLOSEST TO ATM
                        # --------------------------------

                        option_df["Distance"] = (
                            abs(
                                option_df["Strike"]
                                - stock_price
                            )
                        )

                        option_df = (
                            option_df
                            .sort_values("Distance")
                            .drop(columns=["Distance"])
                            .head(30)
                        )

                        st.subheader(
                            "🎯 7–14 DTE Option Candidates"
                        )

                        st.write(
                            f"Underlying: "
                            f"**${stock_price:.2f}**"
                        )

                        st.write(
                            f"Hughes 1% maximum preferred "
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
                            "No usable option contracts "
                            "were returned."
                        )

except Exception as e:

    st.error(
        "🔴 Swing Hunter options engine failed."
    )

    st.code(str(e))
