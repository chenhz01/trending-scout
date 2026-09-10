#!/usr/bin/env python3
"""trending-scout v2.1 — GitHub Trending 对抗性审核引擎（零依赖）

v2.0 升级（2026-09-10，学超破闭环）:
  1. API-first 核实: REST API 一次拿全 star/license/pushed_at/archived 五硬指标,
     网页解析降级为兜底路径。
  2. 许可证风险层: null / NOASSERTION / (A)LGPL/GPL 传染许可自动标记。
  3. 停更检测: pushed_at 超过 --stale-days (默认180) 标记停更风险。
  4. 板块信号检测: 跨仓统计画像命中分布, 榜单集体信号(>=3仓同品类)显式输出。

v2.1 升级（2026-09-10，红蓝对攻 180 补丁蒸馏落地）:
  P23 许可证三态输出: 明确合规 / 需人工复核 / 明确高风险（不做法律意见, 优先降误报 P70）
  P34 维护风险信号: 停更≠风险, 区分「疑似废弃」与「可能稳定完成」
  P3  信号成熟度: experimental → validated(4期) → production(12期), 未验证信号不用于商业决策
  P76 校准库种子: 每次运行信号历史落盘 calibration.jsonl（历史数据=护城河, 闭源不随仓分发）

Pipeline: fetch trending -> adversarial verify (API-first) -> profile scoring
(P0/P1/P2) -> license tri-state / maintenance signals -> category signal (maturity)
-> dark HTML report.

Zero dependencies (stdlib only). Python 3.8+.

Usage:
  python scout.py                          # top 10, API verify on, profile.json
  python scout.py --limit 15 --no-verify   # fast mode, skip per-repo refetch
  python scout.py --since weekly --stale-days 90
  python scout.py --profile my.json --out reports/
"""

import argparse
import json
import re
import ssl
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

UA = {"User-Agent": "Mozilla/5.0 (trending-scout; +https://github.com)",
      "Accept": "application/vnd.github+json"}
CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE  # tolerate corp proxies; fine for read-only scraping


def fetch(url: str, timeout: int = 20) -> str:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
        return r.read().decode("utf-8", errors="replace")


# ---------- Stage 1: collect ----------

ARTICLE_RE = re.compile(r'<article class="Box-row">.*?</article>', re.S)
H2_RE = re.compile(r"<h2.*?</h2>", re.S)
REPO_HREF_RE = re.compile(r'<a\s[^>]*?href="/([^"]+)"', re.S)
DESC_RE = re.compile(r'<p class="col-9[^"]*">\s*(.*?)\s*</p>', re.S)
STARS_RE = re.compile(r'href="/([^"]+)/stargazers"[^>]*>.*?</svg>\s*([\d,]+)', re.S)
TODAY_RE = re.compile(r'([\d,]+)\s*stars today', re.S)
LANG_RE = re.compile(r'itemprop="programmingLanguage">([^<]+)<')

_TAG_RE = re.compile(r"<[^>]+>")


def _clean(s: str) -> str:
    return _TAG_RE.sub("", s).replace("&amp;", "&").replace("&#39;", "'").strip()


def fetch_trending(since: str = "daily") -> list:
    """Parse github.com/trending. Returns [{full_name, desc, stars, today, lang}]."""
    html = fetch(f"https://github.com/trending?since={since}")
    repos = []
    for block in ARTICLE_RE.findall(html):
        h2 = H2_RE.search(block)
        full_name = ""
        if h2:
            for cand in REPO_HREF_RE.findall(h2.group(0)):
                cand = cand.strip("/")
                # repo 链接形如 owner/repo；排除 stargazers/forks 等子页
                if cand.count("/") == 1 and not cand.endswith(("stargazers", "forks", "issues")):
                    full_name = cand
                    break
        if not full_name:
            continue
        d = DESC_RE.search(block)
        s = STARS_RE.search(block)
        t = TODAY_RE.search(block)
        l = LANG_RE.search(block)
        repos.append({
            "full_name": full_name,
            "desc": _clean(d.group(1)) if d else "",
            "stars": int(s.group(2).replace(",", "")) if s else 0,
            "today": int(t.group(1).replace(",", "")) if t else 0,
            "lang": l.group(1) if l else "",
        })
    return repos


