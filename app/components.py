"""Reusable UI components and badge renderers for the CNG Demand Planner dashboard."""

import streamlit as st

BADGE_STYLES = {
    "REAL": {
        "bg": "#10b981",  # Emerald green
        "fg": "#ffffff",
        "label": "REAL (OBSERVED)"
    },
    "MODELLED": {
        "bg": "#3b82f6",  # Blue
        "fg": "#ffffff",
        "label": "MODELLED"
    },
    "ASSUMPTION": {
        "bg": "#f59e0b",  # Amber
        "fg": "#000000",
        "label": "ASSUMPTION"
    },
    "SOURCED": {
        "bg": "#6366f1",  # Indigo
        "fg": "#ffffff",
        "label": "SOURCED"
    }
}


def badge_html(tag_type: str) -> str:
    """Return styled HTML string for a colored status badge."""
    tag_clean = tag_type.upper().strip()
    style = BADGE_STYLES.get(tag_clean, {
        "bg": "#64748b",
        "fg": "#ffffff",
        "label": tag_clean
    })
    return (
        f'<span style="background-color: {style["bg"]}; color: {style["fg"]}; '
        f'padding: 3px 8px; border-radius: 4px; font-weight: 700; font-size: 11px; '
        f'letter-spacing: 0.5px; display: inline-block; vertical-align: middle; '
        f'margin: 0 4px 2px 0;">{style["label"]}</span>'
    )


def render_page_badges(tags: list):
    """Render a row of status badges at the top of a page."""
    badges_html = " ".join([badge_html(t) for t in tags])
    st.markdown(
        f'<div style="margin-bottom: 12px; margin-top: 4px;">{badges_html}</div>',
        unsafe_allow_html=True
    )


def render_notice_banner(message: str, banner_type: str = "warning"):
    """Render a styled notice banner."""
    if banner_type == "warning":
        border_color = "#f59e0b"
        bg_color = "#fffbeb"
        text_color = "#92400e"
        icon = "⚠️"
    elif banner_type == "info":
        border_color = "#3b82f6"
        bg_color = "#eff6ff"
        text_color = "#1e40af"
        icon = "ℹ️"
    else:
        border_color = "#10b981"
        bg_color = "#ecfdf5"
        text_color = "#065f46"
        icon = "✓"

    st.markdown(
        f'<div style="background-color: {bg_color}; border-left: 4px solid {border_color}; '
        f'padding: 12px 16px; border-radius: 4px; margin-bottom: 16px; color: {text_color}; '
        f'font-size: 14.5px; line-height: 1.5;">'
        f'<strong>{icon} Data Notice:</strong> {message}'
        f'</div>',
        unsafe_allow_html=True
    )


def render_footer():
    """Render standardized challenge footer."""
    st.markdown("---")
    st.markdown(
        '<div style="text-align: center; color: #64748b; font-size: 14px; padding: 10px 0;">'
        '<strong>Team ID: TM000846</strong> | '
        'Seva First Innovation Challenge 2026 (PS000002) | '
        '<a href="https://github.com/Soha1711/SSA_hack" target="_blank" style="color: #0066cc; text-decoration: none;">GitHub Repository</a>'
        '</div>',
        unsafe_allow_html=True
    )
