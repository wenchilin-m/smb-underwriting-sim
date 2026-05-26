import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px

from src.utils import load_monthly_rev, ALERT_COLORS, TIER_PARAMS, TERM_MONTHS, fmt_dollar, fmt_pct
from src.revenue_forecaster import RevenueForecaster
from src.offer_simulator import OfferSimulator
from src.risk_monitor import RiskMonitor, classify_alert

st.set_page_config(
    page_title='SMB Underwriting Simulator',
    page_icon='🏦',
    layout='wide',
)

# ── Data loading (cached) ─────────────────────────────────────────────────────
@st.cache_data
def load_all():
    monthly_rev  = load_monthly_rev('data/merchant_transactions.csv')
    forecaster   = RevenueForecaster(monthly_rev)
    df_forecasts = forecaster.fit_all()
    simulator    = OfferSimulator(df_forecasts)
    df_offers    = simulator.compute_base_offers()
    df_grid      = simulator.simulate_grid()
    df_optimal   = simulator.optimal_offers()
    monitor      = RiskMonitor(monthly_rev, df_offers)
    return monthly_rev, forecaster, df_forecasts, simulator, df_offers, df_grid, df_optimal, monitor

monthly_rev, forecaster, df_forecasts, simulator, df_offers, df_grid, df_optimal, monitor = load_all()

# ── Sidebar ───────────────────────────────────────────────────────────────────
st.sidebar.title('🏦 Underwriting Simulator')
st.sidebar.markdown('---')

merchant_options = {
    f"{r.merchant_id} | {r.merchant_type} | store {r.store_id}  ({r.months} mo)": i
    for i, r in df_forecasts.iterrows()
}
selected_label = st.sidebar.selectbox('Select merchant-store', list(merchant_options.keys()))
sel_idx        = merchant_options[selected_label]
sel            = df_forecasts.iloc[sel_idx]
sel_offer      = df_offers[
    (df_offers.merchant_id == sel.merchant_id) & (df_offers.store_id == sel.store_id)
].iloc[0]
sel_grid = df_grid[
    (df_grid.merchant_id == sel.merchant_id) & (df_grid.store_id == sel.store_id)
]

st.sidebar.markdown('---')
st.sidebar.caption(
    f"**Risk tier:** {sel.risk_tier}  \n"
    f"**QR fitted:** {'✅' if sel.qr_available else '❌ (fallback ±20%)'}  \n"
    f"**CV:** {sel.cv:.2f}  |  **History:** {sel.months} months"
)

# ── Header ────────────────────────────────────────────────────────────────────
st.title('SMB Underwriting Simulator')
st.caption(
    'Quantile regression revenue forecasting · P10-anchored loan sizing · '
    'Post-issuance risk monitoring'
)
st.markdown('---')

tab1, tab2, tab3 = st.tabs(['📊 Revenue Forecast', '💰 Offer Simulation', '⚠️ Risk Monitoring'])

