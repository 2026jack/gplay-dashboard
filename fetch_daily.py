# -*- coding: utf-8 -*-
"""
Momcozy Google Play 评分数据每日抓取 (云端版, GitHub Actions 运行)
与本地版差异:
  - 服务账号密钥从环境变量 GCP_SA_KEY 读取(JSON 字符串), 不再依赖本地文件
  - 所有路径相对脚本目录, 无本机绝对路径
数据源:
  1) 官方批量报告 GCS (最权威): 全量评论历史CSV + 每日评分统计
  2) 官方评论 API: 全球近7天评论增量
  3) 美国区网页评论 + 商店页面快照
落库: SQLite db.sqlite3 (由 workflow 提交回仓库做持久化)
产出: data.json (看板数据)
"""
import csv, io, json, os, re, sqlite3, sys, time, urllib.request
from datetime import datetime, timezone, timedelta

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

BASE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE, "db.sqlite3")
DATA_JSON = os.path.join(BASE, "data.json")
PKG = "com.lute.momcozy"
GCS_BUCKET = "pubsite_prod_8947280618898421103"
REPORT_DIR = os.path.join(BASE, "reports")
TZ = timezone(timedelta(hours=8))  # Asia/Shanghai
START_DATE = "2026-09-22"  # API增量累积起点(批量报告已回填更早的官方历史)

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}

def now_str():
    return datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S")

def today():
    return datetime.now(TZ).strftime("%Y-%m-%d")

def http_get(url, headers=None, timeout=30, retries=3):
    h = dict(UA)
    if headers:
        h.update(headers)
    last_err = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers=h)
            return urllib.request.urlopen(req, timeout=timeout).read().decode("utf-8", "ignore")
        except Exception as e:
            last_err = e
            time.sleep(2 * (i + 1))
    raise last_err

# ---------- 服务账号 (从环境变量读取) ----------
def _sa_credentials(scope):
    from google.oauth2 import service_account
    from google.auth.transport.requests import Request
    key_json = os.environ.get("GCP_SA_KEY", "").strip()
    if not key_json:
        raise SystemExit("缺少环境变量 GCP_SA_KEY (服务账号 JSON 全文)")
    info = json.loads(key_json)
    creds = service_account.Credentials.from_service_account_info(info, scopes=[scope])
    creds.refresh(Request())
    return creds

