import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
from streamlit_echarts import st_echarts
from ta.momentum import RSIIndicator
from ta.trend import SMAIndicator, EMAIndicator
from datetime import datetime
import streamlit.components.v1 as components

st.set_page_config(page_title="NSE Nifty 100 Intelligence Terminal", layout="wide")
st.title("📊 NSE Nifty 100 Intelligence Terminal")

# ─────────────────────────────────────────────────────────────────
# RESPONSIVE HEIGHT
# ─────────────────────────────────────────────────────────────────
components.html(
    """
    <script>
    (function() {
        const h = window.innerHeight;
        const url = new URL(window.parent.location.href);
        if (url.searchParams.get('vh') !== String(h)) {
            url.searchParams.set('vh', h);
            window.parent.history.replaceState({}, '', url.toString());
            window.parent.location.reload();
        }
    })();
    </script>
    """,
    height=0,
)
try:
    _vh = max(400, int(st.query_params.get("vh", "900")))
except Exception:
    _vh = 900

def vh(pct: float) -> str:
    return f"{max(280, int(_vh * pct / 100))}px"

# ─────────────────────────────────────────────────────────────────
# STOCK LIST  (Nifty 50 + Nifty Next 50)
# ─────────────────────────────────────────────────────────────────
stocks = {
    "RELIANCE.NS":   ("Energy",        "Oil & Gas"),
    "TCS.NS":        ("IT",            "IT Services"),
    "HDFCBANK.NS":   ("Banking",       "Private Bank"),
    "ICICIBANK.NS":  ("Banking",       "Private Bank"),
    "INFY.NS":       ("IT",            "IT Services"),
    "HINDUNILVR.NS": ("FMCG",          "Consumer Goods"),
    "ITC.NS":        ("FMCG",          "Consumer Goods"),
    "SBIN.NS":       ("Banking",       "PSU Bank"),
    "BHARTIARTL.NS": ("Telecom",       "Telecom"),
    "LT.NS":         ("Capital Goods", "Engineering"),
    "KOTAKBANK.NS":  ("Banking",       "Private Bank"),
    "AXISBANK.NS":   ("Banking",       "Private Bank"),
    "ASIANPAINT.NS": ("Chemicals",     "Paints"),
    "MARUTI.NS":     ("Auto",          "Automobile"),
    "TITAN.NS":      ("Consumer",      "Jewellery"),
    "ULTRACEMCO.NS": ("Cement",        "Cement"),
    "BAJFINANCE.NS": ("Finance",       "NBFC"),
    "WIPRO.NS":      ("IT",            "IT Services"),
    "NESTLEIND.NS":  ("FMCG",          "Consumer Goods"),
    "TATAMOTORS.NS": ("Auto",          "Automobile"),
    "SUNPHARMA.NS":  ("Pharma",        "Pharmaceuticals"),
    "POWERGRID.NS":  ("Power",         "Utilities"),
    "NTPC.NS":       ("Power",         "Utilities"),
    "JSWSTEEL.NS":   ("Metals",        "Steel"),
    "TATASTEEL.NS":  ("Metals",        "Steel"),
    "GRASIM.NS":     ("Cement",        "Cement"),
    "HCLTECH.NS":    ("IT",            "IT Services"),
    "TECHM.NS":      ("IT",            "IT Services"),
    "ADANIENT.NS":   ("Conglomerate",  "Adani Group"),
    "ADANIPORTS.NS": ("Logistics",     "Ports"),
    "BAJAJFINSV.NS": ("Finance",       "Financial Services"),
    "INDUSINDBK.NS": ("Banking",       "Private Bank"),
    "ONGC.NS":       ("Energy",        "Oil & Gas"),
    "COALINDIA.NS":  ("Energy",        "Coal"),
    "DRREDDY.NS":    ("Pharma",        "Pharmaceuticals"),
    "CIPLA.NS":      ("Pharma",        "Pharmaceuticals"),
    "DIVISLAB.NS":   ("Pharma",        "Pharmaceuticals"),
    "BPCL.NS":       ("Energy",        "Oil & Gas"),
    "HEROMOTOCO.NS": ("Auto",          "Automobile"),
    "EICHERMOT.NS":  ("Auto",          "Automobile"),
    "APOLLOHOSP.NS": ("Healthcare",    "Hospitals"),
    "BRITANNIA.NS":  ("FMCG",          "Consumer Goods"),
    "DMART.NS":      ("Retail",        "Retail"),
    "PIDILITIND.NS": ("Chemicals",     "Adhesives"),
    "DABUR.NS":      ("FMCG",          "Consumer Goods"),
    "BERGEPAINT.NS": ("Chemicals",     "Paints"),
    "SRF.NS":        ("Chemicals",     "Specialty Chemicals"),
    "M&M.NS":        ("Auto",          "Automobile"),
    "SIEMENS.NS":    ("Capital Goods", "Engineering"),
    "ABB.NS":        ("Capital Goods", "Engineering"),
    "ADANIGREEN.NS":  ("Energy",        "Renewable Energy"),
    "AMBUJACEM.NS":   ("Cement",        "Cement"),
    "AUROPHARMA.NS":  ("Pharma",        "Pharmaceuticals"),
    "BAJAJ-AUTO.NS":  ("Auto",          "Automobile"),
    "BANKBARODA.NS":  ("Banking",       "PSU Bank"),
    "BEL.NS":         ("Capital Goods", "Defence"),
    "BOSCHLTD.NS":    ("Auto",          "Auto Components"),
    "CANBK.NS":       ("Banking",       "PSU Bank"),
    "CHOLAFIN.NS":    ("Finance",       "NBFC"),
    "COLPAL.NS":      ("FMCG",          "Consumer Goods"),
    "CONCOR.NS":      ("Logistics",     "Logistics"),
    "CUMMINSIND.NS":  ("Capital Goods", "Engineering"),
    "DLF.NS":         ("Real Estate",   "Real Estate"),
    "GODREJCP.NS":    ("FMCG",          "Consumer Goods"),
    "GODREJPROP.NS":  ("Real Estate",   "Real Estate"),
    "HAVELLS.NS":     ("Capital Goods", "Electricals"),
    "ICICIPRULI.NS":  ("Finance",       "Insurance"),
    "INDUSTOWER.NS":  ("Telecom",       "Telecom Infrastructure"),
    "NAUKRI.NS":      ("IT",            "Internet Services"),
    "INDIGO.NS":      ("Aviation",      "Aviation"),
    "IOC.NS":         ("Energy",        "Oil & Gas"),
    "IRCTC.NS":       ("Consumer",      "Railways / Tourism"),
    "JINDALSTEL.NS":  ("Metals",        "Steel"),
    "LICI.NS":        ("Finance",       "Insurance"),
    "LODHA.NS":       ("Real Estate",   "Real Estate"),
    "LUPIN.NS":       ("Pharma",        "Pharmaceuticals"),
    "MANKIND.NS":     ("Pharma",        "Pharmaceuticals"),
    "MARICO.NS":      ("FMCG",          "Consumer Goods"),
    "MCDOWELL-N.NS":  ("FMCG",          "Beverages"),
    "MOTHERSON.NS":   ("Auto",          "Auto Components"),
    "MPHASIS.NS":     ("IT",            "IT Services"),
    "MRF.NS":         ("Auto",          "Tyres"),
    "NHPC.NS":        ("Power",         "Utilities"),
    "NMDC.NS":        ("Metals",        "Mining"),
    "OFSS.NS":        ("IT",            "IT Services"),
    "PAGEIND.NS":     ("Consumer",      "Apparel"),
    "PETRONET.NS":    ("Energy",        "Gas"),
    "PFC.NS":         ("Finance",       "Financial Services"),
    "PIIND.NS":       ("Chemicals",     "Specialty Chemicals"),
    "PNB.NS":         ("Banking",       "PSU Bank"),
    "RECLTD.NS":      ("Finance",       "Financial Services"),
    "SAIL.NS":        ("Metals",        "Steel"),
    "SBICARD.NS":     ("Finance",       "Financial Services"),
    "SBILIFE.NS":     ("Finance",       "Insurance"),
    "SHREECEM.NS":    ("Cement",        "Cement"),
    "TATACONSUM.NS":  ("FMCG",          "Consumer Goods"),
    "TORNTPHARM.NS":  ("Pharma",        "Pharmaceuticals"),
    "TRENT.NS":       ("Retail",        "Retail"),
    "VEDL.NS":        ("Metals",        "Mining"),
    "ZOMATO.NS":      ("Consumer",      "Food Delivery"),
    "ZYDUSLIFE.NS":   ("Pharma",        "Pharmaceuticals"),
}

