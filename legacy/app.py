"""
Stock Scanner - Streamlit UI
Quantitative screening for swing trades and options strategies
"""

import io
import os
import shutil
import sys
from datetime import datetime

import pandas as pd
import streamlit as st

from src import (
    StockScanner,
    QUICK_SCAN,
    SP500_SAMPLE,
    get_combined_universe,
)

# Page configuration
st.set_page_config(
    page_title="Stock Scanner",
    page_icon="📊",
    layout="wide"
)

# Load CSS
css_path = os.path.join(os.path.dirname(__file__), 'static', 'styles.css')
if os.path.exists(css_path):
    with open(css_path) as f:
        st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)

# Additional slider styling
st.markdown("""
<style>
.stSlider [data-baseweb="slider"] [role="slider"] {
    background-color: #4a7cd6 !important;
    border: 3px solid #1a1f2e !important;
    width: 18px !important;
    height: 18px !important;
    border-radius: 50% !important;
}
</style>
""", unsafe_allow_html=True)

# Header
st.title("Stock Scanner")
st.caption("Quantitative screening for swing trades and options strategies")

# Tabs
tab_scanner, tab_lookup = st.tabs(["Scanner", "Ticker Lookup"])

# Sidebar configuration
with st.sidebar:
    st.header("Scan Configuration")

    scan_type = st.radio(
        "Universe Selection:",
        [
            "Quick Scan (50 stocks)",
            "S&P 500 Sample (100 stocks)",
            "S&P 500 + Robinhood 100 (~550 stocks)"
        ],
        index=0
    )

    if "Quick" in scan_type:
        st.caption("Estimated scan time: 30-60 seconds")
    elif "Sample" in scan_type:
        st.caption("Estimated scan time: 1-2 minutes")
    else:
        st.caption("Estimated scan time: 5-8 minutes")
        st.info("Large scan - results cached daily for faster subsequent runs.")

    st.write("---")
    st.subheader("Filter Parameters")

    min_iv = st.slider(
        "Minimum Volatility Rank",
        0, 100, 20, 5,
        help="Historical volatility percentile (0-100). Higher = more volatile vs. past year."
    )
    max_price = st.slider("Maximum Price", 10, 500, 300, 10)

    st.write("---")
    clear_cache = st.button("Clear Cache", help="Force fresh data retrieval")

    st.write("---")
    run_scan = st.button("Execute Scan", type="primary", use_container_width=True)


