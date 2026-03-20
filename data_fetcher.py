"""
Data Fetcher v3
- Yahoo Finance v8 primary + NSE India fallback
- FII/DII flow data
- Options chain (PCR, Max Pain, IV)
- Breadth (full universe)
- Earnings / corporate actions flag
- RS Rank (percentile) computed post-fetch
- Minervini template validation per stock
"""

import time, math, requests, threading
import streamlit as st
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional, List
from datetime import datetime, timedelta

from nifty_indices import NIFTY_INDICES, SECTORS, get_all_stocks, get_sector_for_symbol
from technical_indicators import (
    calculate_rsi, calculate_ema, calculate_sma, calculate_dma_status,
    calculate_momentum_score, calculate_volume_ratio, calculate_volume_profile,
    calculate_relative_strength, calculate_rrg_values, get_rrg_quadrant,
    validate_minervini_template, calculate_rs_rank, assign_grade,
    detect_nr7, detect_nr4, detect_vcp, detect_pocket_pivot, detect_rs_divergence,
    calculate_advance_decline, count_new_highs_lows, calculate_pct_above_ma,
    calculate_correlation_matrix, check_price_continuity,
)
from watchlist import (
    init_db, record_rrg_snapshot, get_all_rrg_trails,
    evaluate_alerts, record_breadth,
)

# ── Init DB once ──────────────────────────────────────────────────────────────
init_db()

