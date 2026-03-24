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

# --- Custom CSS for modern plant-themed UI ---
st.markdown("""
<style>
    /* Main background */
    .stApp {
        background: linear-gradient(180deg, #f0f7f0 0%, #e8f5e9 50%, #f1f8e9 100%);
    }
    /* Sidebar */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #1b5e20 0%, #2e7d32 50%, #388e3c 100%);
    }
    section[data-testid="stSidebar"] * {
        color: #e8f5e9 !important;
    }
    /* Fix button text visibility in sidebar */
    section[data-testid="stSidebar"] button,
    section[data-testid="stSidebar"] button * ,
    section[data-testid="stSidebar"] button p,
    section[data-testid="stSidebar"] button span,
    section[data-testid="stSidebar"] .stButton button,
    section[data-testid="stSidebar"] .stButton button * {
        color: #1b5e20 !important;
        background-color: #e8f5e9 !important;
        border-color: #a5d6a7 !important;
    }
    section[data-testid="stSidebar"] button:hover,
    section[data-testid="stSidebar"] button:hover * {
        background-color: #c8e6c9 !important;
        color: #1b5e20 !important;
    }
    section[data-testid="stSidebar"] .stSelectbox label,
    section[data-testid="stSidebar"] .stRadio label,
    section[data-testid="stSidebar"] .stCheckbox label {
        color: #c8e6c9 !important;
    }
    /* Headers */
    h1, h2, h3 {
        color: #1b5e20 !important;
    }
    /* Metric cards */
    [data-testid="stMetric"] {
        background: white;
        border-radius: 12px;
        padding: 16px;
        box-shadow: 0 2px 8px rgba(27,94,32,0.1);
        border-left: 4px solid #4caf50;
    }
    [data-testid="stMetricLabel"] {
        color: #2e7d32 !important;
    }
    /* Info boxes */
    .stAlert {
        border-radius: 10px;
    }
    /* Plotly charts container */
    .stPlotlyChart {
        background: white;
        border-radius: 12px;
        padding: 8px;
        box-shadow: 0 2px 8px rgba(27,94,32,0.08);
    }
    /* Tabs */
    .stTabs [data-baseweb="tab"] {
        color: #2e7d32;
    }
    .stTabs [aria-selected="true"] {
        border-bottom-color: #4caf50 !important;
    }
    /* Expander */
    .streamlit-expanderHeader {
        color: #2e7d32 !important;
    }
</style>
""", unsafe_allow_html=True)

# --- Configuration ---
SHEET_ID = "1Vkc24L-VDzpiR6GrKL9sg7BJ5h5271bmTEASLvmzD9M"
SHEET_TAB = "data"
GSHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={SHEET_TAB}"

# Harvestability thresholds (from manual observation)
HARVEST_THRESH = {'Green': 3700, 'Blue': 4000, 'Control': 4000}
MAX_LENGTH = 30.0       # cm, observed max
THRESHOLD_LENGTH = 10.0  # cm, length at 100% harvestability

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

    # Clean anomalies (simultaneous drops across all 3 channels)
    diff_g = df["Green"].diff().abs()
    diff_b = df["Blue"].diff().abs()
    diff_c = df["Control"].diff().abs()
    anomaly_mask = (diff_g > 200) & (diff_b > 200) & (diff_c > 200)
    anomaly_indices = set(df.index[anomaly_mask].tolist())
    to_remove = set()
    for idx in anomaly_indices:
        to_remove.add(idx)
        if idx > 0:
            to_remove.add(idx - 1)

    df_clean = df.copy()
    for idx in to_remove:
        df_clean.loc[idx, ["Green", "Blue", "Control"]] = np.nan
    df_clean[["Green", "Blue", "Control"]] = df_clean[["Green", "Blue", "Control"]].interpolate(method="linear")

    # Derived columns
    df_clean["Elapsed_hours"] = (df_clean["Timestamp"] - df_clean["Timestamp"].iloc[0]).dt.total_seconds() / 3600
    df_clean["Date"] = df_clean["Timestamp"].dt.date

    # Compute baselines
    baselines = {ch: df_clean[ch].iloc[:10].mean() for ch in ["Green", "Blue", "Control"]}

    # Harvestability
    for ch in ["Green", "Blue", "Control"]:
        bl = baselines[ch]
        thresh = HARVEST_THRESH[ch]
        df_clean[f"{ch}_Harvestability"] = ((df_clean[ch] - bl) / (thresh - bl) * 100).clip(0, 100)

    # Plant length estimation — constant linear rate from start
    for ch in ["Green", "Blue", "Control"]:
        thresh = HARVEST_THRESH[ch]
        crossed = df_clean[df_clean[ch] >= thresh]

        if len(crossed) > 0:
            first_cross_idx = crossed.index[0]
            n_points_to_threshold = first_cross_idx + 1  # 0-based index, so +1
            rate = THRESHOLD_LENGTH / n_points_to_threshold  # constant cm/point
            df_clean[f"{ch}_Length"] = [(i + 1) * rate for i in range(len(df_clean))]
            df_clean[f"{ch}_Length"] = df_clean[f"{ch}_Length"].clip(upper=MAX_LENGTH)
        else:
            df_clean[f"{ch}_Length"] = df_clean[f"{ch}_Harvestability"] / 100.0 * THRESHOLD_LENGTH

    return df, df_clean, to_remove, data_source, baselines


