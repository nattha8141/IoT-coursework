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
    page_icon="🌱",
    layout="wide"
)

# --- Google Sheets Configuration ---
SHEET_ID = "1Vkc24L-VDzpiR6GrKL9sg7BJ5h5271bmTEASLvmzD9M"
SHEET_TAB = "data"
GSHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={SHEET_TAB}"

# --- Data Loading ---
@st.cache_data(ttl=300)  # Re-fetch every 5 minutes for live updates
def load_data():
    try:
        df = pd.read_csv(GSHEET_URL)
        data_source = "Google Sheets (live)"
    except Exception as e:
        st.warning(f"Could not fetch from Google Sheets ({e}). Falling back to local CSV.")
        df = pd.read_csv("data/experiment_result.csv")
        data_source = "Local CSV (offline)"

    # Handle both Google Sheets format (2026-03-05 2:38:27) and local CSV format (05/03/2026 02:38)
    df["Timestamp"] = pd.to_datetime(df["Timestamp"], format="mixed", dayfirst=True)
    df = df.sort_values("Timestamp").reset_index(drop=True)

    # Clean anomalies (simultaneous drops across all 3 channels)
    diff_g = df["Green"].diff().abs()
    diff_b = df["Blue"].diff().abs()
    diff_c = df["Control"].diff().abs()
    anomaly_mask = (diff_g > 200) & (diff_b > 200) & (diff_c > 200)
    anomaly_indices = set(df.index[anomaly_mask].tolist())
    # Also flag the row before each anomaly recovery
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

    return df, df_clean, to_remove, data_source

df_raw, df, anomalies, data_source = load_data()

# --- Sidebar ---
st.sidebar.title("Controls")

# Data source indicator and refresh
st.sidebar.caption(f"Data: {data_source}")
if st.sidebar.button("Refresh Data"):
    st.cache_data.clear()
    st.rerun()

view_mode = st.sidebar.radio("View Mode", ["Dashboard", "Growth Explorer", "Height Estimation", "Movement Analysis", "Environmental", "Compare & Stats"])

show_raw = st.sidebar.checkbox("Show raw data (before cleaning)", False)

time_range = st.sidebar.slider(
    "Time Range (hours from start)",
    min_value=0.0,
    max_value=float(df["Elapsed_hours"].max()),
    value=(0.0, float(df["Elapsed_hours"].max())),
    step=1.0
)

df_filtered = df[(df["Elapsed_hours"] >= time_range[0]) & (df["Elapsed_hours"] <= time_range[1])]

smoothing = st.sidebar.slider("Smoothing Window (samples)", 1, 48, 1)
if smoothing > 1:
    for col in ["Green", "Blue", "Control"]:
        df_filtered[col] = df_filtered[col].rolling(smoothing, center=True, min_periods=1).mean()

# --- Header ---
st.title("Bean Sprout Growth Experiment Dashboard")
st.caption("Effect of Colored Light (Blue vs Green) on Mung Bean Sprout Growth | CID: 06043088")

# --- Metrics Row ---
col1, col2, col3, col4, col5 = st.columns(5)
duration = df["Timestamp"].max() - df["Timestamp"].min()
col1.metric("Duration", f"{duration.days}d {duration.seconds//3600}h")
col2.metric("Data Points", f"{len(df)}")
col3.metric("Green Total Growth", f"+{df['Green'].iloc[-1] - df['Green'].iloc[0]:.0f} ADC")
col4.metric("Blue Total Growth", f"+{df['Blue'].iloc[-1] - df['Blue'].iloc[0]:.0f} ADC*")
col5.metric("Control Total Growth", f"{df['Control'].iloc[-1] - df['Control'].iloc[0]:+.0f} ADC")