# ---------- DB ----------
def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS snapshots(
      date TEXT, region TEXT, rating_value REAL, rating_count INTEGER,
      h1 INT, h2 INT, h3 INT, h4 INT, h5 INT, fetched_at TEXT,
      PRIMARY KEY(date, region));
    CREATE TABLE IF NOT EXISTS reviews(
      review_id TEXT PRIMARY KEY, star INT, version_name TEXT, version_code INT,
      language TEXT, device TEXT, last_modified TEXT, last_modified_ts INT,
      thumbs_up INT, text TEXT, dev_reply TEXT, first_seen TEXT, last_seen TEXT);
    CREATE TABLE IF NOT EXISTS us_reviews(
      review_id TEXT PRIMARY KEY, star INT, at_ts INT, content TEXT,
      version_name TEXT, first_seen TEXT, last_seen TEXT);
    CREATE TABLE IF NOT EXISTS run_log(
      ts TEXT PRIMARY KEY, status TEXT, detail TEXT);
    """)
    conn.commit()
    return conn

# ---------- 1) 官方评论 API ----------
def fetch_api_reviews(conn):
    creds = _sa_credentials("https://www.googleapis.com/auth/androidpublisher")
    auth = {"Authorization": f"Bearer {creds.token}"}
    all_reviews, token = [], None
    while True:
        url = ("https://androidpublisher.googleapis.com/androidpublisher/v3/applications/"
               f"{PKG}/reviews?maxResults=100&translationLanguage=en"
               + (f"&token={token}" if token else ""))
        d = json.loads(http_get(url, auth))
        all_reviews.extend(d.get("reviews", []))
        token = (d.get("tokenPagination") or {}).get("nextPageToken")
        if not token or len(all_reviews) > 2000:
            break
        time.sleep(0.5)
    ts = now_str()
    cur = conn.cursor()
    for r in all_reviews:
        rid = r.get("reviewId")
        user = developer = None
        for c in r.get("comments", []):
            if "userComment" in c:
                user = c["userComment"]
            elif "developerComment" in c:
                developer = c["developerComment"].get("text")
        if not user:
            continue
        lm = user.get("lastModified", {})
        lm_ts = int(lm.get("seconds", 0))
        cur.execute("""INSERT INTO reviews(review_id, star, version_name, version_code,
            language, device, last_modified, last_modified_ts, thumbs_up, text, dev_reply,
            first_seen, last_seen)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(review_id) DO UPDATE SET
              star=excluded.star, version_name=excluded.version_name,
              version_code=excluded.version_code, language=excluded.language,
              device=excluded.device, last_modified=excluded.last_modified,
              last_modified_ts=excluded.last_modified_ts, thumbs_up=excluded.thumbs_up,
              text=excluded.text, dev_reply=excluded.dev_reply, last_seen=excluded.last_seen""",
            (rid, user.get("starRating"), user.get("appVersionName"),
             user.get("appVersionCode"), user.get("reviewerLanguage"), user.get("device"),
             datetime.fromtimestamp(lm_ts, TZ).strftime("%Y-%m-%d %H:%M:%S") if lm_ts else None,
             lm_ts, user.get("thumbsUpCount") or 0, (user.get("text") or "").strip(),
             developer, ts, ts))
    conn.commit()
    return len(all_reviews)

# ---------- 2) 美国区网页评论(原始RPC, 自解析含版本号) ----------
def fetch_us_reviews(conn):
    from google_play_scraper.utils.request import post
    from google_play_scraper.constants.regex import Regex
    from google_play_scraper.constants.request import Formats
    url = Formats.Reviews.build(lang="en", country="us")
    token, all_items = None, []
    for _page in range(10):
        body = Formats.Reviews.build_body(PKG, 2, 150, "null", "null", token)
        dom = post(url, body, {"content-type": "application/x-www-form-urlencoded"})
        match = json.loads(Regex.REVIEWS.findall(dom)[0])
        results = json.loads(match[0][2])
        if not results or not results[0]:
            break
        all_items.extend(results[0])
        try:
            token = results[-2][-1]
        except Exception:
            token = None
        if not token:
            break
        time.sleep(1.0)
    ts = now_str()
    cur = conn.cursor()
    for r in all_items:
        try:
            rid = r[0]
            star = int(r[2]) if r[2] is not None else None
            content = r[4] if isinstance(r[4], str) else ""
            at_raw = r[5]
            at_ts = int(at_raw[0]) if isinstance(at_raw, (list, tuple)) and at_raw else 0
            version = r[10] if isinstance(r[10], str) else None
            cur.execute("""INSERT INTO us_reviews(review_id, star, at_ts, content,
                version_name, first_seen, last_seen)
                VALUES(?,?,?,?,?,?,?)
                ON CONFLICT(review_id) DO UPDATE SET star=excluded.star, at_ts=excluded.at_ts,
                  content=excluded.content, version_name=excluded.version_name,
                  last_seen=excluded.last_seen""",
                (rid, star, at_ts, content[:2000], version, ts, ts))
        except Exception:
            continue
    conn.commit()
    return len(all_items)

# ---------- 3) 商店页面快照 ----------
def fetch_snapshot(conn, gl="US"):
    html = http_get(f"https://play.google.com/store/apps/details?id={PKG}&hl=en&gl={gl}")
    m = re.search(r'"aggregateRating":\s*({[^}]+})', html)
    ld = json.loads(m.group(1)) if m else {}
    hist = {}
    for cnt, star in re.findall(r'aria-label="([0-9,]+) reviews for star rating ([1-5])"', html):
        hist[int(star)] = int(cnt.replace(",", ""))
    d = today()
    conn.execute("""INSERT INTO snapshots(date, region, rating_value, rating_count,
        h1,h2,h3,h4,h5, fetched_at) VALUES(?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(date, region) DO UPDATE SET rating_value=excluded.rating_value,
        rating_count=excluded.rating_count, h1=excluded.h1, h2=excluded.h2, h3=excluded.h3,
        h4=excluded.h4, h5=excluded.h5, fetched_at=excluded.fetched_at""",
        (d, f"gl_{gl}", float(ld.get("ratingValue", 0)), int(ld.get("ratingCount", 0)),
         hist.get(1, 0), hist.get(2, 0), hist.get(3, 0), hist.get(4, 0), hist.get(5, 0),
         now_str()))
    conn.commit()
    return {"rating_value": float(ld.get("ratingValue", 0)), "rating_count": int(ld.get("ratingCount", 0)),
            "hist": hist}

# ---------- 3b) 官方批量报告 (GCS, 最权威口径) ----------
def _gcs_token():
    creds = _sa_credentials("https://www.googleapis.com/auth/devstorage.read_only")
    return creds.token

def _gcs_list(token, prefix):
    import urllib.parse
    url = (f"https://storage.googleapis.com/storage/v1/b/{GCS_BUCKET}/o"
           f"?prefix={urllib.parse.quote(prefix)}&maxResults=100")
    d = json.loads(http_get(url, {"Authorization": f"Bearer {token}"}))
    return [it["name"] for it in d.get("items", [])]

def _gcs_download(token, name):
    import urllib.parse
    url = (f"https://storage.googleapis.com/storage/v1/b/{GCS_BUCKET}/o/"
           f"{urllib.parse.quote(name, safe='')}?alt=media")
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    data = urllib.request.urlopen(req, timeout=60).read()
    os.makedirs(REPORT_DIR, exist_ok=True)
    path = os.path.join(REPORT_DIR, os.path.basename(name))
    with open(path, "wb") as f:
        f.write(data)
    return path

def _read_csv_any(path):
    raw = open(path, "rb").read()
    for enc in ("utf-16", "utf-8-sig", "utf-8"):
        try:
            text = raw.decode(enc)
            if "Package Name" in text or "Date" in text:
                return list(csv.DictReader(io.StringIO(text)))
        except Exception:
            continue
    return []

def init_report_tables(conn):
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS report_reviews(
      submit_millis INTEGER PRIMARY KEY,
      star INTEGER, version_code TEXT, version_name TEXT, language TEXT,
      device TEXT, title TEXT, text TEXT, reply_text TEXT,
      submit_date TEXT, last_update TEXT, review_link TEXT);
    CREATE INDEX IF NOT EXISTS idx_rr_date ON report_reviews(submit_date);
    CREATE TABLE IF NOT EXISTS ratings_overview_daily(
      date TEXT PRIMARY KEY, daily_avg REAL, total_avg REAL);
    CREATE TABLE IF NOT EXISTS ratings_country_daily(
      date TEXT, country TEXT, daily_avg REAL, total_avg REAL,
      PRIMARY KEY(date, country));
    CREATE TABLE IF NOT EXISTS ratings_version_daily(
      date TEXT, version_code TEXT, daily_avg REAL, total_avg REAL,
      PRIMARY KEY(date, version_code));
    """)