# ---------- Stage 2: adversarial verify (API-first, HTML fallback) ----------
# 对抗层：榜单名称/描述/star 数会被转载渠道以讹传讹（OCR 错名、旧数据），
# 逐仓独立取证。v2.0 优先走 REST API：一次拿全五硬指标，还能拿到网页
# 解析拿不到的 license 与 pushed_at。

def _init_verify_fields(out: dict) -> dict:
    out.setdefault("verified", False)
    out.setdefault("verify_note", "")
    out.setdefault("license", None)
    out.setdefault("pushed_at", "")
    out.setdefault("archived", False)
    return out


def verify_repo_api(repo: dict, timeout: int = 20) -> dict:
    """REST API 优先核实：star/license/pushed_at/archived 一次拿全。"""
    out = _init_verify_fields(dict(repo))
    try:
        data = json.loads(fetch(f"https://api.github.com/repos/{repo['full_name']}", timeout))
    except Exception as e:  # noqa: BLE001 - degrade to HTML path, never crash
        out["verify_note"] = f"api-failed({type(e).__name__})"
        return verify_repo_html(out, timeout)
    msg = data.get("message", "")
    if msg == "Not Found":
        out["verify_note"] = "API 404 -> 名称可疑"
        return out
    if msg:  # rate limit / server error -> HTML fallback
        out["verify_note"] = f"api-msg({msg[:40]})"
        return verify_repo_html(out, timeout)
    live = data.get("stargazers_count")
    if live is not None and repo["stars"] and abs(live - repo["stars"]) > max(500, repo["stars"] * 0.25):
        out["verify_note"] = f"star drift: list={repo['stars']} live={live}"
        out["stars"] = live
    elif live is not None:
        out["verify_note"] = "ok"
    else:
        out["verify_note"] = "api ok (no star field)"
    lic = data.get("license") or {}
    out["license"] = lic.get("spdx_id")
    out["pushed_at"] = data.get("pushed_at", "")
    out["archived"] = bool(data.get("archived"))
    out["open_issues"] = data.get("open_issues_count", 0)
    out["verified"] = True
    return out


def verify_repo_html(repo: dict, timeout: int = 20) -> dict:
    """网页解析兜底（API 被限流/不可达时降级路径，v1 行为）。"""
    out = _init_verify_fields(dict(repo))
    try:
        page = fetch(f"https://github.com/{repo['full_name']}", timeout)
        if "404" in page[:400] or "Not Found" in page[:2000]:
            out["verify_note"] = out.get("verify_note", "") + " | page not-found -> 名称可疑"
            return out
        m = re.search(r'"starCount":"?(\d+)', page) or re.search(
            r'aria-label="([\d,]+) users? starred', page)
        live = int(m.group(1).replace(",", "")) if m else None
        if live is not None and repo["stars"] and abs(live - repo["stars"]) > max(500, repo["stars"] * 0.25):
            out["verify_note"] += f" | star drift: list={repo['stars']} live={live}"
            out["stars"] = live
        elif live is not None:
            out["verify_note"] = (out["verify_note"] + " | page ok").strip(" |")
        else:
            out["verify_note"] = (out["verify_note"] + " | page ok (star not parsed)").strip(" |")
        out["verified"] = True
    except Exception as e:  # noqa: BLE001 - degrade, never crash
        out["verify_note"] = (out.get("verify_note", "") + f" | verify failed: {type(e).__name__}").strip(" |")
    return out


def verify_repo(repo: dict, timeout: int = 20) -> dict:
    return verify_repo_api(repo, timeout)


