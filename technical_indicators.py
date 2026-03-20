"""
Technical Indicators v3 — Full professional suite
New additions: Minervini 5-criteria, RS Rank, Volume Profile, Correlation,
Breadth (A/D line, McClellan, 52w H/L), corporate action sanity check.
"""

import math
from typing import List, Dict, Optional, Tuple


# ─── Moving Averages ──────────────────────────────────────────────────────────

def calculate_sma(data: List[float], period: int) -> List[float]:
    result = [float("nan")] * len(data)
    for i in range(period - 1, len(data)):
        result[i] = sum(data[i - period + 1 : i + 1]) / period
    return result


def calculate_ema(data: List[float], period: int) -> List[float]:
    result = [float("nan")] * len(data)
    if len(data) < period:
        return result
    mult = 2.0 / (period + 1)
    ema = sum(data[:period]) / period
    result[period - 1] = ema
    for i in range(period, len(data)):
        ema = (data[i] - ema) * mult + ema
        result[i] = ema
    return result


# ─── RSI (Wilder's Smoothing) ─────────────────────────────────────────────────

def calculate_rsi(closes: List[float], period: int = 14) -> List[float]:
    n = len(closes)
    result = [float("nan")] * n
    if n < period + 1:
        return result
    changes = [closes[i] - closes[i - 1] for i in range(1, n)]
    avg_gain = sum(c for c in changes[:period] if c > 0) / period
    avg_loss = sum(abs(c) for c in changes[:period] if c < 0) / period
    result[period] = 100.0 if avg_loss == 0 else 100.0 - 100.0 / (1 + avg_gain / avg_loss)
    for i in range(period + 1, n):
        c = changes[i - 1]
        avg_gain = (avg_gain * (period - 1) + (c if c > 0 else 0)) / period
        avg_loss = (avg_loss * (period - 1) + (abs(c) if c < 0 else 0)) / period
        result[i] = 100.0 if avg_loss == 0 else 100.0 - 100.0 / (1 + avg_gain / avg_loss)
    return result


# ─── DMA Status ───────────────────────────────────────────────────────────────

def calculate_dma_status(closes: List[float]) -> dict:
    s20, s50, s200 = calculate_sma(closes, 20), calculate_sma(closes, 50), calculate_sma(closes, 200)
    last = closes[-1]
    d20, d50, d200 = s20[-1], s50[-1], s200[-1]
    return {
        "above20": last > d20 if not math.isnan(d20) else False,
        "above50": last > d50 if not math.isnan(d50) else False,
        "above200": not math.isnan(d200) and last > d200,
        "dma20":  0.0 if math.isnan(d20)  else d20,
        "dma50":  0.0 if math.isnan(d50)  else d50,
        "dma200": 0.0 if math.isnan(d200) else d200,
        "sma20_series": s20, "sma50_series": s50, "sma200_series": s200,
    }


# ─── Pattern Detection ────────────────────────────────────────────────────────

def detect_nr7(data: List[dict]) -> List[bool]:
    result = [False] * len(data)
    for i in range(6, len(data)):
        ranges = [data[j]["high"] - data[j]["low"] for j in range(i - 6, i + 1)]
        result[i] = all(r > ranges[-1] for r in ranges[:-1])
    return result


def detect_nr4(data: List[dict]) -> List[bool]:
    result = [False] * len(data)
    for i in range(3, len(data)):
        ranges = [data[j]["high"] - data[j]["low"] for j in range(i - 3, i + 1)]
        result[i] = all(r > ranges[-1] for r in ranges[:-1])
    return result


def detect_vcp(data: List[dict], min_contractions: int = 3) -> List[bool]:
    result = [False] * len(data)
    for i in range(30, len(data)):
        weekly = []
        for w in range(4):
            s, e = i - (w + 1) * 5, i - w * 5
            if s < 0: break
            weekly.append(max(d["high"] for d in data[s:e]) - min(d["low"] for d in data[s:e]))
        contractions = sum(1 for r in range(1, len(weekly)) if weekly[r] > weekly[r - 1])
        result[i] = contractions >= min_contractions - 1
    return result


def detect_pocket_pivot(data: List[dict], lookback: int = 10) -> List[bool]:
    result = [False] * len(data)
    for i in range(lookback, len(data)):
        if data[i]["close"] <= data[i - 1]["close"]:
            continue
        max_down = max((data[j]["volume"] for j in range(i - lookback, i)
                        if j > 0 and data[j]["close"] < data[j - 1]["close"]), default=0)
        result[i] = data[i]["volume"] > max_down > 0
    return result