symbols   = list(stocks.keys())
BENCHMARK = "^NSEI"

# ─────────────────────────────────────────────────────────────────
# DATA DOWNLOAD
# ─────────────────────────────────────────────────────────────────
@st.cache_data(ttl=600)
def load_data(syms):
    return yf.download(
        tickers=syms + [BENCHMARK],
        period="1y", interval="1d",
        group_by="ticker", auto_adjust=True, progress=False,
    )

data = load_data(symbols)

# ─────────────────────────────────────────────────────────────────
# INDICATORS
# ─────────────────────────────────────────────────────────────────
def ema_series(series, window):
    return EMAIndicator(series, window=window, fillna=True).ema_indicator()

def detect_pocket_pivot(df):
    up_day  = df["Close"] > df["Close"].shift(1)
    down_vol = pd.Series(
        np.where(df["Close"] < df["Close"].shift(1), df["Volume"], 0), index=df.index
    )
    return up_day & (df["Volume"] > down_vol.shift(1).rolling(10, min_periods=1).max())

def detect_rs_new_high(close_s, bench_s):
    al = pd.concat([close_s, bench_s], axis=1).dropna()
    al.columns = ["close", "bench"]
    al["rs"]      = al["close"] / al["bench"]
    lb            = min(len(al), 252)
    al["rs_high"] = al["rs"].rolling(lb, min_periods=30).max()
    al["px_high"] = al["close"].rolling(lb, min_periods=30).max()
    sig = (al["rs"] >= al["rs_high"] * 0.99) & ~(al["close"] >= al["px_high"] * 0.99)
    return al["rs"].reindex(close_s.index), sig.reindex(close_s.index, fill_value=False)