# ---------- Stage 2.5: license tri-state & maintenance signal (v2.1) ----------
# P23: 三态输出（明确合规/需人工复核/明确高风险），不做法律意见。
# P70: 优先降低误报——拿不准的一律进 review 而非 high。

PERMISSIVE = {"MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "ISC",
              "0BSD", "Unlicense", "CC0-1.0", "Zlib"}
WEAK_COPYLEFT = ("LGPL", "MPL", "EPL", "CDDL")


def license_tri_state(spdx):
    """返回 (state, label)：state ∈ clear / review / high。"""
    if spdx is None:
        return "high", "无许可证(只借思想禁搬码)"
    if spdx == "NOASSERTION":
        return "review", "自定义协议(人工读LICENSE)"
    if "LGPL" not in spdx and any(spdx.startswith(p) for p in ("GPL", "AGPL")):
        return "high", f"{spdx}强传染(闭源集成禁用)"
    if any(spdx.startswith(p) for p in WEAK_COPYLEFT):
        return "review", f"{spdx}弱传染(集成前评估)"
    if spdx in PERMISSIVE:
        return "clear", ""
    return "review", f"{spdx}非标准许可(人工确认)"


def maintenance_signal(repo: dict, stale_days: int) -> str:
    """P34: 停更≠风险。区分「疑似废弃」与「可能稳定完成」，启发式信号。"""
    pushed_at = repo.get("pushed_at", "")
    if not pushed_at:
        return ""
    try:
        dt = datetime.fromisoformat(pushed_at.replace("Z", "+00:00"))
        age = (datetime.now(timezone.utc) - dt).days
    except ValueError:
        return ""
    if age <= stale_days:
        return ""
    issues = repo.get("open_issues") or 0
    if issues >= 50:
        return f"维护信号:停更{age}天+{issues}个开放issue(疑似废弃)"
    return f"维护信号:停更{age}天,issue少(可能稳定完成,非风险)"


# ---------- Stage 2.6: signal maturity & calibration (v2.1) ----------
# P3: 未验证信号不用于商业决策。P76: 历史数据+校准=护城河（闭源资产）。

CALIBRATION_FILE = Path(__file__).with_name("calibration.jsonl")


def record_calibration(signals: list, total: int) -> None:
    """每次运行的板块信号落盘，供跨期成熟度校准。失败静默（不阻塞主流程）。"""
    try:
        with CALIBRATION_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps({
                "date": datetime.now().strftime("%Y-%m-%d"),
                "total": total,
                "signals": {k: v for k, v in signals},
            }, ensure_ascii=False) + "\n")
    except OSError:
        pass


def signal_maturity():
    """P3 成熟度: experimental(<4期) → validated(4-11期) → production(>=12期)。"""
    try:
        with CALIBRATION_FILE.open(encoding="utf-8") as f:
            weeks = len({json.loads(line)["date"] for line in f if line.strip()})
    except (OSError, json.JSONDecodeError, KeyError):
        weeks = 0
    if weeks >= 12:
        return "production", weeks
    if weeks >= 4:
        return "validated", weeks
    return "experimental", weeks


# ---------- Stage 3: profile scoring ----------

def score(repo: dict, profile: dict) -> dict:
    text = f"{repo['full_name']} {repo['desc']} {repo.get('lang', '')}".lower()
    hits, best = {}, None
    for line in profile.get("business_lines", []):
        n = sum(1 for kw in line.get("keywords", []) if kw.lower() in text)
        if n:
            hits[line["name"]] = n
            if best is None or n * line.get("weight", 1) > best[1]:
                best = (line["name"], n * line.get("weight", 1))
    risks = [r for r in profile.get("risk_keywords", []) if r.lower() in text]
    total = sum(hits.values())
    if total >= profile.get("p0_threshold", 3):
        grade = "P0"
    elif total >= profile.get("p1_threshold", 1):
        grade = "P1"
    else:
        grade = "P2"
    repo["grade"] = grade
    repo["hits"] = hits
    repo["best_line"] = best[0] if best else ""
    repo["risks"] = risks
    return repo