# =============================================
# DASHBOARD VIEW
# =============================================
if view_mode == "Dashboard":
    st.subheader("Growth Curves — All Channels")

    fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                        subplot_titles=("Photoresistor Readings (ADC)", "Relative Growth from Baseline"),
                        vertical_spacing=0.12)

    # Raw data if toggled
    source = df_raw if show_raw else df_filtered

    for col, color, name in [("Green", "#2ca02c", "Green"), ("Blue", "#1f77b4", "Blue"), ("Control", "#555555", "Control")]:
        fig.add_trace(go.Scatter(x=source["Timestamp"], y=source[col], name=name,
                                 line=dict(color=color, width=1.5)), row=1, col=1)

    # Relative growth
    baselines = {c: df["Green"].iloc[:10].mean() if c == "Green" else df["Blue"].iloc[:10].mean() if c == "Blue" else df["Control"].iloc[:10].mean() for c in ["Green", "Blue", "Control"]}
    for col, color, name in [("Green", "#2ca02c", "Green"), ("Blue", "#1f77b4", "Blue"), ("Control", "#555555", "Control")]:
        fig.add_trace(go.Scatter(x=df_filtered["Timestamp"], y=df_filtered[col] - baselines[col],
                                 name=f"{name} (rel)", line=dict(color=color, width=1.5, dash="dot"),
                                 showlegend=False), row=2, col=1)

    fig.add_hline(y=4095, line_dash="dot", line_color="red", annotation_text="Sensor Saturation", row=1, col=1)
    fig.update_layout(height=700, template="plotly_white")
    fig.update_yaxes(title_text="ADC Reading", row=1, col=1)
    fig.update_yaxes(title_text="Change from Baseline", row=2, col=1)
    st.plotly_chart(fig, use_container_width=True)

    st.info("**Blue saturated at 4095** (ADC max) ~3 days in, meaning blue-light growth exceeded sensor range. The control group oscillation reveals plant movement (phototropism).")

# =============================================
# GROWTH EXPLORER
# =============================================
elif view_mode == "Growth Explorer":
    st.subheader("Growth Rate Explorer")

    rate_window = st.slider("Rate calculation window (samples)", 2, 24, 4)
    smooth_rate = st.slider("Rate smoothing (rolling avg)", 1, 24, 8)

    rate_df = df_filtered.copy()
    for col in ["Green", "Blue", "Control"]:
        rate_df[f"{col}_rate"] = rate_df[col].diff(rate_window) / rate_window
        if smooth_rate > 1:
            rate_df[f"{col}_rate"] = rate_df[f"{col}_rate"].rolling(smooth_rate, center=True, min_periods=1).mean()

    fig = go.Figure()
    for col, color in [("Green_rate", "#2ca02c"), ("Blue_rate", "#1f77b4"), ("Control_rate", "#555555")]:
        fig.add_trace(go.Scatter(x=rate_df["Timestamp"], y=rate_df[col], name=col.replace("_rate", ""),
                                 line=dict(color=color, width=1.5)))
    fig.add_hline(y=0, line_dash="dash", line_color="gray")
    fig.update_layout(height=500, template="plotly_white",
                      title="Growth Rate (ADC units per 15-min interval)",
                      yaxis_title="Rate (ADC/sample)")
    st.plotly_chart(fig, use_container_width=True)

    # Daily growth bar chart
    st.subheader("Daily Growth Summary")
    daily = df.groupby("Date").agg(
        Green_start=("Green", "first"), Green_end=("Green", "last"),
        Blue_start=("Blue", "first"), Blue_end=("Blue", "last"),
        Control_start=("Control", "first"), Control_end=("Control", "last")
    )
    daily["Green"] = daily["Green_end"] - daily["Green_start"]
    daily["Blue"] = daily["Blue_end"] - daily["Blue_start"]
    daily["Control"] = daily["Control_end"] - daily["Control_start"]

    fig2 = go.Figure()
    for col, color in [("Green", "#2ca02c"), ("Blue", "#1f77b4"), ("Control", "#555555")]:
        fig2.add_trace(go.Bar(x=[str(d) for d in daily.index], y=daily[col], name=col,
                              marker_color=color, opacity=0.85))
    fig2.update_layout(barmode="group", height=400, template="plotly_white",
                       title="Net ADC Change Per Day", yaxis_title="ADC Change")
    st.plotly_chart(fig2, use_container_width=True)

