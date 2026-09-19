import streamlit as st


def apply_theme() -> None:
    st.markdown(
        """
        <style>
        :root {
            --ink: #17212b;
            --muted: #66737f;
            --line: #dce4e8;
            --paper: #0b0f12;
            --panel: #141a1f;
            --iv: #0c7285;
            --track: #bd7b19;
            --ztc: #c34d46;
        }
        .stApp { background: var(--paper); color: #ffffff; }
        [data-testid="stHeader"] { background: rgba(11, 15, 18, .92); }
        [data-testid="stSidebar"] { background: #17212b; border-right: 1px solid #2c3a45; }
        [data-testid="stSidebar"] * { color: #edf4f5; }
        [data-testid="stSidebar"] [data-testid="stRadio"] label { border-radius: 8px; padding: .35rem .55rem; }
        [data-testid="stSidebar"] [data-testid="stRadio"] label:hover { background: #263743; }
        h1, h2, h3 { letter-spacing: 0; color: #ffffff; font-weight: 750; }
        [data-testid="stCaptionContainer"] { color: #d7e3e6; }
        [data-testid="stMarkdownContainer"], [data-testid="stMarkdownContainer"] p { color: #ffffff; }
        [data-testid="stSidebar"] [data-testid="stMarkdownContainer"], [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p { color: #edf4f5; }
        [data-testid="stMetric"] { background: var(--panel); border: 1px solid #5d737b; border-radius: 10px; padding: .8rem .9rem; }
        [data-testid="stMetricLabel"], [data-testid="stMetricValue"] { color: #ffffff; }
        [data-baseweb="tab-list"] { gap: .35rem; border-bottom: 1px solid var(--line); }
        [data-baseweb="tab"] { color: #d7e3e6; padding: .7rem 1rem; }
        [aria-selected="true"][data-baseweb="tab"] { color: #7de3ef; border-bottom-color: #7de3ef; }
        [data-testid="stSelectbox"] label, [data-testid="stMultiSelect"] label, [data-testid="stNumberInput"] label, [data-testid="stCheckbox"] label, [data-testid="stToggle"] label, [data-testid="stTextInput"] label, [data-testid="stTextArea"] label, [data-testid="stFileUploader"] label { color: #ffffff; font-weight: 650; }
        [data-baseweb="select"] > div, [data-baseweb="input"] > div { min-height: 2.65rem; border-radius: 8px; border-color: #5d737b; background: #141a1f; color: #ffffff; }
        [data-baseweb="tag"] { background: #075866; color: #ffffff; border-radius: 999px; }
        [data-baseweb="select"] input, [data-baseweb="select"] span { color: #ffffff; }
        [data-baseweb="popover"] [role="option"], [data-baseweb="popover"] [role="listbox"] { background: #141a1f; color: #ffffff; }
        [data-baseweb="popover"] [role="option"]:hover { background: #075866; color: #ffffff; }
        [data-testid="stButton"] button, [data-testid="stDownloadButton"] button, [data-testid="stFormSubmitButton"] button { min-height: 2.65rem; border-radius: 8px; font-weight: 700; color: #ffffff; background: #000000; border: 1px solid #ffffff; }
        [data-testid="stButton"] button:hover, [data-testid="stDownloadButton"] button:hover, [data-testid="stFormSubmitButton"] button:hover { color: #000000; border-color: #ffffff; background: #ffffff; }
        [data-testid="stButton"] button[kind="primary"], [data-testid="stFormSubmitButton"] button[kind="primary"] { color: #ffffff; background: #000000; border-color: #7de3ef; }
        [data-testid="stButton"] button[kind="primary"]:hover, [data-testid="stFormSubmitButton"] button[kind="primary"]:hover { color: #000000; background: #7de3ef; }
        [data-testid="stDownloadButton"] button { color: #ffffff; border-color: #7de3ef; background: #000000; }
        [data-testid="stDownloadButton"] button:hover { color: #000000; background: #7de3ef; }
        [data-testid="stButton"] button:disabled, [data-testid="stDownloadButton"] button:disabled, [data-testid="stFormSubmitButton"] button:disabled { color: #9aabb0; background: #20282d; border-color: #5d737b; }
        [data-testid="stDataFrame"], [data-testid="stDataEditor"] { border: 1px solid #5d737b; border-radius: 8px; overflow: hidden; }
        .section-banner { border-left: 5px solid var(--iv); background: #141a1f; border-radius: 0 10px 10px 0; padding: 1rem 1.2rem; margin: .2rem 0 1.2rem; }
        .section-banner.track { border-left-color: var(--track); }
        .section-banner.ztc { border-left-color: var(--ztc); }
        .section-kicker { color: #7de3ef; font-size: .78rem; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; }
        .section-title { color: #ffffff; font-size: 1.45rem; font-weight: 750; margin-top: .2rem; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def banner(kicker: str, title: str, description: str, tone: str = "") -> None:
    st.markdown(
        f'<div class="section-banner {tone}"><div class="section-kicker">{kicker}</div><div class="section-title">{title}</div><div>{description}</div></div>',
        unsafe_allow_html=True,
    )