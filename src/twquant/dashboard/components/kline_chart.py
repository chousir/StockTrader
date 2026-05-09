"""台股 K 線圖元件：Plotly make_subplots，台股紅漲綠跌配色"""

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from ..styles.plotly_theme import register_twquant_dark_template
from ..styles.theme import TWStockColors

register_twquant_dark_template()


def create_tw_stock_chart(
    df: pd.DataFrame,
    ma_periods: list[int] | None = None,
    show_volume: bool = True,
) -> go.Figure:
    """
    建立台股 K 線圖。

    Parameters:
        df: OHLCV DataFrame，需含 date/open/high/low/close/volume 欄位
        ma_periods: 均線週期列表，預設 [5, 10, 20, 60]
        show_volume: 是否顯示成交量副圖（單位：張）

    Returns:
        Plotly Figure，支援縮放與 Hover
    """
    if ma_periods is None:
        ma_periods = [5, 10, 20, 60]

    rows = 2 if show_volume else 1
    row_heights = [0.7, 0.3] if show_volume else [1.0]

    fig = make_subplots(
        rows=rows,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=row_heights,
        subplot_titles=("K 線圖", "成交量（張）") if show_volume else ("K 線圖",),
    )

    dates = df["date"].astype(str)

    # 漲跌資訊
    prev_close = df["close"].shift(1)
    change = df["close"] - prev_close
    change_pct = change / prev_close * 100

    # 自訂 hover text（含漲跌資訊）
    hover_texts = []
    for i, row in df.iterrows():
        chg = change.iloc[i] if i > 0 else 0.0
        chg_pct = change_pct.iloc[i] if i > 0 else 0.0
        arrow = "▲" if chg > 0 else ("▼" if chg < 0 else "─")
        color_tag = "red" if chg > 0 else ("green" if chg < 0 else "gray")
        vol_zhang = row["volume"] / 1000
        text = (
            f"開：{row['open']:.1f}　高：{row['high']:.1f}<br>"
            f"低：{row['low']:.1f}　收：{row['close']:.1f}<br>"
            f"漲跌：<span style='color:{color_tag}'>{arrow}{abs(chg):.1f} ({chg_pct:+.2f}%)</span><br>"
            f"成交量：{vol_zhang:,.0f} 張"
        )
        hover_texts.append(text)

    # ── 主圖：K 線（台股慣例：紅漲綠跌）──
    fig.add_trace(
        go.Candlestick(
            x=dates,
            open=df["open"],
            high=df["high"],
            low=df["low"],
            close=df["close"],
            text=hover_texts,
            hoverinfo="x+text",
            name="K線",
            increasing_line_color=TWStockColors.CANDLE_UP_BORDER,
            increasing_fillcolor=TWStockColors.CANDLE_UP_FILL,
            decreasing_line_color=TWStockColors.CANDLE_DOWN_BORDER,
            decreasing_fillcolor=TWStockColors.CANDLE_DOWN_FILL,
        ),
        row=1,
        col=1,
    )

    # ── 均線 ──
    for period in ma_periods:
        if len(df) >= period:
            ma = df["close"].rolling(period).mean()
            color = TWStockColors.MA_COLORS.get(period, "#888888")
            fig.add_trace(
                go.Scatter(
                    x=dates,
                    y=ma,
                    mode="lines",
                    name=f"MA{period}",
                    line=dict(color=color, width=1.2),
                    hovertemplate=f"MA{period}: %{{y:.1f}}<extra></extra>",
                ),
                row=1,
                col=1,
            )

    # ── 副圖：成交量（張 = 股 ÷ 1000，漲紅跌綠）──
    if show_volume:
        is_up = df["close"] >= df["open"]
        bar_colors = [
            TWStockColors.VOLUME_UP if up else TWStockColors.VOLUME_DOWN
            for up in is_up
        ]
        vol_zhang = df["volume"] / 1000
        fig.add_trace(
            go.Bar(
                x=dates,
                y=vol_zhang,
                name="成交量",
                marker_color=bar_colors,
                showlegend=False,
                hovertemplate="%{y:,.0f} 張<extra></extra>",
            ),
            row=2,
            col=1,
        )

    fig.update_layout(
        height=520,
        xaxis_rangeslider_visible=False,
        margin=dict(l=40, r=20, t=40, b=20),
        hovermode="x unified",
        legend=dict(orientation="h", y=1.02),
    )

    # y軸格式
    fig.update_yaxes(title_text="價格（元）", row=1, col=1)
    if show_volume:
        fig.update_yaxes(title_text="張", row=2, col=1)

    return fig
