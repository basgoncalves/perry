"""Builds market/data.json for the Market tab of basgoncalves.github.io/perry.

Run by .github/workflows/market-data.yml on a schedule (GitHub Pages can't
fetch prices itself: Yahoo blocks browser requests). Same maths as Scrooge's
Market map page on the PC.

    pip install yfinance pandas
    python market/build.py           # writes market/data.json
"""

from __future__ import annotations

import json
import math
import os
import sys
from datetime import datetime, timezone

import pandas as pd

# symbol -> (name, sector). Roughly the 60 largest US listings.
UNIVERSE = {
    "NVDA": ("Nvidia", "Technology"), "MSFT": ("Microsoft", "Technology"),
    "AAPL": ("Apple", "Technology"), "AVGO": ("Broadcom", "Technology"),
    "ORCL": ("Oracle", "Technology"), "AMD": ("AMD", "Technology"),
    "CRM": ("Salesforce", "Technology"), "CSCO": ("Cisco", "Technology"),
    "IBM": ("IBM", "Technology"), "MU": ("Micron", "Technology"),
    "PLTR": ("Palantir", "Technology"), "INTC": ("Intel", "Technology"),
    "QCOM": ("Qualcomm", "Technology"), "TXN": ("Texas Instr.", "Technology"),
    "ADBE": ("Adobe", "Technology"), "NOW": ("ServiceNow", "Technology"),
    "AMAT": ("Applied Mat.", "Technology"), "LRCX": ("Lam Research", "Technology"),
    "GOOGL": ("Alphabet", "Communication"), "META": ("Meta", "Communication"),
    "NFLX": ("Netflix", "Communication"), "TMUS": ("T-Mobile", "Communication"),
    "DIS": ("Disney", "Communication"), "VZ": ("Verizon", "Communication"),
    "AMZN": ("Amazon", "Consumer"), "TSLA": ("Tesla", "Consumer"),
    "WMT": ("Walmart", "Consumer"), "COST": ("Costco", "Consumer"),
    "HD": ("Home Depot", "Consumer"), "PG": ("Procter & Gamble", "Consumer"),
    "KO": ("Coca-Cola", "Consumer"), "PEP": ("PepsiCo", "Consumer"),
    "MCD": ("McDonald's", "Consumer"), "PM": ("Philip Morris", "Consumer"),
    "BRK-B": ("Berkshire", "Financials"), "JPM": ("JPMorgan", "Financials"),
    "V": ("Visa", "Financials"), "MA": ("Mastercard", "Financials"),
    "BAC": ("Bank of America", "Financials"), "WFC": ("Wells Fargo", "Financials"),
    "GS": ("Goldman Sachs", "Financials"), "MS": ("Morgan Stanley", "Financials"),
    "AXP": ("AmEx", "Financials"), "C": ("Citigroup", "Financials"),
    "LLY": ("Eli Lilly", "Healthcare"), "JNJ": ("J&J", "Healthcare"),
    "UNH": ("UnitedHealth", "Healthcare"), "ABBV": ("AbbVie", "Healthcare"),
    "MRK": ("Merck", "Healthcare"), "ABT": ("Abbott", "Healthcare"),
    "TMO": ("Thermo Fisher", "Healthcare"), "ISRG": ("Intuitive Surg.", "Healthcare"),
    "XOM": ("Exxon", "Energy & Industry"), "CVX": ("Chevron", "Energy & Industry"),
    "GE": ("GE Aerospace", "Energy & Industry"), "CAT": ("Caterpillar", "Energy & Industry"),
    "RTX": ("RTX", "Energy & Industry"), "BA": ("Boeing", "Energy & Industry"),
    "LIN": ("Linde", "Energy & Industry"), "NEE": ("NextEra", "Energy & Industry"),
}

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "data.json")
STOCK_DIR = os.path.join(HERE, "stocks")