# ─────────────────────────────────────────────────────────────────
# RRG COMPUTATION
# ─────────────────────────────────────────────────────────────────
def compute_rrg(price_dict, bench_s, tail=10):
    rows = []
    for name, ps in price_dict.items():
        al = pd.concat([ps, bench_s], axis=1).dropna()
        if len(al) < 60:
            continue
        al.columns = ["ind", "bench"]
        pr       = (al["ind"] / al["bench"]) / (al["ind"].iloc[0] / al["bench"].iloc[0]) * 100
        rs_ratio = 100 * pr.ewm(span=10, adjust=False).mean() / pr.ewm(span=26, adjust=False).mean()
        rs_mom   = 100 * rs_ratio.ewm(span=10, adjust=False).mean() / rs_ratio.ewm(span=26, adjust=False).mean()
        r, m = rs_ratio.iloc[-1], rs_mom.iloc[-1]
        quad = ("Leading" if r >= 100 and m >= 100 else
                "Weakening" if r >= 100 else
                "Improving" if m >= 100 else "Lagging")
        rows.append({
            "Name": name, "RS_Ratio": round(r, 4), "RS_Momentum": round(m, 4),
            "Quadrant": quad,
            "tail_ratio": rs_ratio.iloc[-tail:].tolist(),
            "tail_mom":   rs_mom.iloc[-tail:].tolist(),
        })
    return pd.DataFrame(rows)

# ─────────────────────────────────────────────────────────────────
# ECHARTS BUILDERS
# ─────────────────────────────────────────────────────────────────
BG   = "#0E1117"
GRID = "#1E2130"
TEXT = "#C0C6D4"

def bar_chart(cats, vals, color_by_value=False):
    items = ([{"value": round(v, 2),
               "itemStyle": {"color": "#26A69A" if v >= 0 else "#EF5350"}}
              for v in vals]
             if color_by_value else [round(v, 2) for v in vals])
    return {
        "backgroundColor": BG,
        "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}},
        "grid":    {"left": "3%", "right": "3%", "bottom": "18%", "containLabel": True},
        "xAxis": {"type": "category", "data": cats,
                  "axisLabel": {"color": TEXT, "rotate": 35, "fontSize": 11},
                  "axisLine":  {"lineStyle": {"color": GRID}}},
        "yAxis": {"type": "value",
                  "axisLabel": {"color": TEXT},
                  "splitLine": {"lineStyle": {"color": GRID}}},
        "series": [{"type": "bar", "data": items,
                    "itemStyle": {} if color_by_value else {"color": "#64B5F6"}}],
    }

