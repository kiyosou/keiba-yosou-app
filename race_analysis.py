"""レース分析

登録済みのレース結果(ActualResult)を、基準タイム(StandardTime)と比べて
「時計面のレベル」「ペース(PCI・RPCI)」「ラップ」「展開(通過順位)」を読み解く。

- analyze()         : DBに依存しない計算本体(テストしやすいよう分離)
- analyze_race()    : DBからデータを集めて analyze() に渡す
"""
import re

from sqlmodel import Session, select

from models import Race, ActualResult, StandardTime, Horse
from analysis_models import RaceLap, StandardTimeExtra
from parsing import infer_age_and_class
from scoring import race_label


# ------------------------------------------------------------------ 読み取り
def parse_time(s):
    """'1:55.5' / '1.55.62' / '55.5' を秒に変換する。読めなければ None。"""
    s = (str(s) if s is not None else "").strip().replace("：", ":")
    if not s:
        return None
    m = re.fullmatch(r"(\d+):(\d{1,2})(?:\.(\d+))?", s)
    if m:
        frac = int(m.group(3)) / 10 ** len(m.group(3)) if m.group(3) else 0.0
        return int(m.group(1)) * 60 + int(m.group(2)) + frac
    m = re.fullmatch(r"(\d+)\.(\d{1,2})\.(\d+)", s)
    if m:
        return int(m.group(1)) * 60 + int(m.group(2)) + int(m.group(3)) / 10 ** len(m.group(3))
    if re.fullmatch(r"\d+\.\d+", s):
        return float(s)
    return None


def parse_laps(text):
    """結果ページの「ハロンタイム」の行(または数字だけ)から、ラップの一覧を取り出す。"""
    text = text or ""
    if "ハロンタイム" in text:
        seg = text.split("ハロンタイム", 1)[1]
        seg = re.split(r"[\r\n]|上り", seg, maxsplit=1)[0]
    else:
        seg = text
    nums = [float(x) for x in re.findall(r"\d{1,2}\.\d+", seg)]
    return [n for n in nums if 4.0 <= n <= 20.0]


def parse_lap_string(s):
    """DBに保存した '12.6-11.8-...' を数値のリストに戻す。"""
    return [float(x) for x in re.findall(r"\d+\.\d+", s or "")]


# ------------------------------------------------------------------ 計算・表示の部品
def calc_pci(total_sec, last3f, distance):
    """PCI = (上がり3Fより前の部分を3F(600m)換算した時計) ÷ 上がり3F × 100 − 50"""
    if not total_sec or not last3f or not distance or distance <= 600:
        return None
    pace_3f = (total_sec - last3f) / (distance - 600) * 600
    return round(pace_3f / last3f * 100 - 50, 1)