# =============================================
# HEIGHT ESTIMATION
# =============================================
elif view_mode == "Height Estimation":
    st.subheader("Geometric Height Estimation Model")
    st.markdown("""
    Since no direct height sensor is available, we estimate plant height using the **physical geometry**
    of the chamber. The LED is at the top corner, the photosensor is lower — as the plant grows upward,
    it blocks more of the light path. Using trigonometry, we map ADC readings to estimated cm.
    """)

    # Adjustable geometry parameters
    st.sidebar.markdown("---")
    st.sidebar.subheader("Geometry Parameters")
    H_led = st.sidebar.number_input("LED height (cm)", value=11.0, step=0.5)
    H_sensor = st.sidebar.number_input("Sensor height (cm)", value=4.0, step=0.5)
    D_horizontal = st.sidebar.number_input("Horizontal distance (cm)", value=10.0, step=0.5)
    H_base = st.sidebar.number_input("Container rim height (cm)", value=4.0, step=0.5)
    X_plant = st.sidebar.number_input("Plant position from sensor (cm)", value=5.0, step=0.5)
    cone_factor = st.sidebar.slider("Cone spread factor", 1.0, 3.0, 1.5, 0.1)

    # Calculate full block height
    h_line_at_plant = H_sensor + (H_led - H_sensor) * (X_plant / D_horizontal)
    H_full_block = (h_line_at_plant - H_base) * cone_factor
    ADC_MAX = 4095

    col1, col2, col3 = st.columns(3)
    col1.metric("Line-of-sight at plant", f"{h_line_at_plant:.1f} cm")
    col2.metric("Full block height", f"{H_full_block:.1f} cm")
    col3.metric("Growth above rim for saturation", f"{H_full_block:.1f} cm")

    # Compute estimated heights
    baselines = {
        "Green": df_filtered["Green"].iloc[:10].mean(),
        "Blue": df_filtered["Blue"].iloc[:10].mean(),
        "Control": df_filtered["Control"].iloc[:10].mean()
    }

    height_data = df_filtered.copy()
    for ch in ["Green", "Blue", "Control"]:
        ratio = ((height_data[ch] - baselines[ch]) / (ADC_MAX - baselines[ch])).clip(0, 1)
        height_data[f"{ch}_cm"] = ratio * H_full_block

    # Height plot
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                        subplot_titles=("Estimated Plant Height (cm)", "Estimated Growth Rate (cm/hour)"),
                        vertical_spacing=0.12)

    for ch, color, name in [("Green_cm", "#2ca02c", "Green"), ("Blue_cm", "#1f77b4", "Blue"), ("Control_cm", "#555555", "Control")]:
        fig.add_trace(go.Scatter(x=height_data["Timestamp"], y=height_data[ch], name=name,
                                 line=dict(color=color, width=1.5)), row=1, col=1)

    fig.add_hline(y=H_full_block, line_dash="dot", line_color="red",
                  annotation_text=f"Sensor limit ({H_full_block:.1f} cm)", row=1, col=1)

    # Growth rate in cm/hour
    for ch in ["Green", "Blue", "Control"]:
        height_data[f"{ch}_rate_cm"] = height_data[f"{ch}_cm"].diff(4) / 1.0  # 4 samples = 1 hour
        rate_smooth = height_data[f"{ch}_rate_cm"].rolling(8, center=True, min_periods=1).mean()
        color = "#2ca02c" if ch == "Green" else "#1f77b4" if ch == "Blue" else "#555555"
        fig.add_trace(go.Scatter(x=height_data["Timestamp"], y=rate_smooth, name=f"{ch} rate",
                                 line=dict(color=color, width=1.2), showlegend=False), row=2, col=1)

    fig.add_hline(y=0, line_dash="dash", line_color="gray", row=2, col=1)
    fig.update_layout(height=700, template="plotly_white")
    fig.update_yaxes(title_text="Height (cm)", row=1, col=1)
    fig.update_yaxes(title_text="Rate (cm/hour)", row=2, col=1)
    st.plotly_chart(fig, use_container_width=True)

    # Summary metrics
    st.subheader("Height Summary")
    cols = st.columns(3)
    for i, (ch, name) in enumerate([("Green", "Green Light"), ("Blue", "Blue Light"), ("Control", "Control (Dark)")]):
        h_final = height_data[f"{ch}_cm"].iloc[-1]
        h_max = height_data[f"{ch}_cm"].max()
        rate = height_data[f"{ch}_rate_cm"].dropna()
        pos_rate = rate[rate > 0]
        with cols[i]:
            st.metric(f"{name} — Current", f"{h_final:.1f} cm")
            st.metric(f"{name} — Peak", f"{h_max:.1f} cm")
            st.metric(f"{name} — Avg growth rate", f"{pos_rate.mean():.3f} cm/h" if len(pos_rate) > 0 else "N/A")

    # ADC to height calibration curve
    st.subheader("ADC to Height Calibration")
    adc_range = np.linspace(3400, 4095, 200)
    fig_cal = go.Figure()
    for ch, color in [("Green", "#2ca02c"), ("Blue", "#1f77b4"), ("Control", "#555555")]:
        bl = baselines[ch]
        ratio = np.clip((adc_range - bl) / (ADC_MAX - bl), 0, 1)
        height = ratio * H_full_block
        fig_cal.add_trace(go.Scatter(x=adc_range, y=height, name=f"{ch} (baseline={bl:.0f})",
                                     line=dict(color=color, width=2)))
    fig_cal.add_vline(x=4095, line_dash="dot", line_color="red", annotation_text="ADC Max")
    fig_cal.update_layout(xaxis_title="ADC Reading", yaxis_title="Estimated Height (cm)",
                          height=400, template="plotly_white", title="ADC → Height Calibration Curve")
    st.plotly_chart(fig_cal, use_container_width=True)

    st.info(f"**Model**: height = obstruction_ratio x {H_full_block:.1f} cm. "
            f"Adjust the geometry parameters in the sidebar to refine. "
            f"The control group's negative values reflect phototropic bending, not shrinkage.")