def treemap_chart(df):
    def chg_color(c):
        if c >  2: return "#1B5E20"
        if c >  0: return "#2E7D32"
        if c > -2: return "#B71C1C"
        return "#7F0000"

    sector_map = {}
    for _, row in df.iterrows():
        sector_map.setdefault(row["Sector"], []).append(row)

    children = [
        {"name": sec, "children": [
            {"name": r["Symbol"].replace(".NS", ""),
             "value": max(r["Momentum"], 1),
             "itemStyle": {"color": chg_color(r["Change%"])}}
            for r in rows
        ]}
        for sec, rows in sector_map.items()
    ]
    return {
        "backgroundColor": BG,
        "tooltip": {"trigger": "item", "formatter": "{b}"},
        "series": [{
            "type": "treemap", "data": children,
            "roam": False, "nodeClick": "zoomToNode",
            "label":      {"show": True, "fontSize": 11, "color": "#fff"},
            "upperLabel": {"show": True, "height": 26, "color": "#fff", "fontWeight": "bold"},
            "itemStyle":  {"borderColor": BG, "borderWidth": 2, "gapWidth": 2},
            "levels": [
                {"itemStyle": {"borderColor": "#555", "borderWidth": 3, "gapWidth": 3},
                 "upperLabel": {"show": True}},
                {"itemStyle": {"borderColor": BG, "borderWidth": 2, "gapWidth": 2}},
            ],
        }],
    }

def rrg_chart(rrg_df):
    QFILL = {"Leading": "rgba(38,166,154,0.10)", "Weakening": "rgba(255,193,7,0.10)",
              "Lagging": "rgba(239,83,80,0.10)",  "Improving": "rgba(100,181,246,0.10)"}
    QDOT  = {"Leading": "#26A69A", "Weakening": "#FFC107",
              "Lagging": "#EF5350", "Improving": "#64B5F6"}

    all_r = [v for _, r in rrg_df.iterrows() for v in r["tail_ratio"]]
    all_m = [v for _, r in rrg_df.iterrows() for v in r["tail_mom"]]
    pad = 0.35
    xmin = min(min(all_r)-pad, 99.4);  xmax = max(max(all_r)+pad, 100.6)
    ymin = min(min(all_m)-pad, 99.4);  ymax = max(max(all_m)+pad, 100.6)

    series = []
    for _, row in rrg_df.iterrows():
        c   = QDOT[row["Quadrant"]]
        pts = [[round(r, 4), round(m, 4)] for r, m in zip(row["tail_ratio"], row["tail_mom"])]
        # tail line
        series.append({"type": "line", "data": pts, "showSymbol": False,
                        "lineStyle": {"color": c, "width": 1.5, "type": "dashed", "opacity": 0.6},
                        "z": 1})
        # current dot + label
        series.append({
            "type": "scatter", "name": row["Name"],
            "data": [[round(row["RS_Ratio"], 4), round(row["RS_Momentum"], 4)]],
            "symbolSize": 14,
            "itemStyle": {"color": c, "borderColor": "#fff", "borderWidth": 1.5},
            "label": {"show": True, "formatter": row["Name"],
                      "position": "top", "color": "#fff", "fontSize": 10},
            "tooltip": {"formatter": (
                f"<b>{row['Name']}</b><br/>"
                f"Quadrant: {row['Quadrant']}<br/>"
                f"RS-Ratio: {row['RS_Ratio']}<br/>"
                f"RS-Mom: {row['RS_Momentum']}")},
            "z": 3,
        })

    # quad backgrounds
    series.append({
        "type": "scatter", "data": [],
        "markArea": {"silent": True, "data": [
            [{"coord": [100, 100],    "itemStyle": {"color": QFILL["Leading"]}},   {"coord": [xmax, ymax]}],
            [{"coord": [100, ymin],   "itemStyle": {"color": QFILL["Weakening"]}}, {"coord": [xmax, 100]}],
            [{"coord": [xmin, ymin],  "itemStyle": {"color": QFILL["Lagging"]}},   {"coord": [100, 100]}],
            [{"coord": [xmin, 100],   "itemStyle": {"color": QFILL["Improving"]}}, {"coord": [100, ymax]}],
        ]}, "z": 0,
    })

    return {
        "backgroundColor": BG,
        "tooltip": {"trigger": "item"},
        "legend":  {"show": False},
        "grid":    {"left": "8%", "right": "6%", "top": "8%", "bottom": "8%", "containLabel": True},
        "xAxis": {"type": "value", "min": xmin, "max": xmax,
                  "name": "← Lagging   RS-Ratio   Leading →",
                  "nameLocation": "middle", "nameGap": 30,
                  "nameTextStyle": {"color": TEXT, "fontSize": 11},
                  "axisLabel": {"color": TEXT, "fontSize": 10},
                  "splitLine": {"lineStyle": {"color": GRID}}},
        "yAxis": {"type": "value", "min": ymin, "max": ymax,
                  "name": "RS-Momentum",
                  "nameLocation": "middle", "nameGap": 50,
                  "nameTextStyle": {"color": TEXT, "fontSize": 11},
                  "axisLabel": {"color": TEXT, "fontSize": 10},
                  "splitLine": {"lineStyle": {"color": GRID}}},
        "series": series,
    }