# Scanner Tab
with tab_scanner:
    if clear_cache:
        if os.path.exists('scanner_cache'):
            shutil.rmtree('scanner_cache')
            os.makedirs('scanner_cache')
            st.success("Cache cleared. Execute scan for fresh data.")

    if run_scan:
        # Determine universe
        if "Quick" in scan_type:
            universe = QUICK_SCAN
            universe_name = "Quick Scan (50 stocks)"
        elif "Sample" in scan_type:
            universe = SP500_SAMPLE
            universe_name = "S&P 500 Sample (100 stocks)"
        else:
            universe = get_combined_universe()
            universe_name = f"S&P 500 + Robinhood 100 ({len(universe)} unique stocks)"

        progress_bar = st.progress(0)
        status_text = st.empty()

        st.info(f"Scanning {universe_name}")

        def update_progress(current, total):
            progress = current / total
            progress_bar.progress(progress)
            remaining = total - current
            eta_seconds = remaining * 0.5
            eta_display = f"~{int(eta_seconds / 60)}m" if eta_seconds > 60 else f"~{int(eta_seconds)}s"
            status_text.text(f"Processing: {current}/{total} ({progress*100:.0f}%) - ETA: {eta_display}")

        # Run scanner
        scanner = StockScanner()
        debug_container = st.expander("Debug Output", expanded=False)

        with st.spinner("Executing scan..."):
            # Capture debug output
            old_stdout = sys.stdout
            sys.stdout = buffer = io.StringIO()

            try:
                results = scanner.run_scan(universe, progress_callback=update_progress)
            finally:
                sys.stdout = old_stdout
                debug_output = buffer.getvalue()

            with debug_container:
                st.code(debug_output, language="text")

        if not results:
            st.error("Scan execution failed - no data analyzed")
            st.warning("""
            **Potential Issues:**
            - API authentication error (check FMP_API_KEY in .env)
            - Network connectivity problem
            - Rate limit exceeded

            **Steps:**
            1. Verify .env file exists with FMP_API_KEY
            2. Check your API key is valid
            3. Retry after 60 seconds
            """)
            st.stop()

        # Apply filters
        filtered = [
            r for r in results
            if (r.get('hv_rank') or 0) >= min_iv and r['price'] <= max_price
        ]

        if filtered:
            st.success(f"Scan complete: {len(filtered)} opportunities identified")
            st.caption(f"Pipeline: {len(universe)} scanned → {len(results)} analyzed → {len(filtered)} passed filters")
        else:
            st.warning("Scan complete: 0 stocks passed filter criteria")
            st.info(f"""
            **Analysis Results:**
            - Successfully scanned {len(results)} stocks
            - Current filters: HV Rank ≥ {min_iv}%, Price ≤ ${max_price}

            **Try:**
            - Reduce Minimum Volatility Rank to 20-30%
            - Increase Maximum Price
            """)

        # Display results
        st.subheader("Top 20 Opportunities")

        for rank, r in enumerate(filtered[:20], 1):
            with st.expander(f"#{rank} - {r['ticker']} @ ${r['price']:.2f} | Score: {r['score']}"):
                col1, col2, col3 = st.columns(3)

                with col1:
                    st.write("**Price Analysis**")
                    st.metric("Current Price", f"${r['price']:.2f}")
                    st.metric(
                        "52W Position",
                        f"{r['range_position']:.0f}%",
                        help="0% = at low, 100% = at high. Below 40% = value zone"
                    )
                    st.metric(
                        "50-MA Distance",
                        f"{r['dist_50']:+.1f}%" if r['dist_50'] else "N/A",
                        help="Distance from 50-day moving average"
                    )

                with col2:
                    st.write("**Technical Indicators**")
                    st.metric("Trend", r['trend'])
                    st.metric(
                        "RSI",
                        f"{r['rsi']:.0f}",
                        help="Below 30 = oversold, above 70 = overbought"
                    )
                    st.metric(
                        "Volume Pace",
                        f"{r['volume_pace']:.2f}x",
                        help="Intraday volume vs expected. Above 1.5x = unusual activity"
                    )

                with col3:
                    st.write("**Key Levels**")
                    st.metric(
                        "HV Rank",
                        f"{r['hv_rank']:.0f}%" if r.get('hv_rank') else "N/A",
                        help="Historical volatility percentile. Above 60% = elevated volatility, good for option selling."
                    )
                    st.metric("Support", f"${r['support']:.2f}")
                    st.metric("Resistance", f"${r['resistance']:.2f}")

                st.write("**Active Signals:**", ", ".join(r['signals']) if r['signals'] else "None")

                hv_rank = r.get('hv_rank')
                if hv_rank and hv_rank > 60:
                    st.info(f"Strategy: Sell ${r['support']:.0f} puts, 30-45 DTE. High HV ({hv_rank:.0f}%) = enhanced premium.")

        # Data table
        st.write("---")
        st.subheader("Complete Results")

        if filtered:
            df = pd.DataFrame(filtered)
            cols = ['ticker', 'price', 'trend', 'hv_rank', 'range_position', 'dist_50', 'volume_pace', 'rsi', 'score']
            display_df = df[cols].copy()
            display_df.columns = ['Symbol', 'Price', 'Trend', 'HV Rank', '52W %', '50-MA %', 'Vol Pace', 'RSI', 'Score']

            st.dataframe(display_df, use_container_width=True, hide_index=True)

            csv = df.to_csv(index=False)
            st.download_button(
                "Export to CSV",
                csv,
                f"scan_{datetime.now().strftime('%Y%m%d')}.csv",
                "text/csv"
            )

    else:
        # Instructions when not scanning
        st.info("""
        **How to Use:**

        1. Select universe size in sidebar
        2. Configure filter parameters
        3. Click "Execute Scan"
        4. Review ranked opportunities

        **What It Finds:**
        - High volatility opportunities for premium selling
        - Pullback patterns in uptrends
        - Oversold bounce plays
        - Quality setups ranked by score

        **Note:** Volatility rank is based on historical volatility (HV), not implied volatility.
        """)

        st.write("**Available Universes:**")
        col1, col2, col3 = st.columns(3)

        with col1:
            st.write("**Quick Scan (50)**")
            st.caption(", ".join(QUICK_SCAN[:10]) + "...")

        with col2:
            st.write("**S&P 500 Sample (100)**")
            st.caption(", ".join(SP500_SAMPLE[:10]) + "...")

        with col3:
            combined = get_combined_universe()
            st.write(f"**Full Universe ({len(combined)})**")
            st.caption("S&P 500 + Robinhood 100 combined")