YAHOO_BASE  = "https://query1.finance.yahoo.com/v8/finance/chart"
NSE_BASE    = "https://www.nseindia.com/api"
YH_HEADERS  = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
NSE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept":         "application/json, text/plain, */*",
    "Accept-Language":"en-US,en;q=0.9",
    "Referer":        "https://www.nseindia.com/",
    "X-Requested-With":"XMLHttpRequest",
}

# ── NSE session (cookie is required) ─────────────────────────────────────────
_nse_session = requests.Session()
_nse_session.headers.update(NSE_HEADERS)
_nse_cookie_ts = 0.0

def _refresh_nse_session():
    global _nse_cookie_ts
    if time.time() - _nse_cookie_ts < 3600:
        return
    try:
        _nse_session.get("https://www.nseindia.com", timeout=8)
        _nse_cookie_ts = time.time()
    except Exception:
        pass


# ─── Yahoo Finance fetch (primary) ───────────────────────────────────────────

@st.cache_data(ttl=60, show_spinner=False)
def fetch_chart(symbol: str, range_: str = "6mo", interval: str = "1d") -> dict:
    """Single Yahoo v8 fetch. Returns {ohlcv, meta} or {ohlcv:[], meta:None}."""
    url = f"{YAHOO_BASE}/{requests.utils.quote(symbol)}?range={range_}&interval={interval}&includePrePost=false"
    try:
        r = requests.get(url, headers=YH_HEADERS, timeout=10)
        r.raise_for_status()
        data   = r.json()
        result = data.get("chart", {}).get("result", [None])[0]
        if not result:
            return {"ohlcv": [], "meta": None}

        m = result.get("meta", {})
        meta = {
            "symbol":       m.get("symbol", symbol),
            "short_name":   m.get("shortName", symbol),
            "price":        m.get("regularMarketPrice", 0.0),
            "prev_close":   m.get("previousClose") or m.get("chartPreviousClose", 0.0),
            "volume":       m.get("regularMarketVolume", 0),
            "day_high":     m.get("regularMarketDayHigh", 0.0),
            "day_low":      m.get("regularMarketDayLow",  0.0),
            "week52_high":  m.get("fiftyTwoWeekHigh", 0.0),
            "week52_low":   m.get("fiftyTwoWeekLow",  0.0),
            "avg_volume_3m":m.get("averageDailyVolume3Month", 0),
            "exchange_tz":  m.get("exchangeTimezoneName", "Asia/Kolkata"),
        }

        ohlcv, ts = [], result.get("timestamp", [])
        q = (result.get("indicators", {}).get("quote") or [{}])[0]
        for i, t in enumerate(ts):
            c = (q.get("close") or [])[i] if i < len(q.get("close") or []) else None
            o = (q.get("open")  or [])[i] if i < len(q.get("open")  or []) else None
            if c is not None and o is not None:
                ohlcv.append({
                    "date":   time.strftime("%Y-%m-%d", time.gmtime(t)),
                    "open":   o or 0.0,
                    "high":   (q.get("high",   [0.0] * (i+1))[i] or 0.0),
                    "low":    (q.get("low",    [0.0] * (i+1))[i] or 0.0),
                    "close":  c or 0.0,
                    "volume": (q.get("volume", [0]   * (i+1))[i] or 0),
                })
        return {"ohlcv": ohlcv, "meta": meta}
    except Exception as e:
        return {"ohlcv": [], "meta": None}


@st.cache_data(ttl=60, show_spinner=False)
def fetch_chart_nse_fallback(symbol: str, range_: str = "6mo") -> dict:
    """Try Yahoo first; if empty, attempt NSE quote as minimal fallback."""
    result = fetch_chart(symbol, range_)
    if result["ohlcv"]:
        return result

    # NSE fallback — gets only current quote, no OHLCV history
    _refresh_nse_session()
    clean = symbol.replace(".NS", "").replace("-", "%2D").replace("&", "%26")
    try:
        r = _nse_session.get(f"{NSE_BASE}/quote-equity?symbol={clean}", timeout=8)
        if r.status_code == 200:
            d  = r.json()
            pd_ = d.get("priceInfo", {})
            meta = {
                "symbol":       symbol,
                "short_name":   d.get("info", {}).get("companyName", symbol),
                "price":        pd_.get("lastPrice", 0.0),
                "prev_close":   pd_.get("previousClose", 0.0),
                "volume":       d.get("marketDeptOrderBook", {}).get("tradeInfo", {}).get("totalTradedVolume", 0),
                "day_high":     pd_.get("intraDayHighLow", {}).get("max", 0.0),
                "day_low":      pd_.get("intraDayHighLow", {}).get("min", 0.0),
                "week52_high":  pd_.get("weekHighLow", {}).get("max", 0.0),
                "week52_low":   pd_.get("weekHighLow", {}).get("min", 0.0),
                "avg_volume_3m":0,
                "exchange_tz":  "Asia/Kolkata",
                "nse_fallback": True,
            }
            return {"ohlcv": [], "meta": meta}
    except Exception:
        pass
    return {"ohlcv": [], "meta": None}


# ─── Market hours check ───────────────────────────────────────────────────────

def is_market_open() -> bool:
    """NSE trading hours: Mon–Fri 09:15–15:30 IST (UTC+5:30)."""
    now_utc = datetime.utcnow()
    now_ist = now_utc + timedelta(hours=5, minutes=30)
    if now_ist.weekday() >= 5:
        return False
    open_t  = now_ist.replace(hour=9,  minute=15, second=0, microsecond=0)
    close_t = now_ist.replace(hour=15, minute=30, second=0, microsecond=0)
    return open_t <= now_ist <= close_t


# ─── FII / DII Flow ──────────────────────────────────────────────────────────

@st.cache_data(ttl=1800, show_spinner=False)
def fetch_fii_dii() -> list:
    """
    NSE FII/DII provisional data.
    Returns list of {date, fii_net, dii_net} dicts — last 30 trading days.
    Falls back to empty list if NSE API is unavailable.
    """
    _refresh_nse_session()
    try:
        r = _nse_session.get(f"{NSE_BASE}/fiidiiTradeReact", timeout=10)
        if r.status_code != 200:
            return _synthetic_fii_dii()
        data = r.json()
        result = []
        for row in data:
            try:
                result.append({
                    "date":    row.get("date", ""),
                    "fii_net": float(str(row.get("fiiNet", "0")).replace(",", "") or 0),
                    "dii_net": float(str(row.get("diiNet", "0")).replace(",", "") or 0),
                    "fii_buy": float(str(row.get("fiiBuy", "0")).replace(",", "") or 0),
                    "fii_sell":float(str(row.get("fiiSell","0")).replace(",", "") or 0),
                    "dii_buy": float(str(row.get("diiBuy", "0")).replace(",", "") or 0),
                    "dii_sell":float(str(row.get("diiSell","0")).replace(",", "") or 0),
                })
            except Exception:
                continue
        return result[-30:] if result else _synthetic_fii_dii()
    except Exception:
        return _synthetic_fii_dii()


def _synthetic_fii_dii() -> list:
    """Placeholder data when NSE API is unavailable."""
    import random; random.seed(42)
    base = datetime.utcnow()
    rows = []
    for i in range(30):
        d = base - timedelta(days=i)
        if d.weekday() < 5:
            fii = random.uniform(-3000, 3000)
            dii = random.uniform(-1000, 2000)
            rows.append({"date": d.strftime("%d-%b-%Y"), "fii_net": fii, "dii_net": dii,
                         "fii_buy":abs(fii)+1000,"fii_sell":abs(fii),"dii_buy":abs(dii)+500,"dii_sell":abs(dii),
                         "_synthetic": True})
    return rows[::-1]


# ─── Options Chain ────────────────────────────────────────────────────────────

@st.cache_data(ttl=300, show_spinner=False)
def fetch_options_data(symbol: str = "NIFTY") -> dict:
    """
    Fetches NSE options chain. Returns PCR, max pain, IV data.
    Falls back to None values if unavailable.
    """
    _refresh_nse_session()
    try:
        url = f"{NSE_BASE}/option-chain-indices?symbol={symbol}"
        r   = _nse_session.get(url, timeout=12)
        if r.status_code != 200:
            return _empty_options()

        data    = r.json()
        records = data.get("records", {})
        oc      = records.get("data", [])
        spot    = records.get("underlyingValue", 0)

        total_call_oi = total_put_oi = 0
        strikes = {}

        for row in oc:
            strike = row.get("strikePrice", 0)
            ce = row.get("CE", {})
            pe = row.get("PE", {})
            c_oi = ce.get("openInterest", 0) or 0
            p_oi = pe.get("openInterest", 0) or 0
            total_call_oi += c_oi
            total_put_oi  += p_oi
            strikes[strike] = strikes.get(strike, {"c_oi": 0, "p_oi": 0, "c_iv": 0, "p_iv": 0})
            strikes[strike]["c_oi"] += c_oi
            strikes[strike]["p_oi"] += p_oi
            strikes[strike]["c_iv"]  = ce.get("impliedVolatility", 0) or 0
            strikes[strike]["p_iv"]  = pe.get("impliedVolatility", 0) or 0

        pcr = total_put_oi / total_call_oi if total_call_oi > 0 else 0

        # Max Pain = strike where total OI loss for option buyers is maximized
        max_pain = _calc_max_pain(strikes, spot)

        # ATM IV
        atm = min(strikes.keys(), key=lambda k: abs(k - spot)) if strikes else 0
        atm_iv = strikes.get(atm, {}).get("c_iv", 0)

        # Top strikes by OI (support/resistance)
        top_call = sorted(strikes.items(), key=lambda x: x[1]["c_oi"], reverse=True)[:5]
        top_put  = sorted(strikes.items(), key=lambda x: x[1]["p_oi"], reverse=True)[:5]

        return {
            "symbol":        symbol,
            "spot":          spot,
            "pcr":           round(pcr, 3),
            "pcr_signal":    "Bullish" if pcr > 1.2 else "Bearish" if pcr < 0.7 else "Neutral",
            "max_pain":      max_pain,
            "atm_iv":        atm_iv,
            "total_call_oi": total_call_oi,
            "total_put_oi":  total_put_oi,
            "top_call_strikes": [{"strike": k, "oi": v["c_oi"]} for k, v in top_call],
            "top_put_strikes":  [{"strike": k, "oi": v["p_oi"]} for k, v in top_put],
            "strikes_data":  strikes,
        }
    except Exception:
        return _empty_options()


def _calc_max_pain(strikes: dict, spot: float) -> float:
    if not strikes:
        return spot
    min_pain, max_pain_strike = float("inf"), spot
    for k in strikes:
        pain = sum(
            max(0, k - sk) * v["c_oi"] + max(0, sk - k) * v["p_oi"]
            for sk, v in strikes.items()
        )
        if pain < min_pain:
            min_pain, max_pain_strike = pain, k
    return max_pain_strike


def _empty_options() -> dict:
    return {"symbol": "NIFTY", "spot": 0, "pcr": 0, "pcr_signal": "N/A",
            "max_pain": 0, "atm_iv": 0, "total_call_oi": 0, "total_put_oi": 0,
            "top_call_strikes": [], "top_put_strikes": [], "strikes_data": {}}


# ─── Earnings Calendar ────────────────────────────────────────────────────────

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_upcoming_earnings() -> List[str]:
    """
    Returns list of NSE symbols with results announced in next 7 days.
    Uses NSE corporate actions API.
    """
    _refresh_nse_session()
    try:
        today = datetime.utcnow() + timedelta(hours=5, minutes=30)
        fmt   = "%d-%m-%Y"
        params = {
            "index": "equities",
            "from_date": today.strftime(fmt),
            "to_date": (today + timedelta(days=7)).strftime(fmt),
        }
        r = _nse_session.get(f"{NSE_BASE}/corporate-actions", params=params, timeout=10)
        if r.status_code != 200:
            return []
        data = r.json() if isinstance(r.json(), list) else r.json().get("data", [])
        symbols = set()
        for row in data:
            purpose = (row.get("purpose") or row.get("subject") or "").lower()
            if any(kw in purpose for kw in ["results", "quarterly", "financial"]):
                sym = row.get("symbol", "")
                if sym:
                    symbols.add(sym + ".NS")
        return list(symbols)
    except Exception:
        return []


# ─── Process single stock ─────────────────────────────────────────────────────

def process_stock(symbol: str, bench_ohlcv: list, sector_name: str = "Unknown",
                  earnings_symbols: list = None) -> Optional[dict]:
    res   = fetch_chart_nse_fallback(symbol, "6mo")
    ohlcv = res["ohlcv"]
    meta  = res["meta"]

    if len(ohlcv) < 20 or not meta:
        return None

    # Sanity check for corporate action gaps
    bad_bars = check_price_continuity(ohlcv)

    closes  = [d["close"]  for d in ohlcv]
    volumes = [d["volume"] for d in ohlcv]

    rsi_arr = calculate_rsi(closes)
    ema5    = calculate_ema(closes, 5)
    ema10   = calculate_ema(closes, 10)
    ema21   = calculate_ema(closes, 21)
    ema50   = calculate_ema(closes, 50)
    dma     = calculate_dma_status(closes)

    nr7  = detect_nr7(ohlcv)
    nr4  = detect_nr4(ohlcv)
    vcp  = detect_vcp(ohlcv)
    pp   = detect_pocket_pivot(ohlcv)
    rsd  = detect_rs_divergence(ohlcv, bench_ohlcv) if len(bench_ohlcv) >= 20 else [False]*len(ohlcv)

    mom   = calculate_momentum_score(ohlcv)
    volr  = calculate_volume_ratio(volumes)
    bc    = [d["close"] for d in bench_ohlcv]
    rs    = calculate_relative_strength(closes, bc)
    rrg   = calculate_rrg_values(closes, bc)
    quad  = get_rrg_quadrant(rrg["rs_ratio"], rrg["rs_momentum"])

    # Minervini (needs 1y+ data — use what we have, flag if insufficient)
    minervini = validate_minervini_template(ohlcv)

    # Volume profile (last 60 bars)
    vp = calculate_volume_profile(ohlcv[-60:], bins=20)

    price   = meta["price"]
    prev    = meta["prev_close"]
    change  = price - prev
    chg_pct = change / prev * 100 if prev else 0.0

    has_earnings = (earnings_symbols or []) and symbol in (earnings_symbols or [])

    return {
        "symbol":   symbol,
        "name":     meta["short_name"],
        "sector":   sector_name,
        "price":    price,
        "change":   change,
        "change_pct": chg_pct,
        "volume":   meta["volume"],
        "avg_volume": meta["avg_volume_3m"],
        "high52w":  meta["week52_high"],
        "low52w":   meta["week52_low"],
        "rsi":      rsi_arr[-1],
        "ema5":     ema5[-1],   "ema10": ema10[-1],
        "ema21":    ema21[-1],  "ema50": ema50[-1],
        "dma20":    dma["dma20"], "dma50": dma["dma50"], "dma200": dma["dma200"],
        "above20dma": dma["above20"], "above50dma": dma["above50"], "above200dma": dma["above200"],
        "is_nr7":   nr7[-1],  "is_nr4": nr4[-1],
        "is_vcp":   vcp[-1],  "is_pocket_pivot": pp[-1],
        "is_rs_div": rsd[-1] if rsd else False,
        "momentum": mom,
        "vol_ratio": volr,
        "rs":        rs,
        "rs_ratio":  rrg["rs_ratio"],
        "rs_momentum": rrg["rs_momentum"],
        "rrg_quadrant": quad,
        "rs_rank":   50,  # filled in post-processing
        "minervini_passes": minervini["passes"],
        "minervini_criteria_met": minervini.get("criteria_met", 0),
        "minervini_detail": minervini,
        "volume_profile": vp,
        "has_earnings": has_earnings,
        "data_gap": len(bad_bars) > 0,
        "nse_fallback": meta.get("nse_fallback", False),
        "ohlcv":    ohlcv[-60:],
    }


# ─── Sector data ─────────────────────────────────────────────────────────────

@st.cache_data(ttl=60, show_spinner=False)
def fetch_sector_data(sector_name: str) -> Optional[dict]:
    sector = next((s for s in SECTORS if s["name"] == sector_name), None)
    if not sector: return None

    bench       = fetch_chart("^NSEI", "6mo")["ohlcv"]
    bench_c     = [d["close"] for d in bench]
    earnings_s  = fetch_upcoming_earnings()

    stocks = []
    with ThreadPoolExecutor(max_workers=6) as pool:
        futs = {pool.submit(process_stock, s["symbol"], bench, sector_name, earnings_s): s
                for s in sector["stocks"]}
        for f in as_completed(futs):
            try:
                r = f.result()
                if r: stocks.append(r)
            except Exception: pass

    if not stocks: return None

    # RS rank within sector
    rs_scores = [s["rs"] for s in stocks]
    ranks = calculate_rs_rank(rs_scores)
    for s, rk in zip(stocks, ranks): s["rs_rank"] = rk

    avg = lambda key: sum(s.get(key,0) for s in stocks) / max(1,len(stocks))
    breadth = sum(1 for s in stocks if s["above20dma"]) / max(1,len(stocks)) * 100

    sh = fetch_chart(sector["index_symbol"], "6mo")["ohlcv"]
    rrg = calculate_rrg_values([d["close"] for d in sh], bench_c) if sh else {"rs_ratio":100,"rs_momentum":100}

    # Record RRG trail
    record_rrg_snapshot(sector_name, rrg["rs_ratio"], rrg["rs_momentum"])

    sorted_s = sorted(stocks, key=lambda s: s["change_pct"], reverse=True)
    return {
        "name": sector["name"], "color": sector["color"],
        "change": avg("change_pct"), "rsi": avg("rsi"), "momentum": avg("momentum"),
        "breadth": breadth, "vol_ratio": avg("vol_ratio"),
        "rs_ratio": rrg["rs_ratio"], "rs_momentum": rrg["rs_momentum"],
        "rrg_quadrant": get_rrg_quadrant(rrg["rs_ratio"], rrg["rs_momentum"]),
        "stocks": stocks,
        "top_gainers": sorted_s[:3], "top_losers": sorted_s[-3:][::-1],
        "industries": list(dict.fromkeys(s["industry"] for s in sector["stocks"])),
    }


@st.cache_data(ttl=60, show_spinner=False)
def fetch_all_sectors() -> list:
    bench    = fetch_chart("^NSEI", "6mo")["ohlcv"]
    bench_c  = [d["close"] for d in bench]
    earnings = fetch_upcoming_earnings()
    results  = []

    def _proc_sector(sector):
        stocks = []
        with ThreadPoolExecutor(max_workers=5) as pool:
            futs = {pool.submit(process_stock, s["symbol"], bench, sector["name"], earnings): s
                    for s in sector["stocks"]}
            for f in as_completed(futs):
                try:
                    r = f.result()
                    if r: stocks.append(r)
                except Exception: pass

        if not stocks:
            return {"name": sector["name"], "color": sector["color"],
                    "index_symbol": sector["index_symbol"], "change": 0, "rsi": 50,
                    "momentum": 50, "breadth": 0, "vol_ratio": 1,
                    "rs_ratio": 100, "rs_momentum": 100, "rrg_quadrant": "Lagging",
                    "top_gainers": [], "top_losers": [], "stock_count": len(sector["stocks"])}

        avg = lambda k: sum(s.get(k,0) for s in stocks) / max(1,len(stocks))
        breadth = sum(1 for s in stocks if s["above20dma"]) / max(1,len(stocks)) * 100
        sh  = fetch_chart(sector["index_symbol"], "6mo")["ohlcv"]
        rrg = calculate_rrg_values([d["close"] for d in sh], bench_c) if sh else {"rs_ratio":100,"rs_momentum":100}
        record_rrg_snapshot(sector["name"], rrg["rs_ratio"], rrg["rs_momentum"])
        sorted_s = sorted(stocks, key=lambda s: s["change_pct"], reverse=True)
        return {
            "name": sector["name"], "color": sector["color"],
            "index_symbol": sector["index_symbol"],
            "change": avg("change_pct"), "rsi": avg("rsi"), "momentum": avg("momentum"),
            "breadth": breadth, "vol_ratio": avg("vol_ratio"),
            "rs_ratio": rrg["rs_ratio"], "rs_momentum": rrg["rs_momentum"],
            "rrg_quadrant": get_rrg_quadrant(rrg["rs_ratio"], rrg["rs_momentum"]),
            "top_gainers": sorted_s[:3], "top_losers": sorted_s[-3:][::-1],
            "stock_count": len(sector["stocks"]),
        }

    with ThreadPoolExecutor(max_workers=3) as pool:
        futs = {pool.submit(_proc_sector, s): s for s in SECTORS}
        for f in as_completed(futs):
            try: results.append(f.result())
            except Exception: pass

    order = {s["name"]: i for i, s in enumerate(SECTORS)}
    return sorted(results, key=lambda r: order.get(r["name"], 99))


@st.cache_data(ttl=60, show_spinner=False)
def fetch_indices() -> list:
    results = []
    for name, sym in NIFTY_INDICES.items():
        res   = fetch_chart(sym, "3mo")
        ohlcv = res["ohlcv"]; meta = res["meta"]
        if not meta: continue
        closes = [d["close"] for d in ohlcv]
        rsi_arr = calculate_rsi(closes)
        results.append({
            "name": name, "symbol": sym,
            "price":      meta["price"],
            "change":     meta["price"] - meta["prev_close"],
            "change_pct": (meta["price"] - meta["prev_close"]) / meta["prev_close"] * 100 if meta["prev_close"] else 0,
            "rsi":        rsi_arr[-1] if rsi_arr else float("nan"),
            "volume":     meta["volume"],
            "week52_high": meta.get("week52_high", 0),
            "week52_low":  meta.get("week52_low",  0),
        })
    return results


@st.cache_data(ttl=60, show_spinner=False)
def fetch_screener(rsi_min=0, rsi_max=100, momentum_min=0, volume_breakout=False,
                   pattern="all", rrg_quadrant="all", dma_filter="all",
                   minervini_only=False) -> list:
    bench    = fetch_chart("^NSEI", "6mo")["ohlcv"]
    earnings = fetch_upcoming_earnings()

    # Sector momentum map for grading
    sector_mom = {}
    for sec in SECTORS:
        sh = fetch_chart(sec["index_symbol"], "3mo")["ohlcv"]
        closes = [d["close"] for d in sh]
        if len(closes) >= 20:
            sector_mom[sec["name"]] = 50 + (closes[-1] - closes[-20]) / closes[-20] * 100
        else:
            sector_mom[sec["name"]] = 50.0

    all_stocks_cfg = get_all_stocks()
    stocks = []
    with ThreadPoolExecutor(max_workers=12) as pool:
        futs = {pool.submit(process_stock, s["symbol"], bench, s["sector"], earnings): s
                for s in all_stocks_cfg}
        for f in as_completed(futs):
            try:
                r = f.result()
                if r: stocks.append(r)
            except Exception: pass

    # Compute RS Rank across full universe
    rs_scores = [s["rs"] for s in stocks]
    ranks = calculate_rs_rank(rs_scores)
    for s, rk in zip(stocks, ranks):
        s["rs_rank"] = rk

    # Assign grades with real sector strength
    for s in stocks:
        ss = sector_mom.get(s["sector"], 50.0)
        g  = assign_grade(ss, s["momentum"], s["rs_rank"])
        s["grade"] = g["grade"]
        s["grade_desc"] = g["description"]

    # Fire alerts
    evaluate_alerts(stocks)

    # Breadth snapshot
    ad  = calculate_advance_decline(stocks)
    hl  = count_new_highs_lows(stocks)
    pma = calculate_pct_above_ma(stocks)
    record_breadth(ad["advances"], ad["declines"], hl["new_highs"], hl["new_lows"],
                   pma["above_20dma"], pma["above_50dma"])

    # Apply filters
    def passes(s):
        rsi = s.get("rsi", 0) or 0
        if not (rsi_min <= rsi <= rsi_max): return False
        if s["momentum"] < momentum_min: return False
        if volume_breakout and s["vol_ratio"] <= 1.5: return False
        if minervini_only and not s["minervini_passes"]: return False
        if pattern == "nr7"        and not s["is_nr7"]: return False
        if pattern == "nr4"        and not s["is_nr4"]: return False
        if pattern == "vcp"        and not s["is_vcp"]: return False
        if pattern == "pocketpivot"and not s["is_pocket_pivot"]: return False
        if pattern == "rsdiv"      and not s["is_rs_div"]: return False
        if pattern == "minervini"  and not s["minervini_passes"]: return False
        if rrg_quadrant != "all"   and s["rrg_quadrant"] != rrg_quadrant: return False
        if dma_filter == "above20"  and not s["above20dma"]:  return False
        if dma_filter == "above50"  and not s["above50dma"]:  return False
        if dma_filter == "above200" and not s["above200dma"]: return False
        if dma_filter == "allAbove" and not (s["above20dma"] and s["above50dma"] and s["above200dma"]): return False
        return True

    return [s for s in stocks if passes(s)]


@st.cache_data(ttl=60, show_spinner=False)
def fetch_breadth_universe() -> dict:
    """Full breadth computation across all sectors."""
    bench  = fetch_chart("^NSEI", "6mo")["ohlcv"]
    stocks = []
    with ThreadPoolExecutor(max_workers=12) as pool:
        futs = {pool.submit(process_stock, s["symbol"], bench, s["sector"]): s
                for s in get_all_stocks()}
        for f in as_completed(futs):
            try:
                r = f.result()
                if r: stocks.append(r)
            except Exception: pass
    ad  = calculate_advance_decline(stocks)
    hl  = count_new_highs_lows(stocks)
    pma = calculate_pct_above_ma(stocks)
    return {"stocks": stocks, "ad": ad, "hl": hl, "pma": pma}


@st.cache_data(ttl=300, show_spinner=False)
def fetch_sector_correlation() -> dict:
    """30-day return correlation matrix across all sector indices."""
    returns = {}
    for sec in SECTORS:
        sh = fetch_chart(sec["index_symbol"], "3mo")["ohlcv"]
        if len(sh) < 5: continue
        closes = [d["close"] for d in sh]
        rets = [(closes[i] - closes[i-1]) / closes[i-1] for i in range(1, len(closes))]
        returns[sec["name"]] = rets
    return calculate_correlation_matrix(returns, window=30)


@st.cache_data(ttl=60, show_spinner=False)
def fetch_watchlist_stocks() -> list:
    from watchlist import get_watchlist_symbols
    symbols = get_watchlist_symbols()
    if not symbols: return []
    bench = fetch_chart("^NSEI", "6mo")["ohlcv"]
    stocks = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        futs = {pool.submit(process_stock, sym, bench): sym for sym in symbols}
        for f in as_completed(futs):
            try:
                r = f.result()
                if r: stocks.append(r)
            except Exception: pass
    return stocks
