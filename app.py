"""
SMB Underwriting Simulator - Merchant 360

Single-merchant underwriting case file in an editorial layout. Consolidates the
former three tabs (forecast / offer / monitor) into one top-to-bottom case view:
hero verdict + key stats, then Step 1 forecast, Step 2 risk signals,
Step 3 offer construction, Step 4 post-decision monitor, with a model-driven
sidebar (risk tier, model notes, signals).

Design ported from the Claude Design handoff "Merchant 360.html"; data comes
from the real quantile-regression forecaster, offer simulator, and risk monitor.
The previous tabbed dashboard is preserved in app_legacy_tabs.py.
"""
import streamlit as st
import streamlit.components.v1 as components

from src.utils import load_monthly_rev
from src.revenue_forecaster import RevenueForecaster
from src.offer_simulator import OfferSimulator
from src.merchant360 import build_merchants
from src.merchant360_view import render_merchant360_html

st.set_page_config(
    page_title="Merchant 360 · Credit Lab",
    page_icon="🏦",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Strip Streamlit chrome so the editorial page reads as a full-bleed canvas.
st.markdown(
    """
    <style>
      #MainMenu, header[data-testid="stHeader"], footer {visibility:hidden;}
      .block-container {padding:0 !important; max-width:100% !important;}
      [data-testid="stAppViewContainer"] > .main {padding:0 !important;}
      [data-testid="stSidebar"] {display:none;}
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data
def load_merchants():
    monthly_rev = load_monthly_rev("data/merchant_transactions.csv")
    forecaster = RevenueForecaster(monthly_rev)
    df_forecasts = forecaster.fit_all()
    simulator = OfferSimulator(df_forecasts)
    df_offers = simulator.compute_base_offers()
    return build_merchants(forecaster, df_forecasts, df_offers)


merchants = load_merchants()

if not merchants:
    st.error("No merchant data available. Check data/merchant_transactions.csv.")
else:
    html = render_merchant360_html(merchants)
    components.html(html, height=1880, scrolling=True)