# ─────────────────────────────────────────────────────────────────────────────
# TAB 1 — REVENUE FORECAST
# ─────────────────────────────────────────────────────────────────────────────
with tab1:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric('Avg Monthly Revenue', fmt_dollar(sel.baseline))
    c2.metric('Revenue CV',          f'{sel.cv:.2f}')
    c3.metric('Months of History',   str(sel.months))
    c4.metric('Forecast model',      'Quantile Reg' if sel.qr_available else 'Rolling ±20%')

    st.markdown('### Next-Month Revenue Forecast')

    hist_rev    = forecaster.get_history(sel.merchant_id, sel.store_id, last_n=18)
    hist_labels = forecaster.get_period_labels(sel.merchant_id, sel.store_id, last_n=18)
    x_hist  = list(range(len(hist_rev)))
    x_next  = len(hist_rev)

    fig = go.Figure()

    # Historical line
    fig.add_trace(go.Scatter(
        x=x_hist, y=hist_rev.tolist(),
        mode='lines+markers',
        name='Historical',
        line=dict(color='steelblue', width=2),
        marker=dict(size=5),
        hovertemplate='%{text}<br>$%{y:,.0f}<extra></extra>',
        text=hist_labels,
    ))

    # P10–P90 fan at next month
    fig.add_trace(go.Scatter(
        x=[x_next - 0.3, x_next + 0.3, x_next + 0.3, x_next - 0.3],
        y=[sel.p10, sel.p10, sel.p90, sel.p90],
        fill='toself', fillcolor='rgba(44,160,44,0.12)',
        line=dict(color='rgba(0,0,0,0)'),
        name='P10–P90 range',
        hoverinfo='skip',
    ))

    # P50 marker
    fig.add_trace(go.Scatter(
        x=[x_next], y=[sel.p50],
        mode='markers',
        name=f'P50  {fmt_dollar(sel.p50)}',
        marker=dict(color='forestgreen', size=14, symbol='diamond'),
    ))

    # P10 / P90 error bar
    fig.add_trace(go.Scatter(
        x=[x_next], y=[sel.p50],
        error_y=dict(
            type='data',
            symmetric=False,
            array=[sel.p90 - sel.p50],
            arrayminus=[sel.p50 - sel.p10],
            color='forestgreen',
            thickness=2.5,
            width=12,
        ),
        mode='markers',
        marker=dict(size=0),
        showlegend=False,
        hovertemplate=(
            f'P10: {fmt_dollar(sel.p10)}<br>'
            f'P50: {fmt_dollar(sel.p50)}<br>'
            f'P90: {fmt_dollar(sel.p90)}<extra></extra>'
        ),
    ))

    fig.add_vline(x=x_next - 0.5, line_dash='dash', line_color='gray',
                  annotation_text='Forecast →', annotation_position='top left')

    fig.update_xaxes(
        tickvals=x_hist + [x_next],
        ticktext=hist_labels + ['Next month'],
        tickangle=-45,
    )
    fig.update_yaxes(tickprefix='$', tickformat=',.0f')
    fig.update_layout(
        height=420, hovermode='x unified',
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
        margin=dict(t=40, b=80),
    )
    st.plotly_chart(fig, use_container_width=True)

    with st.expander('Forecast details'):
        display = df_forecasts[df_forecasts.merchant_id == sel.merchant_id].copy()
        for col in ['p10', 'p50', 'p90', 'naive', 'baseline']:
            display[col] = display[col].map(fmt_dollar)
        display['cv'] = display['cv'].map(fmt_pct)
        st.dataframe(
            display[['merchant_id','merchant_type','store_id','months','cv',
                      'baseline_type','qr_available','p10','p50','p90']],
            use_container_width=True, hide_index=True,
        )

