"""????"""
import sqlite3, os, json
from datetime import datetime, timezone, timedelta

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "inforecon.db")
TZ = timezone(timedelta(hours=8))

def now(): return datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S")
def today(): return datetime.now(TZ).strftime("%Y-%m-%d")

def conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    return c

def init_db():
    c = conn()
    c.executescript("""
        CREATE TABLE IF NOT EXISTS indicators (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            category TEXT NOT NULL,
            name TEXT NOT NULL,
            value REAL NOT NULL,
            unit TEXT DEFAULT "",
            source TEXT DEFAULT ""
        );
        CREATE INDEX IF NOT EXISTS idx_icat ON indicators(category, timestamp);

        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT DEFAULT "",
            category TEXT DEFAULT "other",
            impact_score INTEGER DEFAULT 5,
            ticker TEXT DEFAULT "",
            sentiment TEXT DEFAULT "neutral",
            impact_metric REAL DEFAULT 0.0,
            is_resolved INTEGER DEFAULT 0,
            resolution_date TEXT
        );

        CREATE TABLE IF NOT EXISTS predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            category TEXT NOT NULL,
            subject TEXT NOT NULL,
            direction TEXT NOT NULL,
            target_value TEXT DEFAULT "",
            timeframe TEXT DEFAULT "3m",
            confidence INTEGER DEFAULT 5,
            reasoning TEXT DEFAULT "",
            status TEXT DEFAULT "pending",
            resolved_at TEXT,
            actual_outcome TEXT DEFAULT ""
        );

        CREATE TABLE IF NOT EXISTS rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            name TEXT NOT NULL,
            description TEXT DEFAULT "",
            condition_type TEXT NOT NULL,
            condition_params TEXT DEFAULT "{}",
            action_type TEXT NOT NULL,
            action_target TEXT DEFAULT "",
            confidence REAL DEFAULT 0.0,
            accuracy REAL DEFAULT 0.0,
            trigger_count INTEGER DEFAULT 0,
            correct_count INTEGER DEFAULT 0,
            last_triggered TEXT,
            is_active INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            ticker TEXT NOT NULL,
            trade_type TEXT NOT NULL,
            price REAL NOT NULL,
            quantity REAL DEFAULT 1,
            amount REAL NOT NULL,
            rule_id INTEGER,
            prediction_id INTEGER,
            notes TEXT DEFAULT "",
            status TEXT DEFAULT "open",
            pnl REAL DEFAULT 0.0,
            close_price REAL,
            close_at TEXT,
            FOREIGN KEY(rule_id) REFERENCES rules(id),
            FOREIGN KEY(prediction_id) REFERENCES predictions(id)
        );

        CREATE TABLE IF NOT EXISTS portfolios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            total_value REAL NOT NULL,
            cash REAL NOT NULL,
            positions_json TEXT DEFAULT "{}",
            metrics_json TEXT DEFAULT "{}"
        );
    """)
    # Ensure events have new columns (migration safe)
    for col in ["ticker", "sentiment", "impact_metric"]:
        try: c.execute(f"ALTER TABLE events ADD COLUMN {col}")
        except: pass
    c.commit(); c.close()

init_db()

def save_indicator(cat, name, val, unit="", source=""):
    c = conn(); c.execute("INSERT INTO indicators(timestamp,category,name,value,unit,source) VALUES(?,?,?,?,?,?)",(now(),cat,name,val,unit,source)); c.commit(); c.close()

def get_latest():
    c = conn()
    rows = c.execute("""SELECT i.* FROM indicators i
        INNER JOIN (SELECT category, name, MAX(timestamp) as mt FROM indicators GROUP BY category, name) m
        ON i.category=m.category AND i.name=m.mt ORDER BY i.category, i.name""").fetchall()
    c.close(); return [dict(r) for r in rows]

def save_event(date, title, desc="", cat="other", score=5, ticker="", sentiment="neutral", impact=0.0):
    c = conn()
    c.execute("INSERT INTO events(date,title,description,category,impact_score,ticker,sentiment,impact_metric) VALUES(?,?,?,?,?,?,?,?)",
              (date,title,desc,cat,score,ticker,sentiment,impact))
    c.commit(); c.close()

def get_events(cat=None, pending=False):
    c = conn()
    if pending: rows = c.execute("SELECT * FROM events WHERE is_resolved=0 ORDER BY date DESC LIMIT 50").fetchall()
    elif cat: rows = c.execute("SELECT * FROM events WHERE category=? ORDER BY date DESC LIMIT 50",(cat,)).fetchall()
    else: rows = c.execute("SELECT * FROM events ORDER BY date DESC LIMIT 50").fetchall()
    c.close(); return [dict(r) for r in rows]

