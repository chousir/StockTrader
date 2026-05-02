"""Plotly 深色模板：所有圖表自動套用 TWQuant 風格"""

import plotly.graph_objects as go
import plotly.io as pio

_REGISTERED = False


def register_twquant_dark_template() -> None:
    """註冊並設為預設模板（可重複呼叫，只執行一次）"""
    global _REGISTERED
    if _REGISTERED:
        return

    pio.templates["twquant_dark"] = go.layout.Template(
        layout=go.Layout(
            paper_bgcolor="#0F1117",
            plot_bgcolor="#0F1117",
            font=dict(color="#E8EAED", family="Noto Sans TC, sans-serif"),
            xaxis=dict(
                gridcolor="#2A2D3A",
                zerolinecolor="#2A2D3A",
                linecolor="#2A2D3A",
            ),
            yaxis=dict(
                gridcolor="#2A2D3A",
                zerolinecolor="#2A2D3A",
                linecolor="#2A2D3A",
            ),
            colorway=[
                "#00D4AA", "#3B82F6", "#F97316", "#A855F7",
                "#FBBF24", "#EF4444", "#22C55E", "#EC4899",
            ],
            hoverlabel=dict(
                bgcolor="#1E2130",
                font_color="#E8EAED",
                bordercolor="#2A2D3A",
            ),
            legend=dict(
                bgcolor="rgba(0,0,0,0)",
                font=dict(color="#9CA3AF"),
            ),
        )
    )
    pio.templates.default = "twquant_dark"
    _REGISTERED = True