def candlestick_chart(symbol, df, ema_sel):
    EMA_COLORS = {5: "#00FFFF", 10: "#FF8C00", 21: "#FFFF00", 50: "#FF00FF"}
    dates = df.index.strftime("%Y-%m-%d").tolist()
    ohlc  = [[round(float(o),2), round(float(c),2), round(float(l),2), round(float(h),2)]
              for o,c,l,h in zip(df["Open"], df["Close"], df["Low"], df["High"])]
    vol   = [int(v) for v in df["Volume"]]
    vcols = ["#26A69A" if c >= o else "#EF5350" for c,o in zip(df["Close"], df["Open"])]

    rs_data, rs_nh_pts = [], []
    if "RS_Line" in df.columns and df["RS_Line"].notna().any():
        base    = df["RS_Line"].dropna().iloc[0]
        rs_data = [round(float(v)/base*100, 4) if pd.notna(v) else None for v in df["RS_Line"]]
        for d, val, nh in zip(dates, rs_data, df["RS_NewHigh"]):
            if nh and val is not None:
                rs_nh_pts.append([d, val])

    pp_marks = []
    for d, row in df[df["PocketPivot"] == True].iterrows():
        pp_marks.append({"coord": [d.strftime("%Y-%m-%d"), round(float(row["Low"]) * 0.988, 2)],
                         "symbol": "triangle", "symbolSize": 14,
                         "itemStyle": {"color": "lime"}})

    series = [{
        "type": "candlestick", "name": symbol, "data": ohlc,
        "xAxisIndex": 0, "yAxisIndex": 0,
        "itemStyle": {"color": "#26A69A", "color0": "#EF5350",
                      "borderColor": "#26A69A", "borderColor0": "#EF5350"},
    }]
    if pp_marks:
        series[0]["markPoint"] = {"data": pp_marks, "label": {"show": False}}

    for e in ema_sel:
        col = f"EMA{e}"
        if col in df.columns:
            series.append({
                "type": "line", "name": f"EMA{e}",
                "data": [round(float(v), 2) for v in df[col]],
                "showSymbol": False,
                "lineStyle": {"color": EMA_COLORS[e], "width": 1.4},
                "xAxisIndex": 0, "yAxisIndex": 0,
            })

    series.append({
        "type": "bar", "name": "Volume",
        "data": [{"value": v, "itemStyle": {"color": c}} for v,c in zip(vol, vcols)],
        "xAxisIndex": 1, "yAxisIndex": 1, "barMaxWidth": 6,
    })

    if rs_data:
        series.append({
            "type": "line", "name": "RS Line", "data": rs_data,
            "showSymbol": False,
            "lineStyle": {"color": "#64B5F6", "width": 1.8},
            "xAxisIndex": 2, "yAxisIndex": 2,
        })
    if rs_nh_pts:
        series.append({
            "type": "scatter", "name": "RS New High ⭐", "data": rs_nh_pts,
            "symbol": "star", "symbolSize": 16,
            "itemStyle": {"color": "gold"},
            "xAxisIndex": 2, "yAxisIndex": 2,
        })

    return {
        "backgroundColor": BG,
        "tooltip": {"trigger": "axis", "axisPointer": {"type": "cross"}},
        "legend": {"data": [f"EMA{e}" for e in ema_sel] + ["RS New High ⭐"],
                   "top": 4, "textStyle": {"color": TEXT, "fontSize": 11}},
        "axisPointer": {"link": [{"xAxisIndex": "all"}]},
        "dataZoom": [
            {"type": "inside", "xAxisIndex": [0,1,2], "start": 0, "end": 100},
            {"type": "slider", "xAxisIndex": [0,1,2], "start": 0, "end": 100,
             "bottom": 2, "height": 22,
             "fillerColor": "rgba(100,181,246,0.15)", "borderColor": GRID},
        ],
        "grid": [
            {"left": "5%", "right": "2%", "top":    "6%",  "height": "54%"},
            {"left": "5%", "right": "2%", "top":    "64%", "height": "12%"},
            {"left": "5%", "right": "2%", "bottom": "8%",  "height": "12%"},
        ],
        "xAxis": [
            {"type": "category", "data": dates, "gridIndex": 0,
             "axisLabel": {"show": False}, "axisLine": {"lineStyle": {"color": GRID}}},
            {"type": "category", "data": dates, "gridIndex": 1,
             "axisLabel": {"show": False}, "axisLine": {"lineStyle": {"color": GRID}}},
            {"type": "category", "data": dates, "gridIndex": 2,
             "axisLabel": {"color": TEXT, "fontSize": 10, "rotate": 30},
             "axisLine": {"lineStyle": {"color": GRID}}},
        ],
        "yAxis": [
            {"scale": True, "gridIndex": 0, "position": "right",
             "splitLine": {"lineStyle": {"color": GRID}},
             "axisLabel": {"color": TEXT, "fontSize": 10}},
            {"scale": True, "gridIndex": 1, "position": "right",
             "splitLine": {"show": False},
             "axisLabel": {"color": TEXT, "fontSize": 9}},
            {"scale": True, "gridIndex": 2, "position": "right",
             "name": "RS", "nameTextStyle": {"color": "#64B5F6", "fontSize": 9},
             "splitLine": {"lineStyle": {"color": GRID}},
             "axisLabel": {"color": TEXT, "fontSize": 9}},
        ],
        "series": series,
    }

