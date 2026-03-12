"""
╔══════════════════════════════════════════════════════════════╗
║          SNIPER FX — Smart Money Scalping Scanner           ║
║     28 Pairs | SMC + Classic | All Sessions | M5-H4         ║
╚══════════════════════════════════════════════════════════════╝
"""

import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime
import warnings
import requests
import zipfile
import io
warnings.filterwarnings("ignore")

# ============================================================
# COT REPORT — CFTC MAPPING
# ============================================================
# CFTC uses "Market and Exchange Names" — these are the exact
# contract names in the Traders in Financial Futures (TFF) report
COT_MARKET_MAP = {
    "EURUSD": "EURO FX",
    "GBPUSD": "BRITISH POUND",
    "USDJPY": "JAPANESE YEN",
    "USDCHF": "SWISS FRANC",
    "AUDUSD": "AUSTRALIAN DOLLAR",
    "USDCAD": "CANADIAN DOLLAR",
    "NZDUSD": "NEW ZEALAND DOLLAR",
    # Cross pairs — mapped to base currency futures
    "EURJPY": "EURO FX",
    "EURGBP": "EURO FX",
    "EURCAD": "EURO FX",
    "EURAUD": "EURO FX",
    "EURNZD": "EURO FX",
    "EURCHF": "EURO FX",
    "GBPJPY": "BRITISH POUND",
    "GBPCAD": "BRITISH POUND",
    "GBPAUD": "BRITISH POUND",
    "GBPNZD": "BRITISH POUND",
    "GBPCHF": "BRITISH POUND",
    "AUDJPY": "AUSTRALIAN DOLLAR",
    "AUDCAD": "AUSTRALIAN DOLLAR",
    "AUDNZD": "AUSTRALIAN DOLLAR",
    "AUDCHF": "AUSTRALIAN DOLLAR",
    "CADJPY": "CANADIAN DOLLAR",
    "NZDJPY": "NEW ZEALAND DOLLAR",
    "NZDCAD": "NEW ZEALAND DOLLAR",
    "NZDCHF": "NEW ZEALAND DOLLAR",
    "CHFJPY": "SWISS FRANC",
    "CADCHF": "CANADIAN DOLLAR",
    "XAUUSD": "GOLD",   # Gold futures COT
}

# Whether the pair moves WITH or AGAINST the base currency futures
# e.g. USDJPY: when JPY futures are net long, USD/JPY goes DOWN (JPY stronger)
COT_INVERSE = {"USDJPY", "USDCHF", "USDCAD"}  # USD is base, so inverse

# ============================================================
# CONFIG & CONSTANTS
# ============================================================

st.set_page_config(
    page_title="SNIPER FX",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded"
)

MAJOR_PAIRS = {
    "EURUSD": "EUR/USD", "GBPUSD": "GBP/USD", "USDJPY": "USD/JPY",
    "USDCHF": "USD/CHF", "AUDUSD": "AUD/USD", "USDCAD": "USD/CAD",
    "NZDUSD": "NZD/USD"
}
MINOR_PAIRS = {
    "EURJPY": "EUR/JPY", "EURGBP": "EUR/GBP", "EURCAD": "EUR/CAD",
    "EURAUD": "EUR/AUD", "EURNZD": "EUR/NZD", "EURCHF": "EUR/CHF",
    "GBPJPY": "GBP/JPY", "GBPCAD": "GBP/CAD", "GBPAUD": "GBP/AUD",
    "GBPNZD": "GBP/NZD", "GBPCHF": "GBP/CHF", "AUDJPY": "AUD/JPY",
    "AUDCAD": "AUD/CAD", "AUDNZD": "AUD/NZD", "AUDCHF": "AUD/CHF",
    "CADJPY": "CAD/JPY", "CHFJPY": "CHF/JPY", "NZDJPY": "NZD/JPY",
    "NZDCAD": "NZD/CAD", "NZDCHF": "NZD/CHF", "CADCHF": "CAD/CHF"
}
COMMODITY_PAIRS = {
    "XAUUSD": "Gold/USD",   # Gold
}
ALL_PAIRS = {**MAJOR_PAIRS, **MINOR_PAIRS, **COMMODITY_PAIRS}
JPY_PAIRS = [p for p in ALL_PAIRS if "JPY" in p]

# yfinance symbol mapping (some pairs use different symbols)
YF_SYMBOL_MAP = {
    "XAUUSD": "GC=F",   # Gold futures
}

def get_yf_symbol(symbol):
    """Get correct yfinance symbol for a pair."""
    return YF_SYMBOL_MAP.get(symbol, symbol + "=X")

def get_pip(symbol):
    if symbol in JPY_PAIRS: return 0.01
    if symbol == "XAUUSD":  return 0.1   # Gold: 1 pip = $0.10
    return 0.0001

# ============================================================
# CSS — Military Dark Theme
# ============================================================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&family=Exo+2:wght@300;400;600;700;900&display=swap');
:root {
    --bg:   #050a0e; --bg2: #0a1520; --card: #0d1e2e;
    --green:#00ff88; --red: #ff3355; --gold: #ffd700;
    --blue: #00bfff; --org: #ff8c00;
    --txt:  #e0f0ff; --muted:#5a7a9a; --border:#1a3a5c;
}
*{font-family:'Exo 2',sans-serif}
.stApp{background:var(--bg);color:var(--txt)}
section[data-testid="stSidebar"]{background:var(--bg2)!important;border-right:1px solid var(--border)!important}
section[data-testid="stSidebar"] *{color:var(--txt)!important}
h1,h2,h3{font-family:'Exo 2',sans-serif;font-weight:900;letter-spacing:2px}
.metric-box{background:var(--card);border:1px solid var(--border);border-radius:4px;
    padding:12px 16px;text-align:center;position:relative;overflow:hidden}
.metric-box::before{content:'';position:absolute;top:0;left:0;right:0;height:2px;background:var(--green)}
.metric-label{font-size:10px;color:var(--muted);letter-spacing:2px;text-transform:uppercase;font-family:'Share Tech Mono',monospace}
.metric-value{font-size:22px;font-weight:900;color:var(--green);font-family:'Share Tech Mono',monospace}
.signal-card{background:var(--card);border:1px solid var(--border);border-radius:6px;
    padding:16px;margin:8px 0}