# =============================================
# MOVEMENT ANALYSIS
# =============================================
elif view_mode == "Movement Analysis":
    st.subheader("Plant Movement / Oscillation Analysis")
    st.markdown("""
    The control group (dark chamber) shows periodic oscillations in the sensor data.
    This indicates **phototropic movement** — the sprouts bend toward faint light leaking from adjacent chambers.
    Below, the long-term growth trend is removed to isolate the oscillation pattern.
    """)

    trend_window = st.slider("Trend window (samples for detrending)", 12, 96, 48)
    channel = st.selectbox("Channel", ["Control", "Green", "Blue"])

    detrend_df = df_filtered.copy()
    detrend_df["trend"] = detrend_df[channel].rolling(trend_window, center=True, min_periods=1).mean()
    detrend_df["detrended"] = detrend_df[channel] - detrend_df["trend"]

    fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                        subplot_titles=(f"{channel} — Raw + Trend", f"{channel} — Detrended (Oscillation)"),
                        vertical_spacing=0.12)

    fig.add_trace(go.Scatter(x=detrend_df["Timestamp"], y=detrend_df[channel], name="Raw",
                             line=dict(color="#888", width=1)), row=1, col=1)
    fig.add_trace(go.Scatter(x=detrend_df["Timestamp"], y=detrend_df["trend"], name="Trend",
                             line=dict(color="red", width=2)), row=1, col=1)
    fig.add_trace(go.Scatter(x=detrend_df["Timestamp"], y=detrend_df["detrended"], name="Oscillation",
                             line=dict(color="#1f77b4", width=1)), row=2, col=1)
    fig.add_hline(y=0, line_dash="dash", line_color="gray", row=2, col=1)
    fig.update_layout(height=600, template="plotly_white")
    st.plotly_chart(fig, use_container_width=True)

    # FFT
    st.subheader("Frequency Spectrum (FFT)")
    detrended_vals = detrend_df["detrended"].dropna().values
    if len(detrended_vals) > 10:
        n = len(detrended_vals)
        fft_vals = np.fft.rfft(detrended_vals)
        fft_freq = np.fft.rfftfreq(n, d=0.25)  # 0.25 hours = 15 min
        power = np.abs(fft_vals[1:]) ** 2
        periods = 1 / fft_freq[1:]

        fig_fft = go.Figure()
        fig_fft.add_trace(go.Scatter(x=periods, y=power / power.max(), mode="lines",
                                     line=dict(color="#333", width=1)))
        fig_fft.add_vline(x=24, line_dash="dash", line_color="red", annotation_text="24h")
        fig_fft.add_vline(x=12, line_dash="dash", line_color="orange", annotation_text="12h")
        fig_fft.update_layout(xaxis_title="Period (hours)", yaxis_title="Normalised Power",
                              xaxis_range=[0, 48], height=400, template="plotly_white",
                              title=f"FFT Power Spectrum — {channel} Channel")
        st.plotly_chart(fig_fft, use_container_width=True)

