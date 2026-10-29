"""
Knowvia — editorial Wikipedia research workspace (Streamlit).

Run:  python3 -m streamlit run curio_app.py

The backend (Wikipedia search + answer generation) lives in backend.py and is imported below:
    search_and_answer(question, history) -> dict(answer=str, sources=list[dict])
Each source dict contains: title, url (a https://en.wikipedia.org/wiki/... link), excerpt.
Setup (API key, database location) is described in README.md.

Saved chats are kept in st.session_state and also written to
curio_chats.json next to this file, so they survive an app restart.
"""
import copy
import html
import json
import random
import re
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote, unquote, urlencode, urlparse
from urllib.request import Request, urlopen

import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="Knowvia — Research Workspace", page_icon="✳", layout="wide")

# ==========================================================================
# BACKEND  (real Wikipedia search + answer pipeline - see backend.py)
# ==========================================================================
from backend import check_configuration, get_db_stats, search_and_answer  # noqa: E402


# ==========================================================================
# UI HELPERS  (presentation only - no backend logic in here)
# ==========================================================================

# --------------------------------------------------------------------------
# Icons (simple line icons, inherit colour via currentColor)
# --------------------------------------------------------------------------
_ICONS = {
    "book": '<path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/>',
    "search": '<circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>',
    "cpu": '<rect x="4" y="4" width="16" height="16" rx="2"/><rect x="9" y="9" width="6" height="6"/><line x1="9" y1="1" x2="9" y2="4"/><line x1="15" y1="1" x2="15" y2="4"/><line x1="9" y1="20" x2="9" y2="23"/><line x1="15" y1="20" x2="15" y2="23"/><line x1="20" y1="9" x2="23" y2="9"/><line x1="20" y1="14" x2="23" y2="14"/><line x1="1" y1="9" x2="4" y2="9"/><line x1="1" y1="14" x2="4" y2="14"/>',
    "ext": '<path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/>',
    "globe": '<circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>',
    "alert": '<circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>',
}


def _icon(name: str, size: int = 16) -> str:
    return (f'<svg class="wm-i" width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" '
            f'stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">'
            f'{_ICONS[name]}</svg>')


def _logo(size: int) -> str:
    return (f'<svg width="{size}" height="{size}" viewBox="0 0 36 36" class="wm-logo-svg">'
            f'<rect x="0.5" y="0.5" width="35" height="35" rx="6" fill="#78836A"/>'
            f'<g transform="translate(8.5 8.5) scale(0.79)" fill="none" stroke="#FCFAF6" stroke-width="1.6" '
            f'stroke-linecap="round" stroke-linejoin="round">{_ICONS["book"]}</g></svg>')


# --------------------------------------------------------------------------
# Theme  (single source of truth: st.session_state["wm_theme"])
# --------------------------------------------------------------------------
THEMES = ("beige", "light", "dark")


def get_theme() -> str:
    if "wm_theme" not in st.session_state:
        qp = st.query_params.get("theme", "beige")
        st.session_state["wm_theme"] = qp if qp in THEMES else "beige"
    return st.session_state["wm_theme"]


def theme_toggle(key: str = "wm_theme_toggle"):
    """Cycle through the three appearance themes with one icon button."""
    current = get_theme()
    if st.button(
        "Change appearance",
        key=key,
        help=f"Current appearance: {current.title()}. Click to change.",
    ):
        next_theme = THEMES[(THEMES.index(current) + 1) % len(THEMES)]
        st.session_state["wm_theme"] = next_theme
        try:
            st.query_params["theme"] = next_theme
        except Exception:
            pass
        st.rerun()


_VARS = {
    "beige": """
      --page:#E9DFCF; --bg:#F1E8DA; --sidebar:#E8DECE; --card:#F7F0E5; --card2:#EAE0D0; --card3:#F2E9DC; --input:#E8DECE;
      --border:#D3C6B3; --border-strong:#C4B6A1; --grid:rgba(196,182,161,.32);
      --text:#292923; --muted:#716B60; --accent:#7B866D; --accent-strong:#59654D; --accent-ink:#59654D;
      --accent-soft:rgba(123,134,109,.14); --sage:#7B866D; --sage-soft:rgba(123,134,109,.16);
      --display-accent:#6D795F; --shadow:0 1px 2px rgba(41,41,35,.04); --on-accent:#FCFAF6;
    """,
    "light": """
      --page:#F3F1EC; --bg:#FAF9F6; --sidebar:#F4F2ED; --card:#FFFFFF; --card2:#F4F2ED; --card3:#F8F7F3; --input:#FFFDFC;
      --border:#E5E1D8; --border-strong:#D8D3C8; --grid:rgba(216,211,200,.3);
      --text:#292923; --muted:#77736B; --accent:#7B866D; --accent-strong:#59654D; --accent-ink:#59654D;
      --accent-soft:rgba(123,134,109,.12); --sage:#7B866D; --sage-soft:rgba(123,134,109,.13);
      --display-accent:#6D795F; --shadow:0 1px 2px rgba(41,41,35,.035); --on-accent:#FFFFFF;
    """,
    "dark": """
      --page:#171916; --bg:#1D201C; --sidebar:#191B18; --card:#242722; --card2:#292C26; --card3:#222520; --input:#252923;
      --display-accent:#A9B69A; --border:#363A32; --border-strong:#464B40; --grid:rgba(70,75,64,.28);
      --text:#EAE9E2; --muted:#AAA99F; --accent:#849477; --accent-strong:#9BAA8B; --accent-ink:#B8C5A9;
      --accent-soft:rgba(151,169,132,.14); --sage:#A4B395; --sage-soft:rgba(151,169,132,.15);
      --shadow:0 1px 2px rgba(0,0,0,.18); --on-accent:#171916;
    """,
}

_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,400;0,9..144,500;0,9..144,600;1,9..144,400;1,9..144,500&family=Inter:wght@400;500;600&display=swap');
:root{ /*VARS*/ --toggle-icon:url("/*TOGGLE*/"); color-scheme:/*SCHEME*/; --serif:'Fraunces',Georgia,'Times New Roman',serif; --sans:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif; --r:7px; }
.stApp, .stApp p, .stApp li, .stApp span, .stApp label, .stApp h1, .stApp h2, .stApp h3, .stApp h4,
[data-testid="stMarkdownContainer"]{ color:var(--text); }
html, body, .stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"]{ background-color:var(--page) !important; font-family:var(--sans); }
.stApp{ background-image:linear-gradient(to right, var(--grid) 1px, transparent 1px); background-size:140px 100%; background-position:center top; }
[data-testid="stHeader"]{ background:transparent; }
[data-testid="stIconMaterial"], [data-testid="stHeader"] button{ color:var(--muted); }
[data-testid="stTooltipContent"]{ background:var(--card); color:var(--text); border:1px solid var(--border-strong); }
.block-container{ max-width:1240px; margin:0 auto; padding:2.6rem 2.6rem 9rem; min-height:calc(100vh + 4.5rem); background:var(--bg);
  border-left:1px solid var(--border); border-right:1px solid var(--border); }
[data-testid="stVerticalBlock"]{ gap:.75rem; }
* { overflow-wrap:anywhere; }
a{ color:var(--accent-ink); }
.wm-i{ flex:0 0 auto; vertical-align:-3px; }
.wm-hr{ height:1px; background:var(--border); margin:.1rem 0 .3rem; }

/* ---------- Sidebar ---------- */
[data-testid="stSidebar"]{ background:var(--sidebar) !important; border-right:1px solid var(--border); }
[data-testid="stSidebar"] [data-testid="stSidebarContent"]{ padding-top:.4rem; }
[data-testid="stSidebar"] [data-testid="stVerticalBlock"]{ gap:.6rem; }
.wm-brand{ display:flex; gap:.7rem; align-items:center; margin:.3rem 0 .9rem; }
.wm-brand b{ font-family:var(--serif); font-size:1.18rem; font-weight:500; display:block; line-height:1.1; letter-spacing:-.01em; }
.wm-brand small{ color:var(--muted); font-size:.7rem; letter-spacing:.02em; }
.wm-section-title{ display:flex; justify-content:space-between; align-items:baseline; font-size:.64rem; font-weight:600;
  letter-spacing:.15em; text-transform:uppercase; color:var(--muted);
  margin:.9rem 0 .2rem; padding-top:1rem; border-top:1px solid var(--border-strong); }