# ---------- Stage 3.5: category signal (v2.0) ----------
# 元缺口层的量化：单仓评级回答"对我有没有用"，板块信号回答
# "榜单集体在押注什么赛道"——同品类 >=3 仓上榜即为集体信号。

def category_signals(repos: list, min_repos: int = 3) -> list:
    counter = {}
    for r in repos:
        for line in r.get("hits", {}):
            counter[line] = counter.get(line, 0) + 1
    return sorted(((k, v) for k, v in counter.items() if v >= min_repos),
                  key=lambda x: -x[1])


# ---------- Stage 4: dark HTML report ----------

CSS = """:root{--bg:#0b0e14;--card:#161c2c;--line:#2a3350;--txt:#dbe2f0;--dim:#8a93a8;--gold:#ffb454;--green:#4ade80;--red:#ff5d5d;--cyan:#5ecfe6}
*{margin:0;box-sizing:border-box}body{background:var(--bg);color:var(--txt);font-family:Inter,'PingFang SC','Microsoft YaHei',sans-serif;line-height:1.7;padding:34px 8%;max-width:1100px}
h1{font-size:24px}.meta{color:var(--dim);font-size:13px;margin:6px 0 22px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px 20px;margin-bottom:12px}
.tag{display:inline-block;font-size:11px;font-weight:700;padding:2px 10px;border-radius:20px;margin-left:8px}
.p0{background:rgba(74,222,128,.15);color:var(--green);border:1px solid rgba(74,222,128,.4)}
.p1{background:rgba(255,180,84,.12);color:var(--gold);border:1px solid rgba(255,180,84,.4)}
.p2{background:rgba(138,147,168,.12);color:var(--dim);border:1px solid rgba(138,147,168,.35)}
.risk{background:rgba(255,93,93,.12);color:var(--red);border:1px solid rgba(255,93,93,.35);margin-left:6px}
.name{font-weight:700}.stars{color:var(--gold);font-size:12px;margin-left:8px}
.desc{color:var(--dim);font-size:13px;margin:6px 0}.kv{font-size:13px;margin:3px 0}.kv b{color:var(--cyan)}
.degraded{border:1px solid var(--red);color:var(--red);padding:10px 16px;border-radius:10px;margin-bottom:18px}
.signal{background:var(--card);border:1px solid var(--gold);border-radius:12px;padding:14px 20px;margin-bottom:18px}
.signal b{color:var(--gold)}
"""