# ─────────────────────────────────────────────────────────────────
# BENCHMARK
# ─────────────────────────────────────────────────────────────────
try:
    benchmark_close = data[BENCHMARK]["Close"].dropna()
except Exception:
    benchmark_close = None

# ─────────────────────────────────────────────────────────────────
# MAIN INDICATOR LOOP
# ─────────────────────────────────────────────────────────────────
results, stock_dfs = [], {}

for symbol in symbols:
    try:
        df = data[symbol].copy().dropna()
        if len(df) < 50:
            continue
        df["RSI"]         = RSIIndicator(df["Close"], window=14, fillna=True).rsi()
        df["Range"]       = df["High"] - df["Low"]
        sma20             = SMAIndicator(df["Close"], 20).sma_indicator()
        sma50             = SMAIndicator(df["Close"], 50).sma_indicator()
        df["EMA5"]        = ema_series(df["Close"],  5)
        df["EMA10"]       = ema_series(df["Close"], 10)
        df["EMA21"]       = ema_series(df["Close"], 21)
        df["EMA50"]       = ema_series(df["Close"], 50)
        df["PocketPivot"] = detect_pocket_pivot(df)
        if benchmark_close is not None:
            df["RS_Line"], df["RS_NewHigh"] = detect_rs_new_high(df["Close"], benchmark_close)
        else:
            df["RS_Line"], df["RS_NewHigh"] = np.nan, False

        last, prev = df.iloc[-1], df.iloc[-2]
        change   = (last["Close"] - prev["Close"]) / prev["Close"] * 100
        nr7      = last["Range"] <= df["Range"].tail(7).min()
        momentum = max(0, min(
            (last["RSI"]/100)*40 + (change/5)*30 + (last["Close"]/sma20.iloc[-1])*30, 100))

        sector, industry = stocks[symbol]
        stock_dfs[symbol] = df
        results.append({
            "Symbol":      symbol,         "Sector":     sector,
            "Industry":    industry,       "Price":      round(float(last["Close"]), 2),
            "Change%":     round(float(change), 2),
            "RSI":         round(float(last["RSI"]), 1),
            "Momentum":    round(float(momentum), 1),
            "NR7":         bool(nr7),
            "PocketPivot": bool(last["PocketPivot"]),
            "RS_NewHigh":  bool(last["RS_NewHigh"]),
            "Above20DMA":  bool(last["Close"] > sma20.iloc[-1]),
            "Above50DMA":  bool(last["Close"] > sma50.iloc[-1]),
        })
    except Exception as e:
        st.warning(f"⚠️ Skipped {symbol}: {e}")