.wm-section-title span{ letter-spacing:.05em; color:var(--accent-ink); }
.wm-hist-empty{ color:var(--muted); font-size:.8rem; font-style:italic; margin:.2rem 0; }
.wm-sys{ font-size:.78rem; }
.wm-sys > div{ display:flex; gap:.6rem; align-items:flex-start; margin:.55rem 0; }
.wm-sys .k{ display:block; font-size:.62rem; text-transform:uppercase; letter-spacing:.12em; color:var(--muted); }
.wm-sys .v{ display:block; color:var(--text); font-weight:500; font-size:.78rem; }
.wm-sys .wm-i{ color:var(--sage); margin-top:2px; }
[data-testid="stSidebar"] [data-testid="stVerticalBlock"]:has(.st-key-sys_box){ min-height:calc(100vh - 5rem); }
.st-key-sys_box, [data-testid="stSidebar"] :has(> .st-key-sys_box){ margin-top:auto; }
.st-key-sys_box .wm-section-title{ margin-top:.5rem; }

/* Saved chats list */
.st-key-chatlist{ gap:.15rem !important; border:0 !important; padding:0 !important; }
[class*="st-key-chatsel_"] button, [class*="st-key-chatact_"] button{ background:transparent; border:1px solid transparent;
  border-radius:var(--r); justify-content:flex-start; text-align:left; min-height:2.1rem; padding:.3rem .65rem; font-weight:400; }