df_raw, df, anomalies, data_source, baselines = load_data()

# --- Sidebar ---
st.sidebar.markdown("## \U0001F331 Controls")
st.sidebar.caption(f"Data: {data_source}")
if st.sidebar.button("\U0001F504 Refresh Data"):
    st.cache_data.clear()
    st.rerun()

view_mode = st.sidebar.radio(
    "View",
    ["Harvestability", "Plant Length", "Environmental", "Correlation & Stats"]
)

show_raw = st.sidebar.checkbox("Show raw data (before cleaning)", False)

time_range = st.sidebar.slider(
    "Time Range (hours from start)",
    min_value=0.0,
    max_value=float(df["Elapsed_hours"].max()),
    value=(0.0, min(170.0, float(df["Elapsed_hours"].max()))),
    step=1.0
)

df_filtered = df[(df["Elapsed_hours"] >= time_range[0]) & (df["Elapsed_hours"] <= time_range[1])].copy()

# --- Header ---
st.markdown("# \U0001F331 Bean Sprout Growth Dashboard")
st.caption("Effect of Coloured Light (Blue vs Green) on Mung Bean Sprout Growth | CID: 06043088")

# --- Metrics Row ---
col1, col2, col3, col4, col5 = st.columns(5)
duration = df["Timestamp"].max() - df["Timestamp"].min()
col1.metric("Duration", f"{duration.days}d {duration.seconds // 3600}h")
col2.metric("Data Points", f"{len(df):,}")
col3.metric("Green Est. Length", f"{df['Green_Length'].iloc[-1]:.1f} cm")
col4.metric("Blue Est. Length", f"{df['Blue_Length'].iloc[-1]:.1f} cm")
col5.metric("Control Est. Length", f"{df['Control_Length'].iloc[-1]:.1f} cm")

PLOT_TEMPLATE = "plotly_white"
COLORS = {"Green": "#2ca02c", "Blue": "#1f77b4", "Control": "#555555"}