def save_prediction(cat, subj, direction, target="", tf="3m", conf=5, reason=""):
    c = conn(); c.execute("INSERT INTO predictions(created_at,category,subject,direction,target_value,timeframe,confidence,reasoning) VALUES(?,?,?,?,?,?,?,?)",(now(),cat,subj,direction,target,tf,conf,reason)); c.commit(); c.close()

def resolve_prediction(pid, status, actual=""):
    c = conn(); c.execute("UPDATE predictions SET status=?,resolved_at=?,actual_outcome=? WHERE id=?",(status,now(),actual,pid)); c.commit(); c.close()

def get_predictions(status=None):
    c = conn()
    if status: rows = c.execute("SELECT * FROM predictions WHERE status=? ORDER BY created_at DESC",(status,)).fetchall()
    else: rows = c.execute("SELECT * FROM predictions ORDER BY created_at DESC").fetchall()
    c.close(); return [dict(r) for r in rows]

def get_stats():
    c = conn()
    total = c.execute("SELECT COUNT(*) as c FROM predictions WHERE status IN ('correct','wrong')").fetchone()["c"]
    correct = c.execute("SELECT COUNT(*) as c FROM predictions WHERE status='correct'").fetchone()["c"]
    c.close()
    return {"total": total, "correct": correct, "accuracy": round(correct/total*100,1) if total else 0}

def save_rule(name, desc, cond_type, cond_params, action_type, action_target=""):
    c = conn(); c.execute("INSERT INTO rules(created_at,name,description,condition_type,condition_params,action_type,action_target) VALUES(?,?,?,?,?,?,?)",(now(),name,desc,cond_type,json.dumps(cond_params),action_type,action_target)); c.commit(); c.close()

def get_rules(active_only=False):
    c = conn()
    if active_only: rows = c.execute("SELECT * FROM rules WHERE is_active=1 ORDER BY accuracy DESC").fetchall()
    else: rows = c.execute("SELECT * FROM rules ORDER BY created_at DESC").fetchall()
    c.close(); return [dict(r) for r in rows]

def trigger_rule(rid, success):
    c = conn()
    c.execute("UPDATE rules SET trigger_count=trigger_count+1, last_triggered=?, correct_count=correct_count+? WHERE id=?",(now(),1 if success else 0,rid))
    r = c.execute("SELECT trigger_count, correct_count FROM rules WHERE id=?",(rid,)).fetchone()
    if r: c.execute("UPDATE rules SET accuracy=? WHERE id=?",(round(r["correct_count"]/r["trigger_count"]*100,1) if r["trigger_count"] else 0,rid))
    c.commit(); c.close()

def save_trade(ticker, ttype, price, qty, amount, rule_id=None, pred_id=None, notes=""):
    c = conn(); c.execute("INSERT INTO trades(created_at,ticker,trade_type,price,quantity,amount,rule_id,prediction_id,notes) VALUES(?,?,?,?,?,?,?,?,?)",(now(),ticker,ttype,price,qty,amount,rule_id,pred_id,notes)); c.commit(); c.close()

def close_trade(tid, close_price):
    c = conn()
    t = c.execute("SELECT * FROM trades WHERE id=?",(tid,)).fetchone()
    if t and t["status"]=="open":
        pnl = round((close_price - t["price"]) * t["quantity"], 2)
        c.execute("UPDATE trades SET status='closed', pnl=?, close_price=?, close_at=? WHERE id=?",(pnl,close_price,now(),tid))
    c.commit(); c.close()

def get_trades(status=None):
    c = conn()
    if status: rows = c.execute("SELECT * FROM trades WHERE status=? ORDER BY created_at DESC",(status,)).fetchall()
    else: rows = c.execute("SELECT * FROM trades ORDER BY created_at DESC").fetchall()
    c.close(); return [dict(r) for r in rows]

def get_portfolio_summary():
    c = conn()
    trades = c.execute("SELECT SUM(amount) as total_invested, SUM(pnl) as total_pnl FROM trades WHERE status='closed'").fetchone()
    open_trades = c.execute("SELECT COUNT(*) as cnt, SUM(amount) as val FROM trades WHERE status='open'").fetchone()
    c.close()
    return dict(trades) | {"open_count": open_trades["cnt"], "open_value": open_trades["val"] or 0}