def detect_rs_divergence(stock: List[dict], bench: List[dict], lookback: int = 20) -> List[bool]:
    result = [False] * len(stock)
    n = min(len(stock), len(bench))
    rs = [stock[i]["close"] / bench[i]["close"] for i in range(n)]
    for i in range(lookback, n):
        ph = max(d["high"] for d in stock[i - lookback:i])
        price_at_high = stock[i]["close"] >= ph * 0.98
        rs_at_high = rs[i] >= max(rs[i - lookback:i]) * 0.98
        result[i] = not price_at_high and rs_at_high
    return result


# ─── Minervini Stage 2 Template (all 5 criteria) ─────────────────────────────

def validate_minervini_template(ohlcv: List[dict]) -> dict:
    """
    Checks all Minervini SEPA criteria:
    1. Price > 150 DMA > 200 DMA
    2. 150 DMA > 200 DMA
    3. 200 DMA trending up for >= 20 bars
    4. 50 DMA > 150 DMA and 200 DMA, price > 50 DMA
    5. Price within 25% of 52w high, >= 30% above 52w low

    Returns dict with individual criterion flags + overall pass.
    """
    if len(ohlcv) < 210:
        return {"passes": False, "reason": "Insufficient history", "criteria": {}}

    closes = [d["close"] for d in ohlcv]
    price  = closes[-1]

    sma50  = calculate_sma(closes, 50)
    sma150 = calculate_sma(closes, 150)
    sma200 = calculate_sma(closes, 200)

    s50  = sma50[-1]
    s150 = sma150[-1]
    s200 = sma200[-1]

    # Criterion 3: 200 DMA trending up — slope over last 20 bars
    sma200_20ago = sma200[-21] if not math.isnan(sma200[-21]) else s200
    sma200_trending = s200 > sma200_20ago

    # 52-week metrics
    high52 = max(d["high"] for d in ohlcv[-252:])
    low52  = min(d["low"]  for d in ohlcv[-252:])
    pct_from_high = (price - high52) / high52 * 100   # negative = below high
    pct_from_low  = (price - low52)  / low52  * 100

    c = {
        "price_above_150_200": price > s150 > s200 if not math.isnan(s150) else False,
        "sma150_above_200":    s150 > s200 if not math.isnan(s150) else False,
        "sma200_trending_up":  sma200_trending,
        "sma50_above_150_200": (s50 > s150 and s50 > s200 and price > s50) if not math.isnan(s50) else False,
        "near_52w_high":       pct_from_high >= -25,
        "above_52w_low":       pct_from_low  >= 30,
    }
    passes = all(c.values())

    return {
        "passes": passes,
        "criteria": c,
        "pct_from_52w_high": pct_from_high,
        "pct_from_52w_low":  pct_from_low,
        "sma50": s50, "sma150": s150, "sma200": s200,
        "criteria_met": sum(c.values()),
        "reason": "All criteria met" if passes else
                  f"Failed: {', '.join(k for k, v in c.items() if not v)}",
    }


# ─── RS Rank (percentile 1–99) ────────────────────────────────────────────────

def calculate_rs_rank(rs_scores: List[float]) -> List[int]:
    """
    Given a list of raw RS% values (one per stock in the universe),
    returns the corresponding percentile ranks (1–99).
    Used to rank the full screener universe like IBD's RS Rating.
    """
    n = len(rs_scores)
    if n == 0:
        return []
    indexed = sorted(enumerate(rs_scores), key=lambda x: x[1])
    ranks = [0] * n
    for rank_pos, (orig_idx, _) in enumerate(indexed):
        ranks[orig_idx] = max(1, min(99, int((rank_pos / (n - 1)) * 98) + 1)) if n > 1 else 50
    return ranks


# ─── Volume Profile ───────────────────────────────────────────────────────────

