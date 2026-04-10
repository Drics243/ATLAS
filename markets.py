MARKET_MAP = {
    # ── MAJOR FOREX PAIRS ──────────────────────
    "EURUSD": "EURUSD=X", "GBPUSD": "GBPUSD=X", "USDJPY": "USDJPY=X",
    "USDCHF": "USDCHF=X", "AUDUSD": "AUDUSD=X", "USDCAD": "USDCAD=X",
    "NZDUSD": "NZDUSD=X",

    # ── MINOR FOREX PAIRS ──────────────────────
    "EURGBP": "EURGBP=X", "EURJPY": "EURJPY=X", "EURCHF": "EURCHF=X",
    "EURAUD": "EURAUD=X", "EURCAD": "EURCAD=X", "EURNZD": "EURNZD=X",
    "GBPJPY": "GBPJPY=X", "GBPCHF": "GBPCHF=X", "GBPAUD": "GBPAUD=X",
    "GBPCAD": "GBPCAD=X", "GBPNZD": "GBPNZD=X", "AUDJPY": "AUDJPY=X",
    "AUDCHF": "AUDCHF=X", "AUDCAD": "AUDCAD=X", "AUDNZD": "AUDNZD=X",
    "CADJPY": "CADJPY=X", "CADCHF": "CADCHF=X", "CHFJPY": "CHFJPY=X",
    "NZDJPY": "NZDJPY=X", "NZDCHF": "NZDCHF=X", "NZDCAD": "NZDCAD=X",

    # ── EXOTIC FOREX PAIRS ─────────────────────
    "USDSEK": "USDSEK=X", "USDNOK": "USDNOK=X", "USDDKK": "USDDKK=X",
    "USDSGD": "USDSGD=X", "USDHKD": "USDHKD=X", "USDMXN": "USDMXN=X",
    "USDZAR": "USDZAR=X", "USDTRY": "USDTRY=X", "USDPLN": "USDPLN=X",
    "USDCZK": "USDCZK=X", "USDHUF": "USDHUF=X", "USDRUB": "USDRUB=X",
    "USDCNH": "USDCNH=X", "USDTHB": "USDTHB=X", "USDINR": "USDINR=X",
    "USDKRW": "USDKRW=X", "USDBRL": "USDBRL=X", "USDCLP": "USDCLP=X",
    "USDCOP": "USDCOP=X", "USDMYR": "USDMYR=X", "USDPHP": "USDPHP=X",
    "USDIDR": "USDIDR=X", "EURSEK": "EURSEK=X", "EURNOK": "EURNOK=X",
    "EURPLN": "EURPLN=X", "EURTRY": "EURTRY=X", "EURHUF": "EURHUF=X",

    # ── METALS ────────────────────────────────
    "XAUUSD": "GC=F",   "GOLD": "GC=F",
    "XAGUSD": "SI=F",   "SILVER": "SI=F",
    "XPTUSD": "PL=F",   "PLATINUM": "PL=F",
    "XPDUSD": "PA=F",   "PALLADIUM": "PA=F",
    "XCUUSD": "HG=F",   "COPPER": "HG=F",

    # ── ENERGY / OIL ──────────────────────────
    "XTIUSD": "CL=F",   "USOIL": "CL=F",    "WTI": "CL=F",    "WTIUSD": "CL=F",
    "XBRUSD": "BZ=F",   "UKOIL": "BZ=F",    "BRENT": "BZ=F",
    "NATGAS": "NG=F",   "XNGUSD": "NG=F",

    # ── US INDICES ────────────────────────────
    "SPX500": "^GSPC",  "SP500": "^GSPC",   "US500": "^GSPC",  "SPX": "^GSPC",
    "NAS100": "^NDX",   "NDX": "^NDX",      "US100": "^NDX",   "NASDAQ": "^NDX",
    "US30":   "^DJI",   "DJI": "^DJI",      "DOW": "^DJI",     "DOWJONES": "^DJI",
    "US2000": "^RUT",   "RUT": "^RUT",      "RUSSELL": "^RUT",
    "VIX":    "^VIX",

    # ── GLOBAL INDICES ────────────────────────
    "GER40":  "^GDAXI", "DAX": "^GDAXI",    "DE40": "^GDAXI",
    "UK100":  "^FTSE",  "FTSE": "^FTSE",    "FTSE100": "^FTSE",
    "FRA40":  "^FCHI",  "CAC40": "^FCHI",
    "JPN225": "^N225",  "NIKKEI": "^N225",  "JP225": "^N225",
    "AUS200": "^AXJO",  "ASX200": "^AXJO",
    "HK50":   "^HSI",   "HANGSENG": "^HSI",
    "CHN50":  "000300.SS",
    "STOXX50": "^STOXX50E", "EU50": "^STOXX50E",
    "SWI20":  "^SSMI",  "SMI": "^SSMI",
    "SING30": "^STI",
    "ITA40":  "FTSEMIB.MI",
    "ESP35":  "^IBEX",

    # ── CURRENCY INDICES ──────────────────────
    "DXY":    "DX-Y.NYB", "DOLLAR": "DX-Y.NYB", "USDX": "DX-Y.NYB",
    "EURX":   "EUR=X",
    "JPYX":   "JPY=X",
    "GBPX":   "GBP=X",

    # ── CRYPTO (non-pump.fun) ─────────────────
    "BTCUSD": "BTC-USD", "BITCOIN": "BTC-USD",
    "ETHUSD": "ETH-USD", "ETHEREUM": "ETH-USD",
    "SOLUSD": "SOL-USD", "SOLANA": "SOL-USD",
    "BNBUSD": "BNB-USD",
    "XRPUSD": "XRP-USD",
}

# Aliases with slash notation
SLASH_ALIASES = {}
for k, v in MARKET_MAP.items():
    if len(k) >= 6 and "=" not in k and "^" not in k and "." not in k:
        with_slash = k[:3] + "/" + k[3:]
        SLASH_ALIASES[with_slash] = v

MARKET_MAP.update(SLASH_ALIASES)


def resolve_symbol(user_input: str) -> tuple:
    """
    Returns (yahoo_symbol, display_name, market_type)
    market_type: 'forex' | 'metal' | 'index' | 'energy' | 'crypto_cex' | None
    """
    clean = user_input.upper().strip().replace(" ", "").replace("-", "")

    if clean in MARKET_MAP:
        sym = MARKET_MAP[clean]
        if "=F" in sym or sym in ["GC=F", "SI=F", "PL=F", "PA=F", "HG=F", "CL=F", "BZ=F", "NG=F"]:
            mtype = "metal" if clean.startswith("X") or clean in ["GOLD", "SILVER", "PLATINUM", "PALLADIUM", "COPPER"] else "energy"
        elif sym.startswith("^") or sym.endswith(".NYB") or "." in sym:
            mtype = "index"
        elif sym.endswith("-USD"):
            mtype = "crypto_cex"
        else:
            mtype = "forex"
        return sym, clean, mtype

    return None, clean, None
