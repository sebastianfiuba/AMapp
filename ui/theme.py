import streamlit as st


def apply_theme() -> None:
    st.markdown(
        """
        <style>
        :root {
            --ink: #17212b;
            --muted: #66737f;
            --line: #dce4e8;
            --paper: #f6f8f7;
            --panel: #ffffff;
            --iv: #0c7285;
            --track: #bd7b19;
            --ztc: #c34d46;
        }
        .stApp { background: var(--paper); color: var(--ink); }
        [data-testid="stHeader"] { background: rgba(246, 248, 247, .86); }
        [data-testid="stSidebar"] { background: #17212b; border-right: 1px solid #2c3a45; }
        [data-testid="stSidebar"] * { color: #edf4f5; }
        [data-testid="stSidebar"] [data-testid="stRadio"] label { border-radius: 8px; padding: .35rem .55rem; }
        [data-testid="stSidebar"] [data-testid="stRadio"] label:hover { background: #263743; }
        h1 { letter-spacing: -.02em; color: var(--ink); font-weight: 750; }
        h2, h3 { color: var(--ink); font-weight: 700; }
        [data-testid="stCaptionContainer"] { color: var(--muted); }
        [data-testid="stMetric"] { background: var(--panel); border: 1px solid var(--line); border-radius: 10px; padding: .8rem .9rem; box-shadow: 0 2px 10px rgba(23, 33, 43, .04); }
        [data-testid="stMetricLabel"] { color: var(--muted); }
        [data-testid="stMetricValue"] { color: var(--ink); }
        [data-baseweb="tab-list"] { gap: .35rem; border-bottom: 1px solid var(--line); }
        [data-baseweb="tab"] { color: var(--muted); padding: .7rem 1rem; }
        [aria-selected="true"][data-baseweb="tab"] { color: var(--iv); border-bottom-color: var(--iv); }
        [data-testid="stDataFrame"] { border: 1px solid var(--line); border-radius: 8px; overflow: hidden; }
        .section-banner { border-left: 5px solid var(--iv); background: var(--panel); border-radius: 0 10px 10px 0; padding: 1rem 1.2rem; margin: .2rem 0 1.2rem; box-shadow: 0 2px 10px rgba(23, 33, 43, .04); }
        .section-banner.track { border-left-color: var(--track); }
        .section-banner.ztc { border-left-color: var(--ztc); }
        .section-kicker { color: var(--muted); font-size: .78rem; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; }
        .section-title { color: var(--ink); font-size: 1.45rem; font-weight: 750; margin-top: .2rem; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def banner(kicker: str, title: str, description: str, tone: str = "") -> None:
    st.markdown(
        f'<div class="section-banner {tone}"><div class="section-kicker">{kicker}</div><div class="section-title">{title}</div><div>{description}</div></div>',
        unsafe_allow_html=True,
    )