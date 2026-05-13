"""主推 + 觀察名單的近 3 年回測覆驗（2023-01 ~ 2026-05）"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import numpy as np
import pandas as pd
from twquant.data.storage import SQLiteStorage
from twquant.backtest.engine import TWSEBacktestEngine
from twquant.strategy.registry import get_strategy

STRATS = ["momentum_concentrate", "volume_breakout", "triple_ma_twist",
          "risk_adj_momentum", "donchian_breakout"]
STRAT_LABEL = {
    "momentum_concentrate": "F動能", "volume_breakout": "H量價",
    "triple_ma_twist": "L三線", "risk_adj_momentum": "M-RAM",
    "donchian_breakout": "N唐奇安",
}

MAIN = [("5269","祥碩"),("2377","微星"),("3530","晶相光"),("2382","廣達"),
        ("2353","宏碁"),("3035","智原"),("2345","智邦"),("2492","華新科"),
        ("4977","眾達-KY"),("3034","聯詠"),("2376","技嘉"),("2357","華碩"),("6285","啟碁")]
OBS = [("8299","群聯"),("6669","緯穎"),("2327","國巨*"),("5347","世界先進"),
       ("5274","信驊"),("6533","晶心科"),("2356","英業達"),("3711","日月光投控")]

def bt(sid: str, name: str, start: str, end: str):
    s = SQLiteStorage("data/twquant.db")
    df = s.load(f"daily_price/{sid}", start_date=start, end_date=end)
    if df.empty or len(df) < 100:
        return None
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)
    price = pd.Series(df["close"].astype(float).values, index=pd.to_datetime(df["date"]))
    best = None
    for k in STRATS:
        try:
            entries, exits = get_strategy(k).generate_signals(df)
            if (entries.sum() if hasattr(entries,'sum') else sum(entries)) == 0:
                continue
            m = TWSEBacktestEngine().run(price, entries, exits, init_cash=1_000_000)
            row = {"sid": sid, "name": name, "strategy": STRAT_LABEL[k],
                   "total_return": m["total_return"], "sharpe": m["sharpe_ratio"],
                   "mdd": m["max_drawdown"], "win_rate": m["win_rate"],
                   "trades": m["total_trades"], "final": m["final_value"]}
            if best is None or row["sharpe"] > best["sharpe"]:
                best = row
        except Exception:
            pass
    return best

def main():
    start = "2023-01-01"
    end = "2026-05-12"
    print(f"\n回測區間：{start} ~ {end}（近 3.4 年）\n")

    # 0050 基準
    bench = bt("0050", "0050", start, end)

    def show(title, names):
        print("="*100)
        print(f"{title}")
        print("="*100)
        rows = []
        for sid, name in names:
            r = bt(sid, name, start, end)
            if r:
                rows.append(r)
        if not rows:
            print("(無有效回測)")
            return
        df = pd.DataFrame(rows)
        df["總報酬"] = (df["total_return"]*100).round(1).astype(str) + "%"
        df["MDD"] = (df["mdd"]*100).round(1).astype(str) + "%"
        df["勝率"] = (df["win_rate"]*100).round(1).astype(str) + "%"
        df["Sharpe"] = df["sharpe"].round(2)
        df["筆數"] = df["trades"]
        df["最終資產"] = df["final"].apply(lambda x: f"${x:,.0f}")
        print(df[["sid","name","strategy","總報酬","Sharpe","MDD","勝率","筆數","最終資產"]]
              .rename(columns={"sid":"代號","name":"名稱","strategy":"最佳策略"})
              .to_string(index=False))
        print()

    if bench:
        print(f"基準 0050（{bench['strategy']}）：總報酬 {bench['total_return']*100:.1f}%，Sharpe {bench['sharpe']:.2f}，MDD {bench['mdd']*100:.1f}%\n")
    show("⭐ 主推 13 支", MAIN)
    show("👀 觀察 8 支", OBS)

if __name__ == "__main__":
    main()
