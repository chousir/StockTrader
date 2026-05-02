"""TradingView 免費嵌入式 Widget 元件"""

import json
import streamlit.components.v1 as components


def render_tv_heatmap(height: int = 500) -> None:
    """
    嵌入 TradingView 台股類股熱力圖（TWSE + TPEX）

    免費嵌入 Widget，無需 API Key，數據可能有延遲。
    """
    html = f"""
    <div class="tradingview-widget-container" style="height:{height}px;width:100%;">
      <div class="tradingview-widget-container__widget" style="height:100%;width:100%;"></div>
      <script type="text/javascript"
              src="https://s3.tradingview.com/external-embedding/embed-widget-stock-heatmap.js"
              async>
      {{
        "exchanges": ["TWSE", "TPEX"],
        "dataSource": "TWSE",
        "grouping": "sector",
        "blockSize": "market_cap_basic",
        "blockColor": "change",
        "locale": "zh_TW",
        "colorTheme": "dark",
        "hasTopBar": true,
        "isDataSetEnabled": true,
        "isZoomEnabled": true,
        "hasSymbolTooltip": true,
        "width": "100%",
        "height": "{height}"
      }}
      </script>
    </div>
    """
    components.html(html, height=height + 20)


def render_tv_technicals(stock_id: str, height: int = 400) -> None:
    """
    嵌入 TradingView 技術分析摘要（RSI、MACD、MA 多空評級）

    作為使用者自建指標的第二意見。
    stock_id: 台股代碼，自動轉換為 TWSE:{stock_id} 格式
    """
    symbol = f"TWSE:{stock_id}"
    html = f"""
    <div class="tradingview-widget-container">
      <div class="tradingview-widget-container__widget"></div>
      <script type="text/javascript"
              src="https://s3.tradingview.com/external-embedding/embed-widget-technical-analysis.js"
              async>
      {{
        "interval": "1D",
        "width": "100%",
        "isTransparent": true,
        "height": "{height}",
        "symbol": "{symbol}",
        "showIntervalTabs": true,
        "displayMode": "single",
        "locale": "zh_TW",
        "colorTheme": "dark"
      }}
      </script>
    </div>
    """
    components.html(html, height=height + 20)


def render_tv_ticker_tape(symbols: list[str] | None = None) -> None:
    """
    嵌入 TradingView 跑馬燈（頁面頂部即時行情滾動）

    預設顯示台股權值股，數據可能有延遲。
    """
    if symbols is None:
        symbols = [
            "TWSE:2330", "TWSE:2317", "TWSE:2454",
            "TWSE:2882", "TWSE:2886", "TWSE:2603",
            "TWSE:0050", "TWSE:0056",
        ]

    symbols_json = json.dumps([
        {"proName": s, "title": s.split(":")[1]} for s in symbols
    ])

    html = f"""
    <div class="tradingview-widget-container">
      <div class="tradingview-widget-container__widget"></div>
      <script type="text/javascript"
              src="https://s3.tradingview.com/external-embedding/embed-widget-ticker-tape.js"
              async>
      {{
        "symbols": {symbols_json},
        "showSymbolLogo": false,
        "isTransparent": true,
        "displayMode": "adaptive",
        "colorTheme": "dark",
        "locale": "zh_TW"
      }}
      </script>
    </div>
    """
    components.html(html, height=46)