# =============================================
# HARVESTABILITY VIEW (Main)
# =============================================
if view_mode == "Harvestability":
    st.subheader("Harvestability Analysis")
    st.markdown(
        "A sprout is **100% harvestable** when the sensor reaches: "
        "**Blue/Control \u2265 4000** ADC, **Green \u2265 3700** ADC (based on manual observation)."
    )

    fig = go.Figure()
    for ch in ["Green", "Blue", "Control"]:
        fig.add_trace(go.Scatter(
            x=df_filtered["Timestamp"], y=df_filtered[f"{ch}_Harvestability"],
            name=ch, line=dict(color=COLORS[ch], width=1.5)
        ))
    fig.add_hline(y=100, line_dash="dash", line_color="red", annotation_text="100% Harvestable")
    fig.update_layout(
        height=500, template=PLOT_TEMPLATE,
        title="Harvestability Over Time",
        yaxis_title="Harvestability (%)",
        yaxis_range=[-5, 115]
    )
    st.plotly_chart(fig, use_container_width=True)

    # Gauge widgets showing all chambers reached 100%
    st.markdown("#### Chamber Status")
    gauge_cols = st.columns(3)
    chamber_names = {"Green": "Green Light", "Blue": "Blue Light", "Control": "Control (Dark)"}
    gauge_colors = {"Green": "#2ca02c", "Blue": "#1f77b4", "Control": "#555555"}

    for i, ch in enumerate(["Green", "Blue", "Control"]):
        full = df_filtered[df_filtered[f"{ch}_Harvestability"] >= 100]
        first_100_str = full["Timestamp"].iloc[0].strftime("%b %d, %H:%M") if len(full) > 0 else "Not yet"

        fig_gauge = go.Figure(go.Indicator(
            mode="gauge+number",
            value=100 if len(full) > 0 else df_filtered[f"{ch}_Harvestability"].iloc[-1],
            number={"suffix": "%"},
            title={"text": f"{chamber_names[ch]}<br><span style='font-size:0.7em;color:gray'>First 100%: {first_100_str}</span>"},
            gauge={
                "axis": {"range": [0, 100], "tickwidth": 1},
                "bar": {"color": gauge_colors[ch]},
                "bgcolor": "#f0f0f0",
                "steps": [
                    {"range": [0, 50], "color": "#fff3e0"},
                    {"range": [50, 80], "color": "#ffe0b2"},
                    {"range": [80, 100], "color": "#c8e6c9"},
                ],
                "threshold": {
                    "line": {"color": "red", "width": 3},
                    "thickness": 0.8,
                    "value": 100
                }
            }
        ))
        fig_gauge.update_layout(height=250, margin=dict(t=80, b=20, l=30, r=30))
        with gauge_cols[i]:
            st.plotly_chart(fig_gauge, use_container_width=True)

# =============================================
# PLANT LENGTH VIEW
# =============================================
elif view_mode == "Plant Length":
    st.subheader("Estimated Plant Length")
    st.markdown(
        "Length estimated from sensor data: **10 cm** at harvestability threshold, "
        "then linear growth capped at **30 cm** (manual observation on 24 March)."
    )

    fig = go.Figure()
    for ch in ["Green", "Blue", "Control"]:
        fig.add_trace(go.Scatter(
            x=df_filtered["Timestamp"], y=df_filtered[f"{ch}_Length"],
            name=ch, line=dict(color=COLORS[ch], width=2)
        ))
    fig.add_hline(y=10, line_dash="dash", line_color="orange", annotation_text="Threshold (10 cm)")
    fig.add_hline(y=30, line_dash="dash", line_color="red", annotation_text="Max (30 cm)")
    fig.update_layout(
        height=500, template=PLOT_TEMPLATE,
        title="Estimated Bean Sprout Length Over Time",
        yaxis_title="Length (cm)",
        yaxis_range=[-1, 33]
    )
    st.plotly_chart(fig, use_container_width=True)

    # Summary — estimated length only
    cols = st.columns(3)
    for i, ch in enumerate(["Green", "Blue", "Control"]):
        with cols[i]:
            st.metric(f"{ch} — Current Estimated Length", f"{df_filtered[f'{ch}_Length'].iloc[-1]:.1f} cm")

# =============================================
# ENVIRONMENTAL VIEW
# =============================================
elif view_mode == "Environmental":
    st.subheader("Environmental Conditions")

    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True,
        subplot_titles=("Temperature (\u00b0C)", "Humidity (%)"),
        vertical_spacing=0.1
    )

    fig.add_trace(go.Scatter(
        x=df_filtered["Timestamp"], y=df_filtered["Temp(C)"],
        name="Temperature", line=dict(color="#d62728"), fill="tozeroy",
        fillcolor="rgba(214,39,40,0.1)"
    ), row=1, col=1)
    fig.add_trace(go.Scatter(
        x=df_filtered["Timestamp"], y=df_filtered["Humidity(%)"],
        name="Humidity", line=dict(color="#17becf"), fill="tozeroy",
        fillcolor="rgba(23,190,207,0.1)"
    ), row=2, col=1)
    fig.update_layout(height=500, template=PLOT_TEMPLATE)
    st.plotly_chart(fig, use_container_width=True)

    # Stats
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Mean Temp", f"{df_filtered['Temp(C)'].mean():.1f}\u00b0C")
        st.metric("Temp Range", f"{df_filtered['Temp(C)'].min():.1f} — {df_filtered['Temp(C)'].max():.1f}\u00b0C")
    with col2:
        st.metric("Mean Humidity", f"{df_filtered['Humidity(%)'].mean():.1f}%")
        st.metric("Humidity Range", f"{df_filtered['Humidity(%)'].min():.1f} — {df_filtered['Humidity(%)'].max():.1f}%")

