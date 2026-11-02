"""
Doorstep - AI delivery heads-up.  Run:  python app.py   then open http://127.0.0.1:5000
Flask serves the web page (static/index.html) AND the JSON API under /api.
"""
import os, sqlite3, threading, time, json, urllib.request, urllib.parse
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory
from ml import get_model, predict_risk, explain
from parser import parse_message

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE, "doorstep.db")
app = Flask(__name__, static_folder=os.path.join(BASE, "static"), static_url_path="/static")
TG_TOKEN, TG_CHAT = os.getenv("TELEGRAM_TOKEN"), os.getenv("TELEGRAM_CHAT_ID")


def db():
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row
    c.executescript("""
    CREATE TABLE IF NOT EXISTS deliveries(id INTEGER PRIMARY KEY, uid TEXT, item TEXT, courier TEXT, otp TEXT,
        start TEXT, end TEXT, risk INTEGER, label TEXT, why TEXT, done INTEGER DEFAULT 0, n1 INTEGER DEFAULT 0, n2 INTEGER DEFAULT 0);
    CREATE TABLE IF NOT EXISTS alerts(id INTEGER PRIMARY KEY, uid TEXT, title TEXT, body TEXT, seen INTEGER DEFAULT 0);
    CREATE TABLE IF NOT EXISTS settings(uid TEXT PRIMARY KEY, lead INTEGER DEFAULT 30);""")
    return c


def row(r):
    d = dict(r); d["why"] = json.loads(d["why"] or "[]"); return d


@app.get("/")
def home():
    return send_from_directory(app.static_folder, "index.html")


@app.post("/api/parse")
def api_parse():
    return jsonify(parse_message((request.json or {}).get("text", "")))


@app.get("/api/deliveries")
def api_list():
    with db() as c:
        rows = c.execute("SELECT * FROM deliveries WHERE uid=? ORDER BY done, start", (request.args.get("uid", "demo"),)).fetchall()
    return jsonify([row(r) for r in rows])


@app.post("/api/deliveries")
def api_add():
    d = request.json or {}
    try:
        s, e = datetime.fromisoformat(d["start"]), datetime.fromisoformat(d["end"])
        assert e > s
    except Exception:
        return jsonify(error="Send start and end as ISO times, end after start."), 400
    score, label = predict_risk(d.get("courier"), s, e, d.get("rain_mm", 0))
    why = explain(d.get("courier"), s, e, d.get("rain_mm", 0))
    if d.get("status") == "trouble": score, label, why = max(score, 55), "High", why + ["message mentions a delay"]
    with db() as c:
        cur = c.execute("INSERT INTO deliveries(uid,item,courier,otp,start,end,risk,label,why) VALUES(?,?,?,?,?,?,?,?,?)",
                        (request.args.get("uid") or d.get("uid", "demo"), d.get("item") or "Package", d.get("courier"), d.get("otp"),
                         d["start"], d["end"], score, label, json.dumps(why)))
        r = c.execute("SELECT * FROM deliveries WHERE id=?", (cur.lastrowid,)).fetchone()
    return jsonify(row(r)), 201


@app.post("/api/deliveries/<int:i>/done")
def api_done(i):
    with db() as c: c.execute("UPDATE deliveries SET done=1 WHERE id=?", (i,))
    return jsonify(ok=True)


@app.delete("/api/deliveries/<int:i>")
def api_del(i):
    with db() as c: c.execute("DELETE FROM deliveries WHERE id=?", (i,))
    return jsonify(ok=True)


@app.route("/api/settings", methods=["GET", "POST"])
def api_settings():
    uid = request.args.get("uid", "demo")
    with db() as c:
        if request.method == "POST":
            c.execute("INSERT INTO settings(uid,lead) VALUES(?,?) ON CONFLICT(uid) DO UPDATE SET lead=excluded.lead",
                      (uid, int(request.json.get("lead", 30))))
            c.execute("UPDATE deliveries SET n2=0 WHERE uid=? AND done=0", (uid,))
        r = c.execute("SELECT lead FROM settings WHERE uid=?", (uid,)).fetchone()
    return jsonify(lead=r["lead"] if r else 30)


@app.get("/api/alerts")
def api_alerts():
    """Browser polls this; returns unseen alerts and marks them seen."""
    uid = request.args.get("uid", "demo")
    with db() as c:
        rows = c.execute("SELECT * FROM alerts WHERE uid=? AND seen=0", (uid,)).fetchall()
        c.execute("UPDATE alerts SET seen=1 WHERE uid=? AND seen=0", (uid,))
    return jsonify([dict(r) for r in rows])


def telegram(text):
    if not (TG_TOKEN and TG_CHAT): return
    try:
        url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
        urllib.request.urlopen(url, urllib.parse.urlencode({"chat_id": TG_CHAT, "text": text}).encode(), timeout=10)
    except Exception as ex:
        print("Telegram failed:", ex)


def check_due():
    """Runs every 30 s in a background thread: morning-of notice + lead-time warning."""
    now = datetime.now()
    with db() as c:
        lead = {r["uid"]: r["lead"] for r in c.execute("SELECT * FROM settings")}
        for r in c.execute("SELECT * FROM deliveries WHERE done=0").fetchall():
            s, e = datetime.fromisoformat(r["start"]), datetime.fromisoformat(r["end"])
            msgs = []
            if not r["n1"] and s.date() == now.date() and now.hour >= 7:
                msgs.append(("n1", f"Delivery today: {r['item']}",
                             f"{r['courier'] or 'Courier'} arrives {s:%I:%M %p}-{e:%I:%M %p}. Plan to be home."
                             + (f" OTP {r['otp']}." if r["otp"] else "") + f" Delay risk: {r['label']}."))
            mins = (s - now).total_seconds() / 60
            if not r["n2"] and mins <= lead.get(r["uid"], 30) and now < e:
                msgs.append(("n2", f"Get ready: {r['item']}", f"Courier may arrive in about {max(round(mins), 0)} min. Be at the delivery spot."))
            for col, title, body in msgs:
                c.execute(f"UPDATE deliveries SET {col}=1 WHERE id=?", (r["id"],))
                c.execute("INSERT INTO alerts(uid,title,body) VALUES(?,?,?)", (r["uid"], title, body))
                telegram(f"{title}\n{body}")


def loop():
    while True:
        try: check_due()
        except Exception as ex: print("scheduler error:", ex)
        time.sleep(30)


if __name__ == "__main__":
    get_model()                       # trains on first run, then loads from disk
    threading.Thread(target=loop, daemon=True).start()
    print("Open http://127.0.0.1:5000")
    app.run(host="127.0.0.1", port=5000, debug=False)