def fetch_bulk_reports(conn):
    """下载并入库官方批量报告: 全量评论历史 + 每日评分统计"""
    tok = _gcs_token()
    n_rev, n_ov, n_cty, n_ver = 0, 0, 0, 0
    cur = conn.cursor()
    for name in _gcs_list(tok, "reviews/"):
        if not name.endswith(".csv"):
            continue
        for r in _read_csv_any(_gcs_download(tok, name)):
            cur.execute("""INSERT INTO report_reviews
                (submit_millis, star, version_code, version_name, language, device,
                 title, text, reply_text, submit_date, last_update, review_link)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(submit_millis) DO UPDATE SET star=excluded.star,
                  text=excluded.text, last_update=excluded.last_update,
                  reply_text=excluded.reply_text""",
                (int(r["Review Submit Millis Since Epoch"]), int(r["Star Rating"]),
                 r.get("App Version Code", ""), r.get("App Version Name", ""),
                 r.get("Reviewer Language", ""), r.get("Device", ""),
                 r.get("Review Title", ""), (r.get("Review Text") or ""),
                 (r.get("Developer Reply Text") or ""),
                 r.get("Review Submit Date and Time", "")[:10],
                 r.get("Review Last Update Date and Time", ""),
                 r.get("Review Link", "")))
            n_rev += 1
    for name in _gcs_list(tok, "stats/ratings/"):
        if not name.endswith(".csv"):
            continue
        rows = _read_csv_any(_gcs_download(tok, name))
        if not rows:
            continue
        keys = rows[0].keys()
        if "Country" in keys:
            for r in rows:
                cur.execute("INSERT OR REPLACE INTO ratings_country_daily VALUES(?,?,?,?)",
                    (r["Date"], r["Country"], float(r["Daily Average Rating"]),
                     float(r["Total Average Rating"])))
                n_cty += 1
        elif "App Version Code" in keys:
            for r in rows:
                cur.execute("INSERT OR REPLACE INTO ratings_version_daily VALUES(?,?,?,?)",
                    (r["Date"], r["App Version Code"], float(r["Daily Average Rating"]),
                     float(r["Total Average Rating"])))
                n_ver += 1
        else:
            for r in rows:
                cur.execute("INSERT OR REPLACE INTO ratings_overview_daily VALUES(?,?,?)",
                    (r["Date"], float(r["Daily Average Rating"]),
                     float(r["Total Average Rating"])))
                n_ov += 1
    conn.commit()
    return {"reviews": n_rev, "overview": n_ov, "country": n_cty, "version": n_ver}

