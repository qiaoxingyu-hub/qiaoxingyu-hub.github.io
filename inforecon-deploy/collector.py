import sys, os, json, urllib.request, urllib.parse, re
sys.path.insert(0, os.path.dirname(__file__))
from database import save_indicator, save_event, today
try: import akshare as ak; AK = True
except: AK = False

H = {"User-Agent": "Mozilla/5.0 Chrome/120"}

def bing(q, n=3):
    url = "https://www.bing.com/search?" + urllib.parse.urlencode({"q": q})
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=H), timeout=15) as r:
            h = r.read().decode(errors="replace")
        p = re.compile(r'<li[^>]*class="b_algo"[^>]*>.*?<h2[^>]*>.*?<a[^>]*href="([^"]*)"[^>]*>(.*?)</a>.*?</h2>(.*?)</li>', re.DOTALL)
        out = []
        for u, t, s in p.findall(h)[:n]:
            out.append({"title": re.sub(r"<[^>]+>","",t).strip(), "snippet": re.sub(r"<[^>]+>","",s).strip()[:300]})
        return out
    except: return []

def sh():
    df = ak.stock_zh_index_daily(symbol="sh000001")
    v = float(df.iloc[-1]["close"]); save_indicator("stock","shanghai_composite",v,"点","akshare"); return v

def gold():
    df = ak.spot_golden_benchmark_sge(); last = df.iloc[-1]
    for c in ["早盘价","晚盘价"]:
        if c in df.columns:
            v = float(last[c])
            if 300 < v < 2000: save_indicator("commodity","gold_cny",v,"元/克","akshare"); return v
    return None

def oil():
    df = ak.futures_foreign_hist(symbol="OIL"); v = float(df.iloc[-1]["close"])
    if 30 < v < 200: save_indicator("commodity","wti_oil",v,"美元/桶","akshare"); return v

def cpi():
    df = ak.macro_usa_cpi_yoy()
    for i in range(len(df)-1,-1,-1):
        v = float(df.iloc[i]["现值"])
        if 1.0 < v < 10.0: save_indicator("macro","us_cpi_yoy",v,"%","akshare"); return v

def fx():
    df = ak.currency_boc_sina(); v = float(df.iloc[-1]["央行中间价"]) / 100.0
    if 6.0 < v < 8.0: save_indicator("currency","usdcny",v,"CNY/USD","akshare"); return v

def collect():
    # AI科技 - 用尽量具体的搜索词
    for q in ["AI芯片 半导体 国产替代", "英伟达 台积电 芯片 产能", "数据中心 算力 建设", "先进封装 CoWoS HBM", "AI GPU 供应 市场"]:
        for r in bing(q, 2):
            save_event(today(), "[AI产业] " + r["title"], r["snippet"][:200], "tech", 5)
    # geopolitics
    for q in ["伊朗 以色列 最新 局势", "霍尔木兹 海峡 封锁"]:
        for r in bing(q, 3):
            save_event(today(), r["title"], r["snippet"][:200], "geopolitics", 5)
    # economy
    for q in ["美联储 沃什 利率 决议", "美国 CPI 通胀 最新", "中国经济 政策 2026"]:
        for r in bing(q, 3):
            save_event(today(), r["title"], r["snippet"][:200], "economy", 5)

def all():
    ind = {}
    for n,f in [("sh",sh),("gold",gold),("oil",oil),("cpi",cpi),("fx",fx)]:
        try: ind[n] = f()
        except: ind[n] = None
    collect()
    return ind

if __name__ == "__main__":
    print(json.dumps(all(), ensure_ascii=False, indent=2))