# =============================================
# CORRELATION & STATS VIEW
# =============================================
elif view_mode == "Correlation & Stats":
    st.subheader("Statistical Analysis")

    from scipy import stats as sp_stats

    # Growth rates
    rates = df.copy()
    for col in ["Green", "Blue", "Control"]:
        rates[f"{col}_rate"] = rates[col].diff(4) / 4
    rates = rates.dropna(subset=["Green_rate", "Blue_rate", "Control_rate"])

    col1, col2, col3 = st.columns(3)
    for i, (ch, container) in enumerate(zip(["Green", "Blue", "Control"], [col1, col2, col3])):
        with container:
            st.metric(f"{ch} Mean Rate", f"{rates[f'{ch}_rate'].mean():.3f} ADC/sample")
            st.metric(f"{ch} Std Dev", f"{rates[f'{ch}_rate'].std():.3f}")

    st.markdown("---")
    st.subheader("Welch's t-test Results")

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
    st.table(pd.DataFrame(results))

    # Box plot
    fig_box = go.Figure()
    for col, color, name in [("Green_rate", COLORS["Green"], "Green"), ("Blue_rate", COLORS["Blue"], "Blue"), ("Control_rate", COLORS["Control"], "Control")]:
        fig_box.add_trace(go.Box(y=rates[col], name=name, marker_color=color))
    fig_box.update_layout(title="Growth Rate Distribution by Group", yaxis_title="Rate (ADC/sample)",
                          height=450, template=PLOT_TEMPLATE)
    st.plotly_chart(fig_box, use_container_width=True)

    # Separate correlation matrices per chamber
    st.markdown("---")
    st.subheader("Correlation Matrices by Chamber")
    st.caption("ADC values capped at harvest threshold after first crossing to remove oscillation artefacts.")

    # Prepare capped ADC for correlation
    df_corr = df[["Timestamp", "Temp(C)", "Humidity(%)"]].copy()
    for ch in ["Green", "Blue", "Control"]:
        thresh = HARVEST_THRESH[ch]
        capped = df[ch].copy()
        first_cross = df[df[ch] >= thresh].index
        if len(first_cross) > 0:
            capped.iloc[first_cross[0]:] = capped.iloc[first_cross[0]:].clip(lower=thresh)
        df_corr[f"{ch}_ADC"] = capped
        df_corr[f"{ch}_Length"] = df[f"{ch}_Length"]

    cols = st.columns(3)
    for i, ch in enumerate(["Green", "Blue", "Control"]):
        corr_cols = [f"{ch}_ADC", f"{ch}_Length", "Temp(C)", "Humidity(%)"]
        labels = [f"{ch} ADC", f"{ch} Length", "Temp", "Humidity"]
        corr = df_corr[corr_cols].dropna().corr()

        fig_corr = px.imshow(
            corr.values, text_auto=".2f", color_continuous_scale="RdBu_r",
            zmin=-1, zmax=1, x=labels, y=labels,
            title=f"{ch} Chamber"
        )
        fig_corr.update_layout(height=380, width=380)
        with cols[i]:
            st.plotly_chart(fig_corr, use_container_width=True)

# --- Footer ---
st.markdown("---")
st.markdown(
    f"**Data Source**: {data_source} | ESP32 + Photoresistors + DHT11 \u2192 Google Sheets \u2192 Dashboard | "
    f"Auto-refreshes every 5 minutes"
)

# Raw data viewer
with st.expander("\U0001F4CA View Raw Data"):
    st.dataframe(df, use_container_width=True)
    st.caption(f"{len(df)} data points | Last reading: {df['Timestamp'].max()}")
