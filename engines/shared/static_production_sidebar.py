"""Lightweight, visual-only copy of the fixed Production sidebar.

This module intentionally has no imports from the Production engine, portfolio
stores, market-data clients, or calculation modules. Keep it static and cheap:
research dashboards only need the familiar visual reference panel.
"""


def render_static_production_sidebar(st):
    """Render the non-interactive Production reference panel in research modes."""
    st.markdown(
        """
        <style>
        [data-testid="stSidebar"] .btc-static-production {
            color: #f5f9fc;
            font-family: inherit;
        }
        .btc-static-production .btc-panel-heading {
            color: #f5f9fc;
            font-size: 1.05rem;
            font-weight: 750;
            margin: .35rem 0 .65rem;
        }
        .btc-static-production .btc-panel-card {
            background: #0a2133;
            border: 1px solid #174c6b;
            border-radius: 10px;
            padding: .58rem .7rem;
            margin: .35rem 0;
            color: #e8f2f8;
            font-size: .88rem;
            line-height: 1.35;
        }
        .btc-static-production .btc-panel-card strong {
            color: #f7fbff;
            display: block;
            font-weight: 700;
            margin-bottom: .12rem;
        }
        .btc-static-production .btc-panel-note {
            color: #9fb8c9;
            font-size: .76rem;
            line-height: 1.4;
            margin-top: .65rem;
        }
        .btc-static-production .btc-panel-rule {
            border: 0;
            border-top: 1px solid #174c6b;
            margin: .8rem 0;
        }
        </style>
        <div class="btc-static-production">
          <div class="btc-panel-heading">Production</div>
          <div class="btc-panel-card"><strong>DCA Today</strong>Current signal and deployment view</div>
          <div class="btc-panel-card"><strong>DCA Backtest</strong>Historical strategy evaluation</div>
          <div class="btc-panel-card"><strong>My Portfolio</strong>Portfolio and transaction records</div>
          <hr class="btc-panel-rule">
          <div class="btc-panel-heading">V5.8.2 · Production</div>
          <div class="btc-panel-card"><strong>Smart DCA</strong>Risk-based position sizing</div>
          <div class="btc-panel-card"><strong>Multiplier curve</strong>Configured Production curve · fixed reference</div>
          <div class="btc-panel-note">Static reference panel on research pages. No Production controls, portfolio data, market feeds, or trade calculations are loaded here.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