df_main      = pd.DataFrame(results)
sector_table = df_main.groupby("Sector").agg({"Change%": "mean", "Momentum": "mean", "RSI": "mean"}).reset_index()

# ─────────────────────────────────────────────────────────────────
# RRG DATA BUILD
# ─────────────────────────────────────────────────────────────────
def _make_index(sym_list):
    ss = []
    for s in sym_list:
        try:
            c = data[s]["Close"].dropna()
            if len(c) > 30:
                ss.append(c / c.iloc[0] * 100)
        except Exception:
            pass
    return pd.concat(ss, axis=1).mean(axis=1) if ss else None

ind_map = {}
sec_map = {}
for sym, (sec, ind) in stocks.items():
    ind_map.setdefault(ind, []).append(sym)
    sec_map.setdefault(sec, []).append(sym)

ind_price = {k: v for k, v in {k: _make_index(v) for k, v in ind_map.items()}.items() if v is not None}
sec_price = {k: v for k, v in {k: _make_index(v) for k, v in sec_map.items()}.items() if v is not None}

rrg_ind = compute_rrg(ind_price, benchmark_close) if benchmark_close is not None else pd.DataFrame()
rrg_sec = compute_rrg(sec_price, benchmark_close) if benchmark_close is not None else pd.DataFrame()

# ─────────────────────────────────────────────────────────────────
# SIDEBAR FILTERS
# ─────────────────────────────────────────────────────────────────
st.sidebar.title("Market Filters")
rsi_min   = st.sidebar.slider("RSI Minimum",      0, 100, 50)
mom_min   = st.sidebar.slider("Momentum Minimum", 0, 100, 40)
show_pp   = st.sidebar.checkbox("Pocket Pivot only",          False)
show_rsnh = st.sidebar.checkbox("RS New High (before price)", False)

filtered = df_main[(df_main["RSI"] > rsi_min) & (df_main["Momentum"] > mom_min)]
if show_pp:   filtered = filtered[filtered["PocketPivot"]]
if show_rsnh: filtered = filtered[filtered["RS_NewHigh"]]

# ═════════════════════════════════════════════════════════════════
# LAYOUT
# ═════════════════════════════════════════════════════════════════

# 1. Sector bar charts
c1, c2 = st.columns(2)
with c1:
    st.subheader("Sector Performance")
    st_echarts(bar_chart(sector_table["Sector"].tolist(),
                         sector_table["Change%"].tolist(), color_by_value=True), height=vh(42))
with c2:
    st.subheader("Sector Momentum")
    st_echarts(bar_chart(sector_table["Sector"].tolist(),
                         sector_table["Momentum"].tolist()), height=vh(42))

# 2. RRG
st.subheader("🔄 Relative Rotation Graph (RRG)")
tab1, tab2 = st.tabs(["By Industry", "By Sector"])
qi = {"Leading": "🟢", "Weakening": "🟡", "Lagging": "🔴", "Improving": "🔵"}

with tab1:
    if not rrg_ind.empty:
        st_echarts(rrg_chart(rrg_ind), height=vh(72))
        d = rrg_ind[["Name","Quadrant","RS_Ratio","RS_Momentum"]].copy()
        d["Quadrant"] = d["Quadrant"].map(lambda q: f"{qi.get(q,'')} {q}")
        st.dataframe(d.sort_values("Quadrant"), use_container_width=True, hide_index=True)
    else:
        st.info("RRG unavailable — benchmark data missing.")