# Ticker Lookup Tab
with tab_lookup:
    st.subheader("Single Ticker Analysis")
    st.caption("Enter a stock symbol for comprehensive technical evaluation")

    col_input, col_button = st.columns([3, 1])

    with col_input:
        ticker_input = st.text_input(
            "Symbol",
            placeholder="AAPL, MSFT, etc.",
            label_visibility="collapsed"
        ).upper().strip()

    with col_button:
        analyze_btn = st.button("Analyze", type="primary", use_container_width=True)

    if analyze_btn and ticker_input:
        scanner = StockScanner()

        with st.spinner(f"Analyzing {ticker_input}..."):
            result = scanner.analyze_ticker(ticker_input)

        if not result:
            st.error(f"Symbol '{ticker_input}' not found or insufficient data.")
        else:
            # Price header
            change_color = "green" if result.get('change', 0) >= 0 else "red"
            st.markdown(f"## {ticker_input} @ ${result['price']:.2f}")
            st.markdown(f"**Change:** :{change_color}[{result.get('change', 0):+.2f} ({result.get('change_pct', 0):+.2f}%)]")

            st.write("---")

            col1, col2, col3 = st.columns(3)

            with col1:
                st.write("**Price Metrics**")
                st.metric("Current Price", f"${result['price']:.2f}")
                st.metric("52W Position", f"{result['range_position']:.0f}%")
                st.metric("52W High", f"${result['high_52w']:.2f}")
                st.metric("52W Low", f"${result['low_52w']:.2f}")

            with col2:
                st.write("**Technical Analysis**")
                st.metric("Trend", result['trend'])
                if result['dist_50']:
                    st.metric("50-MA Distance", f"{result['dist_50']:+.1f}%")
                if result['dist_200']:
                    st.metric("200-MA Distance", f"{result['dist_200']:+.1f}%")
                st.metric("RSI", f"{result['rsi']:.0f}")
                st.metric("10-Day Momentum", f"{result['momentum_10d']:+.1f}%")

            with col3:
                st.write("**Volume & Volatility**")
                st.metric("Current Volume", f"{result['volume']:,.0f}")
                if result.get('avg_volume'):
                    st.metric("Avg Volume (20d)", f"{result['avg_volume']:,.0f}")
                pace_label = "Volume Pace"
                if not result.get('volume_pace_reliable'):
                    pace_label += " (off-hours)"
                st.metric(pace_label, f"{result['volume_pace']:.2f}x")
                if result.get('hv_rank'):
                    st.metric(
                        "HV Rank",
                        f"{result['hv_rank']:.0f}%",
                        help="Historical volatility percentile vs past year"
                    )

            st.write("---")
            st.write("**Support & Resistance**")

            col_s, col_r = st.columns(2)
            with col_s:
                pct_to_support = ((result['support'] - result['price']) / result['price']) * 100
                st.metric("Support", f"${result['support']:.2f}", f"{pct_to_support:.1f}% from current")
            with col_r:
                pct_to_resistance = ((result['resistance'] - result['price']) / result['price']) * 100
                st.metric("Resistance", f"${result['resistance']:.2f}", f"{pct_to_resistance:+.1f}% from current")

            # Strategy suggestions
            hv_rank = result.get('hv_rank')
            if hv_rank and hv_rank > 50:
                st.write("---")
                st.write("**Strategy Considerations**")
                st.info(f"Put Selling: HV Rank at {hv_rank:.0f}% indicates elevated volatility - consider selling ${result['support']:.0f} puts")

                if result['rsi'] < 35:
                    st.success(f"Oversold: RSI at {result['rsi']:.0f} suggests potential bounce")

                if result['trend'] == 'Pullback in Uptrend':
                    st.success("Swing Setup: Pullback in uptrend presents long entry opportunity")

            elif result['rsi'] < 35 or result['trend'] == 'Pullback in Uptrend':
                st.write("---")
                st.write("**Strategy Considerations**")
                if result['rsi'] < 35:
                    st.success(f"Oversold: RSI at {result['rsi']:.0f} suggests potential bounce")
                if result['trend'] == 'Pullback in Uptrend':
                    st.success("Swing Setup: Pullback in uptrend presents long entry opportunity")

    elif not ticker_input and analyze_btn:
        st.warning("Enter a symbol to analyze")
    else:
        st.info("Enter a ticker symbol and click Analyze for detailed metrics")
