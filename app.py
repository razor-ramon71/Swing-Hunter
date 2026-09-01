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
    "Swing Hunter V1 Prototype • Simulated data only • "
    "Not financial advice"
)
# -----------------------------
# TRADIER CONNECTION TEST
# -----------------------------

import requests

st.divider()
st.header("📡 Tradier Market Data Connection")

try:
    token = st.secrets["TRADIER_SANDBOX_TOKEN"]

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json"
    }

    response = requests.get(
        "https://sandbox.tradier.com/v1/markets/quotes",
        params={
            "symbols": "AAPL",
            "greeks": "false"
        },
        headers=headers,
        timeout=10
    )

    if response.status_code == 200:

        data = response.json()
        quote = data["quotes"]["quote"]

        st.success("🟢 Tradier connection successful!")

        st.write(f"**Symbol:** {quote.get('symbol')}")
        st.write(f"**Last Price:** ${quote.get('last')}")
        st.write(f"**Volume:** {quote.get('volume')}")

    else:

        st.error(
            f"🔴 Tradier returned HTTP {response.status_code}"
        )

        st.code(response.text)

except Exception as e:

    st.error("🔴 Tradier connection failed.")

    st.code(str(e))
# -----------------------------
# OPTIONS CHAIN + 1% RULE TEST
# -----------------------------

st.divider()
st.header("🧮 Swing Hunter Options Engine")

try:
    token = st.secrets["TRADIER_SANDBOX_TOKEN"]

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json"
    }

    # Get AAPL option expirations
    exp_response = requests.get(
        "https://sandbox.tradier.com/v1/markets/options/expirations",
        params={"symbol": "AAPL", "includeAllRoots": "true"},
        headers=headers,
        timeout=10
    )

    if exp_response.status_code != 200:
        st.error(f"Expiration request failed: HTTP {exp_response.status_code}")
        st.code(exp_response.text)

    else:
        exp_data = exp_response.json()
        dates = exp_data["expirations"]["date"]

        # Handle either a list of dates or a single date
        if isinstance(dates, list):
            expiration = dates[0]
        else:
            expiration = dates

        st.write(f"**Testing expiration:** {expiration}")

        # Get option chain
        chain_response = requests.get(
            "https://sandbox.tradier.com/v1/markets/options/chains",
            params={
                "symbol": "AAPL",
                "expiration": expiration,
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
            options = chain_data["options"]["option"]

            if isinstance(options, dict):
                options = [options]

            option_rows = []

            # Use the quote already retrieved above when available
            stock_price = quote.get("last", None)

            if stock_price is not None:

                for opt in options:

                    strike = opt.get("strike")
                    bid = opt.get("bid")
                    ask = opt.get("ask")
                    option_type = opt.get("option_type")

                    if strike is None or bid is None or ask is None:
                        continue

                    mid = (float(bid) + float(ask)) / 2

                    if option_type == "call":
                        intrinsic = max(
                            float(stock_price) - float(strike),
                            0
                        )
                    else:
                        intrinsic = max(
                            float(strike) - float(stock_price),
                            0
                        )

                    time_value = max(
                        mid - intrinsic,
                        0
                    )

                    one_percent_limit = (
                        float(stock_price) * 0.01
                    )

                    rule = (
                        "PASS"
                        if time_value < one_percent_limit
                        else "FAIL"
                    )

                    option_rows.append({
                        "Type": option_type,
                        "Strike": strike,
                        "Bid": bid,
                        "Ask": ask,
                        "Mid": round(mid, 2),
                        "Intrinsic": round(intrinsic, 2),
                        "Time Value": round(time_value, 2),
                        "1% Limit": round(one_percent_limit, 2),
                        "Hughes 1%": rule
                    })

                option_df = pd.DataFrame(option_rows)

                if not option_df.empty:

                    # Show options closest to the stock price
                    option_df["Distance"] = (
                        abs(option_df["Strike"].astype(float)
                            - float(stock_price))
                    )

                    option_df = (
                        option_df
                        .sort_values("Distance")
                        .drop(columns=["Distance"])
                        .head(20)
                    )

                    st.success(
                        "🟢 Live option-chain data received!"
                    )

                    st.write(
                        f"Underlying AAPL price: "
                        f"**${float(stock_price):.2f}**"
                    )

                    st.write(
                        f"Hughes 1% maximum preferred time value: "
                        f"**${one_percent_limit:.2f}**"
                    )

                    st.dataframe(
                        option_df,
                        use_container_width=True,
                        hide_index=True
                    )

                else:
                    st.warning(
                        "No usable option contracts were returned."
                    )

except Exception as e:

    st.error("🔴 Options engine test failed.")
    st.code(str(e))