# =============================================
# ENVIRONMENTAL
# =============================================
elif view_mode == "Environmental":
    st.subheader("Environmental Conditions")

    fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                        subplot_titles=("Temperature (°C)", "Humidity (%)"),
                        vertical_spacing=0.1)

    fig.add_trace(go.Scatter(x=df_filtered["Timestamp"], y=df_filtered["Temp(C)"],
                             name="Temperature", line=dict(color="#d62728"), fill="tozeroy",
                             fillcolor="rgba(214,39,40,0.1)"), row=1, col=1)
    fig.add_trace(go.Scatter(x=df_filtered["Timestamp"], y=df_filtered["Humidity(%)"],
                             name="Humidity", line=dict(color="#17becf"), fill="tozeroy",
                             fillcolor="rgba(23,190,207,0.1)"), row=2, col=1)
    fig.update_layout(height=500, template="plotly_white")
    st.plotly_chart(fig, use_container_width=True)

    # Scatter: temp/humidity vs growth
    st.subheader("Environmental Impact on Growth Rate")
    env_col = st.selectbox("Environmental Variable", ["Temp(C)", "Humidity(%)"])
    growth_col = st.selectbox("Growth Channel", ["Green", "Blue", "Control"])

    rate = df.copy()
    rate["rate"] = rate[growth_col].diff(4) / 4
    rate = rate.dropna(subset=["rate"])

    fig_scatter = px.scatter(rate, x=env_col, y="rate", opacity=0.4, trendline="ols",
                             labels={"rate": f"{growth_col} Growth Rate (ADC/sample)"},
                             title=f"{growth_col} Growth Rate vs {env_col}")
    fig_scatter.update_layout(height=450, template="plotly_white")
    st.plotly_chart(fig_scatter, use_container_width=True)

# =============================================
# COMPARE & STATS
# =============================================
elif view_mode == "Compare & Stats":
    st.subheader("Statistical Comparison")

    from scipy import stats as sp_stats

    rates = df.copy()
    for col in ["Green", "Blue", "Control"]:
        rates[f"{col}_rate"] = rates[col].diff(4) / 4
    rates = rates.dropna(subset=["Green_rate", "Blue_rate", "Control_rate"])

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Green Mean Rate", f"{rates['Green_rate'].mean():.3f} ADC/sample")
        st.metric("Green Std Dev", f"{rates['Green_rate'].std():.3f}")
    with col2:
        st.metric("Blue Mean Rate", f"{rates['Blue_rate'].mean():.3f} ADC/sample")
        st.metric("Blue Std Dev", f"{rates['Blue_rate'].std():.3f}")
    with col3:
        st.metric("Control Mean Rate", f"{rates['Control_rate'].mean():.3f} ADC/sample")
        st.metric("Control Std Dev", f"{rates['Control_rate'].std():.3f}")

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
    for col, color, name in [("Green_rate", "#2ca02c", "Green"), ("Blue_rate", "#1f77b4", "Blue"), ("Control_rate", "#555555", "Control")]:
        fig_box.add_trace(go.Box(y=rates[col], name=name, marker_color=color))
    fig_box.update_layout(title="Growth Rate Distribution by Group", yaxis_title="Rate (ADC/sample)",
                          height=450, template="plotly_white")
    st.plotly_chart(fig_box, use_container_width=True)

    # Correlation heatmap
    st.subheader("Cross-Correlation Matrix")
    corr = df[["Green", "Blue", "Control", "Temp(C)", "Humidity(%)"]].dropna().corr()
    fig_corr = px.imshow(corr, text_auto=".2f", color_continuous_scale="RdBu_r",
                         zmin=-1, zmax=1, title="Pearson Correlation Matrix")
    fig_corr.update_layout(height=500)
    st.plotly_chart(fig_corr, use_container_width=True)

# --- Footer ---
st.markdown("---")
st.markdown(f"**Data Source**: {data_source} | ESP32 + Photoresistors + DHT11 → Google Sheets (live) → Dashboard | "
            f"Auto-refreshes every 5 minutes | "
            "[GitHub Repository](https://github.com/hajidnaufalatthousi/internet-of-things-project)")

# Raw data viewer
with st.expander("View Raw Data"):
    st.dataframe(df, use_container_width=True)
    st.caption(f"{len(df)} data points | Last reading: {df['Timestamp'].max()}")