# ─────────────────────────────────────────────────────────────────────────────
# TAB 2 — OFFER SIMULATION
# ─────────────────────────────────────────────────────────────────────────────
with tab2:
    st.markdown('### Recommended Offer')

    params = TIER_PARAMS[sel.risk_tier]
    oa, ob, oc, od = st.columns(4)
    oa.metric('Advance Amount', fmt_dollar(sel_offer.advance_amount))
    ob.metric('Fixed Fee',      fmt_dollar(sel_offer.fixed_fee) + f'  ({fmt_pct(params["factor_rate"])} factor rate)')
    oc.metric('Total Payback',  fmt_dollar(sel_offer.total_payback))
    od.metric('Implied Term',   f'{sel_offer.implied_term_mo:.1f} months' if sel_offer.implied_term_mo else 'N/A')

    st.caption(
        f'Sized at **{fmt_pct(params["advance_rate"])} of P10 × {TERM_MONTHS} months** '
        f'= {fmt_dollar(sel.p10)} × {TERM_MONTHS} × {fmt_pct(params["advance_rate"])}. '
        f'Monthly repayment ≈ {fmt_pct(params["repayment_rate"])} of P50 revenue '
        f'({fmt_dollar(sel_offer.monthly_payment)}/month). '
        f'Effective APR ≈ {fmt_pct(sel_offer.eff_apr) if sel_offer.eff_apr else "N/A"}.'
    )

    st.markdown('---')
    st.markdown('### Offer Grid: Expected Profit by Configuration')
    st.caption(
        'Conversion probability falls as factor rate rises (price elasticity). '
        'Default risk rises as advance size exceeds the P10 floor. '
        'Darker green = higher expected profit.'
    )

    pivot = sel_grid.pivot_table(
        values='exp_profit', index='factor_rate', columns='advance_rate', aggfunc='first'
    )

    fig_heat = go.Figure(data=go.Heatmap(
        z=pivot.values,
        x=[fmt_pct(v) for v in pivot.columns],
        y=[fmt_pct(v) for v in pivot.index],
        colorscale='RdYlGn',
        zmid=0,
        text=[[fmt_dollar(v) for v in row] for row in pivot.values],
        texttemplate='%{text}',
        textfont=dict(size=10),
        colorbar=dict(title='Expected<br>Profit ($)'),
        hovertemplate='Advance rate: %{x}<br>Factor rate: %{y}<br>Expected profit: %{text}<extra></extra>',
    ))
    fig_heat.update_layout(
        xaxis_title='Advance Rate (% of P10 × 6 months)',
        yaxis_title='Factor Rate',
        height=380, margin=dict(t=20, b=40),
    )
    st.plotly_chart(fig_heat, use_container_width=True)

    st.markdown('### Conversion vs. Default Risk')

    fig_sc = px.scatter(
        sel_grid,
        x='default_prob', y='conv_prob',
        size='exp_profit', color='exp_profit',
        color_continuous_scale='RdYlGn',
        size_max=28,
        hover_data={
            'advance_rate': ':.0%',
            'factor_rate':  ':.0%',
            'exp_profit':   ':,.0f',
            'advance_amount':':.0f',
        },
        labels={
            'default_prob': 'Default Probability',
            'conv_prob':    'Conversion Probability',
            'exp_profit':   'Expected Profit ($)',
        },
    )

    # Star = optimal offer
    best = sel_grid.loc[sel_grid['exp_profit'].idxmax()]
    fig_sc.add_trace(go.Scatter(
        x=[best['default_prob']], y=[best['conv_prob']],
        mode='markers',
        marker=dict(symbol='star', size=24, color='navy'),
        name=f'Optimal  AR={fmt_pct(best["advance_rate"])}  FR={fmt_pct(best["factor_rate"])}',
        hovertemplate=(
            f'Optimal config<br>'
            f'Advance: {fmt_dollar(best["advance_amount"])}<br>'
            f'Fee: {fmt_pct(best["factor_rate"])} factor rate<br>'
            f'Expected profit: {fmt_dollar(best["exp_profit"])}<extra></extra>'
        ),
    ))
    fig_sc.update_xaxes(tickformat='.0%', title='Default Probability')
    fig_sc.update_yaxes(tickformat='.0%', title='Conversion Probability')
    fig_sc.update_layout(height=400, margin=dict(t=20))
    st.plotly_chart(fig_sc, use_container_width=True)