with tab2:
    if not rrg_sec.empty:
        st_echarts(rrg_chart(rrg_sec), height=vh(72))
        d2 = rrg_sec[["Name","Quadrant","RS_Ratio","RS_Momentum"]].copy()
        d2["Quadrant"] = d2["Quadrant"].map(lambda q: f"{qi.get(q,'')} {q}")
        st.dataframe(d2.sort_values("Quadrant"), use_container_width=True, hide_index=True)
    else:
        st.info("RRG unavailable — benchmark data missing.")

r1,r2,r3,r4 = st.columns(4)
r1.success("🟢 **Leading** — Strong RS, rising momentum")
r2.warning("🟡 **Weakening** — Strong RS, fading momentum")
r3.error("🔴 **Lagging** — Weak RS, falling momentum")
r4.info("🔵 **Improving** — Weak RS, turning up")

st.divider()

# 3. Heatmap
st.subheader("Market Heatmap")
st_echarts(treemap_chart(df_main), height=vh(65))

# 4. Breadth
st.subheader("Market Breadth")
b20 = (df_main["Above20DMA"].sum() / len(df_main)) * 100
b50 = (df_main["Above50DMA"].sum() / len(df_main)) * 100
m1,m2,m3,m4 = st.columns(4)
m1.metric("Above 20 DMA",              f"{round(b20,1)}%")
m2.metric("Above 50 DMA",              f"{round(b50,1)}%")
m3.metric("Pocket Pivots Today",        int(df_main["PocketPivot"].sum()))
m4.metric("RS New High (Before Price)", int(df_main["RS_NewHigh"].sum()))

st.divider()

# 5. Candlestick
st.subheader("📈 Candlestick  ·  EMA  ·  Pocket Pivot  ·  RS Line")
cc1, cc2 = st.columns([2,1])
with cc1:
    chart_sym = st.selectbox("Select Stock", list(stock_dfs.keys()), index=0)
with cc2:
    ema_choices = st.multiselect("EMA Overlays", [5,10,21,50], default=[21,50])

if chart_sym in stock_dfs:
    st_echarts(candlestick_chart(chart_sym, stock_dfs[chart_sym], ema_choices), height=vh(88))
    l1,l2,l3 = st.columns(3)
    l1.info("🟢 **Pocket Pivot** — Up-day vol > highest down-vol of prior 10 sessions")
    l2.warning("⭐ **RS New High** — RS Line at new high before price breakout")
    l3.success("**EMA colours** — Cyan=5 · Orange=10 · Yellow=21 · Magenta=50")

st.divider()

# 6–8. Scanners
st.subheader("NR7 — Volatility Contraction")
nr7_t = df_main[df_main["NR7"]]
(st.info("No NR7 stocks today.") if nr7_t.empty
 else st.dataframe(nr7_t, use_container_width=True))

st.subheader("🟢 Pocket Pivot Scanner")
pp_t = df_main[df_main["PocketPivot"]].sort_values("Momentum", ascending=False)
(st.info("No Pocket Pivots today.") if pp_t.empty
 else st.dataframe(pp_t, use_container_width=True))

st.subheader("⭐ RS New High Before Price High")
st.caption("RS Line vs Nifty 50 at a new high while price hasn't broken out — early-entry signal.")
rs_t = df_main[df_main["RS_NewHigh"]].sort_values("Momentum", ascending=False)
(st.info("No RS New High signals today.") if rs_t.empty
 else st.dataframe(rs_t, use_container_width=True))

# 9. Momentum leaders
st.subheader("Top Momentum Stocks")
leaders = df_main.sort_values("Momentum", ascending=False).head(10)
st_echarts(bar_chart(
    leaders["Symbol"].str.replace(".NS","",regex=False).tolist(),
    leaders["Momentum"].tolist()
), height=vh(40))

# 10. Screener
st.subheader("📋 Stock Screener")
disp = filtered.copy()
for col in ["NR7","PocketPivot","RS_NewHigh","Above20DMA","Above50DMA"]:
    disp[col] = disp[col].map({True: "✅", False: ""})
st.dataframe(disp.sort_values("Momentum", ascending=False), use_container_width=True)

st.caption(f"Last Updated : {datetime.now().strftime('%d %b %Y  %H:%M:%S')}")