def render(repos, profile_name, verified_count, degraded_reason="", stale_days=180):
    today = datetime.now().strftime("%Y-%m-%d")
    order = {"P0": 0, "P1": 1, "P2": 2}
    repos = sorted(repos, key=lambda r: (order.get(r.get("grade", "P2"), 2), -r["today"]))
    parts = [f"<h1>GitHub Trending 对抗性审核日报 · {today}</h1>",
             f'<div class="meta">trending-scout v2.1 · profile: {profile_name} · '
             f"repos: {len(repos)} · verified: {verified_count}/{len(repos)} · "
             f"generated {datetime.now().strftime('%H:%M')}</div>"]
    if degraded_reason:
        parts.append(f'<div class="degraded">DEGRADED: {degraded_reason} — 数据不完整，不作结论。</div>')
    signals = category_signals(repos)
    if signals:
        maturity, periods = signal_maturity()
        sig_txt = " ｜ ".join(f"<b>{k}</b> {v}/{len(repos)} 仓" for k, v in signals)
        gate = "" if maturity == "production" else \
            f'（成熟度 {maturity}·{periods} 期校准，未达 production 前不用于商业决策）'
        parts.append(f'<div class="signal">📡 板块集体信号 [{maturity}]: {sig_txt} —— '
                     f'同品类 ≥3 仓上榜，视为赛道级押注信号。{gate}<br>'
                     f'<span style="font-size:12px;color:var(--dim)">样本 n={len(repos)}，'
                     f'小样本统计存在较大不确定性（P70 降误报原则：宁可少报，不虚报）。</span></div>')
    for r in repos:
        g = r.get("grade", "P2")
        tags = f'<span class="tag p{g[1]}">{g}</span>'
        lic_state, lic_label = license_tri_state(r.get("license"))
        if r.get("archived"):
            tags += '<span class="tag risk">已归档</span>'
        if lic_state == "high":
            tags += f'<span class="tag risk">License: {lic_label}</span>'
        elif lic_state == "review":
            tags += f'<span class="tag p1">License: {lic_label}</span>'
        maint = maintenance_signal(r, stale_days)
        if maint:
            tags += f'<span class="tag risk">{maint}</span>'
        if r.get("risks"):
            tags += f'<span class="tag risk">风险: {", ".join(r["risks"])}</span>'
        if r.get("verify_note") and r["verify_note"] != "ok":
            tags += f'<span class="tag p2">核实: {r["verify_note"]}</span>'
        hits = "、".join(f"{k}×{v}" for k, v in r.get("hits", {}).items()) or "无画像命中"
        lic = r.get("license") or "—"
        parts.append(
            f'<div class="card"><div class="name">{r["full_name"]}'
            f'<span class="stars">★{r["stars"]:,} · +{r["today"]}/日 · {r.get("lang", "")} · License: {lic}</span>{tags}</div>'
            f'<div class="desc">{r["desc"]}</div>'
            f'<div class="kv"><b>画像命中:</b> {hits}</div>'
            f'<div class="kv"><b>链接:</b> https://github.com/{r["full_name"]}</div></div>')
    html = (f"<!DOCTYPE html><html lang='zh-CN'><head><meta charset='UTF-8'>"
            f"<title>trending-scout {today}</title><style>{CSS}</style></head><body>"
            + "".join(parts) + "</body></html>")
    return html


# ---------- main ----------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=10)
    ap.add_argument("--profile", default=str(Path(__file__).with_name("profile.json")))
    ap.add_argument("--out", default=str(Path(__file__).with_name("reports")))
    ap.add_argument("--no-verify", action="store_true")
    ap.add_argument("--since", default="daily", choices=["daily", "weekly", "monthly"])
    ap.add_argument("--stale-days", type=int, default=180)
    args = ap.parse_args()

    profile_path = Path(args.profile)
    profile = json.loads(profile_path.read_text(encoding="utf-8")) if profile_path.exists() else {}
    profile_name = profile.get("profile_name", "default")

    degraded = ""
    try:
        repos = fetch_trending(args.since)[: args.limit]
        if len(repos) < 3:
            degraded = f"trending parse yielded only {len(repos)} repos"
    except Exception as e:  # noqa: BLE001
        repos, degraded = [], f"trending fetch failed: {type(e).__name__}: {e}"

    verified = 0
    for i, r in enumerate(repos):
        if not args.no_verify and not degraded:
            r = verify_repo(r)
            time.sleep(0.4)  # polite rate
            if r.get("verified"):
                verified += 1
        score(r, profile)
        repos[i] = r

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"trending-scout-{datetime.now():%Y-%m-%d}.html"
    out_file.write_text(render(repos, profile_name, verified, degraded, args.stale_days),
                        encoding="utf-8")
    if not degraded and repos:
        record_calibration(category_signals(repos), len(repos))
    print(f"[trending-scout v2.1] repos={len(repos)} verified={verified} degraded={bool(degraded)}")
    print(f"[trending-scout v2.1] report -> {out_file}")
    return 0 if not degraded else 2  # 2 = degraded (report written, data incomplete)


if __name__ == "__main__":
    sys.exit(main())
