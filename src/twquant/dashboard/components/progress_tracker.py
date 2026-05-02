"""Streamlit 非同步進度條元件：支援 ETA 估算與錯誤計數"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class TaskType(Enum):
    FULL_SYNC = "全市場數據同步"
    INCREMENTAL_SYNC = "增量數據更新"
    GAP_FILL = "闕漏數據回補"
    MULTI_BACKTEST = "多標的平行回測"
    PARAM_OPTIMIZE = "參數最佳化搜索"


@dataclass
class ProgressState:
    """進度狀態物件，跨 Streamlit rerun 保持"""

    task_type: TaskType
    total: int
    completed: int = 0
    current_item: str = ""
    errors: list[str] = field(default_factory=list)
    start_time: datetime = field(default_factory=datetime.now)

    @property
    def pct(self) -> float:
        return self.completed / self.total if self.total > 0 else 0

    @property
    def eta_seconds(self) -> float:
        if self.completed == 0:
            return float("inf")
        elapsed = (datetime.now() - self.start_time).total_seconds()
        rate = self.completed / elapsed
        remaining = self.total - self.completed
        return remaining / rate if rate > 0 else float("inf")


def render_progress_bar(state: ProgressState) -> None:
    """渲染 Streamlit 進度條 UI（需在 Streamlit 環境中呼叫）"""
    import streamlit as st

    col1, col2 = st.columns([3, 1])

    with col1:
        st.progress(state.pct, text=f"{state.task_type.value}：{state.current_item}")

    with col2:
        eta = state.eta_seconds
        if eta == float("inf"):
            eta_str = "計算中..."
        elif eta > 3600:
            eta_str = f"約 {eta/3600:.1f} 小時"
        elif eta > 60:
            eta_str = f"約 {eta/60:.0f} 分鐘"
        else:
            eta_str = f"約 {eta:.0f} 秒"

        st.caption(f"{state.completed}/{state.total} | ETA: {eta_str}")

    if state.errors:
        with st.expander(f"⚠️ {len(state.errors)} 個錯誤", expanded=False):
            for err in state.errors[-10:]:
                st.text(err)