# ---------- 4) 生成 data.json ----------
def build_data(conn):
    cur = conn.cursor()
    data = {"package": PKG, "generated_at": now_str(), "start_date": START_DATE,
            "timezone": "Asia/Shanghai", "daily_new": [], "version_global": [],
            "version_us": [], "us": {}, "global": {}, "overview": {}}

    # 美国: 最新快照
    cur.execute("""SELECT rating_value, rating_count, h1,h2,h3,h4,h5, fetched_at, date
                   FROM snapshots WHERE region='gl_US' ORDER BY date DESC, fetched_at DESC LIMIT 1""")
    row = cur.fetchone()
    if row:
        hs = {"1": row[2], "2": row[3], "3": row[4], "4": row[5], "5": row[6]}
        hsum = sum(hs.values()) or 1
        wsum = sum(int(k) * v for k, v in hs.items())
        data["us"] = {"rating_value": round(row[0], 2), "rating_count": row[1],
                      "hist": hs, "hist_sum": hsum,
                      "hist_avg": round(wsum / hsum, 4) if hsum else None,
                      "snapshot_at": row[7], "date": row[8]}

    # 后台锚定值: 全球默认评分仅 Play Console 可见, 由用户从后台同步
    anchor_path = os.path.join(BASE, "console_anchor.json")
    if os.path.exists(anchor_path):
        try:
            data["anchor"] = json.load(open(anchor_path, encoding="utf-8"))
        except Exception:
            data["anchor"] = {}

    # 全球: 官方批量报告累计书面评论(全量历史, 最权威)
    cur.execute("SELECT COUNT(*), SUM(star) FROM report_reviews")
    n, ssum = cur.fetchone()
    cur.execute("SELECT star, COUNT(*) FROM report_reviews GROUP BY star")
    gh = {str(k): v for k, v in cur.fetchall()}
    gh = {k: gh.get(k, 0) for k in ["1", "2", "3", "4", "5"]}
    gsum = sum(gh.values())
    grc = (row[1] if row else 0)
    data["global"] = {
        "rating_count": grc,
        "written_reviews": n or 0,
        "avg_from_reviews": round(ssum / n, 2) if n else None,
        "hist_from_reviews": gh,
        "hist_sum": gsum}

    # 官方评分统计: 最新全球累计均分 + 近28天日均分均值
    cur.execute("SELECT total_avg FROM ratings_overview_daily ORDER BY date DESC LIMIT 1")
    r = cur.fetchone()
    data["official"] = {"global_latest_avg": round(r[0], 2) if r else None}
    cur.execute("""SELECT ROUND(AVG(daily_avg),2) FROM ratings_overview_daily
                   WHERE date >= date('now','-28 days') AND daily_avg > 0""")
    r = cur.fetchone()
    data["official"]["avg28_daily_mean"] = r[0] if r else None
    cur.execute("SELECT MIN(date), MAX(date) FROM ratings_overview_daily")
    r = cur.fetchone()
    data["official"]["report_range"] = list(r) if r else None

    # 每日新增(全球书面评论)
    cur.execute("""SELECT submit_date, star, COUNT(*) FROM report_reviews
                   GROUP BY submit_date, star""")
    daily = {}
    for d, star, c in cur.fetchall():
        daily.setdefault(d, {"1": 0, "2": 0, "3": 0, "4": 0, "5": 0})
        daily[d][str(star)] = c
    cur.execute("""SELECT date(last_modified), star, COUNT(*) FROM reviews
                   WHERE last_modified IS NOT NULL GROUP BY date(last_modified), star""")
    for d, star, c in cur.fetchall():
        if not d:
            continue
        daily.setdefault(d, {"1": 0, "2": 0, "3": 0, "4": 0, "5": 0})
        daily[d][str(star)] = c
    data["daily_new"] = [{"date": d, "s1": v["1"], "s2": v["2"], "s3": v["3"],
                          "s4": v["4"], "s5": v["5"], "total": sum(v.values())}
                         for d, v in sorted(daily.items())]

    # 版本分布 - 全球
    cur.execute("""SELECT version_name, star, COUNT(*) FROM report_reviews
                   WHERE version_name != '' GROUP BY version_name, star""")
    vg = {}
    for v, star, c in cur.fetchall():
        vg.setdefault(v, {"1": 0, "2": 0, "3": 0, "4": 0, "5": 0})
        vg[v][str(star)] = c
    data["version_global"] = [
        {"version": v, "s1": c["1"], "s2": c["2"], "s3": c["3"], "s4": c["4"], "s5": c["5"],
         "total": sum(c.values())}
        for v, c in sorted(vg.items(), key=lambda x: -sum(x[1].values()))]

    # 版本分布 - 美国
    cur.execute("""SELECT version_name, star, COUNT(*) FROM us_reviews
                   WHERE version_name IS NOT NULL GROUP BY version_name, star""")
    vu = {}
    for v, star, c in cur.fetchall():
        vu.setdefault(v, {"1": 0, "2": 0, "3": 0, "4": 0, "5": 0})
        vu[v][str(star)] = c
    data["version_us"] = [
        {"version": v, "s1": c["1"], "s2": c["2"], "s3": c["3"], "s4": c["4"], "s5": c["5"],
         "total": sum(c.values())}
        for v, c in sorted(vu.items(), key=lambda x: -sum(x[1].values()))]

    # 美国每日新增
    cur.execute("""SELECT date(datetime(at_ts, 'unixepoch', '+8 hours')), star, COUNT(*)
                   FROM us_reviews WHERE at_ts > 0 GROUP BY 1, 2 ORDER BY 1""")
    du = {}
    for d, star, c in cur.fetchall():
        du.setdefault(d, {"1": 0, "2": 0, "3": 0, "4": 0, "5": 0})
        du[d][str(star)] = c
    data["daily_new_us"] = [{"date": d, "s1": v["1"], "s2": v["2"], "s3": v["3"],
                             "s4": v["4"], "s5": v["5"], "total": sum(v.values())}
                            for d, v in sorted(du.items())]

    # 总览: 评分值趋势
    cur.execute("SELECT date, total_avg FROM ratings_overview_daily ORDER BY date")
    data["overview"]["trend"] = [{"date": d, "avg": round(a, 2)}
                                 for d, a in cur.fetchall() if a]
    cur.execute("""SELECT date, total_avg FROM ratings_country_daily
                   WHERE country='US' ORDER BY date""")
    data["overview"]["trend_us"] = [{"date": d, "avg": round(a, 2)}
                                    for d, a in cur.fetchall() if a]
    cur.execute("""SELECT date, rating_value, rating_count FROM snapshots
                   WHERE region='gl_US' ORDER BY date""")
    data["overview"]["us_snapshot_history"] = [
        {"date": d, "rating_value": round(r, 2), "rating_count": rc}
        for d, r, rc in cur.fetchall()]

    with io.open(DATA_JSON, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    return data

def main():
    conn = init_db()
    init_report_tables(conn)
    ok, detail = True, []
    try:
        bulk = fetch_bulk_reports(conn)
        detail.append(f"批量报告: 评论CSV{bulk['reviews']}行/评分日{bulk['overview']}天")
        n_api = fetch_api_reviews(conn)
        detail.append(f"API评论{n_api}条")
        n_us = fetch_us_reviews(conn)
        detail.append(f"美国评论{n_us}条")
        snap = fetch_snapshot(conn, "US")
        detail.append(f"美国快照{snap['rating_value']}★/{snap['rating_count']}")
        data = build_data(conn)
        detail.append("data.json已生成")
        conn.execute("INSERT OR REPLACE INTO run_log VALUES(?,?,?)",
                     (now_str(), "ok", "; ".join(str(x) for x in detail)))
        conn.commit()
        print("[OK]", "; ".join(str(x) for x in detail))
        print("全球书面评论:", data["global"]["written_reviews"],
              "均分:", data["global"]["avg_from_reviews"],
              "| 美国书面评论:", data["us"].get("hist_sum"))
        print("每日新增天数:", len(data["daily_new"]),
              "| 全球版本数:", len(data["version_global"]),
              "| 美国版本数:", len(data["version_us"]))
    except Exception as e:
        import traceback
        conn.execute("INSERT OR REPLACE INTO run_log VALUES(?,?,?)",
                     (now_str(), "error", f"{type(e).__name__}: {e}"))
        conn.commit()
        print("[ERROR]", type(e).__name__, str(e)[:500])
        traceback.print_exc()
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    main()
