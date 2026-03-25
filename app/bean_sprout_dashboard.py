"""
Bean Sprout Growth Experiment — Interactive Dashboard
ELEC70126 Internet of Things and Applications
CID: 06043088

Run with: streamlit run app/bean_sprout_dashboard.py
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots

st.set_page_config(
    page_title="Bean Sprout Growth Dashboard",
    page_icon="\U0001F331",
    layout="wide"
)

# Green gradient sidebar
st.markdown("""<style>
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #1b5e20 0%, #2e7d32 40%, #43a047 100%);
}
section[data-testid="stSidebar"] * { color: #e8f5e9 !important; }
section[data-testid="stSidebar"] button,
section[data-testid="stSidebar"] button * { color: #1b5e20 !important; background: #e8f5e9 !important; }
section[data-testid="stSidebar"] button:hover,
section[data-testid="stSidebar"] button:hover * { background: #c8e6c9 !important; }
</style>""", unsafe_allow_html=True)

# --- Configuration ---
SHEET_ID = "1Vkc24L-VDzpiR6GrKL9sg7BJ5h5271bmTEASLvmzD9M"
SHEET_TAB = "data"
GSHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={SHEET_TAB}"

HARVEST_THRESH = {'Green': 3700, 'Blue': 4000, 'Control': 4000}
MAX_LENGTH = 30.0
THRESHOLD_LENGTH = 10.0
COLORS = {"Green": "#2ca02c", "Blue": "#1f77b4", "Control": "#636363"}
PLOT_TEMPLATE = "plotly_white"


# --- Data Loading ---
@st.cache_data(ttl=300)
def load_data():
    try:
        df = pd.read_csv(GSHEET_URL)
        data_source = "Google Sheets (live)"
    except Exception as e:
        st.warning(f"Could not fetch from Google Sheets ({e}). Falling back to local CSV.")
        df = pd.read_csv("data/experiment_data_mar22.csv")
        data_source = "Local CSV (offline)"

    df["Timestamp"] = pd.to_datetime(df["Timestamp"], format="mixed", dayfirst=True)
    df = df.sort_values("Timestamp").reset_index(drop=True)

    # Clean anomalies
    diff_g = df["Green"].diff().abs()
    diff_b = df["Blue"].diff().abs()
    diff_c = df["Control"].diff().abs()
    anomaly_mask = (diff_g > 200) & (diff_b > 200) & (diff_c > 200)
    to_remove = set()
    for idx in df.index[anomaly_mask].tolist():
        to_remove.add(idx)
        if idx > 0:
            to_remove.add(idx - 1)

    df_clean = df.copy()
    for idx in to_remove:
        df_clean.loc[idx, ["Green", "Blue", "Control"]] = np.nan
    df_clean[["Green", "Blue", "Control"]] = df_clean[["Green", "Blue", "Control"]].interpolate(method="linear")

    df_clean["Elapsed_hours"] = (df_clean["Timestamp"] - df_clean["Timestamp"].iloc[0]).dt.total_seconds() / 3600
    df_clean["Date"] = df_clean["Timestamp"].dt.date
    baselines = {ch: df_clean[ch].iloc[:10].mean() for ch in ["Green", "Blue", "Control"]}

    # Harvestability
    for ch in ["Green", "Blue", "Control"]:
        df_clean[f"{ch}_Harvestability"] = (
            (df_clean[ch] - baselines[ch]) / (HARVEST_THRESH[ch] - baselines[ch]) * 100
        ).clip(0, 100)

    # Plant length — constant linear rate
    for ch in ["Green", "Blue", "Control"]:
        crossed = df_clean[df_clean[ch] >= HARVEST_THRESH[ch]]
        if len(crossed) > 0:
            n = crossed.index[0] + 1
            rate = THRESHOLD_LENGTH / n
            df_clean[f"{ch}_Length"] = [(i + 1) * rate for i in range(len(df_clean))]
            df_clean[f"{ch}_Length"] = df_clean[f"{ch}_Length"].clip(upper=MAX_LENGTH)
        else:
            df_clean[f"{ch}_Length"] = df_clean[f"{ch}_Harvestability"] / 100.0 * THRESHOLD_LENGTH

    return df, df_clean, data_source, baselines


df_raw, df, data_source, baselines = load_data()

# =============================================
# SIDEBAR
# =============================================
with st.sidebar:
    st.title("\U0001F331 Welcome!")
    ""
    st.caption(f"Data source: {data_source}")
    if st.button("Refresh Data"):
        st.cache_data.clear()
        st.rerun()

    ""
    view_mode = st.radio(
        "View",
        ["Harvestability", "Plant Length", "Environmental", "Correlation & Stats"],
    )
    ""
    show_raw = st.checkbox("Show raw data (before cleaning)", False)
    ""
    time_range = st.slider(
        "Time range (hours)",
        min_value=0.0,
        max_value=float(df["Elapsed_hours"].max()),
        value=(0.0, min(170.0, float(df["Elapsed_hours"].max()))),
        step=1.0,
    )

df_filtered = df[
    (df["Elapsed_hours"] >= time_range[0]) & (df["Elapsed_hours"] <= time_range[1])
].copy()

# =============================================
# HEADER
# =============================================
"# \U0001F331 Bean Sprout Growth Dashboard"
"Effect of Coloured Light (Blue vs Green) on Mung Bean Sprout Growth"
""

# --- Summary metrics ---
duration = df["Timestamp"].max() - df["Timestamp"].min()
met_cols = st.columns(5, gap="medium")
met_cols[0].metric("Duration", f"{duration.days}d {duration.seconds // 3600}h")
met_cols[1].metric("Data Points", f"{len(df):,}")
met_cols[2].metric("Green Est. Length", f"{df['Green_Length'].iloc[-1]:.1f} cm")
met_cols[3].metric("Blue Est. Length", f"{df['Blue_Length'].iloc[-1]:.1f} cm")
met_cols[4].metric("Control Est. Length", f"{df['Control_Length'].iloc[-1]:.1f} cm")

""

# --- Notifications ---
_notifications = []

# Harvestability alerts
for ch in ["Green", "Blue", "Control"]:
    harv = df[f"{ch}_Harvestability"].iloc[-1]
    full = df[df[f"{ch}_Harvestability"] >= 100]
    if len(full) > 0:
        _notifications.append(("success", f"\U0001F33F **{ch}** is harvestable! Reached 100% on {full['Timestamp'].iloc[0].strftime('%b %d at %H:%M')}."))
    elif harv >= 80:
        _notifications.append(("warning", f"\U0001F331 **{ch}** is at {harv:.0f}% harvestability \u2014 almost ready for harvest."))

# Temperature alerts
temp_now = df["Temp(C)"].iloc[-1]
temp_mean = df["Temp(C)"].mean()
temp_std = df["Temp(C)"].std()
if temp_now < temp_mean - 2 * temp_std:
    _notifications.append(("error", f"\U0001F321\uFE0F Temperature is unusually low: **{temp_now:.1f}\u00b0C** (avg: {temp_mean:.1f}\u00b0C)."))
elif temp_now > temp_mean + 2 * temp_std:
    _notifications.append(("warning", f"\U0001F321\uFE0F Temperature is unusually high: **{temp_now:.1f}\u00b0C** (avg: {temp_mean:.1f}\u00b0C)."))

# Humidity alerts
hum_now = df["Humidity(%)"].iloc[-1]
hum_mean = df["Humidity(%)"].mean()
hum_std = df["Humidity(%)"].std()
if hum_now < hum_mean - 2 * hum_std:
    _notifications.append(("error", f"\U0001F4A7 Humidity is unusually low: **{hum_now:.1f}%** (avg: {hum_mean:.1f}%). Consider watering."))
elif hum_now > hum_mean + 2 * hum_std:
    _notifications.append(("warning", f"\U0001F4A7 Humidity is unusually high: **{hum_now:.1f}%** (avg: {hum_mean:.1f}%)."))

if _notifications:
    with st.container(border=True):
        "\U0001F514 **Notifications**"
        for level, msg in _notifications:
            if level == "success":
                st.success(msg)
            elif level == "warning":
                st.warning(msg)
            elif level == "error":
                st.error(msg)
    ""

# =============================================
# HARVESTABILITY
# =============================================
if view_mode == "Harvestability":
    "## Harvestability Analysis"
    "A sprout is **100% harvestable** when the sensor reaches: **Blue/Control \u2265 4000** ADC, **Green \u2265 3700** ADC."
    ""

    with st.container(border=True):
        fig = go.Figure()
        for ch in ["Green", "Blue", "Control"]:
            fig.add_trace(go.Scatter(
                x=df_filtered["Timestamp"], y=df_filtered[f"{ch}_Harvestability"],
                name=ch, line=dict(color=COLORS[ch], width=1.5),
            ))
        fig.add_hline(y=100, line_dash="dash", line_color="red", annotation_text="100% Harvestable")
        fig.update_layout(
            height=450, template=PLOT_TEMPLATE, margin=dict(t=40, b=40),
            yaxis_title="Harvestability (%)", yaxis_range=[-5, 115],
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        )
        st.plotly_chart(fig, use_container_width=True)

    ""
    "### Chamber Status"

    gauge_cols = st.columns(3, gap="medium")
    chamber_names = {"Green": "Green Light", "Blue": "Blue Light", "Control": "Control (Dark)"}

    for i, ch in enumerate(["Green", "Blue", "Control"]):
        full = df_filtered[df_filtered[f"{ch}_Harvestability"] >= 100]
        first_100_str = full["Timestamp"].iloc[0].strftime("%b %d, %H:%M") if len(full) > 0 else "Not yet"
        val = 100.0 if len(full) > 0 else df_filtered[f"{ch}_Harvestability"].iloc[-1]

        fig_g = go.Figure(go.Indicator(
            mode="gauge+number",
            value=val,
            number={"suffix": "%"},
            title={"text": f"{chamber_names[ch]}<br><span style='font-size:0.75em;color:#666'>First 100%: {first_100_str}</span>"},
            gauge={
                "axis": {"range": [0, 100], "tickwidth": 1, "dtick": 25},
                "bar": {"color": COLORS[ch]},
                "bgcolor": "#eee",
                "steps": [
                    {"range": [0, 50], "color": "#f5f5f5"},
                    {"range": [50, 80], "color": "#e8f5e9"},
                    {"range": [80, 100], "color": "#c8e6c9"},
                ],
                "threshold": {"line": {"color": "red", "width": 3}, "thickness": 0.8, "value": 100},
            },
        ))
        fig_g.update_layout(height=220, margin=dict(t=70, b=10, l=30, r=30))
        with gauge_cols[i]:
            with st.container(border=True):
                st.plotly_chart(fig_g, use_container_width=True)

# =============================================
# PLANT LENGTH
# =============================================
elif view_mode == "Plant Length":
    "## Estimated Plant Length"
    "Length estimated from sensor data: **10 cm** at harvestability threshold, linear growth capped at **30 cm**."
    ""

    with st.container(border=True):
        fig = go.Figure()
        for ch in ["Green", "Blue", "Control"]:
            fig.add_trace(go.Scatter(
                x=df_filtered["Timestamp"], y=df_filtered[f"{ch}_Length"],
                name=ch, line=dict(color=COLORS[ch], width=2),
            ))
        fig.add_hline(y=10, line_dash="dash", line_color="orange", annotation_text="Threshold (10 cm)")
        fig.add_hline(y=30, line_dash="dash", line_color="red", annotation_text="Max (30 cm)")
        fig.update_layout(
            height=450, template=PLOT_TEMPLATE, margin=dict(t=40, b=40),
            yaxis_title="Estimated Length (cm)", yaxis_range=[-1, 33],
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        )
        st.plotly_chart(fig, use_container_width=True)

    ""
    length_cols = st.columns(3, gap="medium")
    for i, ch in enumerate(["Green", "Blue", "Control"]):
        with length_cols[i]:
            st.metric(f"{ch} \u2014 Current Estimated Length", f"{df_filtered[f'{ch}_Length'].iloc[-1]:.1f} cm")

# =============================================
# ENVIRONMENTAL
# =============================================
elif view_mode == "Environmental":
    "## Environmental Conditions"
    ""

    left, right = st.columns([3, 1], gap="medium")

    with left:
        with st.container(border=True):
            fig = make_subplots(
                rows=2, cols=1, shared_xaxes=True,
                subplot_titles=("Temperature (\u00b0C)", "Humidity (%)"),
                vertical_spacing=0.12,
            )
            fig.add_trace(go.Scatter(
                x=df_filtered["Timestamp"], y=df_filtered["Temp(C)"],
                name="Temperature", line=dict(color="#d62728"),
                fill="tozeroy", fillcolor="rgba(214,39,40,0.08)",
            ), row=1, col=1)
            fig.add_trace(go.Scatter(
                x=df_filtered["Timestamp"], y=df_filtered["Humidity(%)"],
                name="Humidity", line=dict(color="#17becf"),
                fill="tozeroy", fillcolor="rgba(23,190,207,0.08)",
            ), row=2, col=1)
            fig.update_layout(
                height=450, template=PLOT_TEMPLATE, margin=dict(t=40, b=40),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            )
            st.plotly_chart(fig, use_container_width=True)

    with right:
        with st.container(border=True):
            "### Temperature"
            st.metric("Mean", f"{df_filtered['Temp(C)'].mean():.1f}\u00b0C")
            st.metric("Range", f"{df_filtered['Temp(C)'].min():.1f} \u2013 {df_filtered['Temp(C)'].max():.1f}\u00b0C")

        ""
        with st.container(border=True):
            "### Humidity"
            st.metric("Mean", f"{df_filtered['Humidity(%)'].mean():.1f}%")
            st.metric("Range", f"{df_filtered['Humidity(%)'].min():.1f} \u2013 {df_filtered['Humidity(%)'].max():.1f}%")

# =============================================
# CORRELATION & STATS
# =============================================
elif view_mode == "Correlation & Stats":
    "## Statistical Analysis"
    ""

    from scipy import stats as sp_stats

    # Growth rates
    rates = df.copy()
    for col in ["Green", "Blue", "Control"]:
        rates[f"{col}_rate"] = rates[col].diff(4) / 4
    rates = rates.dropna(subset=["Green_rate", "Blue_rate", "Control_rate"])

    rate_cols = st.columns(3, gap="medium")
    for i, ch in enumerate(["Green", "Blue", "Control"]):
        with rate_cols[i]:
            with st.container(border=True):
                f"### {ch}"
                st.metric("Mean Rate", f"{rates[f'{ch}_rate'].mean():.3f} ADC/sample")
                st.metric("Std Dev", f"{rates[f'{ch}_rate'].std():.3f}")

    ""
    "### Welch's t-test"

    tests = [
        ("Green vs Blue", "Green_rate", "Blue_rate"),
        ("Green vs Control", "Green_rate", "Control_rate"),
        ("Blue vs Control", "Blue_rate", "Control_rate"),
    ]
    results = []
    for name, a, b in tests:
        t, p = sp_stats.ttest_ind(rates[a], rates[b], equal_var=False)
        sig = "***" if p < 0.001 else "**" if p < 0.01 else "*" if p < 0.05 else "ns"
        results.append({"Comparison": name, "t-statistic": f"{t:.3f}", "p-value": f"{p:.6f}", "Significance": sig})

    with st.container(border=True):
        st.dataframe(pd.DataFrame(results), use_container_width=True, hide_index=True)

    ""
    left, right = st.columns(2, gap="medium")

    with left:
        with st.container(border=True):
            "### Growth Rate Distribution"
            fig_box = go.Figure()
            for col, color, name in [("Green_rate", COLORS["Green"], "Green"), ("Blue_rate", COLORS["Blue"], "Blue"), ("Control_rate", COLORS["Control"], "Control")]:
                fig_box.add_trace(go.Box(y=rates[col], name=name, marker_color=color))
            fig_box.update_layout(
                yaxis_title="Rate (ADC/sample)", height=400, template=PLOT_TEMPLATE,
                margin=dict(t=20, b=40),
            )
            st.plotly_chart(fig_box, use_container_width=True)

    with right:
        with st.container(border=True):
            "### Correlation Matrices"
            st.caption("ADC capped at harvest threshold to remove oscillation artefacts.")

            # Prepare capped ADC
            df_corr = df[["Timestamp", "Temp(C)", "Humidity(%)"]].copy()
            for ch in ["Green", "Blue", "Control"]:
                capped = df[ch].copy()
                first_cross = df[df[ch] >= HARVEST_THRESH[ch]].index
                if len(first_cross) > 0:
                    capped.iloc[first_cross[0]:] = capped.iloc[first_cross[0]:].clip(lower=HARVEST_THRESH[ch])
                df_corr[f"{ch}_ADC"] = capped
                df_corr[f"{ch}_Length"] = df[f"{ch}_Length"]

            sel_ch = st.selectbox("Chamber", ["Green", "Blue", "Control"])
            corr_cols = [f"{sel_ch}_ADC", f"{sel_ch}_Length", "Temp(C)", "Humidity(%)"]
            labels = [f"{sel_ch} ADC", f"{sel_ch} Length", "Temp", "Humidity"]
            corr = df_corr[corr_cols].dropna().corr()

            fig_corr = px.imshow(
                corr.values, text_auto=".2f", color_continuous_scale="RdBu_r",
                zmin=-1, zmax=1, x=labels, y=labels,
            )
            fig_corr.update_layout(height=350, margin=dict(t=20, b=20))
            st.plotly_chart(fig_corr, use_container_width=True)

# =============================================
# FOOTER
# =============================================
""
"---"
st.caption(
    f"**Data**: {data_source} | ESP32 + Photoresistors + DHT11 \u2192 Google Sheets \u2192 Dashboard | "
    f"Auto-refreshes every 5 min"
)

with st.expander("View Raw Data"):
    st.dataframe(df, use_container_width=True, hide_index=True)
    st.caption(f"{len(df)} data points | Last reading: {df['Timestamp'].max()}")