def calculate_volume_profile(ohlcv: List[dict], bins: int = 24) -> dict:
    """
    Computes a simplified volume profile (visible range).
    Returns POC (Point of Control), VAH (Value Area High), VAL (Value Area Low),
    and a list of {price, volume} bins for chart rendering.
    """
    if not ohlcv:
        return {"poc": 0, "vah": 0, "val": 0, "bins": []}

    lo = min(d["low"]  for d in ohlcv)
    hi = max(d["high"] for d in ohlcv)
    if hi <= lo:
        return {"poc": lo, "vah": hi, "val": lo, "bins": []}

    step = (hi - lo) / bins
    buckets = [{"price": lo + (i + 0.5) * step, "volume": 0.0} for i in range(bins)]

    for bar in ohlcv:
        # Distribute bar volume proportionally across price range
        b_lo, b_hi, vol = bar["low"], bar["high"], bar["volume"]
        bar_range = max(b_hi - b_lo, 0.001)
        for b in buckets:
            overlap = max(0, min(b["price"] + step / 2, b_hi) - max(b["price"] - step / 2, b_lo))
            b["volume"] += vol * (overlap / bar_range)

    poc_bucket = max(buckets, key=lambda b: b["volume"])
    poc = poc_bucket["price"]

    # Value area = 70% of total volume around POC
    total_vol  = sum(b["volume"] for b in buckets)
    target_vol = total_vol * 0.70

    poc_idx  = buckets.index(poc_bucket)
    va_idxs  = {poc_idx}
    accum    = poc_bucket["volume"]
    lo_idx, hi_idx = poc_idx, poc_idx

    while accum < target_vol and (lo_idx > 0 or hi_idx < bins - 1):
        add_lo = buckets[lo_idx - 1]["volume"] if lo_idx > 0 else 0
        add_hi = buckets[hi_idx + 1]["volume"] if hi_idx < bins - 1 else 0
        if add_hi >= add_lo and hi_idx < bins - 1:
            hi_idx += 1; accum += add_hi; va_idxs.add(hi_idx)
        elif lo_idx > 0:
            lo_idx -= 1; accum += add_lo; va_idxs.add(lo_idx)
        else:
            break

    return {
        "poc":  poc,
        "vah":  buckets[max(va_idxs)]["price"] + step / 2,
        "val":  buckets[min(va_idxs)]["price"] - step / 2,
        "bins": buckets,
        "max_volume": max(b["volume"] for b in buckets),
    }


# ─── Sector Correlation Matrix ────────────────────────────────────────────────

def calculate_correlation_matrix(sector_returns: Dict[str, List[float]], window: int = 30) -> Dict:
    """
    Input:  {sector_name: [daily_returns list]}
    Output: {(s1,s2): correlation_float} for all pairs, using last `window` bars.
    """
    names = list(sector_returns.keys())
    result = {}
    for i, n1 in enumerate(names):
        for n2 in names[i:]:
            r1 = sector_returns[n1][-window:]
            r2 = sector_returns[n2][-window:]
            n  = min(len(r1), len(r2))
            if n < 5:
                result[(n1, n2)] = result[(n2, n1)] = 0.0
                continue
            r1, r2 = r1[-n:], r2[-n:]
            m1, m2 = sum(r1) / n, sum(r2) / n
            cov = sum((a - m1) * (b - m2) for a, b in zip(r1, r2)) / n
            s1  = math.sqrt(sum((a - m1) ** 2 for a in r1) / n)
            s2  = math.sqrt(sum((b - m2) ** 2 for b in r2) / n)
            corr = cov / (s1 * s2) if s1 * s2 > 0 else 0.0
            result[(n1, n2)] = result[(n2, n1)] = round(corr, 3)
    return result


# ─── Breadth Indicators ───────────────────────────────────────────────────────

def calculate_advance_decline(stocks_data: List[dict]) -> dict:
    """
    Input: list of processed stock dicts with change_pct field.
    Returns A/D counts + net, McClellan ratio approximation.
    """
    advances = sum(1 for s in stocks_data if s.get("change_pct", 0) > 0)
    declines  = sum(1 for s in stocks_data if s.get("change_pct", 0) < 0)
    unchanged = len(stocks_data) - advances - declines
    net = advances - declines

    ratio = net / max(1, advances + declines)

    # McClellan Oscillator approximation (simplified — no 19/39 EMA chain without history)
    # Returns ratio * 1000 as a proxy
    mcc_approx = ratio * 1000

    return {
        "advances": advances,
        "declines": declines,
        "unchanged": unchanged,
        "net": net,
        "ratio": ratio,
        "breadth_pct": advances / max(1, len(stocks_data)) * 100,
        "mclellan_approx": mcc_approx,
    }


def count_new_highs_lows(stocks_data: List[dict]) -> dict:
    """Count stocks at 52-week highs/lows based on fetched metadata."""
    new_highs = sum(1 for s in stocks_data
                    if s.get("high52w", 0) > 0 and
                    abs(s.get("price", 0) - s.get("high52w", 0)) / max(1, s.get("high52w", 1)) < 0.02)
    new_lows  = sum(1 for s in stocks_data
                    if s.get("low52w", 0) > 0 and
                    abs(s.get("price", 0) - s.get("low52w", 0)) / max(1, s.get("low52w", 1)) < 0.02)
    return {"new_highs": new_highs, "new_lows": new_lows,
            "hl_ratio": new_highs / max(1, new_lows)}


def calculate_pct_above_ma(stocks_data: List[dict]) -> dict:
    return {
        "above_20dma":  sum(1 for s in stocks_data if s.get("above20dma"))  / max(1,len(stocks_data)) * 100,
        "above_50dma":  sum(1 for s in stocks_data if s.get("above50dma"))  / max(1,len(stocks_data)) * 100,
        "above_200dma": sum(1 for s in stocks_data if s.get("above200dma")) / max(1,len(stocks_data)) * 100,
    }