.signal-card.buy{border-left:4px solid var(--green)}
.signal-card.sell{border-left:4px solid var(--red)}
.signal-card.neutral{border-left:4px solid var(--muted)}
.score-bar-bg{background:#0a1520;border-radius:2px;height:6px;overflow:hidden;margin:4px 0}
.badge{display:inline-block;padding:2px 10px;border-radius:3px;font-size:11px;font-weight:700;letter-spacing:1px;font-family:'Share Tech Mono',monospace}
.b-sniper{background:#ffd70022;color:#ffd700;border:1px solid #ffd700}
.b-strong{background:#00ff8822;color:#00ff88;border:1px solid #00ff88}
.b-setup{background:#00ff8811;color:#00cc66;border:1px solid #00cc66}
.b-watch{background:#ff8c0022;color:#ff8c00;border:1px solid #ff8c00}
.b-wait{background:#5a7a9a22;color:#5a7a9a;border:1px solid #5a7a9a}
.b-avoid{background:#33111122;color:#443333;border:1px solid #331111}
.stTabs [data-baseweb="tab-list"]{background:var(--bg2)!important;border-bottom:1px solid var(--border)!important}
.stTabs [data-baseweb="tab"]{color:var(--muted)!important;font-family:'Share Tech Mono',monospace!important;font-size:12px!important;letter-spacing:1px!important}
.stTabs [aria-selected="true"]{color:var(--green)!important;border-bottom:2px solid var(--green)!important;background:var(--card)!important}
.stButton button{background:transparent!important;border:1px solid var(--green)!important;
    color:var(--green)!important;font-family:'Share Tech Mono',monospace!important;letter-spacing:2px!important;font-size:12px!important}
.stButton button:hover{background:var(--green)!important;color:var(--bg)!important}
.conf-tag{display:inline-block;background:#0d1e2e;border:1px solid #1a3a5c;border-radius:3px;
    padding:2px 7px;font-size:10px;margin:2px 2px;color:#7a9abf;font-family:'Share Tech Mono',monospace}
.conf-pos{border-color:#00ff8844!important;color:#00ff88!important}
.conf-neg{border-color:#ff335544!important;color:#ff3355!important}
.info-row{display:flex;justify-content:space-between;align-items:center;
    padding:7px 0;border-bottom:1px solid #0d1e2e;font-size:12px}
.info-row:last-child{border-bottom:none}
hr{border-color:var(--border)!important}
.hdr{background:linear-gradient(135deg,#050a0e,#0a1e2e,#050a0e);border:1px solid var(--border);
    border-top:3px solid var(--green);padding:22px 30px;margin-bottom:20px}
.hdr-title{font-size:36px;font-weight:900;color:var(--green);letter-spacing:8px;
    font-family:'Share Tech Mono',monospace;text-shadow:0 0 20px #00ff8866}
.hdr-sub{font-size:11px;color:var(--muted);letter-spacing:4px;font-family:'Share Tech Mono',monospace;margin-top:4px}
.sess-dot{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:6px}
.alert-box{background:#0d1e2e;border:1px solid var(--border);border-left:4px solid var(--gold);
    padding:12px 16px;border-radius:0 4px 4px 0;font-size:13px;margin:8px 0}
</style>
""", unsafe_allow_html=True)

# ============================================================
# SESSION HELPERS
# ============================================================

def get_active_sessions():
    h = datetime.utcnow().hour
    active = []
    if h >= 21 or h < 6:  active.append("Sydney")
    if 0 <= h < 9:        active.append("Tokyo")
    if 7 <= h < 16:       active.append("London")
    if 12 <= h < 21:      active.append("New York")
    return active

def get_session_score(active):
    if "London" in active and "New York" in active:
        return 100, "🔥 London-NY Overlap — HIGHEST volatility"
    if "London" in active:  return 85, "⚡ London Open — High volatility"
    if "New York" in active: return 80, "⚡ New York Session — Good volatility"
    if "Tokyo" in active:   return 50, "〽️ Tokyo Session — JPY pairs active"
    if "Sydney" in active:  return 30, "💤 Sydney Only — Low volatility"
    return 20, "💤 Dead Zone — Avoid scalping"

# ============================================================
# DATA FETCHING
# ============================================================

@st.cache_data(ttl=60, show_spinner=False)
def fetch_data(symbol, period="5d", interval="5m"):
    yf_sym = get_yf_symbol(symbol)
    # Try multiple periods as fallback in case server has data gaps
    periods_to_try = [period]
    if period == "5d":  periods_to_try = ["5d", "7d", "10d"]
    if period == "30d": periods_to_try = ["30d", "60d"]
    if period == "60d": periods_to_try = ["60d", "90d"]

    for p in periods_to_try:
        try:
            df = yf.download(yf_sym, period=p, interval=interval,
                             auto_adjust=True, progress=False, timeout=20)
            if df is None or df.empty: continue
            # Flatten MultiIndex columns if present
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = [c[0] for c in df.columns]
            df = df[["Open","High","Low","Close","Volume"]].dropna()
            if len(df) >= 30:
                return df
        except Exception:
            continue
    return None

@st.cache_data(ttl=300, show_spinner=False)
def fetch_h1(symbol): return fetch_data(symbol, "30d", "1h")

@st.cache_data(ttl=900, show_spinner=False)
def fetch_h4(symbol): return fetch_data(symbol, "60d", "4h")

# ============================================================
# INDICATORS
# ============================================================

def calc_rsi(c, p=14):
    if len(c) < p+1: return 50.0
    c = np.array(c, dtype=float); d = np.diff(c)
    g = np.where(d>0,d,0.); l = np.where(d<0,-d,0.)
    ag = np.mean(g[:p]); al = np.mean(l[:p])
    for i in range(p,len(g)):
        ag=(ag*(p-1)+g[i])/p; al=(al*(p-1)+l[i])/p
    return round(100-(100/(1+ag/al)) if al>0 else 100., 2)

def calc_ema(v, p):
    v = np.array(v, dtype=float)
    if len(v) < p: return float(np.mean(v))
    k = 2/(p+1); e = np.mean(v[:p])
    for x in v[p:]: e = x*k+e*(1-k)
    return e

def calc_ema_series(v, p):
    v = np.array(v, dtype=float)
    r = np.full(len(v), np.nan)
    if len(v) < p: return r
    r[p-1] = np.mean(v[:p]); k = 2/(p+1)
    for i in range(p,len(v)): r[i] = v[i]*k+r[i-1]*(1-k)
    return r

def calc_macd(c):
    if len(c) < 35: return 0,0,0
    e12=calc_ema_series(c,12); e26=calc_ema_series(c,26)
    ml=e12-e26; valid=ml[~np.isnan(ml)]
    if len(valid)<9: return 0,0,0
    sig=calc_ema_series(valid,9)
    if np.isnan(sig[-1]): return 0,0,0
    return round(valid[-1],6), round(sig[-1],6), round(valid[-1]-sig[-1],6)

def calc_atr(h,l,c,p=14):
    if len(c)<p+1: return 0.001
    h=np.array(h,dtype=float); l=np.array(l,dtype=float); c=np.array(c,dtype=float)
    tr=np.maximum(h[1:]-l[1:],np.maximum(abs(h[1:]-c[:-1]),abs(l[1:]-c[:-1])))
    return max(float(np.mean(tr[-p:])), 0.00001)

def calc_adx(h,l,c,p=14):
    if len(c)<p*2: return 20.
    h=np.array(h,dtype=float); l=np.array(l,dtype=float); c=np.array(c,dtype=float)
    tr_a,pd_a,nd_a=[],[],[]
    for i in range(1,len(c)):
        tr=max(h[i]-l[i],abs(h[i]-c[i-1]),abs(l[i]-c[i-1]))
        pdm=h[i]-h[i-1] if h[i]-h[i-1]>l[i-1]-l[i] else 0
        ndm=l[i-1]-l[i] if l[i-1]-l[i]>h[i]-h[i-1] else 0
        tr_a.append(tr); pd_a.append(max(pdm,0)); nd_a.append(max(ndm,0))
    tr_a=np.array(tr_a); pd_a=np.array(pd_a); nd_a=np.array(nd_a)
    atrs=np.convolve(tr_a,np.ones(p)/p,'valid')
    pdi=np.convolve(pd_a,np.ones(p)/p,'valid')/(atrs+1e-10)*100
    ndi=np.convolve(nd_a,np.ones(p)/p,'valid')/(atrs+1e-10)*100
    dx=np.abs(pdi-ndi)/(pdi+ndi+1e-10)*100
    return round(float(np.mean(dx[-p:])) if len(dx)>=p else 20.,1)

def calc_bb(c,p=20,s=2):
    if len(c)<p: v=c[-1]; return v,v*1.001,v*0.999
    arr=np.array(c[-p:],dtype=float); m=np.mean(arr); std=np.std(arr)
    return round(m,5),round(m+s*std,5),round(m-s*std,5)

def calc_stoch(h,l,c,k=14,d=3):
    if len(c)<k: return 50.,50.
    hh=np.max(np.array(h[-k:],dtype=float)); ll=np.min(np.array(l[-k:],dtype=float))
    if hh==ll: return 50.,50.
    kv=(float(c[-1])-ll)/(hh-ll)*100
    return round(kv,1), round(kv,1)

# ============================================================
# SMC ENGINE
# ============================================================

def market_structure(df):
    if df is None or len(df)<20: return "RANGING",False,False
    c=df["Close"].values; h=df["High"].values; l=df["Low"].values

    def pivots(arr,n=3):
        pts=[]
        for i in range(n,len(arr)-n):
            if all(arr[i]>arr[i-j] for j in range(1,n+1)) and all(arr[i]>arr[i+j] for j in range(1,n+1)):
                pts.append((i,arr[i],"H"))
            elif all(arr[i]<arr[i-j] for j in range(1,n+1)) and all(arr[i]<arr[i+j] for j in range(1,n+1)):
                pts.append((i,arr[i],"L"))
        return pts

    pts=pivots(c)
    if len(pts)<4: return "RANGING",False,False
    sh=[(i,v) for i,v,t in pts if t=="H"][-4:]
    sl=[(i,v) for i,v,t in pts if t=="L"][-4:]
    if not sh or not sl: return "RANGING",False,False

    cp=c[-1]; lh=sh[-1][1]; ll_=sl[-1][1]
    bias="RANGING"; bos=False; choch=False

    if len(sh)>=2 and len(sl)>=2:
        hh=sh[-1][1]>sh[-2][1]; hl=sl[-1][1]>sl[-2][1]
        lh_=sh[-1][1]<sh[-2][1]; ll=sl[-1][1]<sl[-2][1]
        if hh and hl:
            bias="BULLISH"
            if cp>lh: bos=True
            if ll: choch=True
        elif lh_ and ll:
            bias="BEARISH"
            if cp<ll_: bos=True
            if hh: choch=True

    return bias,bos,choch

def order_blocks(df, n=60):
    if df is None or len(df)<n: return []
    s=df.tail(n); o=s["Open"].values; c=s["Close"].values
    h=s["High"].values; l=s["Low"].values; cp=c[-1]
    obs=[]
    for i in range(2,len(c)-3):
        rng=h[i]-l[i]
        if rng<1e-6: continue
        if c[i]<o[i]:  # bearish → potential bullish OB
            nb=sum(1 for j in range(i+1,min(i+4,len(c))) if c[j]>o[j])
            if nb>=2 and cp>l[i]:
                mv=c[min(i+3,len(c)-1)]-c[i]
                obs.append({"type":"BULL","high":round(h[i],5),"low":round(l[i],5),
                            "mid":round((h[i]+l[i])/2,5),"str":min(100,int(abs(mv)/(rng+1e-8)*30)),"age":len(c)-i})
        elif c[i]>o[i]:  # bullish → potential bearish OB
            nb=sum(1 for j in range(i+1,min(i+4,len(c))) if c[j]<o[j])
            if nb>=2 and cp<h[i]:
                mv=c[i]-c[min(i+3,len(c)-1)]
                obs.append({"type":"BEAR","high":round(h[i],5),"low":round(l[i],5),
                            "mid":round((h[i]+l[i])/2,5),"str":min(100,int(abs(mv)/(rng+1e-8)*30)),"age":len(c)-i})
    bull=sorted([o for o in obs if o["type"]=="BULL"],key=lambda x:-x["str"])[:3]
    bear=sorted([o for o in obs if o["type"]=="BEAR"],key=lambda x:-x["str"])[:3]
    return bull+bear

def fvg_zones(df, n=30):
    if df is None or len(df)<10: return []
    s=df.tail(n); h=s["High"].values; l=s["Low"].values; c=s["Close"].values
    fvgs=[]; cp=c[-1]
    for i in range(1,len(h)-1):
        if l[i+1]>h[i-1] and not cp<=l[i+1]:
            fvgs.append({"type":"BULL","top":round(l[i+1],5),"bot":round(h[i-1],5),
                        "mid":round((l[i+1]+h[i-1])/2,5),"age":len(h)-i})
        elif h[i+1]<l[i-1] and not cp>=h[i+1]:
            fvgs.append({"type":"BEAR","top":round(l[i-1],5),"bot":round(h[i+1],5),
                        "mid":round((l[i-1]+h[i+1])/2,5),"age":len(h)-i})
    return sorted([f for f in fvgs if f["age"]<=15], key=lambda x:x["age"])[:4]

def premium_discount(df):
    if df is None or len(df)<20: return 50.,"EQ"
    h=np.max(df["High"].values[-20:]); l=np.min(df["Low"].values[-20:])
    cp=float(df["Close"].values[-1])
    if h==l: return 50.,"EQ"
    pct=(cp-l)/(h-l)*100
    zone="PREMIUM" if pct>65 else "DISCOUNT" if pct<35 else "EQ"
    return round(pct,1),zone

# ============================================================
# COT REPORT ENGINE — CFTC Traders in Financial Futures (TFF)
# ============================================================

@st.cache_data(ttl=3600*6, show_spinner=False)  # Cache 6 hours (CFTC updates Friday)
def fetch_cot_data():
    """
    Download COT Traders in Financial Futures report from CFTC.
    Returns DataFrame with latest + historical positions.
    Source: https://www.cftc.gov/MarketReports/CommitmentsofTraders/index.htm
    TFF Report columns we care about:
      - Dealer Net (Commercial — banks/institutions)
      - Asset Manager Net (Large specs — hedge funds)
      - Leveraged Funds Net (Retail/CTA)
    """
    # CFTC TFF historical zip — updated weekly
    cot_url = "https://www.cftc.gov/files/dea/history/fut_fin_xls_{year}.zip"
    current_year = datetime.utcnow().year

    all_dfs = []
    # Fetch last 2 years for COT Index calculation
    for year in [current_year - 1, current_year]:
        url = cot_url.format(year=year)
        try:
            r = requests.get(url, timeout=15)
            if r.status_code != 200:
                continue
            z = zipfile.ZipFile(io.BytesIO(r.content))
            # File inside zip is FinFutYY.xls or similar
            fname = [n for n in z.namelist() if n.endswith(('.xls', '.xlsx', '.csv'))][0]
            with z.open(fname) as f:
                if fname.endswith('.csv'):
                    df = pd.read_csv(f, encoding='latin-1', low_memory=False)
                else:
                    df = pd.read_excel(f, engine='xlrd')
            all_dfs.append(df)
        except Exception:
            continue

    if not all_dfs:
        return None

    df = pd.concat(all_dfs, ignore_index=True)

    # Normalize column names
    df.columns = [str(c).strip().upper() for c in df.columns]

    # Key columns (CFTC TFF report standard names)
    col_map = {
        'MARKET_AND_EXCHANGE_NAMES': 'market',
        'MARKET AND EXCHANGE NAMES': 'market',
        'REPORT_DATE_AS_YYYY_MM_DD': 'date',
        'REPORT DATE AS YYYY-MM-DD': 'date',
        'AS_OF_DATE_IN_FORM_YYMMDD': 'date',
        # Dealer = Commercial/Institutional
        'DEALER_POSITIONS_LONG_ALL': 'dealer_long',
        'DEALER_POSITIONS_SHORT_ALL': 'dealer_short',
        # Asset Manager = Large Speculators / Hedge Funds
        'ASSET_MGR_POSITIONS_LONG_ALL': 'am_long',
        'ASSET_MGR_POSITIONS_SHORT_ALL': 'am_short',
        # Leveraged Funds = Retail speculators
        'LEVERAGED_FUNDS_POSITIONS_LONG_ALL': 'lev_long',
        'LEVERAGED_FUNDS_POSITIONS_SHORT_ALL': 'lev_short',
        # Open Interest
        'OPEN_INTEREST_ALL': 'open_interest',
    }

    # Try to match columns flexibly
    rename = {}
    for orig, new in col_map.items():
        for col in df.columns:
            if orig in col or col in orig:
                rename[col] = new
                break

    df = df.rename(columns=rename)

    needed = ['market', 'date']
    if not all(c in df.columns for c in needed):
        return None

    # Parse date
    df['date'] = pd.to_datetime(df['date'], errors='coerce')
    df = df.dropna(subset=['date'])
    df['market'] = df['market'].str.upper().str.strip()

    # Calculate net positions
    for prefix in ['dealer', 'am', 'lev']:
        lc = f'{prefix}_long'; sc_ = f'{prefix}_short'
        if lc in df.columns and sc_ in df.columns:
            df[f'{prefix}_net'] = pd.to_numeric(df[lc], errors='coerce') - \
                                   pd.to_numeric(df[sc_], errors='coerce')

    return df.sort_values('date').reset_index(drop=True)


def get_cot_for_pair(symbol, cot_df, lookback_weeks=52):
    """
    Extract COT metrics for a specific currency pair.
    Returns dict with:
      - dealer_net: latest net position (institutional)
      - am_net: asset manager net
      - lev_net: leveraged funds (retail) net
      - dealer_net_chg: week-over-week change
      - cot_index: percentile vs last 52 weeks (0-100)
      - signal: BULLISH / BEARISH / NEUTRAL
      - extreme: True if at extreme (>80 or <20 percentile)
      - sentiment: human readable
    """
    if cot_df is None:
        return _cot_empty()

    market_name = COT_MARKET_MAP.get(symbol, "")
    if not market_name:
        return _cot_empty()

    # Filter for this currency
    mask = cot_df['market'].str.contains(market_name, case=False, na=False)
    df_pair = cot_df[mask].copy()

    if len(df_pair) < 4:
        return _cot_empty()

    df_pair = df_pair.sort_values('date').tail(lookback_weeks)

    # Latest row
    latest = df_pair.iloc[-1]
    prev   = df_pair.iloc[-2] if len(df_pair) >= 2 else latest

    # Get net positions (prefer dealer/institutional, fallback to am)
    net_col = 'dealer_net' if 'dealer_net' in df_pair.columns else \
              'am_net' if 'am_net' in df_pair.columns else None

    if net_col is None:
        return _cot_empty()

    dealer_net = float(latest.get('dealer_net', 0) or 0)
    am_net     = float(latest.get('am_net', 0) or 0)
    lev_net    = float(latest.get('lev_net', 0) or 0)

    dealer_prev = float(prev.get('dealer_net', dealer_net) or dealer_net)
    dealer_chg  = dealer_net - dealer_prev

    am_prev = float(prev.get('am_net', am_net) or am_net)
    am_chg  = am_net - am_prev

    # COT Index = percentile of current net vs last N weeks
    net_series = df_pair[net_col].dropna()
    if len(net_series) >= 4:
        mn = net_series.min(); mx = net_series.max()
        cot_index = round((dealer_net - mn) / (mx - mn + 1e-8) * 100, 1) if mx > mn else 50.
    else:
        cot_index = 50.

    # Adjust for inverse pairs (USD is base)
    if symbol in COT_INVERSE:
        cot_index = 100 - cot_index
        dealer_net = -dealer_net
        dealer_chg = -dealer_chg
        am_net = -am_net
        lev_net = -lev_net

    # Signal logic
    extreme = cot_index > 80 or cot_index < 20
    if cot_index >= 65:
        signal = "BULLISH"
        sentiment = f"Institutions NET LONG ({dealer_net:+,.0f}) — bullish bias"
    elif cot_index <= 35:
        signal = "BEARISH"
        sentiment = f"Institutions NET SHORT ({dealer_net:+,.0f}) — bearish bias"
    else:
        signal = "NEUTRAL"
        sentiment = f"Institutions mixed ({dealer_net:+,.0f}) — no strong bias"

    # Extreme reversal warning
    if cot_index > 90:
        sentiment += " ⚠️ EXTREME LONG — reversal risk"
    elif cot_index < 10:
        sentiment += " ⚠️ EXTREME SHORT — reversal risk"

    # Momentum (is positioning getting stronger or weaker?)
    if len(net_series) >= 4:
        recent_trend = net_series.values[-1] - net_series.values[-4]
        cot_momentum = "INCREASING" if recent_trend > 0 else "DECREASING"
    else:
        cot_momentum = "UNKNOWN"

    return {
        "available": True,
        "dealer_net": round(dealer_net),
        "dealer_chg": round(dealer_chg),
        "am_net": round(am_net),
        "am_chg": round(am_chg),
        "lev_net": round(lev_net),
        "cot_index": cot_index,
        "signal": signal,
        "extreme": extreme,
        "sentiment": sentiment,
        "cot_momentum": cot_momentum,
        "report_date": str(latest.get('date', 'N/A'))[:10],
    }

def _cot_empty():
    return {
        "available": False,
        "dealer_net": 0, "dealer_chg": 0,
        "am_net": 0, "am_chg": 0, "lev_net": 0,
        "cot_index": 50., "signal": "NEUTRAL",
        "extreme": False, "sentiment": "COT data unavailable",
        "cot_momentum": "UNKNOWN", "report_date": "N/A",
    }

def cot_score_contribution(cot, direction):
    """
    Calculate how much COT adds/subtracts from sniper score.
    Returns (score_delta, confirmation_delta, signal_text)
    """
    if not cot["available"]:
        return 0, 0, []

    score_delta = 0
    conf_delta  = 0
    sigs = []
    ci = cot["cot_index"]

    if direction == "BUY":
        if cot["signal"] == "BULLISH":
            if ci > 80:
                score_delta += 20; conf_delta += 2
                sigs.append(f"📋 COT: Institutions HEAVILY LONG (Index:{ci:.0f}) — strong bull confirmation")
            elif ci > 65:
                score_delta += 14; conf_delta += 1
                sigs.append(f"📋 COT: Institutions NET LONG (Index:{ci:.0f}) — bull bias confirmed")
            if cot["cot_momentum"] == "INCREASING":
                score_delta += 6; conf_delta += 1
                sigs.append(f"📋 COT Momentum: Institutional longs INCREASING week-over-week")
        elif cot["signal"] == "BEARISH":
            score_delta -= 15
            sigs.append(f"📋 COT WARNING: Institutions SHORT while you BUY (Index:{ci:.0f}) — risk!")
        if cot["extreme"] and ci < 20:
            score_delta += 8  # Extreme short = mean reversion buy
            sigs.append(f"📋 COT EXTREME SHORT (Index:{ci:.0f}) — contrarian buy signal")

    elif direction == "SELL":
        if cot["signal"] == "BEARISH":
            if ci < 20:
                score_delta += 20; conf_delta += 2
                sigs.append(f"📋 COT: Institutions HEAVILY SHORT (Index:{ci:.0f}) — strong bear confirmation")
            elif ci < 35:
                score_delta += 14; conf_delta += 1
                sigs.append(f"📋 COT: Institutions NET SHORT (Index:{ci:.0f}) — bear bias confirmed")
            if cot["cot_momentum"] == "DECREASING":
                score_delta += 6; conf_delta += 1
                sigs.append(f"📋 COT Momentum: Institutional shorts INCREASING week-over-week")
        elif cot["signal"] == "BULLISH":
            score_delta -= 15
            sigs.append(f"📋 COT WARNING: Institutions LONG while you SELL (Index:{ci:.0f}) — risk!")
        if cot["extreme"] and ci > 80:
            score_delta += 8  # Extreme long = mean reversion sell
            sigs.append(f"📋 COT EXTREME LONG (Index:{ci:.0f}) — contrarian sell signal")

    return score_delta, conf_delta, sigs


# ============================================================
# MAIN ANALYSIS ENGINE
# ============================================================

def analyze(symbol, cot_df=None):
    r={
        "symbol":symbol,"name":ALL_PAIRS.get(symbol,symbol),
        "score":0,"direction":"NEUTRAL","rating":"🚫 AVOID",
        "confirmations":0,"signals":[],"warnings":[],
        "price":0.,"atr":0.,"rsi":50.,"macd":0.,"macd_hist":0.,
        "adx":20.,"stoch_k":50.,"stoch_d":50.,"bb_pct":50.,
        "bias":"RANGING","bos":False,"choch":False,
        "premium_pct":50.,"premium_zone":"EQ",
        "order_blocks":[],"fvg":[],"buy_s":0,"sell_s":0,
        "sl_pips":0,"tp1_pips":0,"tp2_pips":0,"rr_ratio":0.,
        "sl_price":0.,"tp1_price":0.,"tp2_price":0.,
        "h1_trend":"N/A","h4_bias":"N/A","m5_momentum":"N/A",
        "cot": _cot_empty(),
    }

    df5=fetch_data(symbol,"5d","5m")
    dfh1=fetch_h1(symbol)
    dfh4=fetch_h4(symbol)

    if df5 is None or len(df5)<50:
        r["signals"].append("⚠️ Insufficient data"); return r

    c5=df5["Close"].values; h5=df5["High"].values; l5=df5["Low"].values
    cp=float(c5[-1]); pip=get_pip(symbol)
    atr=calc_atr(h5,l5,c5); r["price"]=round(cp,5); r["atr"]=round(atr,5)

    score=0; conf=0; buy_s=0; sell_s=0
    sigs=[]; warns=[]

    # ── LAYER 1: H4 STRUCTURE ──
    bias,bos,choch=market_structure(dfh4)
    r["bias"]=bias; r["bos"]=bos; r["choch"]=choch

    if bias=="BULLISH":   score+=15;buy_s+=1;conf+=1;sigs.append("📈 H4 BULLISH structure (HH/HL)")
    elif bias=="BEARISH": score+=15;sell_s+=1;conf+=1;sigs.append("📉 H4 BEARISH structure (LH/LL)")
    else:                 score-=5;warns.append("↔️ H4: Ranging — no clear bias")

    if bos:
        score+=12;conf+=1
        if bias=="BULLISH": buy_s+=1;sigs.append("💥 BOS Bullish — structure confirmed")
        else: sell_s+=1;sigs.append("💥 BOS Bearish — structure confirmed")
    if choch:
        score+=8;conf+=1
        sigs.append("🔄 CHoCH — Change of Character (reversal signal)")
        if bias=="BULLISH": sell_s+=1
        else: buy_s+=1

    # H1 trend
    if dfh1 is not None and len(dfh1)>=50:
        c1=dfh1["Close"].values
        e20=calc_ema(c1,20); e50=calc_ema(c1,50)
        if c1[-1]>e20>e50: score+=8;buy_s+=1;conf+=1;sigs.append("📊 H1: Bullish (price>EMA20>EMA50)"); r["h1_trend"]="BULL"
        elif c1[-1]<e20<e50: score+=8;sell_s+=1;conf+=1;sigs.append("📊 H1: Bearish (price<EMA20<EMA50)"); r["h1_trend"]="BEAR"
        else: warns.append("〽️ H1: Mixed trend"); r["h1_trend"]="MIXED"

    # Premium/Discount
    pp,pz=premium_discount(dfh4)
    r["premium_pct"]=pp; r["premium_zone"]=pz
    if pz=="DISCOUNT" and bias=="BULLISH":   score+=10;buy_s+=1;conf+=1;sigs.append(f"💎 DISCOUNT zone ({pp:.0f}%) — ideal buy")
    elif pz=="PREMIUM" and bias=="BEARISH":  score+=10;sell_s+=1;conf+=1;sigs.append(f"💎 PREMIUM zone ({pp:.0f}%) — ideal sell")
    elif pz=="PREMIUM" and bias=="BULLISH":  score-=8;warns.append(f"⚠️ Premium zone ({pp:.0f}%) — expensive to buy")
    elif pz=="DISCOUNT" and bias=="BEARISH": score-=8;warns.append(f"⚠️ Discount zone ({pp:.0f}%) — risky to sell")

    # ── LAYER 2: SMC ZONES ──
    obs=order_blocks(dfh1 if dfh1 is not None else df5)
    fvgs=fvg_zones(df5)
    r["order_blocks"]=obs[:4]; r["fvg"]=fvgs[:3]

    bull_ob=[o for o in obs if o["type"]=="BULL"]
    bear_ob=[o for o in obs if o["type"]=="BEAR"]
    at_bull=any(o["low"]<=cp<=o["high"]*1.002 for o in bull_ob)
    at_bear=any(o["low"]*0.998<=cp<=o["high"] for o in bear_ob)

    if at_bull:   score+=18;buy_s+=1;conf+=2;sigs.append("🟩 AT Bullish OB — HIGH PROB buy zone")
    elif bull_ob: score+=5;sigs.append(f"🟩 Bullish OB support @ {bull_ob[0]['mid']:.5f}")
    if at_bear:   score+=18;sell_s+=1;conf+=2;sigs.append("🟥 AT Bearish OB — HIGH PROB sell zone")
    elif bear_ob: score+=5;sigs.append(f"🟥 Bearish OB resistance @ {bear_ob[0]['mid']:.5f}")

    bull_fvg=[f for f in fvgs if f["type"]=="BULL"]
    bear_fvg=[f for f in fvgs if f["type"]=="BEAR"]
    if bull_fvg:
        nf=min(bull_fvg,key=lambda x:abs(x["mid"]-cp))
        if abs(nf["mid"]-cp)<atr*0.5: score+=12;buy_s+=1;conf+=1;sigs.append(f"🔷 Entering Bullish FVG {nf['bot']:.5f}–{nf['top']:.5f}")
        else: sigs.append(f"🔷 Bullish FVG nearby @ {nf['mid']:.5f}")
    if bear_fvg:
        nf=min(bear_fvg,key=lambda x:abs(x["mid"]-cp))
        if abs(nf["mid"]-cp)<atr*0.5: score+=12;sell_s+=1;conf+=1;sigs.append(f"🔶 Entering Bearish FVG {nf['bot']:.5f}–{nf['top']:.5f}")
        else: sigs.append(f"🔶 Bearish FVG nearby @ {nf['mid']:.5f}")

    # ── LAYER 3: CLASSIC INDICATORS ──
    rsi=calc_rsi(c5); r["rsi"]=rsi
    ml,ms,mh=calc_macd(c5); r["macd"]=ml; r["macd_hist"]=mh
    adx=calc_adx(h5,l5,c5); r["adx"]=adx
    sk,sd=calc_stoch(h5,l5,c5); r["stoch_k"]=sk; r["stoch_d"]=sd
    bm,bu,bl=calc_bb(c5); rng=bu-bl
    bbp=((cp-bl)/rng*100) if rng>0 else 50; r["bb_pct"]=round(bbp,1)

    # RSI
    if 30<=rsi<=45 and bias=="BULLISH":   score+=12;buy_s+=1;conf+=1;sigs.append(f"📊 RSI {rsi} — Oversold in uptrend (ideal buy)")
    elif 55<=rsi<=70 and bias=="BEARISH": score+=12;sell_s+=1;conf+=1;sigs.append(f"📊 RSI {rsi} — Overbought in downtrend (ideal sell)")
    elif rsi<30:  score+=6;buy_s+=1;sigs.append(f"📊 RSI {rsi} — Extreme oversold")
    elif rsi>70:  score+=6;sell_s+=1;sigs.append(f"📊 RSI {rsi} — Extreme overbought")
    else: warns.append(f"📊 RSI {rsi} — Neutral zone")

    # MACD
    if mh>0 and ml>0:   score+=8;buy_s+=1;conf+=1;sigs.append("📈 MACD Bullish — above zero, hist positive")
    elif mh<0 and ml<0: score+=8;sell_s+=1;conf+=1;sigs.append("📉 MACD Bearish — below zero, hist negative")
    if len(c5)>=36:
        pm,ps,ph=calc_macd(c5[:-1])
        if ph<0 and mh>0: score+=10;buy_s+=1;conf+=1;sigs.append("⚡ MACD Bullish Cross just fired!")
        elif ph>0 and mh<0: score+=10;sell_s+=1;conf+=1;sigs.append("⚡ MACD Bearish Cross just fired!")

    # ADX
    if adx>35:    score+=10;conf+=1;sigs.append(f"💪 ADX {adx} — STRONG trend")
    elif adx>25:  score+=6;sigs.append(f"📏 ADX {adx} — Trending")
    else:         score-=5;warns.append(f"😴 ADX {adx} — Weak/choppy")

    # Stochastic
    if sk<25 and bias=="BULLISH":   score+=8;buy_s+=1;conf+=1;sigs.append(f"🔽 Stoch {sk:.0f} — Oversold, bull setup")
    elif sk>75 and bias=="BEARISH": score+=8;sell_s+=1;conf+=1;sigs.append(f"🔼 Stoch {sk:.0f} — Overbought, bear setup")

    # BB
    if bbp<15:   score+=8;buy_s+=1;sigs.append(f"📉 BB lower band touch ({bbp:.0f}%)")
    elif bbp>85: score+=8;sell_s+=1;sigs.append(f"📈 BB upper band touch ({bbp:.0f}%)")

    # EMA M5
    if len(c5)>=50:
        e8=calc_ema(c5,8); e21=calc_ema(c5,21)
        if e8>e21 and cp>e8:   score+=7;buy_s+=1;sigs.append("📈 M5 EMA8>EMA21 — bullish momentum")
        elif e8<e21 and cp<e8: score+=7;sell_s+=1;sigs.append("📉 M5 EMA8<EMA21 — bearish momentum")

    # ── LAYER 4: SESSION ──
    active=get_active_sessions()
    ss,sn=get_session_score(active)
    if ss>=85:   score+=15;conf+=1;sigs.append(f"⏰ {sn}")
    elif ss>=50: score+=8;sigs.append(f"⏰ {sn}")
    else:        score-=15;warns.append(f"⏰ {sn}")

    if "JPY" in symbol and "Tokyo" in active:   score+=8;conf+=1;sigs.append("🗾 JPY pair — Tokyo session active")
    if "GBP" in symbol and "London" in active:  score+=6;sigs.append("🇬🇧 GBP pair — London session active")
    if "EUR" in symbol and "London" in active:  score+=5;sigs.append("🇪🇺 EUR pair — London session active")
    if "USD" in symbol and "New York" in active: score+=5;sigs.append("🇺🇸 USD pair — NY session active")

    # ── LAYER 5: M5 ENTRY TRIGGER ──
    if len(c5)>=5:
        co=df5["Open"].values; ch=h5; cl=l5
        # Bullish engulfing
        if c5[-2]<co[-2] and c5[-1]>co[-1] and c5[-1]>co[-2] and co[-1]<c5[-2]:
            score+=10;buy_s+=1;conf+=1;sigs.append("🕯️ Bullish Engulfing — strong buy trigger")
        # Bearish engulfing
        elif c5[-2]>co[-2] and c5[-1]<co[-1] and c5[-1]<co[-2] and co[-1]>c5[-2]:
            score+=10;sell_s+=1;conf+=1;sigs.append("🕯️ Bearish Engulfing — strong sell trigger")
        # Hammer / Shooting star
        body=abs(c5[-1]-co[-1]); lw=min(c5[-1],co[-1])-cl[-1]; uw=ch[-1]-max(c5[-1],co[-1])
        if body>0:
            if lw>body*2 and uw<body*0.5: score+=8;buy_s+=1;sigs.append("🔨 Hammer pattern")
            elif uw>body*2 and lw<body*0.5: score+=8;sell_s+=1;sigs.append("⭐ Shooting Star pattern")
        # Pin bar
        tr_=ch[-1]-cl[-1]
        if tr_>0 and abs(c5[-1]-co[-1])/tr_<0.3:
            if lw>uw and bias=="BULLISH": score+=6;buy_s+=1;sigs.append("📌 Bullish Pin Bar")
            elif uw>lw and bias=="BEARISH": score+=6;sell_s+=1;sigs.append("📌 Bearish Pin Bar")

    # Momentum M5
    if len(c5)>=5:
        mom=c5[-1]-c5[-5]
        if mom>atr*0.3:   score+=5;buy_s+=1;sigs.append("⚡ Strong bullish M5 momentum"); r["m5_momentum"]="BULL"
        elif mom<-atr*0.3: score+=5;sell_s+=1;sigs.append("⚡ Strong bearish M5 momentum"); r["m5_momentum"]="BEAR"

    # Volume
    if df5["Volume"].sum()>0:
        av=np.mean(df5["Volume"].values[-20:]); cv=df5["Volume"].values[-1]
        if av>0:
            vr=cv/av
            if vr>1.8: score+=8;conf+=1;sigs.append(f"📊 Volume spike {vr:.1f}x — institutional")
            elif vr<0.4: score-=5;warns.append(f"📊 Low volume {vr:.1f}x — thin market")

    # ── LAYER 4b: COT REPORT (CFTC) ──
    cot = get_cot_for_pair(symbol, cot_df)
    r["cot"] = cot

    # ── CONFLICT PENALTIES ──
    if bias=="BULLISH" and rsi>72: score-=10;warns.append("⚠️ RSI overbought vs bullish bias")
    if bias=="BEARISH" and rsi<28: score-=10;warns.append("⚠️ RSI oversold vs bearish bias")
    if adx<18 and bos: score-=8;warns.append("⚠️ BOS but ADX very weak — false signal risk")

    # ── COT CONTRIBUTION (applied after direction known) ──
    cot_score_d, cot_conf_d, cot_sigs = cot_score_contribution(cot, direction)
    score += cot_score_d
    conf  += cot_conf_d
    sigs  += cot_sigs

    # ── NORMALIZE ──
    if buy_s>sell_s: direction="BUY"
    elif sell_s>buy_s: direction="SELL"
    else: direction="NEUTRAL"

    if direction=="BUY" and bias=="BEARISH":   score=int(score*0.6);warns.append("⚠️ BUY vs H4 BEARISH — counter-trend!")
    elif direction=="SELL" and bias=="BULLISH": score=int(score*0.6);warns.append("⚠️ SELL vs H4 BULLISH — counter-trend!")

    final=min(100,max(0,round((score+40)/2.4)))

    if final>=80 and conf>=6:   rating="🎯 SNIPER"
    elif final>=72 and conf>=5: rating="⚡ STRONG"
    elif final>=60 and conf>=4: rating="✅ SETUP"
    elif final>=45 and conf>=3: rating="👀 WATCH"
    elif final>=30:             rating="⏳ WAIT"
    else:                       rating="🚫 AVOID"

    if direction=="NEUTRAL" and rating in ["🎯 SNIPER","⚡ STRONG"]: rating="✅ SETUP"

    # ── SL/TP ──
    sl_d=atr*1.5; tp1_d=atr*2.5; tp2_d=atr*4.5
    sl_p=round(sl_d/pip); tp1_p=round(tp1_d/pip); tp2_p=round(tp2_d/pip)
    if direction=="BUY":
        slpr=round(cp-sl_d,5); tp1pr=round(cp+tp1_d,5); tp2pr=round(cp+tp2_d,5)
    elif direction=="SELL":
        slpr=round(cp+sl_d,5); tp1pr=round(cp-tp1_d,5); tp2pr=round(cp-tp2_d,5)
    else:
        slpr=tp1pr=tp2pr=cp
    rr=round(tp1_p/sl_p,2) if sl_p>0 else 0

    r.update({"score":final,"direction":direction,"rating":rating,"confirmations":conf,
               "signals":sigs,"warnings":warns,"buy_s":buy_s,"sell_s":sell_s,
               "sl_pips":sl_p,"tp1_pips":tp1_p,"tp2_pips":tp2_p,
               "sl_price":slpr,"tp1_price":tp1pr,"tp2_price":tp2pr,"rr_ratio":rr})
    return r

# ============================================================
# UI HELPERS
# ============================================================

def sc(score):
    if score>=75: return "#00ff88"
    if score>=60: return "#ffd700"
    if score>=45: return "#ff8c00"
    return "#ff3355"

def dc(d): return {"BUY":"#00ff88","SELL":"#ff3355"}.get(d,"#5a7a9a")

def badge(rating):
    cls={"🎯 SNIPER":"b-sniper","⚡ STRONG":"b-strong","✅ SETUP":"b-setup",
         "👀 WATCH":"b-watch","⏳ WAIT":"b-wait","🚫 AVOID":"b-avoid"}.get(rating,"b-avoid")
    return f"<span class='badge {cls}'>{rating}</span>"

def mcard(col, label, value, color="#00ff88"):
    col.markdown(f"<div class='metric-box'><div class='metric-label'>{label}</div>"
                 f"<div class='metric-value' style='color:{color}'>{value}</div></div>",
                 unsafe_allow_html=True)

def sbar(score, color=None):
    c=color or sc(score)
    return (f"<div class='score-bar-bg'>"
            f"<div style='height:100%;width:{score}%;background:{c};border-radius:2px'></div></div>")

# ============================================================
# COT RENDER HELPER
# ============================================================

def _render_cot_tab(cot, symbol):
    """Render full COT Report panel for a pair."""
    if not cot["available"]:
        st.markdown("""<div class='alert-box'>
        <b style='color:#ffd700'>📋 COT Data Not Loaded</b><br>
        Run a full scan first to load COT data from CFTC.<br>
        <span style='color:#5a7a9a;font-size:11px'>
        Data is updated every Friday after market close (UTC).
        Source: CFTC Traders in Financial Futures (TFF) Report.
        </span></div>""", unsafe_allow_html=True)
        return

    ci = cot["cot_index"]
    sig_color = "#00ff88" if cot["signal"]=="BULLISH" else "#ff3355" if cot["signal"]=="BEARISH" else "#ffd700"
    bar_color  = sig_color

    # COT Index visual gauge
    st.markdown(f"""
    <div style='background:#0d1e2e;border:1px solid #1a3a5c;border-radius:6px;padding:16px;margin-bottom:12px'>
        <div style='font-family:Share Tech Mono;font-size:11px;color:#5a7a9a;letter-spacing:2px;margin-bottom:8px'>
            COT INDEX — INSTITUTIONAL POSITIONING (0=MAX SHORT · 100=MAX LONG)
        </div>
        <div style='display:flex;justify-content:space-between;font-family:Share Tech Mono;
            font-size:10px;color:#1a3a5c;margin-bottom:4px'>
            <span>◀ EXTREME SHORT</span><span>NEUTRAL</span><span>EXTREME LONG ▶</span>
        </div>
        <div style='background:#050a0e;border-radius:3px;height:20px;position:relative;overflow:hidden'>
            <div style='position:absolute;left:50%;top:0;bottom:0;width:1px;background:#1a3a5c'></div>
            <div style='height:100%;width:{ci}%;background:linear-gradient(90deg,#ff3355,#ffd700,#00ff88);
                border-radius:3px;opacity:0.8'></div>
            <div style='position:absolute;top:2px;left:{min(ci,95)}%;font-family:Share Tech Mono;
                font-size:11px;color:#fff;font-weight:900'>{ci:.0f}</div>
        </div>
        <div style='margin-top:10px;font-family:Share Tech Mono;font-size:13px;color:{sig_color};font-weight:700'>
            {cot["signal"]} — {cot["sentiment"]}
        </div>
    </div>
    """, unsafe_allow_html=True)

    # 4 metric cards
    ca,cb,cc,cd = st.columns(4)
    chg_color = "#00ff88" if cot["dealer_chg"]>0 else "#ff3355"
    am_color  = "#00ff88" if cot["am_net"]>0 else "#ff3355"
    lev_color = "#ff3355" if cot["lev_net"]>0 else "#00ff88"  # retail is contra-indicator

    ca.markdown(f"""<div class='metric-box'>
    <div class='metric-label'>DEALER NET (Inst.)</div>
    <div class='metric-value' style='color:{sig_color};font-size:16px'>{cot["dealer_net"]:+,}</div>
    <div style='font-size:10px;color:{chg_color};font-family:Share Tech Mono'>
        WoW: {cot["dealer_chg"]:+,}</div></div>""", unsafe_allow_html=True)

    cb.markdown(f"""<div class='metric-box'>
    <div class='metric-label'>ASSET MGR NET</div>
    <div class='metric-value' style='color:{am_color};font-size:16px'>{cot["am_net"]:+,}</div>
    <div style='font-size:10px;color:{chg_color};font-family:Share Tech Mono'>
        WoW: {cot["am_chg"]:+,}</div></div>""", unsafe_allow_html=True)

    cc.markdown(f"""<div class='metric-box'>
    <div class='metric-label'>RETAIL (Lev.Funds)</div>
    <div class='metric-value' style='color:{lev_color};font-size:16px'>{cot["lev_net"]:+,}</div>
    <div style='font-size:10px;color:#5a7a9a;font-family:Share Tech Mono'>
        ⚠️ Retail = contra signal</div></div>""", unsafe_allow_html=True)

    mom_color = "#00ff88" if cot["cot_momentum"]=="INCREASING" else "#ff3355" if cot["cot_momentum"]=="DECREASING" else "#5a7a9a"
    cd.markdown(f"""<div class='metric-box'>
    <div class='metric-label'>COT MOMENTUM</div>
    <div class='metric-value' style='color:{mom_color};font-size:14px'>{cot["cot_momentum"]}</div>
    <div style='font-size:10px;color:#5a7a9a;font-family:Share Tech Mono'>
        Report: {cot["report_date"]}</div></div>""", unsafe_allow_html=True)

    # Interpretation guide
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("""<div style='background:#050a0e;border:1px solid #1a3a5c;border-radius:4px;
    padding:12px;font-family:Share Tech Mono;font-size:11px;color:#5a7a9a;line-height:2'>
    <b style='color:#7a9abf'>📚 HOW TO READ COT:</b><br>
    ◈ <b style='color:#e0f0ff'>Dealer/Institutional</b> = banks & market makers — follow their NET position<br>
    ◈ <b style='color:#e0f0ff'>Asset Manager</b> = hedge funds & large specs — usually trend followers<br>
    ◈ <b style='color:#ff8c00'>Leveraged Funds (Retail)</b> = small speculators — <b>CONTRA indicator</b> (when retail all long = smart money about to sell)<br>
    ◈ <b style='color:#ffd700'>COT Index &gt;80</b> = institutions max long = strong bullish bias (or potential reversal if extreme)<br>
    ◈ <b style='color:#ffd700'>COT Index &lt;20</b> = institutions max short = strong bearish bias<br>
    ◈ Best setup: COT aligns WITH your technical direction
    </div>""", unsafe_allow_html=True)


# ============================================================
# HEADER
# ============================================================

st.markdown("""
<div class='hdr'>
    <div class='hdr-title'>🎯 SNIPER FX</div>
    <div class='hdr-sub'>SMART MONEY SCALPING SCANNER — 28 PAIRS — SMC + CLASSIC — M5 / H1 / H4</div>
</div>
""", unsafe_allow_html=True)

# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:
    st.markdown("### ⚙️ SCANNER CONFIG")
    st.divider()

    active_sess=get_active_sessions()
    ss_val,ss_note=get_session_score(active_sess)
    st.markdown("**📡 SESSIONS (UTC)**")
    for sn in ["Sydney","Tokyo","London","New York"]:
        ia=sn in active_sess
        col="#00ff88" if ia else "#1a3a5c"
        dot=f"<span class='sess-dot' style='background:{col};{'box-shadow:0 0 6px '+col if ia else ''}'></span>"
        st.markdown(f"<div style='font-size:12px;color:{col};font-family:Share Tech Mono'>{dot}{sn}</div>",
                    unsafe_allow_html=True)
    sc_color="#00ff88" if ss_val>=75 else "#ffd700" if ss_val>=50 else "#ff3355"
    st.markdown(f"<div style='margin-top:8px;padding:7px;background:#0d1e2e;"
                f"border-left:3px solid {sc_color};font-family:Share Tech Mono;font-size:11px;"
                f"color:{sc_color}'>Session Score: {ss_val}/100<br>{ss_note}</div>",
                unsafe_allow_html=True)

    st.divider()
    st.markdown("**🌐 PAIRS**")
    pg=st.selectbox("Pair Group",["All (29)","Major (7)","Minor/Cross (21)","Commodities (XAUUSD)","Custom"])
    cp_list=[]
    if pg=="Custom":
        cp_list=st.multiselect("Select",list(ALL_PAIRS.keys()),default=["EURUSD","GBPUSD","USDJPY"])

    st.divider()
    st.markdown("**🎛️ FILTERS**")
    min_sc=st.slider("Min Score",0,100,50)
    min_cf=st.slider("Min Confirmations",0,10,3)
    show_r=st.multiselect("Ratings",["🎯 SNIPER","⚡ STRONG","✅ SETUP","👀 WATCH","⏳ WAIT","🚫 AVOID"],
                           default=["🎯 SNIPER","⚡ STRONG","✅ SETUP","👀 WATCH","⏳ WAIT","🚫 AVOID"])
    dir_f=st.selectbox("Direction",["All","BUY only","SELL only"])

    st.divider()
    st.markdown("""<div style='font-size:10px;color:#1a3a5c;font-family:Share Tech Mono;line-height:1.8'>
    ◈ SMC: Smart Money Concepts<br>◈ OB: Order Block<br>◈ FVG: Fair Value Gap<br>
    ◈ BOS: Break of Structure<br>◈ CHoCH: Change of Character<br>◈ P/D: Premium/Discount Zone
    </div>""", unsafe_allow_html=True)

# ============================================================
# PAIRS TO SCAN
# ============================================================

if pg=="Major (7)":            pairs=list(MAJOR_PAIRS.keys())
elif pg=="Minor/Cross (21)":   pairs=list(MINOR_PAIRS.keys())
elif pg=="Commodities (XAUUSD)": pairs=list(COMMODITY_PAIRS.keys())
elif pg=="Custom":             pairs=cp_list if cp_list else list(MAJOR_PAIRS.keys())
else:                          pairs=list(ALL_PAIRS.keys())

# ============================================================
# SCAN + QUICK ANALYZE BUTTONS
# ============================================================

cb1,cb2,cb3=st.columns([2,1,1])
with cb1: scan_btn=st.button(f"🔍 SCAN {len(pairs)} PAIRS",use_container_width=True)
with cb2:
    if st.button("🔄 CLEAR CACHE",use_container_width=True):
        st.cache_data.clear(); st.rerun()
with cb3:
    qp=st.selectbox("Quick Analyze",["—"]+list(ALL_PAIRS.keys()),label_visibility="collapsed")

# ============================================================
# QUICK SINGLE PAIR
# ============================================================

if qp and qp != "—":
    with st.spinner(f"Analyzing {qp}..."):
        res=analyze(qp)
    dc_=dc(res["direction"]); sc_=sc(res["score"])
    arrow="▲" if res["direction"]=="BUY" else "▼" if res["direction"]=="SELL" else "◆"
    dclass="buy" if res["direction"]=="BUY" else "sell" if res["direction"]=="SELL" else "neutral"

    st.markdown(f"""<div class='signal-card {dclass}'>
    <div style='display:flex;justify-content:space-between;align-items:center'>
        <div><span style='font-size:22px;font-weight:900;color:#e0f0ff;font-family:Share Tech Mono;
            letter-spacing:2px'>{res["symbol"]}</span>
        <span style='margin-left:10px;color:#5a7a9a;font-family:Share Tech Mono;font-size:13px'>
            {res["name"]} · {res["price"]:.5f}</span></div>
        <div style='text-align:right'>{badge(res["rating"])}
        <div style='font-size:22px;color:{dc_};font-weight:900;margin-top:4px'>{arrow} {res["direction"]}</div></div>
    </div></div>""", unsafe_allow_html=True)

    ca,cb_,cc,cd,ce=st.columns(5)
    mcard(ca,"SCORE",f"{res['score']}/100",sc_)
    mcard(cb_,"H4 BIAS",res["bias"],"#ffd700")
    mcard(cc,"CONFIRMATIONS",res["confirmations"],"#00bfff")
    mcard(cd,"ZONE",res["premium_zone"],"#ff8c00")
    mcard(ce,"RR RATIO",f"1:{res['rr_ratio']:.1f}","#ff8c00")

    st.markdown("<br>",unsafe_allow_html=True)
    ca2,cb2_,cc2=st.columns(3)
    mcard(ca2,"RSI",res["rsi"])
    mcard(cb2_,"ADX",res["adx"])
    mcard(cc2,"STOCH",f"{res['stoch_k']:.0f}")

    if res["direction"]!="NEUTRAL" and res["sl_pips"]>0:
        tc="#00ff88" if res["direction"]=="BUY" else "#ff3355"
        st.markdown(f"""<div class='alert-box'>
        <b style='color:{tc}'>📍 {res["direction"]} ENTRY PLAN</b><br>
        Entry <b>{res["price"]:.5f}</b> &nbsp;|&nbsp;
        SL <b style='color:#ff3355'>{res["sl_price"]:.5f}</b> ({res["sl_pips"]}p) &nbsp;|&nbsp;
        TP1 <b style='color:#00ff88'>{res["tp1_price"]:.5f}</b> ({res["tp1_pips"]}p) &nbsp;|&nbsp;
        TP2 <b style='color:#00ff88'>{res["tp2_price"]:.5f}</b> ({res["tp2_pips"]}p) &nbsp;|&nbsp;
        <b style='color:#ffd700'>RR 1:{res["rr_ratio"]:.1f}</b>
        </div>""", unsafe_allow_html=True)

    t1,t2,t3,t4=st.tabs(["📡 SIGNALS","⚠️ WARNINGS","🏗️ SMC ZONES","📋 COT REPORT"])
    with t1:
        for s in res["signals"]:
            st.markdown(f"<span class='conf-tag conf-pos'>{s}</span>",unsafe_allow_html=True)
    with t2:
        for w in res["warnings"]:
            st.markdown(f"<span class='conf-tag conf-neg'>{w}</span>",unsafe_allow_html=True)
        if not res["warnings"]: st.success("No warnings ✓")
    with t3:
        if res["order_blocks"]:
            st.markdown("**Order Blocks**")
            for ob in res["order_blocks"]:
                c_="#00ff88" if ob["type"]=="BULL" else "#ff3355"
                st.markdown(f"<div class='info-row'><span style='color:{c_}'>{ob['type']} OB</span>"
                            f"<span style='color:#7a9abf;font-family:Share Tech Mono;font-size:11px'>"
                            f"{ob['low']:.5f}–{ob['high']:.5f} str:{ob['str']}</span></div>",
                            unsafe_allow_html=True)
        if res["fvg"]:
            st.markdown("**Fair Value Gaps**")
            for f in res["fvg"]:
                c_="#00bfff" if f["type"]=="BULL" else "#ff8c00"
                st.markdown(f"<div class='info-row'><span style='color:{c_}'>{f['type']} FVG</span>"
                            f"<span style='color:#7a9abf;font-family:Share Tech Mono;font-size:11px'>"
                            f"{f['bot']:.5f}–{f['top']:.5f}</span></div>",
                            unsafe_allow_html=True)
    with t4:
        _render_cot_tab(res["cot"], res["symbol"])
    st.divider()

# ============================================================
# MAIN SCAN
# ============================================================

if scan_btn:
    st.session_state["scan_results"]=[]
    st.session_state["debug_log"]=[]

    # Load COT data once for all pairs
    cot_status = st.empty()
    cot_status.markdown("<div style='font-family:Share Tech Mono;font-size:11px;color:#ffd700'>"
                        "📋 Loading COT Report from CFTC...</div>", unsafe_allow_html=True)
    cot_df = fetch_cot_data()
    if cot_df is not None:
        cot_status.markdown("<div style='font-family:Share Tech Mono;font-size:11px;color:#00ff88'>"
                            f"✅ COT Report loaded — {len(cot_df)} records</div>", unsafe_allow_html=True)
    else:
        cot_status.markdown("<div style='font-family:Share Tech Mono;font-size:11px;color:#ff8c00'>"
                            "⚠️ COT data unavailable — analysis continues without it</div>", unsafe_allow_html=True)

    bar=st.progress(0,"Initializing...")
    txt=st.empty()
    results=[]
    debug_log=[]
    data_ok=0; data_fail=0
    for i,sym in enumerate(pairs):
        bar.progress((i+1)/len(pairs),f"Scanning {sym}... ({i+1}/{len(pairs)})")
        txt.markdown(f"<div style='font-family:Share Tech Mono;font-size:11px;color:#5a7a9a'>"
                     f"◈ Analyzing {ALL_PAIRS.get(sym,sym)}</div>",unsafe_allow_html=True)
        try:
            r = analyze(sym, cot_df)
            results.append(r)
            if r["price"] > 0:
                data_ok += 1
                debug_log.append(f"✅ {sym}: price={r['price']:.5f} score={r['score']} rating={r['rating']}")
            else:
                data_fail += 1
                sig_preview = r["signals"][0] if r["signals"] else "no signal"
                debug_log.append(f"❌ {sym}: no price data — {sig_preview}")
        except Exception as e:
            data_fail += 1
            debug_log.append(f"💥 {sym}: exception — {str(e)[:80]}")
            results.append({"symbol":sym,"name":ALL_PAIRS.get(sym,sym),"score":0,
                "direction":"NEUTRAL","rating":"🚫 AVOID","confirmations":0,
                "signals":[f"Error: {e}"],"warnings":[],"price":0,"rsi":50,"adx":20,
                "bias":"RANGING","bos":False,"choch":False,"premium_zone":"EQ","premium_pct":50,
                "sl_pips":0,"tp1_pips":0,"tp2_pips":0,"rr_ratio":0,"sl_price":0,
                "tp1_price":0,"tp2_price":0,"buy_s":0,"sell_s":0,"macd":0,"macd_hist":0,
                "stoch_k":50,"stoch_d":50,"bb_pct":50,"atr":0,"order_blocks":[],"fvg":[],
                "h1_trend":"N/A","h4_bias":"N/A","m5_momentum":"N/A","cot":_cot_empty()})
    bar.empty(); txt.empty(); cot_status.empty()
    st.session_state["scan_results"]=results
    st.session_state["debug_log"]=debug_log
    st.session_state["data_ok"]=data_ok
    st.session_state["data_fail"]=data_fail

# ============================================================
# DISPLAY RESULTS
# ============================================================

if st.session_state.get("scan_results"):
    results=st.session_state["scan_results"]

    # ── DEBUG PANEL ──
    data_ok   = st.session_state.get("data_ok", 0)
    data_fail = st.session_state.get("data_fail", 0)
    debug_log = st.session_state.get("debug_log", [])

    if data_fail > 0:
        with st.expander(f"⚠️ DEBUG — {data_ok} pairs OK / {data_fail} pairs FAILED (click to expand)", expanded=data_ok==0):
            st.markdown(f"""<div style='background:#050a0e;border:1px solid #1a3a5c;border-radius:4px;
            padding:12px;font-family:Share Tech Mono;font-size:11px;line-height:1.8'>""",
            unsafe_allow_html=True)
            for line in debug_log:
                color = "#00ff88" if line.startswith("✅") else "#ff3355" if line.startswith(("❌","💥")) else "#ffd700"
                st.markdown(f"<div style='color:{color}'>{line}</div>", unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)
            if data_ok == 0:
                st.markdown("""<div class='alert-box'>
                <b style='color:#ff3355'>🚨 All data fetches failed</b><br>
                yfinance cannot reach Yahoo Finance from this server.<br>
                <b>Solutions:</b><br>
                ◈ Try running locally: <code>streamlit run app.py</code><br>
                ◈ Or check if HF Spaces has network restrictions<br>
                ◈ yfinance sometimes needs a few minutes — try scanning again
                </div>""", unsafe_allow_html=True)
    rorder={"🎯 SNIPER":0,"⚡ STRONG":1,"✅ SETUP":2,"👀 WATCH":3,"⏳ WAIT":4,"🚫 AVOID":5}

    filtered=[r for r in results
              if r["score"]>=min_sc and r["confirmations"]>=min_cf
              and r["rating"] in show_r
              and (dir_f=="All"
                   or (dir_f=="BUY only" and r["direction"]=="BUY")
                   or (dir_f=="SELL only" and r["direction"]=="SELL"))]
    filtered.sort(key=lambda x:(rorder.get(x["rating"],9),-x["score"]))

    # Summary
    st.markdown("### 📊 SCAN SUMMARY")
    total=len(results)
    sniper=len([r for r in results if r["rating"]=="🎯 SNIPER"])
    strong=len([r for r in results if r["rating"]=="⚡ STRONG"])
    setups=len([r for r in results if r["rating"] in ["🎯 SNIPER","⚡ STRONG","✅ SETUP"]])
    buys=len([r for r in results if r["direction"]=="BUY"])
    sells=len([r for r in results if r["direction"]=="SELL"])

    c1,c2,c3,c4,c5,c6=st.columns(6)
    mcard(c1,"SCANNED",total,"#5a7a9a")
    mcard(c2,"🎯 SNIPER",sniper,"#ffd700")
    mcard(c3,"⚡ STRONG",strong,"#00ff88")
    mcard(c4,"📋 SETUPS",setups,"#00bfff")
    mcard(c5,"🟢 BUY",buys,"#00ff88")
    mcard(c6,"🔴 SELL",sells,"#ff3355")

    st.markdown(f"### 🎯 {len(filtered)} PAIRS MATCH FILTERS")

    if not filtered:
        st.markdown("<div class='alert-box'>No pairs match current filters — try lowering thresholds.</div>",
                    unsafe_allow_html=True)
    else:
        tab1,tab2,tab3,tab_cot=st.tabs(["🃏 SIGNAL CARDS","📋 TABLE","🏆 TOP SETUPS","📋 COT OVERVIEW"])

        with tab1:
            for r in filtered[:20]:
                dc_=dc(r["direction"]); sc_=sc(r["score"])
                dclass="buy" if r["direction"]=="BUY" else "sell" if r["direction"]=="SELL" else "neutral"
                arrow="▲" if r["direction"]=="BUY" else "▼" if r["direction"]=="SELL" else "◆"
                st.markdown(f"""<div class='signal-card {dclass}'>
                <div style='display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:8px'>
                    <div><span style='font-size:17px;font-weight:900;color:#e0f0ff;
                        font-family:Share Tech Mono;letter-spacing:2px'>{r["symbol"]}</span>
                    <span style='margin-left:8px;font-size:11px;color:#5a7a9a;
                        font-family:Share Tech Mono'>{r["price"]:.5f}</span></div>
                    <div style='text-align:right'>{badge(r["rating"])}
                    <div style='color:{dc_};font-size:18px;font-weight:900'>{arrow} {r["direction"]}</div>
                    </div></div>
                <div style='display:flex;gap:10px;flex-wrap:wrap;margin-bottom:6px'>
                    <span style='font-family:Share Tech Mono;font-size:11px;color:{sc_}'>SCORE:{r["score"]}</span>
                    <span style='font-family:Share Tech Mono;font-size:11px;color:#00bfff'>CONF:{r["confirmations"]}</span>
                    <span style='font-family:Share Tech Mono;font-size:11px;color:#ffd700'>H4:{r["bias"]}</span>
                    <span style='font-family:Share Tech Mono;font-size:11px;color:#ff8c00'>ZONE:{r["premium_zone"]}</span>
                    <span style='font-family:Share Tech Mono;font-size:11px;color:#7a9abf'>RSI:{r["rsi"]}</span>
                    <span style='font-family:Share Tech Mono;font-size:11px;color:#7a9abf'>ADX:{r["adx"]}</span>
                </div>
                {sbar(r["score"],sc_)}
                <div style='margin-top:6px'>""", unsafe_allow_html=True)
                for s in r["signals"][:3]:
                    st.markdown(f"<span class='conf-tag conf-pos'>◈ {s}</span>",unsafe_allow_html=True)
                if r["direction"]!="NEUTRAL" and r["sl_pips"]>0:
                    tc="#00ff88" if r["direction"]=="BUY" else "#ff3355"
                    st.markdown(f"""<div style='margin-top:8px;padding:8px;background:#050a0e;
                        border-radius:4px;font-family:Share Tech Mono;font-size:11px'>
                        <span style='color:#5a7a9a'>ENTRY</span>
                        <span style='color:#e0f0ff;margin:0 8px'>{r["price"]:.5f}</span>
                        <span style='color:#ff3355'>SL {r["sl_price"]:.5f} ({r["sl_pips"]}p)</span>
                        <span style='margin:0 6px;color:#1a3a5c'>|</span>
                        <span style='color:#00ff88'>TP1 {r["tp1_price"]:.5f} ({r["tp1_pips"]}p)</span>
                        <span style='margin:0 6px;color:#1a3a5c'>|</span>
                        <span style='color:#00ff88'>TP2 {r["tp2_price"]:.5f}</span>
                        <span style='margin-left:8px;color:#ffd700'>RR 1:{r["rr_ratio"]:.1f}</span>
                    </div>""", unsafe_allow_html=True)
                st.markdown("</div></div><br>",unsafe_allow_html=True)

        with tab2:
            rows=[]
            for r in filtered:
                cot=r.get("cot",_cot_empty())
                rows.append({
                    "Pair":r["symbol"],"Price":f"{r['price']:.5f}",
                    "Dir":r["direction"],"Score":r["score"],"Rating":r["rating"],
                    "Conf":r["confirmations"],"H4":r["bias"],"Zone":r["premium_zone"],
                    "RSI":r["rsi"],"ADX":r["adx"],
                    "BOS":"✓" if r.get("bos") else "","CHoCH":"✓" if r.get("choch") else "",
                    "COT Idx":f"{cot['cot_index']:.0f}" if cot["available"] else "N/A",
                    "COT Sig":cot["signal"] if cot["available"] else "N/A",
                    "SL p":r["sl_pips"],"TP1 p":r["tp1_pips"],"RR":f"1:{r['rr_ratio']:.1f}"
                })
            if rows:
                st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True,
                             height=min(600,40+len(rows)*35))

        with tab3:
            st.markdown("### 🏆 TOP 5 SETUPS")
            top5=[r for r in filtered if r["rating"] in ["🎯 SNIPER","⚡ STRONG"]][:5]
            if not top5: top5=filtered[:5]
            medals=["🥇","🥈","🥉","4️⃣","5️⃣"]
            for i,r in enumerate(top5):
                dc_=dc(r["direction"]); sc_=sc(r["score"])
                dclass="buy" if r["direction"]=="BUY" else "sell" if r["direction"]=="SELL" else "neutral"
                st.markdown(f"""<div class='signal-card {dclass}'>
                <div style='display:flex;justify-content:space-between'>
                    <div><span style='font-size:16px'>{medals[i]}</span>
                    <span style='font-size:22px;font-weight:900;color:#e0f0ff;
                        font-family:Share Tech Mono;margin-left:8px'>{r["symbol"]}</span>
                    <span style='font-size:20px;font-weight:900;color:{dc_};margin-left:12px'>
                        {r["direction"]}</span></div>
                    <div style='text-align:right'>
                        <div style='font-size:30px;font-weight:900;color:{sc_};
                            font-family:Share Tech Mono'>{r["score"]}</div>
                        <div style='font-size:9px;color:#5a7a9a;letter-spacing:1px'>SNIPER SCORE</div>
                    </div></div>
                {sbar(r["score"],sc_)}
                <div style='margin-top:10px;font-family:Share Tech Mono;font-size:11px;
                    color:#7a9abf;line-height:1.8'>
                    ◈ {r["price"]:.5f} &nbsp;|&nbsp; SL {r["sl_price"]:.5f} ({r["sl_pips"]}p)
                    &nbsp;|&nbsp; TP1 {r["tp1_price"]:.5f} &nbsp;|&nbsp; TP2 {r["tp2_price"]:.5f}
                    &nbsp;|&nbsp; <span style='color:#ffd700'>RR 1:{r["rr_ratio"]:.1f}</span>
                </div><div style='margin-top:6px'>""", unsafe_allow_html=True)
                for s in r["signals"][:4]:
                    st.markdown(f"<span class='conf-tag conf-pos'>{s}</span>",unsafe_allow_html=True)
                st.markdown("</div></div><br>",unsafe_allow_html=True)

        with tab_cot:
            st.markdown("### 📋 COT REPORT — INSTITUTIONAL POSITIONING OVERVIEW")
            st.caption("CFTC Traders in Financial Futures | Updated every Friday | Source: CFTC.gov")
            st.divider()

            # Check if any COT data available
            cot_available = any(r.get("cot",{}).get("available") for r in results)
            if not cot_available:
                st.markdown("""<div class='alert-box'>
                <b style='color:#ffd700'>⚠️ COT data was not loaded</b><br>
                CFTC may be unreachable or data may not be available yet.
                COT is published every Friday ~3:30 PM EST.
                The scanner still works with all other 5 layers.
                </div>""", unsafe_allow_html=True)
            else:
                # Sort by COT index for most bullish/bearish
                cot_results = [(r["symbol"], r.get("cot",_cot_empty()))
                               for r in results if r.get("cot",{}).get("available")]
                cot_bull = sorted([(s,c) for s,c in cot_results if c["signal"]=="BULLISH"],
                                  key=lambda x:-x[1]["cot_index"])
                cot_bear = sorted([(s,c) for s,c in cot_results if c["signal"]=="BEARISH"],
                                  key=lambda x:x[1]["cot_index"])
                cot_neut = [(s,c) for s,c in cot_results if c["signal"]=="NEUTRAL"]

                col_l, col_r = st.columns(2)
                with col_l:
                    st.markdown(f"**🟢 INSTITUTIONALLY BULLISH ({len(cot_bull)})**")
                    for sym, cot in cot_bull[:10]:
                        ci=cot["cot_index"]
                        bar_w=int(ci)
                        st.markdown(f"""
                        <div style='margin:6px 0'>
                            <div style='display:flex;justify-content:space-between;
                                font-family:Share Tech Mono;font-size:12px;margin-bottom:3px'>
                                <span style='color:#e0f0ff'>{sym}</span>
                                <span style='color:#00ff88'>Index:{ci:.0f} | Net:{cot["dealer_net"]:+,}</span>
                            </div>
                            <div style='background:#050a0e;border-radius:2px;height:4px'>
                                <div style='width:{bar_w}%;height:100%;background:#00ff88;border-radius:2px'></div>
                            </div>
                        </div>""", unsafe_allow_html=True)

                with col_r:
                    st.markdown(f"**🔴 INSTITUTIONALLY BEARISH ({len(cot_bear)})**")
                    for sym, cot in cot_bear[:10]:
                        ci=cot["cot_index"]
                        bar_w=int(100-ci)
                        st.markdown(f"""
                        <div style='margin:6px 0'>
                            <div style='display:flex;justify-content:space-between;
                                font-family:Share Tech Mono;font-size:12px;margin-bottom:3px'>
                                <span style='color:#e0f0ff'>{sym}</span>
                                <span style='color:#ff3355'>Index:{ci:.0f} | Net:{cot["dealer_net"]:+,}</span>
                            </div>
                            <div style='background:#050a0e;border-radius:2px;height:4px'>
                                <div style='width:{bar_w}%;height:100%;background:#ff3355;border-radius:2px'></div>
                            </div>
                        </div>""", unsafe_allow_html=True)

                # Extreme alerts
                extremes = [(s,c) for s,c in cot_results if c["extreme"]]
                if extremes:
                    st.divider()
                    st.markdown("**⚠️ EXTREME POSITIONING ALERTS — Potential Reversal Zones**")
                    for sym, cot in extremes:
                        ci = cot["cot_index"]
                        if ci > 80:
                            msg = f"🔴 {sym}: EXTREME LONG (Index:{ci:.0f}) — institutions max long, reversal risk"
                            col = "#ff8c00"
                        else:
                            msg = f"🟢 {sym}: EXTREME SHORT (Index:{ci:.0f}) — institutions max short, bounce risk"
                            col = "#00bfff"
                        st.markdown(f"<div style='font-family:Share Tech Mono;font-size:12px;"
                                    f"color:{col};padding:4px 0'>{msg}</div>", unsafe_allow_html=True)

    # Market overview
    st.divider()
    st.markdown("### 🌐 MARKET OVERVIEW")
    all_buy=sorted([r for r in results if r["direction"]=="BUY"],key=lambda x:-x["score"])
    all_sell=sorted([r for r in results if r["direction"]=="SELL"],key=lambda x:-x["score"])
    all_neut=[r for r in results if r["direction"]=="NEUTRAL"]

    co1,co2,co3=st.columns(3)
    with co1:
        st.markdown(f"**🟢 BUY ({len(all_buy)})**")
        for r in all_buy[:10]:
            s_=sc(r["score"])
            st.markdown(f"<div class='info-row'>"
                        f"<span style='color:#e0f0ff;font-family:Share Tech Mono;font-size:12px'>{r['symbol']}</span>"
                        f"<span style='color:{s_};font-family:Share Tech Mono;font-size:12px'>{r['score']} {r['rating'].split()[0]}</span></div>",
                        unsafe_allow_html=True)
    with co2:
        st.markdown(f"**🔴 SELL ({len(all_sell)})**")
        for r in all_sell[:10]:
            s_=sc(r["score"])
            st.markdown(f"<div class='info-row'>"
                        f"<span style='color:#e0f0ff;font-family:Share Tech Mono;font-size:12px'>{r['symbol']}</span>"
                        f"<span style='color:{s_};font-family:Share Tech Mono;font-size:12px'>{r['score']} {r['rating'].split()[0]}</span></div>",
                        unsafe_allow_html=True)
    with co3:
        st.markdown(f"**⚪ NEUTRAL ({len(all_neut)})**")
        for r in all_neut[:10]:
            st.markdown(f"<div class='info-row'>"
                        f"<span style='color:#5a7a9a;font-family:Share Tech Mono;font-size:12px'>{r['symbol']}</span>"
                        f"<span style='color:#1a3a5c;font-family:Share Tech Mono;font-size:12px'>{r['score']}</span></div>",
                        unsafe_allow_html=True)

# Empty state
elif not st.session_state.get("scan_results"):
    st.markdown("""<div style='text-align:center;padding:60px 20px'>
    <div style='font-size:64px;margin-bottom:20px'>🎯</div>
    <div style='font-family:Share Tech Mono;font-size:22px;color:#5a7a9a;
        letter-spacing:4px;margin-bottom:12px'>SCANNER READY</div>
    <div style='font-family:Share Tech Mono;font-size:11px;color:#1a3a5c;
        line-height:2.2;max-width:480px;margin:auto'>
        ◈ LAYER 1 — H4 Market Structure (BOS / CHoCH)<br>
        ◈ LAYER 2 — SMC Zones (Order Block / FVG / Liquidity)<br>
        ◈ LAYER 3 — Classic Indicators (RSI / MACD / ADX / Stoch / BB)<br>
        ◈ LAYER 4 — Session Filter (London / NY / Tokyo / Sydney)<br>
        ◈ LAYER 5 — M5 Entry Trigger (Engulfing / Hammer / Pin Bar)
    </div></div>""", unsafe_allow_html=True)

# Footer
st.divider()
st.markdown("""<div style='text-align:center;font-family:Share Tech Mono;font-size:10px;
color:#1a3a5c;letter-spacing:2px;padding:10px'>
SNIPER FX v1.0 ◈ EDUCATIONAL PURPOSES ONLY ◈ NOT FINANCIAL ADVICE ◈
ALWAYS USE PROPER RISK MANAGEMENT ◈ MAX 1-2% RISK PER TRADE
</div>""", unsafe_allow_html=True)

if "scan_results" not in st.session_state: st.session_state["scan_results"]=[]