def _fmt_time(sec, digits=1):
    if sec is None:
        return "-"
    total = round(sec, digits)
    m = int(total // 60)
    s = total - m * 60
    if m:
        return f"{m}:{s:0{digits + 3}.{digits}f}"
    return f"{s:.{digits}f}"


def _diff_text(diff, digits=2):
    """diff = 基準 − 実際(プラスなら実際の方が速い)"""
    if diff is None:
        return "-"
    if abs(diff) < 0.5 * 10 ** -digits:
        return "同じ"
    return f"{abs(diff):.{digits}f}秒{'速い' if diff > 0 else '遅い'}"


def _cls(diff):
    if diff is None:
        return ""
    if diff > 0.005:
        return "stat-hit"
    if diff < -0.005:
        return "stat-miss"
    return ""


def _level_label(pct):
    """基準との差の平均(基準の勝ち時計に対する%)から、レベルの目安を返す。"""
    if pct >= 0.7:
        return "高レベル"
    if pct >= 0.25:
        return "やや高い"
    if pct > -0.25:
        return "標準的"
    if pct > -0.7:
        return "やや低い"
    return "低レベル"


def _mean(values):
    return sum(values) / len(values) if values else None


# ------------------------------------------------------------------ 分析本体
def analyze(race, results, baseline, laps, dup_count=1):
    """
    race     : {"venue","surface","distance","course_type","track_condition",
                "age","race_class","race_name"}
    results  : [{"name","finish","time"(秒|None),"last3f"(float|None),"corners"([int]),"weight"}]
    baseline : {"winner","top3","all_avg","pci3","rpci","ave_3f","race_count","laps"} または None
               (数値が無い項目は 0 / None / 空リスト)
    laps     : このレースのラップ(秒)のリスト。無ければ []
    """
    notes = []
    dist = race["distance"]
    b = baseline
    rows_src = sorted(results, key=lambda r: r["finish"])
    timed = [r for r in rows_src if r.get("time")]
    winner = timed[0] if timed else None
    winner_sec = winner["time"] if winner else None
    top3 = timed[:3]
    top3_avg = _mean([r["time"] for r in top3])
    all_avg = _mean([r["time"] for r in timed])

    # ---- 時計面: 基準との比較
    metrics = []
    time_diffs = []

    def add(name, actual, base, actual_digits, base_digits, use_for_index):
        d = base - actual
        metrics.append({
            "name": name,
            "actual": _fmt_time(actual, actual_digits),
            "base": _fmt_time(base, base_digits),
            "diff": _diff_text(d),
            "cls": _cls(d),
        })
        if use_for_index:
            time_diffs.append(d)

    if b and b.get("winner") and winner_sec:
        add("1着タイム", winner_sec, b["winner"], 1, 2, True)
    if b and b.get("top3") and top3_avg:
        add("1〜3着の平均", top3_avg, b["top3"], 2, 2, True)
    if b and b.get("all_avg") and all_avg:
        add("全馬の平均", all_avg, b["all_avg"], 2, 2, True)
    elif b and not b.get("all_avg"):
        notes.append("基準の「全馬平均」が未取り込みのため、全馬平均の比較は省略しました"
                     "(基準タイムのExcelを取り込み直すと表示されます)。")
    if b and b.get("ave_3f") and winner and winner.get("last3f"):
        d = b["ave_3f"] - winner["last3f"]
        metrics.append({
            "name": "1着の上がり3F(基準はAve-3F)",
            "actual": f"{winner['last3f']:.1f}",
            "base": f"{b['ave_3f']:.2f}",
            "diff": _diff_text(d),
            "cls": _cls(d),
        })

    verdict = None
    index = None
    if time_diffs and b and b.get("winner"):
        index = _mean(time_diffs)
        pct = index / b["winner"] * 100
        label = _level_label(pct)
        verdict = {
            "label": label,
            "text": (f"時計の比較(1着・1〜3着平均"
                     f"{'・全馬平均' if any(m['name'] == '全馬の平均' for m in metrics) else ''})の平均は、"
                     f"基準より{_diff_text(index)}(基準の勝ち時計に対して{pct:+.2f}%)です。"
                     "目安として +0.7%以上を「高レベル」、−0.7%以下を「低レベル」としています。"),
        }
    elif not b:
        notes.append(f"基準タイムが見つかりませんでした(条件: {race['venue']} {race['surface']}{dist}m"
                     f"{race['course_type'] or ''} {race['age']} {race['race_class']})。"
                     "レース登録の内容と、基準タイムの取り込み状況を確認してください。"
                     "時計の比較はできませんが、以下のペース・展開の分析は表示します。")

    if b and b.get("race_count") and b["race_count"] < 20:
        notes.append(f"基準のレース数が{b['race_count']}件と少ないため、比較は参考程度に見てください。")
    if dup_count > 1:
        notes.append(f"同じ条件の基準タイムが{dup_count}件重複しています(先頭の1件を使用)。"
                     "基準タイムのExcelに重複した行が無いか確認してください。")

    # ---- ペース: 馬ごとのPCI
    pace = None
    pcis = [p for p in (calc_pci(r["time"], r.get("last3f"), dist) for r in top3) if p is not None]
    if pcis:
        avg_pci = _mean(pcis)
        lines = [f"1〜3着馬のPCIの平均は{avg_pci:.1f}です"
                 "(PCIが大きいほど後半重視、小さいほど前半重視の走り)。"]
        if b and b.get("pci3"):
            d = avg_pci - b["pci3"]
            if d >= 2.0:
                reading = "基準より後半重視(上がり勝負寄り)の流れで、瞬発力が問われたレースです。"
            elif d <= -2.0:
                reading = "基準より前半重視(消耗戦寄り)の流れで、持続力が問われたレースです。"
            else:
                reading = "基準と同程度のバランスの流れです。"
            lines.append(f"基準のPCI3は{b['pci3']:.2f}で、{d:+.1f}の差です。{reading}")
            if index is not None:
                if index > 0 and d >= 2.0:
                    lines.append("時計が速いのは前半が速かったからではなく、終いの脚が速かったためです。")
                elif index > 0 and d <= -2.0:
                    lines.append("前半から速い流れを押し切っており、地力の高い内容です。")
                elif index < 0 and d >= 2.0:
                    lines.append("前半が緩く上がり勝負になった分、時計は平凡です。レベルの判断には注意が必要です。")
                elif index < 0 and d <= -2.0:
                    lines.append("前半が速く消耗した分、時計が遅くなった可能性があります。")
        pace = {"lines": lines}

    # ---- ラップ
    lap_info = None
    if laps and len(laps) >= 4:
        total = sum(laps)
        first3 = sum(laps[:3])
        last3 = sum(laps[-3:])
        rpci = calc_pci(total, last3, dist)
        lines = [f"前半3F {first3:.1f}秒 → 後半3F {last3:.1f}秒"
                 f"(後半が{abs(last3 - first3):.1f}秒{'速い(後傾ラップ)' if last3 < first3 else '遅い(前傾ラップ)'})。"]
        if rpci is not None:
            line = f"RPCI(レース全体のペース指数)は{rpci:.1f}です。"
            if b and b.get("rpci"):
                dr = rpci - b["rpci"]
                if dr >= 2.0:
                    reading = "基準より緩い流れでした。"
                elif dr <= -2.0:
                    reading = "基準より速い流れでした。"
                else:
                    reading = "基準と同程度の流れでした。"
                line += f"基準は{b['rpci']:.2f}で、{dr:+.1f}の差です。{reading}"
            lines.append(line)
        mid = laps[1:-3]
        if len(mid) >= 2:
            lines.append(f"中盤のラップは最速{min(mid):.1f}秒・最遅{max(mid):.1f}秒(幅{max(mid) - min(mid):.1f}秒)です。")
        if winner_sec and abs(total - winner_sec) > 1.0:
            notes.append(f"ラップの合計({total:.1f}秒)が勝ち時計({winner_sec:.1f}秒)と"
                         f"{abs(total - winner_sec):.1f}秒ずれています。貼り付けた内容を確認してください。")
        table = []
        base_laps = (b or {}).get("laps") or []
        same_len = len(base_laps) == len(laps)
        n = len(laps)
        for i, lap in enumerate(laps):
            cum = dist - (n - 1 - i) * 200
            row = {"point": f"{cum}m", "lap": f"{lap:.1f}", "base": "-", "diff": "-", "cls": ""}
            if same_len:
                row["base"] = f"{base_laps[i]:.2f}"
                dd = lap - base_laps[i]
                row["diff"] = f"{dd:+.2f}"
                row["cls"] = "stat-miss" if dd >= 0.3 else ("stat-hit" if dd <= -0.3 else "")
            table.append(row)
        lap_info = {"lines": lines, "table": table, "compared": same_len}

    # ---- 展開: 通過順位
    development = None
    with_c = [r for r in rows_src if len(r.get("corners") or []) >= 2]
    if len(with_c) >= 6:
        n = len(with_c)
        front_n = max(2, round(n * 0.2))
        front = [r for r in with_c if r["corners"][0] <= front_n]
        field_mean = _mean([r["finish"] for r in with_c])
        top3c = [r for r in with_c if r["finish"] <= 3]
        lines = []
        if front:
            front_avg = _mean([r["finish"] for r in front])
            gap = front_avg - field_mean
            thr = max(1.5, n * 0.1)
            if gap >= thr:
                reading = "前で運んだ馬が苦しく、後ろから動いた馬に向いた流れでした(前崩れ)。"
            elif gap <= -thr:
                reading = "前で運んだ馬が有利な流れでした(前有利)。"
            else:
                reading = "位置取りによる有利不利は大きくありませんでした(フラット)。"
            lines.append(f"最初のコーナーで{front_n}番手以内だった馬({len(front)}頭)の平均着順は{front_avg:.1f}着"
                         f"(全体平均{field_mean:.1f}着)。{reading}")
        if top3c:
            first_pos = _mean([r["corners"][0] for r in top3c])
            last_pos = _mean([r["corners"][-1] for r in top3c])
            lines.append(f"1〜3着馬の位置取りは、最初のコーナー平均{first_pos:.1f}番手 → 最後のコーナー平均{last_pos:.1f}番手でした。")
        development = {"lines": lines}

    # ---- 着順ごとの一覧
    l3s = [r["last3f"] for r in rows_src if r.get("last3f")]
    fastest_l3 = min(l3s) if l3s else None
    rows = []
    for r in rows_src:
        t = r.get("time")
        gap = (t - winner_sec) if (t and winner_sec) else None
        pci = calc_pci(t, r.get("last3f"), dist) if t else None
        score = None
        if t and b and b.get("winner"):
            score = round(max(0.0, min(10.0, 5.0 + (b["winner"] - t) * 4)), 1)
        corners = r.get("corners") or []
        rows.append({
            "finish": r["finish"],
            "name": r["name"],
            "time": _fmt_time(t, 1) if t else "-",
            "gap": ("-" if not gap else f"+{gap:.1f}") if gap is not None else "-",
            "last3f": f"{r['last3f']:.1f}" if r.get("last3f") else "-",
            "best3f": bool(fastest_l3 and r.get("last3f") == fastest_l3),
            "pci": f"{pci:.1f}" if pci is not None else "-",
            "corners": "→".join(str(c) for c in corners) if corners else "-",
            "score": f"{score:.1f}" if score is not None else "-",
        })

    # ---- 注意点
    tc = race.get("track_condition") or ""
    if tc in ("重", "不良"):
        if race["surface"] == "ダート":
            notes.append(f"馬場状態が「{tc}」です。ダートは水分を含むと時計が速くなる傾向があり、"
                         "基準(良〜不良の平均)と比べて時計が速めに出ている可能性があります。")
        else:
            notes.append(f"馬場状態が「{tc}」です。芝は渋ると時計が遅くなる傾向があり、"
                         "時計面の評価が低めに出ている可能性があります。")
    if "歳" not in (race.get("race_name") or ""):
        notes.append(f"レース名から年齢・クラスを推定しています(年齢: {race['age']} / クラス: {race['race_class']})。"
                     "3歳限定の重賞などは基準とずれることがあります。")
    if any(not r.get("last3f") for r in timed):
        notes.append("上がり3Fが読み取れていない馬がいるため、その馬のPCIは表示していません。")
    notes.append("ここでの評価は基準タイムとの比較にもとづく目安です。"
                 "基準は馬場状態や天候を区別していません。")

    conditions = (f"{race['venue']} {race['surface']}{dist}m{race['course_type'] or ''}・"
                  f"{race['age']} {race['race_class']}"
                  f"{'・馬場' + tc if tc else ''}")
    return {
        "conditions": conditions,
        "baseline_ok": bool(b),
        "verdict": verdict,
        "metrics": metrics,
        "pace": pace,
        "laps": lap_info,
        "development": development,
        "rows": rows,
        "notes": notes,
    }


# ------------------------------------------------------------------ DBからの組み立て
def analyze_race(session: Session, race: Race) -> dict:
    age, race_class = infer_age_and_class(race.race_name or "")
    course_type = getattr(race, "course_type", "") or ""

    matches = session.exec(
        select(StandardTime).where(
            StandardTime.venue == race.venue,
            StandardTime.surface == race.surface,
            StandardTime.distance == race.distance,
            StandardTime.course_type == course_type,
            StandardTime.age == age,
            StandardTime.race_class == race_class,
        )
    ).all()

    baseline = None
    if matches:
        m = matches[0]
        extra = session.exec(
            select(StandardTimeExtra).where(
                StandardTimeExtra.venue == race.venue,
                StandardTimeExtra.surface == race.surface,
                StandardTimeExtra.distance == race.distance,
                StandardTimeExtra.course_type == course_type,
                StandardTimeExtra.age == age,
                StandardTimeExtra.race_class == race_class,
            )
        ).first()
        baseline = {
            "winner": m.winner_time_seconds or None,
            "top3": m.top3_avg_seconds or None,
            "all_avg": (extra.all_avg_seconds if extra else 0.0) or None,
            "pci3": m.pci3 or None,
            "rpci": getattr(m, "rpci", 0.0) or None,
            "ave_3f": m.ave_3f or None,
            "race_count": m.race_count,
            "laps": parse_lap_string(extra.lap_avg if extra else ""),
        }

    # 同じ馬の結果が二重に登録されている場合は、あとから登録した方を使う
    latest = {}
    for ar in sorted(
        session.exec(select(ActualResult).where(ActualResult.race_id == race.id)).all(),
        key=lambda x: x.id or 0,
    ):
        latest[ar.horse_name] = ar

    results = []
    for ar in latest.values():
        try:
            l3 = float(ar.final_3f) if ar.final_3f else None
        except ValueError:
            l3 = None
        results.append({
            "name": ar.horse_name,
            "finish": ar.finish_position,
            "time": parse_time(ar.time),
            "last3f": l3,
            "corners": [int(x) for x in re.findall(r"\d+", ar.corner_positions or "")],
            "weight": ar.weight,
        })

    race_info = {
        "venue": race.venue,
        "surface": race.surface,
        "distance": race.distance,
        "course_type": course_type,
        "track_condition": race.track_condition,
        "age": age,
        "race_class": race_class,
        "race_name": race.race_name,
    }
    lap_row = session.get(RaceLap, race.id)
    laps = parse_lap_string(lap_row.lap_times if lap_row else "")
    out = analyze(race_info, results, baseline, laps, dup_count=len(matches))
    out["has_results"] = bool(results)
    return out


def save_race_laps(session: Session, race_id: int, laps):
    row = session.get(RaceLap, race_id)
    text = "-".join(str(x) for x in laps)
    if row:
        row.lap_times = text
    else:
        row = RaceLap(race_id=race_id, lap_times=text)
    session.add(row)
    session.commit()


def list_analyzable_races(session: Session):
    """結果が登録済みのレースの一覧(新しい日付順)。"""
    names_by_race = {}
    for r in session.exec(select(ActualResult)).all():
        names_by_race.setdefault(r.race_id, set()).add(r.horse_name)
    out = []
    for race_id, names in names_by_race.items():
        race = session.get(Race, race_id)
        if race:
            out.append({
                "id": race.id,
                "label": race_label(race),
                "count": len(names),
                "date": race.date,
                "number": race.race_number,
            })
    out.sort(key=lambda x: (x["date"], -x["number"]), reverse=True)
    return out


# ------------------------------------------------------------------ 結果の貼り付け登録
def extract_laps_from_result_text(text):
    """結果ページを貼り付けたときに使う。「ハロンタイム」の行があるときだけラップを取り出す。"""
    return parse_laps(text) if "ハロンタイム" in (text or "") else []


def detect_going(text, surface):
    """結果ページの「芝 重」「ダート 良」の行から、そのレースの馬場状態を読み取る。"""
    for line in (text or "").splitlines():
        m = re.fullmatch(r"(芝|ダート)\t(良|稍重|重|不良)", line.strip())
        if m and m.group(1) == surface:
            return m.group(2)
    return None


def save_race_results(session: Session, race_id: int, entries):
    """貼り付けた着順表を登録する。同じレースの結果がすでにあれば置き換える。"""
    for old in session.exec(select(ActualResult).where(ActualResult.race_id == race_id)).all():
        session.delete(old)
    for e in entries:
        session.add(ActualResult(
            race_id=race_id,
            horse_name=e["name"],
            finish_position=e["finish_position"],
            time=e["time"],
            corner_positions=e["corner_positions"],
            final_3f=e["final_3f"],
            weight=e["weight"],
        ))
    session.commit()


def names_match_ratio(session: Session, race_id: int, names):
    """貼り付けた馬名のうち、このレースの登録済み出走馬と一致する割合。比べられなければ None。"""
    registered = {h.name for h in session.exec(select(Horse).where(Horse.race_id == race_id)).all()}
    names = set(names)
    if not registered or not names:
        return None
    return len(registered & names) / len(names)