def pick_shares(reported, market_cap, price):
    """Yahoo's sharesOutstanding counts ONE class for dual-class companies
    (Alphabet, Berkshire); marketCap covers all. Trust the reported count
    only when it roughly agrees with cap / price."""
    implied = market_cap / price if market_cap and price else None
    if reported and implied:
        return reported if abs(reported / implied - 1) < 0.25 else implied
    return reported or implied


def total_series(closes: pd.DataFrame, shares: dict) -> pd.Series:
    """Daily sum of close x today's shares, from the first day every company
    has a price (so a late listing can't fake a jump)."""
    cols = [c for c in closes.columns if shares.get(c)]
    frame = closes[cols].ffill().dropna()
    return (frame * pd.Series({c: shares[c] for c in cols})).sum(axis=1)


def thin(series: pd.Series) -> pd.Series:
    """Daily points for the last 2 years, weekly before that — keeps the
    file small for phones."""
    cut = series.index[-1] - pd.Timedelta(days=730)
    old = series[series.index < cut].resample("W-FRI").last().dropna()
    return pd.concat([old, series[series.index >= cut]])


def build(closes: pd.DataFrame, info: dict) -> dict:
    """closes: daily closes, one column per symbol. info: symbol -> dict with
    marketCap / sharesOutstanding. Pure, so it can be tested offline."""
    closes = closes.sort_index()
    tiles, shares = [], {}
    for sym, (name, sector) in UNIVERSE.items():
        if sym not in closes:
            continue
        s = closes[sym].dropna()
        if len(s) < 2:
            continue
        price, prev = float(s.iloc[-1]), float(s.iloc[-2])
        i = info.get(sym) or {}
        n = pick_shares(i.get("sharesOutstanding"), i.get("marketCap"), price)
        if not n:
            continue
        shares[sym] = n
        tiles.append({"s": sym, "n": name, "sec": sector,
                      "cap": round(n * price), "chg": round((price / prev - 1) * 100, 2)})
    tiles.sort(key=lambda t: -t["cap"])
    total = thin(total_series(closes, shares))
    return {
        "updated": datetime.now(timezone.utc).isoformat(timespec="minutes"),
        "asof": str(closes.index[-1].date()),
        "tiles": tiles,
        "total": [[str(d.date()), round(v / 1e9, 1)] for d, v in total.items()
                  if not math.isnan(v)],   # billions of USD
    }


def stock_files(closes: pd.DataFrame, data: dict) -> dict:
    """One small file per company for its own page: daily for 2 years,
    weekly before that, prices rounded to cents."""
    out = {}
    for t in data["tiles"]:
        s = closes[t["s"]].dropna()
        if len(s) < 2:
            continue
        s.index = pd.to_datetime(s.index)
        out[t["s"]] = {**t, "asof": data["asof"],
                       "px": [[str(d.date()), round(float(v), 2)] for d, v in thin(s).items()]}
    return out


def fetch():
    import yfinance as yf
    syms = list(UNIVERSE)
    raw = yf.download(syms, period="5y", interval="1d", auto_adjust=False,
                      progress=False, group_by="column", threads=True)
    closes = raw["Close"]
    closes.index = pd.to_datetime(closes.index).tz_localize(None)
    info = {}
    for s in syms:
        try:
            d = yf.Ticker(s).info
            info[s] = {"marketCap": d.get("marketCap"),
                       "sharesOutstanding": d.get("sharesOutstanding")}
        except Exception as e:
            print(f"info failed for {s}: {e}", file=sys.stderr)
    return closes, info


def main() -> int:
    closes, info = fetch()
    data = build(closes, info)
    if len(data["tiles"]) < 30:   # Yahoo hiccup: keep yesterday's file
        print(f"only {len(data['tiles'])} tiles, not overwriting", file=sys.stderr)
        return 1
    with open(OUT, "w") as f:
        json.dump(data, f, separators=(",", ":"))
    os.makedirs(STOCK_DIR, exist_ok=True)
    for sym, d in stock_files(closes, data).items():
        with open(os.path.join(STOCK_DIR, f"{sym}.json"), "w") as f:
            json.dump(d, f, separators=(",", ":"))
    print(f"{len(data['tiles'])} tiles, {len(data['total'])} points -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