# ─────────────────────────────────────────────────────────────────────────────
# TAB 3 — RISK MONITORING
# ─────────────────────────────────────────────────────────────────────────────
with tab3:
    st.markdown('### Post-Issuance Revenue Monitor')
    st.caption(
        'Simulate the current month\'s revenue and see how the alert system responds. '
        'Drag the slider to model stress scenarios.'
    )

    hist_for_slider = forecaster.get_history(sel.merchant_id, sel.store_id, last_n=24)
    slider_min = max(0, int(hist_for_slider.min() * 0.50))
    slider_max = int(hist_for_slider.max() * 1.30)
    slider_def = int(sel.p50)

    current_rev = st.slider(
        'Current month revenue ($)',
        min_value=slider_min,
        max_value=slider_max,
        value=slider_def,
        step=max(500, (slider_max - slider_min) // 100),
        format='$%d',
    )

    alert_status = classify_alert(current_rev, sel.p10, sel.p50)
    alert_color  = ALERT_COLORS[alert_status]

    a1, a2, a3 = st.columns([1, 2, 2])
    with a1:
        st.markdown(
            f'<div style="background:{alert_color};color:white;padding:16px 24px;'
            f'border-radius:8px;text-align:center;font-size:1.4em;font-weight:bold">'
            f'{alert_status}</div>',
            unsafe_allow_html=True,
        )
    with a2:
        st.metric('Current Revenue', fmt_dollar(current_rev))
        st.metric('P50 Forecast',    fmt_dollar(sel.p50))
    with a3:
        st.metric('P10 Floor',       fmt_dollar(sel.p10))
        st.metric('% of P50',        fmt_pct(current_rev / sel.p50 if sel.p50 > 0 else 0))

    # Alert explanation
    if alert_status == 'GREEN':
        st.success('Revenue is tracking at or above forecast. No action required.')
    elif alert_status == 'YELLOW':
        st.warning(
            f'Revenue is below 90% of P50 but above the P10 floor. '
            f'Monitor next month before adjusting pricing.'
        )
    else:
        st.error(
            f'Revenue has fallen below the P10 floor ({fmt_dollar(sel.p10)}). '
            f'Recommend repricing review immediately.'
        )

    st.markdown('---')

    # Repricing recommendation
    alert_history_demo = ['GREEN', 'GREEN', 'YELLOW', alert_status]
    reprice_result = monitor.reprice(sel_offer.factor_rate, alert_history_demo)

    r1, r2, r3 = st.columns(3)
    r1.metric('Current Factor Rate',   fmt_pct(sel_offer.factor_rate))
    r2.metric('Suggested Factor Rate', fmt_pct(reprice_result['suggested_rate']))
    delta_pct = reprice_result['adjustment']
    r3.metric(
        'Adjustment',
        f'{delta_pct:+.0%}' if delta_pct != 0 else 'No change',
        delta=f'{delta_pct:+.1%}' if delta_pct != 0 else None,
    )
    st.caption('Reason: ' + '  ·  '.join(reprice_result['reasons']))

    st.markdown('---')
    st.markdown('### Revenue History vs Thresholds')

    hist_rev_all    = forecaster.get_history(sel.merchant_id, sel.store_id, last_n=12)
    hist_labels_all = forecaster.get_period_labels(sel.merchant_id, sel.store_id, last_n=12)
    x_hist_all = list(range(len(hist_rev_all)))
    x_cur      = len(hist_rev_all)

    fig_bar = go.Figure()

    # Historical bars colored by alert
    bar_colors = [
        ALERT_COLORS[classify_alert(r, sel.p10, sel.p50)]
        for r in hist_rev_all
    ]
    fig_bar.add_trace(go.Bar(
        x=hist_labels_all, y=hist_rev_all.tolist(),
        marker_color=bar_colors,
        name='Historical Revenue',
        hovertemplate='%{x}<br>$%{y:,.0f}<extra></extra>',
    ))

    # Current month bar
    fig_bar.add_trace(go.Bar(
        x=['Current month'], y=[current_rev],
        marker_color=alert_color,
        marker_line=dict(color='black', width=2),
        name='Current month',
        hovertemplate=f'Current month<br>${current_rev:,.0f}<extra></extra>',
    ))

    # Threshold lines
    all_x = hist_labels_all + ['Current month']
    fig_bar.add_hline(y=sel.p50, line_dash='dot',  line_color='steelblue',
                      annotation_text=f'P50 {fmt_dollar(sel.p50)}',
                      annotation_position='top right')
    fig_bar.add_hline(y=sel.p10, line_dash='dash', line_color='gray',
                      annotation_text=f'P10 {fmt_dollar(sel.p10)}',
                      annotation_position='bottom right')

    fig_bar.update_yaxes(tickprefix='$', tickformat=',.0f')
    fig_bar.update_xaxes(tickangle=-45)
    fig_bar.update_layout(
        height=380, bargap=0.2,
        legend=dict(orientation='h', yanchor='bottom', y=1.02),
        margin=dict(t=20, b=80),
        showlegend=True,
    )
    st.plotly_chart(fig_bar, use_container_width=True)

    with st.expander('Alert color guide'):
        for status, color in ALERT_COLORS.items():
            thresholds = {
                'GREEN':  '≥ 90% of P50 — normal operation',
                'YELLOW': '≥ P10 floor, < 90% of P50 — watch closely',
                'RED':    '< P10 floor — below worst-case forecast; reprice review',
            }
            st.markdown(
                f'<span style="background:{color};color:white;padding:2px 10px;'
                f'border-radius:4px">{status}</span>  {thresholds[status]}',
                unsafe_allow_html=True,
            )

# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown('---')
st.caption(
    'Data: ~1.15M real transactions from 3 merchant types (sandwich, sushi, coffee).  '
    'Forecasting: quantile regression (P10/P50/P90) with seasonal naive fallback.  '
    'Offer sizing: P10-anchored advance × risk-tier factor rate.'
)