[class*="st-key-chatsel_"] button > div, [class*="st-key-chatact_"] button > div{ justify-content:flex-start; width:100%; }
[class*="st-key-chatsel_"] button p, [class*="st-key-chatact_"] button p{ width:100%; text-align:left; font-size:.82rem; font-weight:inherit;
  white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
[class*="st-key-chatsel_"] button:hover{ background:var(--accent-soft); border-color:transparent; }
[class*="st-key-chatact_"] button{ background:var(--card); border-color:var(--border-strong); border-left:2px solid var(--accent); font-weight:500; }
[class*="st-key-chatact_"] button:hover{ background:var(--card); border-color:var(--border-strong); border-left-color:var(--accent); }
/* Tiny, unobtrusive × controls for deleting saved chats */
[class*="st-key-deletechat_"] button{
  display:flex; align-items:center; justify-content:center;
  width:1.45rem; min-width:1.45rem; height:1.45rem; min-height:1.45rem;
  padding:0 !important; margin:.3rem auto 0;
  border:0 !important; border-radius:50% !important;
  background:transparent !important; box-shadow:none !important;
  color:var(--muted) !important; font-size:1rem !important; font-weight:400 !important;
  line-height:1 !important;
}
[class*="st-key-deletechat_"] button p{
  padding:0 !important; margin:0 !important; font-size:1rem !important;
  line-height:1 !important; color:inherit !important;
}
[class*="st-key-deletechat_"] button:hover{
  background:var(--accent-soft) !important; color:var(--accent-ink) !important;
  border:0 !important;
}
/* "Delete this saved chat?" confirmation: filled olive Delete + quiet outlined Cancel (all themes via variables) */
[class*="st-key-confirmdelete_"] button, [class*="st-key-canceldelete_"] button{
  min-height:2.1rem; padding:.25rem .6rem; border-radius:var(--r); box-shadow:none !important;
  font-size:.8rem; font-weight:500; letter-spacing:.01em;
  transition:background .18s, border-color .18s, color .18s;
}
[class*="st-key-confirmdelete_"] button p, [class*="st-key-canceldelete_"] button p{ font-size:.8rem; font-weight:500; }
[class*="st-key-confirmdelete_"] button{ background:var(--accent) !important; border:1px solid var(--accent) !important; }
[class*="st-key-confirmdelete_"] button p{ color:var(--on-accent) !important; }
[class*="st-key-confirmdelete_"] button:hover{ background:var(--accent-strong) !important; border-color:var(--accent-strong) !important; }
[class*="st-key-canceldelete_"] button{ background:transparent !important; border:1px solid var(--border-strong) !important; }
[class*="st-key-canceldelete_"] button p{ color:var(--muted) !important; }
[class*="st-key-canceldelete_"] button:hover{ background:var(--accent-soft) !important; border-color:var(--accent) !important; }
[class*="st-key-canceldelete_"] button:hover p{ color:var(--text) !important; }

/* ---------- Article reader (right-hand panel) ---------- */
.st-key-reader{ background:var(--card); border:1px solid var(--border-strong); border-left:2px solid var(--accent);
  border-radius:var(--r); padding:1.1rem 1.2rem 1.2rem; box-shadow:var(--shadow); gap:.8rem !important; }
.wm-reader-title{ font-family:var(--serif); font-size:1.6rem; font-weight:500; letter-spacing:-.02em; line-height:1.15; color:var(--text); }
.st-key-reader iframe{ border:1px solid var(--border) !important; border-radius:var(--r); background:var(--card3); }
.st-key-close_article button{ min-height:2rem; padding:.2rem .7rem; background:transparent; border-color:var(--border-strong); }
.st-key-close_article button p{ font-size:.78rem; color:var(--muted); }
.st-key-close_article button:hover p{ color:var(--text); }
.st-key-reader a[data-testid^="stBaseLinkButton"], .st-key-reader [data-testid="stLinkButton"] a{
  display:flex; align-items:center; justify-content:center; min-height:2.3rem; border-radius:var(--r);
  background:transparent; border:1px solid var(--border-strong); color:var(--text); text-decoration:none;
  font-size:.82rem; font-weight:500; transition:border-color .18s, background .18s; }
.st-key-reader a[data-testid^="stBaseLinkButton"] p, .st-key-reader [data-testid="stLinkButton"] a p{ color:inherit; font-size:.82rem; }
.st-key-reader a[data-testid^="stBaseLinkButton"]:hover, .st-key-reader [data-testid="stLinkButton"] a:hover{
  border-color:var(--accent); background:var(--accent-soft); }

/* ---------- Polish & extras ---------- */
:root{ --book-icon:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M4 19.5A2.5 2.5 0 0 1 6.5 17H20'/%3E%3Cpath d='M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z'/%3E%3C/svg%3E"); }
/* hide Streamlit's own Deploy button and menu */
[data-testid="stAppDeployButton"], [data-testid="stDeployButton"], [data-testid="stMainMenu"], [data-testid="stToolbarActions"]{ display:none !important; }
/* answers use the Knowvia book mark as their avatar */
[data-testid="stChatMessageAvatarAssistant"]{ display:flex; align-items:center; justify-content:center; }
[data-testid="stChatMessageAvatarAssistant"] > *{ display:none; }
[data-testid="stChatMessageAvatarAssistant"]::after{ content:""; width:62%; height:62%; background:#fff;
  -webkit-mask:var(--book-icon) center/contain no-repeat; mask:var(--book-icon) center/contain no-repeat; }
/* keep chat text tight against its avatar instead of floating in the middle of the card */
[data-testid="stChatMessage"]{ justify-content:flex-start; }
[data-testid="stChatMessageContent"]{ flex:1 1 0; min-width:0; margin:0; }
/* hero fade-in */
.wm-hero > *{ animation:wmIn .7s ease both; }
.wm-hero > *:nth-child(2){ animation-delay:.08s; } .wm-hero > *:nth-child(3){ animation-delay:.16s; } .wm-hero > *:nth-child(4){ animation-delay:.24s; }
@media (prefers-reduced-motion:reduce){ .wm-hero > *{ animation:none; } }
/* source cards */
[class*="st-key-srcbox_"]{ background:var(--card3); border:1px solid var(--border); border-radius:var(--r);
  padding:.8rem .95rem; gap:.3rem !important; transition:border-color .18s; }
[class*="st-key-srcbox_"]:hover{ border-color:var(--accent); }
.wm-src-head{ display:flex; gap:.75rem; align-items:baseline; }
.wm-src-num{ font-family:var(--serif); font-size:1.5rem; line-height:1; color:var(--accent-ink); }
.wm-src-ttl{ font-weight:600; font-size:.95rem; line-height:1.3; }
.wm-thumb{ display:block; width:100%; aspect-ratio:1; object-fit:cover; border-radius:5px; border:1px solid var(--border); }
[class*="st-key-read_article_"] button p{ white-space:nowrap; }
/* follow-up chips under an answer share the suggestion-chip look */
[class*="st-key-related_box_"]{ flex-direction:row !important; flex-wrap:wrap; align-items:center; gap:.4rem .45rem !important; margin-top:.6rem; }
[class*="st-key-related_box_"] > *{ width:auto !important; flex:0 0 auto; min-width:0; }
[class*="st-key-related_"] button{ background:transparent; border:1px solid var(--border-strong); border-radius:var(--r);
  padding:.25rem .75rem; min-height:2rem; line-height:1.3; }
[class*="st-key-related_"] button p{ font-size:.82rem; font-weight:400; color:var(--muted); }
[class*="st-key-related_"] button:hover{ border-color:var(--accent); background:var(--accent-soft); }
[class*="st-key-related_"] button:hover p{ color:var(--accent-ink); }
/* quiet small action buttons */
[class*="st-key-dl_"] button{ min-height:2rem; background:transparent; padding:.2rem .8rem; }
[class*="st-key-dl_"] button p{ font-size:.78rem; color:var(--muted); }
[class*="st-key-dl_"] button:hover p{ color:var(--text); }
.st-key-reader_toggle button{ min-height:2.3rem; background:transparent; }
.st-key-reader_toggle button p{ font-size:.82rem; }
/* "Today on Wikipedia" card on the landing page */
.st-key-today_card{ background:var(--card); border:1px solid var(--border-strong); border-left:2px solid var(--accent);
  border-radius:var(--r); padding:1.1rem 1.3rem; box-shadow:var(--shadow); gap:.5rem !important; margin-top:1rem; }
.wm-today-title{ font-family:var(--serif); font-size:1.5rem; font-weight:500; letter-spacing:-.02em; line-height:1.15; }
.wm-today-text{ color:var(--muted); font-size:.92rem; line-height:1.7; margin:.35rem 0 .2rem; }
/* reader: summary view, and the panel follows you while you scroll the answer */
.wm-reader-desc{ font-size:.66rem; font-weight:600; letter-spacing:.14em; text-transform:uppercase; color:var(--accent-ink); }
.wm-reader-img{ display:block; width:100%; max-height:230px; object-fit:cover; border-radius:var(--r);
  border:1px solid var(--border); margin:.5rem 0 .9rem; }
.wm-reader-extract{ font-family:var(--serif); font-size:1.08rem; line-height:1.75; }
[data-testid="stColumn"]:has(.st-key-reader), [data-testid="column"]:has(.st-key-reader){ position:sticky; top:3.75rem; align-self:flex-start; }

/* ---------- Buttons ---------- */
.stButton > button{ border-radius:var(--r); border:1px solid var(--border-strong);
  background:var(--card); color:var(--text); font-weight:500; font-size:.85rem; min-height:2.5rem; box-shadow:none;
  transition:border-color .18s, background .18s, color .18s, transform .18s; }
.stButton > button p{ color:inherit; }
.stButton > button:hover{ border-color:var(--accent); background:var(--accent-soft); color:var(--text); }
.stButton > button:focus-visible{ outline:2px solid var(--accent); outline-offset:2px; }
.st-key-new_chat button{ background:var(--accent) !important; border-color:var(--accent) !important; color:var(--on-accent) !important;
  font-weight:600; letter-spacing:.01em; min-height:2.7rem; }
.st-key-new_chat button:hover{ background:var(--accent-strong) !important; border-color:var(--accent-strong) !important; }
.st-key-new_chat button p{ color:var(--on-accent) !important; }
.st-key-wm_theme_toggle{ display:flex; justify-content:flex-end; }
.st-key-wm_theme_toggle button{ width:2.3rem; min-width:2.3rem; height:2.3rem; min-height:2.3rem; padding:0; border-radius:999px;
  background:transparent; border:1px solid var(--border-strong); cursor:pointer; }
.st-key-wm_theme_toggle button::before{ content:""; width:1.05rem; height:1.05rem; background-color:var(--muted);
  -webkit-mask:var(--toggle-icon) center/contain no-repeat; mask:var(--toggle-icon) center/contain no-repeat;
  transition:background-color .18s, transform .35s ease; }
.st-key-wm_theme_toggle button:hover{ border-color:var(--accent); background:var(--accent-soft); }
.st-key-wm_theme_toggle button:hover::before{ background-color:var(--accent-ink); transform:rotate(18deg); }
.st-key-wm_theme_toggle button:active::before{ transform:rotate(18deg) scale(.9); }
/* keep the text label for screen readers, hide it visually */
.st-key-wm_theme_toggle button > div{ position:absolute; width:1px; height:1px; margin:-1px; padding:0; overflow:hidden;
  clip:rect(0,0,0,0); white-space:nowrap; border:0; }
@media (prefers-reduced-motion:reduce){ .st-key-wm_theme_toggle button::before{ transition:none; } }

/* ---------- Nav / header ---------- */
.wm-nav{ display:flex; gap:.9rem; align-items:center; }
.wm-nav-name{ font-family:var(--serif); font-size:1.5rem; font-weight:500; letter-spacing:-.02em; line-height:1.05; }
.wm-nav-sub{ color:var(--muted); font-size:.68rem; font-weight:500; letter-spacing:.14em; text-transform:uppercase; margin-top:.3rem; }

/* ---------- Hero ---------- */
.wm-hero{ padding:1.4rem 0 1.5rem; }
.st-key-insights{ margin-top:2.6rem; }
.wm-eyebrow{ display:flex; gap:.6rem; align-items:center; font-size:.66rem; font-weight:600; letter-spacing:.16em;
  text-transform:uppercase; color:var(--accent-ink); }
.wm-eyebrow::before{ content:""; width:28px; height:1px; background:var(--accent); }
.wm-display{ font-family:var(--serif); font-size:clamp(2.6rem,9vw,5.4rem); font-weight:400; line-height:1.02;
  letter-spacing:-.04em; margin:.9rem 0 1.1rem; color:var(--text); }
.wm-display em{ font-style:italic; color:var(--display-accent); font-weight:400; letter-spacing:-.03em; }
.wm-lede{ max-width:38rem; color:var(--muted); font-size:1.04rem; line-height:1.7; margin:0; }
.wm-lede b{ color:var(--text); font-weight:500; }
.wm-hero-rule{ position:relative; height:1px; background:var(--border-strong); margin-top:2rem; }
.wm-hero-rule::before{ content:""; position:absolute; left:0; top:-1px; width:56px; height:3px; background:var(--accent); }
.wm-compact{ display:flex; justify-content:space-between; align-items:baseline; padding:.4rem 0 .2rem; gap:1rem; flex-wrap:wrap; }
.wm-compact .wm-display{ font-size:2rem; margin:0; letter-spacing:-.025em; white-space:normal; }
@media (min-width:640px){ .wm-hero .wm-display{ white-space:nowrap; } }
@media (max-width:640px){ .wm-hero{ padding-top:1rem; } .wm-hero-rule{ margin-top:1.4rem; } }

/* ---------- Section labels ---------- */
.wm-sec{ display:flex; gap:.8rem; align-items:center; margin:2.4rem 0 .4rem; }
.wm-sec .n{ font-family:var(--serif); font-size:.82rem; color:var(--accent-ink); }
.wm-sec .t{ font-size:.66rem; font-weight:600; letter-spacing:.16em; text-transform:uppercase; }
.wm-sec .line{ flex:1; height:1px; background:var(--border-strong); }
.wm-sec .a{ font-size:.72rem; color:var(--muted); text-align:right; }

/* ---------- Suggestions ---------- */
/* one slim row of chips that wraps on small screens */
.st-key-suggestions{ flex-direction:row !important; flex-wrap:wrap; align-items:center; gap:.4rem .45rem !important; }
.st-key-suggestions > *{ width:auto !important; flex:0 0 auto; min-width:0; }
.wm-chiplabel{ font-size:.62rem; font-weight:600; letter-spacing:.16em; text-transform:uppercase; color:var(--muted); margin-right:.2rem; }
[class*="st-key-sugg_"] button{ background:transparent; border:1px solid var(--border-strong); border-radius:var(--r);
  padding:.25rem .75rem; min-height:2rem; line-height:1.3; }
[class*="st-key-sugg_"] button p{ font-size:.82rem; font-weight:400; color:var(--muted); }
[class*="st-key-sugg_"] button:hover{ border-color:var(--accent); background:var(--accent-soft); }
[class*="st-key-sugg_"] button:hover p{ color:var(--accent-ink); }

/* ---------- Expanders / alerts ---------- */
[data-testid="stExpander"]{ background:var(--card); border:1px solid var(--border-strong) !important; border-radius:var(--r); box-shadow:var(--shadow); }
[data-testid="stExpander"] details, [data-testid="stExpander"] summary{ background:transparent; color:var(--text); }
[data-testid="stExpander"] summary{ padding:.7rem 1rem; border-radius:var(--r); transition:background .18s; }
[data-testid="stExpander"] summary:hover{ background:var(--accent-soft); }
[data-testid="stExpander"] summary p{ font-weight:600; font-size:.72rem; letter-spacing:.12em; text-transform:uppercase; }

/* ---------- Conversation ---------- */
[data-testid="stChatMessage"]{ background:var(--card); border:1px solid var(--border); border-left:2px solid var(--accent);
  border-radius:var(--r); padding:1.1rem 1.3rem; box-shadow:var(--shadow); animation:wmIn .35s ease both; }
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]){ background:var(--card2); border-left:1px solid var(--border);
  padding:.7rem 1.1rem; box-shadow:none; }
