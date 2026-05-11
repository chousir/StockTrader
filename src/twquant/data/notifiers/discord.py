"""Discord Webhook 推播 adapter — 用 urllib，不引入額外依賴"""

from __future__ import annotations
import json
import urllib.request
import urllib.error
from typing import Iterable

import pandas as pd
from loguru import logger


_STRATEGY_LABEL = {
    "momentum_concentrate": "F｜動能精選 ★",
    "volume_breakout":      "H｜量價突破",
    "triple_ma_twist":      "L｜三線扭轉",
    "risk_adj_momentum":    "M｜RAM動能",
    "donchian_breakout":    "N｜唐奇安突破",
    "ma_crossover":         "MA 黃金交叉",
    "macd_divergence":      "MACD 背離",
    "rsi_reversal":         "RSI 反轉",
    "bollinger_breakout":   "布林突破",
}

_STRATEGY_COLORS = {
    "momentum_concentrate": 0xFFD700,
    "volume_breakout":      0xF97316,
    "triple_ma_twist":      0x34D399,
    "risk_adj_momentum":    0x60A5FA,
    "donchian_breakout":    0xFB7185,
    "ma_crossover":         0x8B5CF6,
    "macd_divergence":      0xEC4899,
    "rsi_reversal":         0x14B8A6,
    "bollinger_breakout":   0xA855F7,
}


class DiscordNotifier:
    """Discord Webhook 推播器。webhook_url 為空時所有方法 noop。"""

    def __init__(self, webhook_url: str):
        self.webhook_url = (webhook_url or "").strip()

    @property
    def enabled(self) -> bool:
        return bool(self.webhook_url)

    def _post(self, payload: dict) -> bool:
        if not self.enabled:
            return False
        try:
            req = urllib.request.Request(
                self.webhook_url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                if 200 <= resp.status < 300:
                    return True
                logger.warning(f"Discord webhook returned status {resp.status}")
                return False
        except urllib.error.HTTPError as e:
            logger.warning(f"Discord webhook HTTPError {e.code}: {e.reason}")
            return False
        except Exception as e:
            logger.warning(f"Discord webhook failed: {e}")
            return False

    def send_message(self, content: str) -> bool:
        if not self.enabled or not content:
            return False
        return self._post({"content": content[:2000]})

    def send_embeds(self, embeds: list[dict]) -> bool:
        if not self.enabled or not embeds:
            return False
        return self._post({"embeds": embeds[:10]})

    def notify_daily_picks(
        self, scan_date: str, picks_df: pd.DataFrame, max_per_strategy: int = 15
    ) -> bool:
        """把每日選股清單依策略分組成 embeds 發送。

        picks_df columns expected: 代號, 策略, 收盤價, 距MA60%, RSI, 量比
        """
        if not self.enabled:
            return False
        if picks_df is None or picks_df.empty:
            return self.send_message(f"📅 **每日選股 {scan_date}** — 今日無進場訊號")

        embeds: list[dict] = []
        for key, group in picks_df.groupby("策略", sort=False):
            label = _STRATEGY_LABEL.get(key, key)
            color = _STRATEGY_COLORS.get(key, 0x9CA3AF)
            top = group.head(max_per_strategy)
            lines = []
            for _, r in top.iterrows():
                lines.append(
                    f"`{r['代號']}` ${float(r['收盤價']):.1f} "
                    f"距MA60 {float(r['距MA60%']):+.1f}% "
                    f"RSI {float(r['RSI']):.0f} 量比 {float(r['量比']):.1f}"
                )
            description = "\n".join(lines) if lines else "（無）"
            if len(description) > 4000:
                description = description[:3990] + "\n…(截斷)"
            embeds.append({
                "title": f"📡 {label}",
                "description": description,
                "color": color,
                "footer": {"text": f"共 {len(group)} 檔"},
            })

        header_embed = {
            "title": f"📅 每日選股 {scan_date}",
            "description": f"共觸發 **{len(picks_df)}** 筆訊號 / {picks_df['策略'].nunique()} 個策略",
            "color": 0x22C55E,
        }
        return self.send_embeds([header_embed] + embeds)

    def notify_alert(self, rule_name: str, stock_id: str, message: str) -> bool:
        if not self.enabled:
            return False
        return self.send_embeds([{
            "title": f"🔔 告警觸發 — {rule_name}",
            "description": f"`{stock_id}` {message}",
            "color": 0xEF4444,
        }])