# ─── Corporate Action Sanity Check ────────────────────────────────────────────

def check_price_continuity(ohlcv: List[dict], threshold: float = 0.40) -> List[int]:
    """
    Returns list of bar indices where a single-day move > threshold (40%).
    These are likely unadjusted bonus/split dates — flag them in the chart.
    """
    flagged = []
    for i in range(1, len(ohlcv)):
        prev = ohlcv[i - 1]["close"]
        curr = ohlcv[i]["close"]
        if prev > 0 and abs(curr - prev) / prev > threshold:
            flagged.append(i)
    return flagged


# ─── Momentum Score ───────────────────────────────────────────────────────────

def calculate_momentum_score(data: List[dict]) -> float:
    closes, volumes = [d["close"] for d in data], [d["volume"] for d in data]
    score = 0.0
    rsi_arr = calculate_rsi(closes)
    lr = rsi_arr[-1]
    if not math.isnan(lr):
        score += 25 if 50 <= lr <= 70 else 15 if lr > 70 else 10 if lr >= 40 else 0
    dma = calculate_dma_status(closes)
    if dma["above20"]:  score += 10
    if dma["above50"]:  score += 10
    if dma["above200"]: score += 5
    if len(closes) >= 20:
        chg = (closes[-1] - closes[-20]) / closes[-20]
        score += 25 if chg > 0.10 else 20 if chg > 0.05 else 10 if chg > 0 else 0
    if len(volumes) >= 20:
        avg = sum(volumes[-20:]) / 20
        rec = sum(volumes[-5:]) / 5
        score += 25 if rec > avg * 1.5 else 15 if rec > avg else 5
    return min(100.0, score)


# ─── Relative Strength ────────────────────────────────────────────────────────

def calculate_relative_strength(stock: List[float], bench: List[float], period: int = 50) -> float:
    if len(stock) < period or len(bench) < period:
        return 0.0
    sr = (stock[-1] - stock[-period]) / stock[-period]
    br = (bench[-1] - bench[-period]) / bench[-period]
    return ((1 + sr) / (1 + br) - 1) * 100


# ─── RRG (JdK Method) ────────────────────────────────────────────────────────

def calculate_rrg_values(stock: List[float], bench: List[float], period: int = 10) -> dict:
    if len(stock) < period * 3 or len(bench) < period * 3:
        return {"rs_ratio": 100.0, "rs_momentum": 100.0}
    n = min(len(stock), len(bench))
    rs = [stock[i] / bench[i] for i in range(n)]
    rs_ma = calculate_sma(rs, period)
    rr = [rs[i] / rs_ma[i] * 100 if not math.isnan(rs_ma[i]) and rs_ma[i] else float("nan") for i in range(n)]
    filled = [0.0 if math.isnan(v) else v for v in rr]
    rr_ma  = calculate_sma(filled, period)
    last_rr, last_rr_ma = rr[-1], rr_ma[-1]
    rs_ratio = 100.0 if math.isnan(last_rr) else last_rr
    rs_mom   = 100.0 if math.isnan(last_rr_ma) or last_rr_ma == 0 or math.isnan(last_rr) \
               else last_rr / last_rr_ma * 100
    return {
        "rs_ratio":    max(85.0, min(115.0, rs_ratio)),
        "rs_momentum": max(85.0, min(115.0, rs_mom)),
    }


def get_rrg_quadrant(rs_ratio: float, rs_momentum: float) -> str:
    if rs_ratio >= 100 and rs_momentum >= 100: return "Leading"
    if rs_ratio >= 100 and rs_momentum < 100:  return "Weakening"
    if rs_ratio < 100  and rs_momentum < 100:  return "Lagging"
    return "Improving"


# ─── Volume Ratio ─────────────────────────────────────────────────────────────

def calculate_volume_ratio(volumes: List[float]) -> float:
    if len(volumes) < 20: return 1.0
    avg = sum(volumes[-20:]) / 20
    return volumes[-1] / avg if avg > 0 else 1.0


# ─── Grade ────────────────────────────────────────────────────────────────────

def assign_grade(sector_strength: float, momentum: float, rs_rank: float) -> dict:
    if sector_strength > 60 and momentum > 70 and rs_rank > 70:
        return {"grade": "A", "description": "Strong sector + high momentum + top RS rank"}
    if sector_strength > 50 and momentum > 40:
        return {"grade": "B", "description": "Strong sector, moderate strength"}
    return {"grade": "C", "description": "Weak sector or low momentum"}