[data-testid="stChatMessageAvatarUser"]{ background:var(--card) !important; border:1px solid var(--border); color:var(--text) !important; }
[data-testid="stChatMessageAvatarAssistant"]{ background:var(--accent) !important; color:#fff !important; }
[data-testid="stChatMessageContent"]{ max-width:740px; }
@keyframes wmIn{ from{opacity:0; transform:translateY(6px);} to{opacity:1; transform:none;} }
@media (prefers-reduced-motion:reduce){ [data-testid="stChatMessage"]{ animation:none; } }
[data-testid="stChatMessage"] p, [data-testid="stChatMessage"] li{ line-height:1.8; font-size:.96rem; }
[data-testid="stChatMessage"] ul, [data-testid="stChatMessage"] ol{ padding-left:1.3rem; }
[data-testid="stChatMessage"] strong{ font-weight:600; }
[data-testid="stChatMessage"] h1, [data-testid="stChatMessage"] h2, [data-testid="stChatMessage"] h3{ font-family:var(--serif); font-weight:500; }
.wm-label{ display:flex; gap:.7rem; align-items:center; font-size:.64rem; font-weight:600; letter-spacing:.16em;
  text-transform:uppercase; color:var(--accent-ink); margin-bottom:.6rem; }
.wm-label::after{ content:""; flex:1; height:1px; background:var(--border); }

/* ---------- Citations ---------- */
a.wm-cite, span.wm-cite{ display:inline-block; min-width:1.1rem; text-align:center; font-size:.66rem; font-weight:600;
  padding:.03rem .35rem; margin:0 .1rem; border-radius:3px; background:var(--sage-soft); color:var(--text) !important;
  border:1px solid var(--sage); text-decoration:none; vertical-align:.12em; transition:background .15s, color .15s, border-color .15s; }
a.wm-cite:hover{ background:var(--accent-strong); border-color:var(--accent-strong); color:#fff !important; }

/* ---------- Sources ---------- */
.wm-src-title{ display:flex; gap:.7rem; align-items:center; font-size:.64rem; font-weight:600; letter-spacing:.16em;
  text-transform:uppercase; color:var(--muted); margin:1.4rem 0 .7rem; padding-top:1rem; border-top:1px solid var(--border-strong); }
.wm-src-title span{ color:var(--accent-ink); }
.wm-src-grid{ display:grid; grid-template-columns:repeat(auto-fit,minmax(260px,1fr)); gap:.7rem; }
.wm-src{ display:flex; gap:.9rem; background:var(--card3); border:1px solid var(--border); border-radius:var(--r);
  padding:.9rem 1rem; text-decoration:none !important; transition:border-color .18s, background .18s, transform .18s; }
a.wm-src:hover{ border-color:var(--accent); background:var(--accent-soft); transform:translateY(-1px); }
.wm-src .num{ font-family:var(--serif); font-size:1.7rem; font-weight:400; line-height:1; color:var(--accent-ink); min-width:1.5rem; }
.wm-src .body{ display:block; min-width:0; }
.wm-src .t{ display:block; color:var(--text); font-weight:600; font-size:.9rem; line-height:1.3; }
.wm-src .d{ display:block; color:var(--muted); font-size:.8rem; line-height:1.6; margin-top:.35rem; }
.wm-src .u{ display:flex; gap:.4rem; align-items:center; color:var(--sage); font-size:.66rem; font-weight:600;
  letter-spacing:.1em; text-transform:uppercase; margin-top:.6rem; }

/* ---------- Insights ---------- */
.wm-ins{ border:1px solid var(--border-strong); background:var(--card); border-radius:var(--r); padding:1.1rem 1.3rem; box-shadow:var(--shadow); }
.wm-ins-head{ display:flex; justify-content:space-between; align-items:baseline; gap:1rem; padding-bottom:.8rem; border-bottom:1px solid var(--border); margin-bottom:.4rem; }
.wm-ins-head .big{ font-family:var(--serif); font-size:2rem; line-height:1; letter-spacing:-.02em; }
.wm-ins-head .k{ display:block; font-size:.62rem; font-weight:600; letter-spacing:.14em; text-transform:uppercase; color:var(--muted); margin-top:.35rem; }
.wm-ins-head .a{ font-size:.74rem; color:var(--muted); text-align:right; }
.wm-bar{ display:grid; grid-template-columns:1.6rem minmax(0,1fr) minmax(70px,170px) 1.4rem; gap:.8rem; align-items:center; padding:.55rem 0; font-size:.82rem; }
.wm-bar .q{ font-family:var(--serif); color:var(--accent-ink); font-size:.8rem; }
.wm-bar .txt{ white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.wm-bar .track{ height:6px; background:var(--card2); border-radius:3px; overflow:hidden; display:block; }
.wm-bar .track i{ display:block; height:100%; background:var(--accent); border-radius:3px; }
.wm-bar .c{ text-align:right; color:var(--muted); font-variant-numeric:tabular-nums; }

/* ---------- Chat input (the single question input) ---------- */
/* st.chat_input is placed inside containers, so it flows inline with the page instead of floating at the bottom */
div[data-testid="stChatInput"]{ background:var(--input) !important; border:1px solid var(--border-strong) !important; border-radius:28px !important;
  box-shadow:var(--shadow) !important; outline:none !important; min-height:3.2rem; transition:border-color .18s, box-shadow .18s; }
div[data-testid="stChatInput"] div, div[data-testid="stChatInput"] [data-baseweb]{ background:transparent !important; border:0 !important;
  box-shadow:none !important; outline:none !important; }
div[data-testid="stChatInput"]:focus-within{ border-color:var(--accent) !important; box-shadow:0 0 0 3px var(--accent-soft) !important; }
div[data-testid="stChatInput"] textarea{ color:var(--text) !important; -webkit-text-fill-color:var(--text); caret-color:var(--accent-strong);
  font-size:1rem; background:transparent !important; box-shadow:none !important; outline:none !important; border:0 !important; }
div[data-testid="stChatInput"] textarea::placeholder{ color:var(--muted) !important; -webkit-text-fill-color:var(--muted); opacity:1; }
button[data-testid="stChatInputSubmitButton"]{ background:var(--accent) !important; border:0 !important; border-radius:999px !important; width:2.15rem; height:2.15rem; margin-right:.25rem; }
button[data-testid="stChatInputSubmitButton"]:hover{ background:var(--accent-strong) !important; }
button[data-testid="stChatInputSubmitButton"]:disabled{ opacity:.45; }
button[data-testid="stChatInputSubmitButton"] svg, button[data-testid="stChatInputSubmitButton"] [data-testid="stIconMaterial"]{ color:#fff !important; fill:#fff; }

/* ---------- States ---------- */
.wm-loading{ display:flex; gap:.7rem; align-items:center; color:var(--muted); font-size:.88rem; padding:.4rem 0; }
.wm-spin{ width:15px; height:15px; border-radius:50%; border:2px solid var(--border); border-top-color:var(--accent);
  animation:wmSpin .8s linear infinite; }
@keyframes wmSpin{ to{ transform:rotate(360deg);} }
.wm-msg{ display:flex; gap:.7rem; align-items:flex-start; border:1px solid var(--border); border-radius:var(--r);
  padding:.85rem 1rem; background:var(--card2); font-size:.9rem; line-height:1.6; }
.wm-msg .wm-i{ color:var(--sage); margin-top:2px; }
.wm-msg.err{ border-color:var(--accent); } .wm-msg.err .wm-i{ color:var(--accent-ink); }
.wm-foot{ display:flex; justify-content:space-between; gap:1rem; flex-wrap:wrap; margin-top:1.4rem; padding-top:1rem;
  border-top:1px solid var(--border-strong); font-size:.68rem; letter-spacing:.08em; text-transform:uppercase; color:var(--muted); }

 .wm-nav-name{font-size:1.7rem}
.wm-hero .wm-display{font-size:clamp(3rem,8vw,5.4rem)}
div[data-testid="stChatInput"] textarea{padding-top:.72rem !important;padding-bottom:.72rem !important}
.st-key-wm_theme_toggle{max-width:2.8rem;margin-left:auto}
.st-key-wm_theme_toggle button{width:2.5rem;min-width:2.5rem;height:2.5rem;min-height:2.5rem;
  padding:0!important;border-radius:999px!important;display:flex;align-items:center;justify-content:center}
.st-key-wm_theme_toggle button p{font-size:0!important;line-height:0!important}
div[data-testid="stChatInput"]{display:flex!important;align-items:center!important;
  gap:.35rem!important;padding:.25rem .4rem .25rem .9rem!important}
div[data-testid="stChatInput"] [data-testid="stChatInputSubmitButton"]{
  position:static!important;align-self:center!important;flex:0 0 2.15rem!important;
  width:2.15rem!important;height:2.15rem!important;min-height:2.15rem!important;
  margin:0!important;transform:none!important;display:flex!important;
  align-items:center!important;justify-content:center!important}
div[data-testid="stChatInput"] textarea{
  min-height:2.2rem!important;max-height:8rem!important;
  align-self:center!important;padding:.55rem 0!important}
@media (max-width:760px){
  .block-container{ padding:2.4rem 1rem 6rem; }
  .wm-bar{ grid-template-columns:1.6rem minmax(0,1fr) 1.4rem; }
  .wm-bar .track{ display:none; }
}
</style>
"""


_TOGGLE_SHAPES = {
    "beige": "%3Cpath d='M3 18h18M7.5 18a4.5 4.5 0 0 1 9 0M12 7v2.5M5.6 10.6l1.6 1.6M18.4 10.6l-1.6 1.6M2.5 14h2M19.5 14h2'/%3E",
    "light": ("%3Ccircle cx='12' cy='12' r='3.7'/%3E"
              "%3Cpath d='M12 2v2M12 20v2M4.93 4.93l1.42 1.42M17.65 17.65l1.42 1.42M2 12h2M20 12h2"
              "M4.93 19.07l1.42-1.42M17.65 6.35l1.42-1.42'/%3E"),
    "dark": "%3Cpath d='M20.2 15.4A8.4 8.4 0 0 1 8.6 3.8 8.5 8.5 0 1 0 20.2 15.4Z'/%3E",
}


def _toggle_icon_uri(theme: str) -> str:
    """Sunrise for Beige, full sun for Light, crescent moon for Dark - so the icon shows the current theme."""
    colour = "aaa99f" if theme == "dark" else "716b60"
    return ("data:image/svg+xml,"
            "%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' "
            f"stroke='%23{colour}' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'%3E"
            f"{_TOGGLE_SHAPES[theme]}%3C/svg%3E")


def inject_theme():
    theme = get_theme()
    scheme = "dark" if theme == "dark" else "light"
    css = (_CSS.replace("/*VARS*/", _VARS[theme]).replace("/*SCHEME*/", scheme)
               .replace("/*TOGGLE*/", _toggle_icon_uri(theme)))
    st.markdown(css, unsafe_allow_html=True)


# --------------------------------------------------------------------------
# Static layout pieces
# --------------------------------------------------------------------------
def _short(text: str, n: int) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= n else text[: n - 1].rstrip() + "…"


def section_label(num: str, title: str, aside: str = ""):
    st.markdown(
        f'<div class="wm-sec"><span class="n">{num}</span><span class="t">{html.escape(title)}</span>'
        f'<span class="line"></span><span class="a">{html.escape(aside)}</span></div>',
        unsafe_allow_html=True)


def render_nav():
    st.markdown(
        f'<div class="wm-nav">{_logo(44)}<div><div class="wm-nav-name">Knowvia</div>'
        '<div class="wm-nav-sub">A quieter way to explore knowledge</div></div></div>',
        unsafe_allow_html=True)


def render_hero():
    st.markdown(
        '<div class="wm-hero">'
        '<div class="wm-eyebrow">Wikipedia, thoughtfully explored</div>'
        '<div class="wm-display" role="heading" aria-level="1">Start <em>exploring</em></div>'
        '<p class="wm-lede">Ask anything. Discover reliable answers drawn from Wikipedia, with sources you can explore and verify.</p>'
        '<div class="wm-hero-rule"></div></div>',
        unsafe_allow_html=True)


def render_compact_hero():
    st.markdown(
        '<div class="wm-compact"><div class="wm-display">Start <em>exploring</em></div>'
        '<div class="wm-eyebrow">Research session</div></div>',
        unsafe_allow_html=True)


def render_sidebar_brand():
    st.markdown(
        f'<div class="wm-brand">{_logo(38)}'
        '<div><b>Knowvia</b><small>Research, with curiosity</small></div></div>',
        unsafe_allow_html=True)


def render_system_info(search_engine, model_name):
    """Currently unused (technical details are intentionally hidden); kept for later."""
    st.markdown(
        '<div class="wm-section-title">System</div><div class="wm-sys">'
        f'<div>{_icon("search", 15)}<span><span class="k">Search engine</span>'
        f'<span class="v">{html.escape(str(search_engine))}</span></span></div>'
        f'<div>{_icon("cpu", 15)}<span><span class="k">AI model</span>'
        f'<span class="v">{html.escape(str(model_name))}</span></span></div></div>',
        unsafe_allow_html=True)


# --------------------------------------------------------------------------
# Search insights (computed from this session's real messages)
# Currently not shown in the page (see insights_box below); kept for later.
# --------------------------------------------------------------------------
def render_insights(messages):
    rows, pending_q = [], None
    for m in messages:
        if m["role"] == "user":
            pending_q = m["content"]
        elif pending_q is not None:
            rows.append((pending_q, len(m.get("sources") or [])))
            pending_q = None
    if not rows:
        return
    top = max(c for _, c in rows) or 1
    bars = "".join(
        f'<div class="wm-bar"><span class="q">{i:02d}</span><span class="txt">{html.escape(_short(q, 80))}</span>'
        f'<span class="track"><i style="width:{int(100 * c / top)}%"></i></span><span class="c">{c}</span></div>'
        for i, (q, c) in enumerate(rows, 1))
    st.markdown(
        '<div class="wm-ins"><div class="wm-ins-head">'
        f'<div><span class="big">{len(rows)}</span><span class="k">Questions asked</span></div>'
        '<div class="a">Wikipedia sources retrieved<br>per answer</div></div>'
        f'{bars}</div>', unsafe_allow_html=True)


# --------------------------------------------------------------------------
# Answers & sources
# --------------------------------------------------------------------------
_CITE_GROUP = re.compile(r"\[(\s*Sources?\s*\d+(?:\s*,\s*(?:Sources?\s*)?\d+)*\s*)\]", re.I)
_NUM = re.compile(r"\d+")


def format_answer_html(answer_text: str, n_sources: int = 0, uid: int = 0) -> str:
    def repl(m):
        parts = []
        for n in _NUM.findall(m.group(1)):
            if n_sources and 1 <= int(n) <= n_sources:
                parts.append(f'<a class="wm-cite" href="#wm-src-{uid}-{n}">{n}</a>')
            else:
                parts.append(f'<span class="wm-cite">{n}</span>')
        return "".join(parts)
    return _CITE_GROUP.sub(repl, answer_text)


def render_answer(answer_text: str, n_sources: int = 0, uid: int = 0):
    st.markdown('<div class="wm-label">Knowvia Answer</div>', unsafe_allow_html=True)
    st.markdown(format_answer_html(answer_text, n_sources, uid), unsafe_allow_html=True)


def render_sources(sources, uid: int = 0):
    if not sources:
        return
    st.markdown(
        f'<div class="wm-src-title">Sources <span>&middot;</span> {len(sources)} cited &middot; Verify this answer</div>',
        unsafe_allow_html=True,
    )
    for i, source in enumerate(sources, 1):
        title = str(source.get("title") or f"Source {i}")
        url = str(source.get("url") or "")
        excerpt = str(source.get("excerpt") or "")
        summary = get_wikipedia_summary(url) if url else None
        image = (summary or {}).get("image", "")
        try:
            card = st.container(key=f"srcbox_{uid}_{i}")
        except TypeError:
            card = st.container()
        with card:
            if image:
                thumb_col, body_col, btn_col = st.columns([1, 4.2, 1.6], vertical_alignment="center")
                with thumb_col:
                    st.markdown(f'<img class="wm-thumb" src="{html.escape(image, quote=True)}" alt="">',
                                unsafe_allow_html=True)
            else:
                body_col, btn_col = st.columns([5.2, 1.6], vertical_alignment="center")
            with body_col:
                # the empty span is the anchor target for the clickable [n] citation badges in the answer
                st.markdown(f'<span id="wm-src-{uid}-{i}"></span><div class="wm-src-head">'
                            f'<span class="wm-src-num">{i:02d}</span>'
                            f'<span class="wm-src-ttl">{html.escape(title)}</span></div>',
                            unsafe_allow_html=True)
                if excerpt:
                    st.caption(_short(excerpt, 220))
                if url:
                    st.caption(urlparse(url).netloc or "Wikipedia")
            with btn_col:
                if url and st.button("Read article", key=f"read_article_{uid}_{i}", use_container_width=True):
                    st.session_state.article_url = url
                    st.session_state.article_title = title
                    st.session_state.article_open = True
                    st.session_state.article_full = False
                    st.session_state.article_html = ""
                    st.session_state.article_error = ""
                    st.rerun()


def render_followups(sources, uid: int = 0):
    """'Explore further' chips built from the cited article titles (a click asks a follow-up question)."""
    topics, seen = [], set()
    for source in sources:
        topic = " ".join(str(source.get("title") or "").split())
        if topic and topic.lower() not in seen:
            seen.add(topic.lower())
            topics.append(topic)
    if not topics:
        return
    try:
        box = st.container(key=f"related_box_{uid}")
    except TypeError:
        box = st.container()
    with box:
        st.markdown('<span class="wm-chiplabel">Explore further</span>', unsafe_allow_html=True)
        for i, topic in enumerate(topics[:3]):
            if st.button(topic, key=f"related_{uid}_{i}"):
                st.session_state.pending = f"Tell me more about {topic}."
                st.rerun()


def answer_markdown(question: str, answer: str, sources) -> str:
    lines = [f"# {question}", "", answer, "", "## Sources", ""]
    for i, source in enumerate(sources, 1):
        title = str(source.get("title") or f"Source {i}")
        url = str(source.get("url") or "")
        lines.append(f"{i}. [{title}]({url})" if url else f"{i}. {title}")
    return "\n".join(lines) + "\n"


def render_save_answer(question: str, answer: str, sources, uid: int = 0):
    slug = re.sub(r"[^a-z0-9]+", "-", question.lower()).strip("-")[:40] or "answer"
    st.download_button("Save answer", data=answer_markdown(question, answer, sources),
                       file_name=f"knowvia-{slug}.md", mime="text/markdown", key=f"dl_{uid}")


# --------------------------------------------------------------------------
# Article reader (fetches the cited Wikipedia page for the side panel)
# This is frontend-only: it needs just the source URL, not the database.
# --------------------------------------------------------------------------
WIKI_USER_AGENT = "Knowvia/1.0 (Streamlit research workspace)"
ARTICLE_ERROR_TEXT = ("This article couldn't be loaded here. "
                      "Use the button below to open it on Wikipedia.")


def _wikipedia_title_from_url(url: str):
    """Return (host, page title) for a Wikipedia article URL, or raise ValueError."""
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if not (host == "wikipedia.org" or host.endswith(".wikipedia.org")) or not parsed.path.startswith("/wiki/"):
        raise ValueError("Not a Wikipedia article URL")
    title = unquote(parsed.path[len("/wiki/"):])
    if not title:
        raise ValueError("Missing article title")
    return host, title


def _wiki_get_json(url: str, timeout: int = 8) -> dict:
    request = Request(url, headers={"User-Agent": WIKI_USER_AGENT, "Accept": "application/json"})
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _safe_image(url) -> str:
    """Only allow images served by Wikimedia."""
    url = str(url or "")
    return url if url.startswith("https://upload.wikimedia.org/") else ""


@st.cache_data(show_spinner=False, ttl=600)
def _fetch_wikipedia_summary(host: str, title: str) -> dict:
    """Short summary + thumbnail for an article. Returns {} on any failure (cached briefly so we don't retry every rerun)."""
    try:
        data = _wiki_get_json(f"https://{host}/api/rest_v1/page/summary/{quote(title, safe='')}?redirect=true", timeout=5)
        return dict(title=str(data.get("title") or title.replace("_", " ")),
                    description=str(data.get("description") or ""),
                    extract=str(data.get("extract") or ""),
                    image=_safe_image((data.get("thumbnail") or {}).get("source")))
    except Exception:
        return {}


def get_wikipedia_summary(url: str):
    """Summary dict for a Wikipedia URL, or None when it isn't available."""
    try:
        host, title = _wikipedia_title_from_url(url)
    except ValueError:
        return None
    return _fetch_wikipedia_summary(host, title) or None


@st.cache_data(show_spinner=False, ttl=1800)
def _fetch_featured(day: str) -> dict:
    try:
        tfa = _wiki_get_json(f"https://en.wikipedia.org/api/rest_v1/feed/featured/{day}", timeout=3).get("tfa") or {}
        return dict(title=str(tfa.get("normalizedtitle") or tfa.get("title") or "").replace("_", " "),
                    extract=str(tfa.get("extract") or ""),
                    image=_safe_image((tfa.get("thumbnail") or {}).get("source")))
    except Exception:
        return {}


def get_featured_article():
    """Wikipedia's featured article of the day (falls back to yesterday's), or None."""
    today = datetime.now(timezone.utc).date()
    for day in (today, today - timedelta(days=1)):
        item = _fetch_featured(day.strftime("%Y/%m/%d"))
        if item.get("title"):
            return item
    return None


FALLBACK_TOPICS = ["Coral reef", "Black hole", "Silk Road", "Aurora", "Octopus", "Fibonacci sequence",
                   "Printing press", "Great Barrier Reef"]


def random_wikipedia_title() -> str:
    try:
        title = _wiki_get_json("https://en.wikipedia.org/api/rest_v1/page/random/summary", timeout=4).get("title")
        if title:
            return str(title)
    except Exception:
        pass
    return random.choice(FALLBACK_TOPICS)


@st.cache_data(show_spinner=False, ttl=3600)
def _fetch_wikipedia_html(host: str, title: str) -> str:
    params = urlencode(dict(action="parse", page=title, prop="text", format="json", formatversion=2,
                            redirects=1, disableeditsection=1, disablelimitreport=1))
    data = _wiki_get_json(f"https://{host}/w/api.php?{params}", timeout=10)
    if "error" in data:
        raise ValueError(data["error"].get("info", "Article not found"))
    # <base> makes Wikipedia's relative links/images work inside the reader iframe and opens links in a new tab
    text = re.sub(r"<script\b.*?</script>", "", data["parse"]["text"], flags=re.S | re.I)   # never embed scripts
    return f'<base href="https://{host}/" target="_blank">' + text


def load_wikipedia_article(url: str):
    """Fill st.session_state.article_html, or article_error if the page can't be loaded."""
    try:
        host, title = _wikipedia_title_from_url(url)
        st.session_state.article_html = _fetch_wikipedia_html(host, title)
        st.session_state.article_error = ""
    except Exception:
        st.session_state.article_html = ""
        st.session_state.article_error = ARTICLE_ERROR_TEXT


_ARTICLE_COLORS = {
    "beige": dict(text="#292923", muted="#716B60", link="#59654D", border="#D3C6B3", panel="#EAE0D0", accent="#7B866D"),
    "light": dict(text="#292923", muted="#77736B", link="#59654D", border="#E5E1D8", panel="#F4F2ED", accent="#7B866D"),
    "dark":  dict(text="#EAE9E2", muted="#AAA99F", link="#B8C5A9", border="#363A32", panel="#292C26", accent="#849477"),
}

_ARTICLE_CSS = """
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,500&family=Inter:wght@400;500;600&display=swap">
<style>
body{font:15px/1.75 Inter,Arial,sans-serif;color:@text@;margin:0;padding:16px 20px 20px;background:transparent}
h1,h2,h3,h4{font-family:Fraunces,Georgia,serif;font-weight:500;line-height:1.25;letter-spacing:-.01em;color:@text@}
h2{font-size:1.35rem;margin:1.6em 0 .5em;padding-bottom:.3em;border-bottom:1px solid @border@}
h3{font-size:1.1rem;margin:1.3em 0 .4em}
p{margin:.7em 0}
a{color:@link@;text-decoration:underline;text-decoration-color:@border@;text-underline-offset:2px}
a:hover{text-decoration-color:@link@}
sup{line-height:0;font-size:.7em} sup a{text-decoration:none}
img{max-width:100%;height:auto;border-radius:4px}
figure,.thumb{margin:1em 0}
figcaption,.thumbcaption{font-size:.82rem;color:@muted@;line-height:1.5}
table{border-collapse:collapse;max-width:100%}
td,th{border:1px solid @border@;padding:6px 8px;font-size:.88rem}
th{background:@panel@;font-weight:600}
/* Wikipedia ships its own inline colours/floats; force them to follow the Knowvia theme and the narrow panel */
.mw-parser-output [style*="color"], .mw-parser-output [style*="background"]{background:transparent !important;color:inherit !important}
.mw-parser-output a{color:@link@ !important}
.mw-parser-output .infobox, .mw-parser-output .infobox_v2, .mw-parser-output .tright, .mw-parser-output .floatright,
.mw-parser-output [style*="float"], .mw-parser-output figure{float:none !important;clear:both;width:100% !important;max-width:100% !important;margin:1em 0 !important}
.mw-parser-output .infobox, .mw-parser-output .infobox_v2{background:@panel@ !important;color:@text@ !important;font-size:.85rem}
.mw-parser-output .infobox *{background-color:transparent !important;color:inherit !important}
.mw-parser-output .infobox a{color:@link@ !important}
.hatnote{color:@muted@;font-size:.85rem;font-style:italic}
blockquote{margin:1em 0;padding:.2em 1em;border-left:3px solid @accent@;color:@muted@}
ul,ol{padding-left:1.3em}
hr{border:0;border-top:1px solid @border@}
.mw-editsection,.navbox,.vertical-navbox,.metadata,.mw-references-wrap,.ambox,.sistersitebox,.noprint,.mw-empty-elt,.sidebar,.sidebar-collapse{display:none !important}
</style>
"""


def show_html_frame(content: str, height: int):
    """Embed an HTML string in an iframe (st.iframe on new Streamlit, components.html on older versions)."""
    if hasattr(st, "iframe"):
        st.iframe(content, height=height)
    else:
        components.html(content, height=height, scrolling=True)


def _article_css(theme: str) -> str:
    css = _ARTICLE_CSS
    for name, value in _ARTICLE_COLORS.get(theme, _ARTICLE_COLORS["beige"]).items():
        css = css.replace(f"@{name}@", value)
    return css


# --------------------------------------------------------------------------
# States
# --------------------------------------------------------------------------
def render_loading(text="Searching Wikipedia and preparing your answer…"):
    return st.markdown(f'<div class="wm-loading"><div class="wm-spin"></div>{html.escape(text)}</div>',
                       unsafe_allow_html=True)


def render_empty():
    st.markdown(f'<div class="wm-msg">{_icon("search", 17)}<span>No useful Wikipedia results were found. '
                'Try rephrasing your question or using more specific keywords.</span></div>',
                unsafe_allow_html=True)


def render_error():
    st.markdown(f'<div class="wm-msg err">{_icon("alert", 17)}<span>Something went wrong while answering. '
                'Please try again in a moment.</span></div>', unsafe_allow_html=True)


# --------------------------------------------------------------------------
# Saved chats (session_state + JSON file next to this file)
# --------------------------------------------------------------------------
CHATS_FILE = Path(__file__).with_name("curio_chats.json")
MAX_SAVED_CHATS = 50


def load_chats() -> list:
    try:
        data = json.loads(CHATS_FILE.read_text(encoding="utf-8"))
        return [c for c in data if isinstance(c, dict) and c.get("id") and c.get("messages")][:MAX_SAVED_CHATS]
    except Exception:
        return []


def persist_chats():
    try:
        CHATS_FILE.write_text(json.dumps(st.session_state.chats, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass          # read-only filesystem: chats still live in st.session_state for this session


def chat_title(messages) -> str:
    first = next((m["content"] for m in messages if m["role"] == "user"), "Untitled chat")
    return _short(first, 48)


def save_current_chat():
    """Store/update the active conversation in the saved list (most recent first). Empty chats are not saved."""
    msgs = st.session_state.messages
    if not msgs:
        return
    chats, cid = st.session_state.chats, st.session_state.chat_id
    entry = next((c for c in chats if c["id"] == cid), None)
    if entry is None:
        entry = dict(id=cid)
    else:
        chats.remove(entry)
    entry["title"] = chat_title(msgs)
    entry["messages"] = copy.deepcopy(msgs)
    chats.insert(0, entry)
    del chats[MAX_SAVED_CHATS:]
    persist_chats()


def start_new_chat():
    save_current_chat()
    st.session_state.messages = []
    st.session_state.pending = None
    st.session_state.chat_id = uuid.uuid4().hex
    st.session_state.article_open = False


def open_chat(chat_id: str):
    save_current_chat()
    chat = next((c for c in st.session_state.chats if c["id"] == chat_id), None)
    if chat:
        st.session_state.messages = copy.deepcopy(chat["messages"])
        st.session_state.chat_id = chat_id
        st.session_state.pending = None
        st.session_state.article_open = False


def _plain_label(text: str) -> str:
    """Escape markdown characters so a chat title is shown literally on a button."""
    return re.sub(r"([\\`*_{}\[\]()#+\-.!~$<>|])", r"\\\1", text)


def delete_saved_chat(chat_id: str):
    """Delete a saved chat and clear it if it is currently open."""
    st.session_state.chats = [
        c for c in st.session_state.chats if c.get("id") != chat_id
    ]
    if st.session_state.chat_id == chat_id:
        st.session_state.messages = []
        st.session_state.chat_id = uuid.uuid4().hex
        st.session_state.pending = None
        st.session_state.article_open = False
    st.session_state.pending_delete_chat_id = None
    persist_chats()


def render_saved_chats():
    chats = st.session_state.chats
    st.markdown(
        f'<div class="wm-section-title">Saved chats'
        f'<span>{len(chats):02d}</span></div>',
        unsafe_allow_html=True,
    )
    if not chats:
        st.markdown(
            '<div class="wm-hist-empty">Your conversations will appear here.</div>',
            unsafe_allow_html=True,
        )
        return

    opts = dict(key="chatlist", border=False)
    if len(chats) > 8:
        opts["height"] = 400
    try:
        box = st.container(**opts)
    except TypeError:
        box = st.container()

    with box:
        for c in chats:
            cid = c["id"]
            active = cid == st.session_state.chat_id and bool(st.session_state.messages)
            with st.container():
                title_col, delete_col = st.columns([0.84, 0.16], gap="small")
                with title_col:
                    key = f"{'chatact' if active else 'chatsel'}_{cid}"
                    if st.button(
                        _plain_label(c["title"]),
                        key=key,
                        use_container_width=True,
                        help=c["title"],
                    ):
                        open_chat(cid)
                        st.rerun()

                with delete_col:
                    if st.button("×", key=f"deletechat_{cid}", help="Delete saved chat"):
                        st.session_state.pending_delete_chat_id = cid
                        st.rerun()

                if st.session_state.get("pending_delete_chat_id") == cid:
                    st.caption("Delete this saved chat?")
                    yes_col, no_col = st.columns(2, gap="small")
                    with yes_col:
                        if st.button("Delete", key=f"confirmdelete_{cid}", use_container_width=True):
                            delete_saved_chat(cid)
                            st.rerun()
                    with no_col:
                        if st.button("Cancel", key=f"canceldelete_{cid}", use_container_width=True):
                            st.session_state.pending_delete_chat_id = None
                            st.rerun()


# ==========================================================================
# APP
# ==========================================================================
SUGGESTIONS = ["What is artificial intelligence?", "Explain photosynthesis.",
               "Who was Albert Einstein?", "What is quantum computing?"]


def render_suggestions(label: bool = True):
    """One row of small chips; a click sets `pending`, which the normal question handler then submits."""
    try:
        box = st.container(key="suggestions")
    except TypeError:
        box = st.container()
    with box:
        if label:
            st.markdown('<span class="wm-chiplabel">Try asking</span>', unsafe_allow_html=True)
        for i, s in enumerate(SUGGESTIONS):
            if st.button(s, key=f"sugg_{i}"):
                st.session_state.pending = s
                st.rerun()
        if st.button("✦ Surprise me", key="sugg_surprise", help="Ask about a random Wikipedia article"):
            st.session_state.pending = f"Tell me about {random_wikipedia_title()}."
            st.rerun()


def render_featured_card():
    """'Today on Wikipedia' card for the landing page; silently skipped if the feed can't be reached."""
    item = get_featured_article()
    if not item:
        return
    try:
        box = st.container(key="today_card")
    except TypeError:
        box = st.container()
    with box:
        st.markdown('<div class="wm-label">Today on Wikipedia</div>', unsafe_allow_html=True)
        if item["image"]:
            img_col, text_col = st.columns([1, 3], vertical_alignment="center")
            with img_col:
                st.markdown(f'<img class="wm-thumb" src="{html.escape(item["image"], quote=True)}" alt="">',
                            unsafe_allow_html=True)
        else:
            text_col = st.container()
        with text_col:
            st.markdown(f'<div class="wm-today-title">{html.escape(item["title"])}</div>'
                        f'<div class="wm-today-text">{html.escape(_short(item["extract"], 260))}</div>',
                        unsafe_allow_html=True)
            if st.button("Ask Knowvia about this", key="today_ask"):
                st.session_state.pending = f"Tell me about {item['title']}."
                st.rerun()


_STATE_DEFAULTS = {
    "messages": [],
    "pending": None,
    "chat_id": None,          # filled below
    "article_open": False,
    "article_full": False,
    "article_url": "",
    "article_title": "",
    "article_html": "",
    "article_error": "",
}
for _key, _default in _STATE_DEFAULTS.items():
    if _key not in st.session_state:
        st.session_state[_key] = copy.deepcopy(_default)
if st.session_state.chat_id is None:
    st.session_state.chat_id = uuid.uuid4().hex
if "chats" not in st.session_state:
    st.session_state.chats = load_chats()

n_questions = sum(1 for m in st.session_state.messages if m["role"] == "user")
has_messages = bool(st.session_state.messages)

inject_theme()

# Stop with a clear message if the API key or the Wikipedia database is missing.
_setup_problems = check_configuration()
if _setup_problems:
    for _problem in _setup_problems:
        st.error(_problem)
    st.stop()

# ---------------- Sidebar ----------------
with st.sidebar:
    render_sidebar_brand()
    if st.button("+  New Chat", use_container_width=True, key="new_chat"):
        start_new_chat()
        st.rerun()
    render_saved_chats()
    try:
        _box = st.container(key="sys_box")
    except TypeError:
        _box = st.container()
    with _box:
        pass  # Technical implementation details stay out of the interface.

# ---------------- Top navigation ----------------
try:
    top_l, top_r = st.columns([7, 2], vertical_alignment="center")
except TypeError:
    top_l, top_r = st.columns([7, 2])
with top_l:
    render_nav()
with top_r:
    theme_toggle()

st.markdown('<div class="wm-hr"></div>', unsafe_allow_html=True)

# ---------------- Intro ----------------
if has_messages:
    render_compact_hero()
else:
    render_hero()

# Page order (containers keep it stable while a new answer is generated):
#   landing:   intro -> question input -> suggestion chips -> insights
#   in a chat: intro -> conversation -> question input (follow-ups) -> insights
# There is exactly ONE st.chat_input; it is placed inside a container, so it sits in the page flow.
input_top = st.container()
chips_box = st.container()
today_box = st.container()
convo_box = st.container()
input_bottom = st.container()
insights_box = st.container()
foot_box = st.container()

with chips_box:
    if has_messages:
        with st.expander("Suggested questions", expanded=False):
            render_suggestions(label=False)
    else:
        render_suggestions()

with convo_box:
    show_reader = bool(st.session_state.article_open and st.session_state.article_url)
    if show_reader:
        chat_col, reader_col = st.columns([1.15, 1], gap="large")
    else:
        chat_col = st.container()
        reader_col = None
    with chat_col:
        if has_messages:
            section_label("01", "Conversation", f"{n_questions} question{'s' if n_questions != 1 else ''}")
        for idx, m in enumerate(st.session_state.messages):
            if m["role"] == "user":
                with st.chat_message("user"):
                    st.markdown(m["content"])
            else:
                with st.chat_message("assistant"):
                    if m.get("kind") == "empty":
                        render_empty()
                    elif m.get("kind") == "error":
                        render_error()
                    else:
                        sources = m.get("sources") or []
                        render_answer(m["content"], len(sources), idx)
                        render_sources(sources, idx)
                        render_followups(sources, idx)
                        prev = st.session_state.messages[idx - 1] if idx > 0 else {}
                        render_save_answer(prev.get("content", "Answer") if prev.get("role") == "user" else "Answer",
                                           m["content"], sources, idx)
    if show_reader and reader_col is not None:
        with reader_col:
            try:
                reader_box = st.container(key="reader")
            except TypeError:
                reader_box = st.container()
            with reader_box:
                article_url = st.session_state.article_url
                summary = get_wikipedia_summary(article_url)
                show_full = bool(st.session_state.article_full or not summary)   # no summary -> straight to full article
                st.markdown('<div class="wm-label">Wikipedia · Article reader</div>', unsafe_allow_html=True)
                head_l, head_r = st.columns([5, 1], vertical_alignment="center")
                with head_l:
                    st.markdown(f'<div class="wm-reader-title">'
                                f'{html.escape(st.session_state.article_title or "Wikipedia article")}</div>',
                                unsafe_allow_html=True)
                with head_r:
                    if st.button("Close", key="close_article", use_container_width=True):
                        st.session_state.article_open = False
                        st.rerun()
                if summary:
                    act_l, act_r = st.columns(2, gap="small")
                    with act_l:
                        if st.button("Back to summary" if show_full else "Read full article",
                                     key="reader_toggle", use_container_width=True):
                            st.session_state.article_full = not show_full
                            st.rerun()
                    with act_r:
                        st.link_button("Open on Wikipedia ↗", article_url, use_container_width=True)
                else:
                    st.link_button("Open original on Wikipedia ↗", article_url, use_container_width=True)

                if show_full:
                    if not st.session_state.article_html and not st.session_state.article_error:
                        with st.spinner("Loading article…"):
                            load_wikipedia_article(article_url)
                    if st.session_state.article_html:
                        show_html_frame(_article_css(get_theme()) + st.session_state.article_html, height=520)
                    else:
                        st.info(st.session_state.article_error or "Article preview is unavailable.")
                else:
                    desc = html.escape(summary.get("description", ""))
                    extract = html.escape(" ".join(summary.get("extract", "").split()))
                    image = summary.get("image", "")
                    st.markdown(
                        (f'<div class="wm-reader-desc">{desc}</div>' if desc else "")
                        + (f'<img class="wm-reader-img" src="{html.escape(image, quote=True)}" alt="">' if image else "")
                        + f'<div class="wm-reader-extract">{extract}</div>',
                        unsafe_allow_html=True)

with insights_box:
    pass

with foot_box:
    st.markdown('<div class="wm-foot"><span>Knowvia</span>'
                '<span>Answers are generated from Wikipedia &mdash; verify with the cited sources</span></div>',
                unsafe_allow_html=True)

# ---------------- The one question input ----------------
with (input_bottom if has_messages else input_top):
    typed = st.chat_input("Ask Knowvia anything…")
with today_box:
    if not has_messages:
        render_featured_card()      # rendered after the input so a slow feed never delays the page
question = typed or st.session_state.pending
st.session_state.pending = None

if question:
    st.session_state.messages.append(dict(role="user", content=question))
    with convo_box:
        with st.chat_message("user"):
            st.markdown(question)
        with st.chat_message("assistant"):
            render_loading()
            try:
                # earlier messages (everything before the question just added) enable follow-ups
                result = search_and_answer(question, st.session_state.messages[:-1])
                if not result.get("answer"):
                    st.session_state.messages.append(dict(role="assistant", content="", sources=[], kind="empty"))
                else:
                    st.session_state.messages.append(dict(role="assistant", content=result["answer"],
                                                          sources=result.get("sources") or [], kind="answer"))
            except Exception as _err:
                print(f"[Knowvia] answer failed: {type(_err).__name__}: {_err}", file=sys.stderr)
                st.session_state.messages.append(dict(role="assistant", content="", sources=[], kind="error"))
    save_current_chat()
    st.rerun()
