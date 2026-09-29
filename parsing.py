import re

def infer_running_style(position: int) -> str:
    if position <= 2:
        return "逃げ"
    elif position <= 6:
        return "先行"
    elif position <= 11:
        return "差し"
    else:
        return "追込"

def parse_shutsuba_text(text: str) -> list[dict]:
    lines = [l.rstrip("\r") for l in text.split("\n")]
    waku_pattern = re.compile(r"^枠(\d+)[^\t]*\t(\d+)\t?$")
    date_pattern = re.compile(r"^(\d{4}年\d{1,2}月\d{1,2}日)\t(.+)$")
    position_line_pattern = re.compile(r"^\d+(\t\d+)*$")

    start_indices = [i for i, l in enumerate(lines) if waku_pattern.match(l.strip())]
    entries = []

    for k, start in enumerate(start_indices):
        end = start_indices[k + 1] if k + 1 < len(start_indices) else len(lines)
        block = [l.strip() for l in lines[start:end]]

        m = waku_pattern.match(block[0])
        waku = m.group(1)
        horse_number = m.group(2)

        idx = 1
        name = None
        while idx < len(block):
            if block[idx] and "着用" not in block[idx]:
                name = block[idx]
                break
            idx += 1

        odds = None
        j = idx + 1
        while j < len(block):
            if block[j]:
                mo = re.match(r"^(\d+\.\d+)$", block[j])
                if mo:
                    odds = mo.group(1)
                    j += 1
                break
            j += 1

        popularity = None
        while j < len(block):
            if block[j]:
                mp = re.match(r"\((\d+)番人気\)", block[j])
                if mp:
                    popularity = mp.group(1)
                break
            j += 1

        sex_age = None
        for l in block:
            if re.match(r"^(牡|牝|セ|せん)\d+/", l):
                sex_age = l
                break

        date_idx = None
        race_date = venue = None
        for i2, l in enumerate(block):
            md = date_pattern.match(l)
            if md:
                date_idx = i2
                race_date, venue = md.group(1), md.group(2)
                break

        jockey = None
        if date_idx:
            for i3 in range(date_idx - 1, idx, -1):
                l = block[i3]
                if l and "kg" not in l and not re.match(r"^\d", l):
                    jockey = l
                    break

        last_race_summary = ""
        suggested_running_style = "不明"
        past_races = []
        distance_surface_pattern = re.compile(r"^(\d+)(芝|ダ)$")
        colon_time_pattern = re.compile(r"^(\d+):(\d{2})\.(\d)$")

        date_positions = [i for i, l in enumerate(block) if date_pattern.match(l)]
        for k2, pos in enumerate(date_positions[:3]):
            end_pos = date_positions[k2 + 1] if k2 + 1 < len(date_positions) else len(block)
            section = block[pos:end_pos]

            md = date_pattern.match(section[0])
            race_date, venue = md.group(1), md.group(2)

            race_class_text = ""
            for l in section[1:]:
                if l:
                    race_class_text = l
                    break

            distance = None
            surface = None
            time_seconds = None
            for l in section:
                dm = distance_surface_pattern.match(l)
                if dm:
                    distance = int(dm.group(1))
                    surface_raw = dm.group(2)
                    surface = "ダート" if surface_raw == "ダ" else "芝"
                tm = colon_time_pattern.match(l)
                if tm and time_seconds is None:
                    time_seconds = int(tm.group(1)) * 60 + int(tm.group(2)) + int(tm.group(3)) / 10

            if k2 == 0:
                summary_lines = [l for l in section if l]
                last_race_summary = " / ".join(summary_lines[:6])
                for i4, l in enumerate(section):
                    if l.startswith("3F") and i4 > 0:
                        prev_line = section[i4 - 1]
                        if position_line_pattern.match(prev_line):
                            positions = [int(p) for p in prev_line.split("\t")]
                            suggested_running_style = infer_running_style(positions[-1])
                        break

            if distance and surface and time_seconds:
                past_races.append({
                    "date": race_date, "venue": venue, "distance": distance,
                    "surface": surface, "race_class_text": race_class_text,
                    "time_seconds": time_seconds,
                })

        entries.append({
            "waku": waku,
            "horse_number": horse_number,
            "name": name,
            "odds": odds,
            "popularity": popularity,
            "sex_age": sex_age,
            "jockey": jockey,
            "last_race_summary": last_race_summary,
            "suggested_running_style": suggested_running_style,
            "past_races": past_races,
        })

    return entries

# JRAの結果ページの表をコピーすると、1頭ぶんが次の3行になる:
#   着順 <TAB> 枠 <TAB> 馬番 <TAB> 馬名 <TAB> 性齢 <TAB> 斤量 <TAB> 騎手 <TAB> タイム <TAB> 着差
#   コーナー通過順位(例: 15 13 2 2)
#   上がり3F <TAB> 馬体重(増減) <TAB> 調教師 <TAB> 人気
# 「ブリンカー着用」などの注記がある馬は、馬名が次の行、性齢以降がその次の行に分かれる。
_EQUIP_SUFFIX = re.compile(r"(ブリンカー|シャドーロール|チークピーシーズ|パシファイヤー)着用$")
_RESULT_TIME = re.compile(r"^\d+:\d{2}\.\d$")
_CORNER_LINE = re.compile(r"^\d+(?: \d+)*$")
_AGARI = re.compile(r"^\d{2}\.\d$")


def _result_head(line: str):
    """「着順 枠 馬番 …」で始まる行なら、タブで分けたリストを返す。違えば None。"""
    parts = line.rstrip("\r\n").split("\t")
    if (len(parts) >= 3 and parts[0].strip().isdigit()
            and parts[1].strip().startswith("枠") and parts[2].strip().isdigit()):
        return parts
    return None


def parse_result_table(text: str) -> list[dict]:
    lines = text.split("\n")
    entries = []
    i = 0
    while i < len(lines):
        parts = _result_head(lines[i])
        if parts is None:
            i += 1
            continue

        finish_position = int(parts[0].strip())
        i += 1
        if len(parts) > 3 and parts[3].strip():
            name = parts[3].strip()
            detail = parts[4:]
        else:
            while i < len(lines) and not lines[i].strip():
                i += 1
            name = _EQUIP_SUFFIX.sub("", lines[i].strip()) if i < len(lines) else ""
            i += 1
            detail = lines[i].rstrip("\r\n").split("\t") if i < len(lines) else []
            i += 1

        # detail = [性齢, 斤量, 騎手, タイム, 着差, ...]
        time_value = ""
        if len(detail) > 3 and _RESULT_TIME.match(detail[3].strip()):
            time_value = detail[3].strip()

        corner_positions = ""
        while i < len(lines) and not lines[i].strip():
            i += 1
        if i < len(lines) and _CORNER_LINE.match(lines[i].strip()):
            corner_positions = lines[i].strip()
            i += 1

        final_3f = ""
        weight = ""
        while i < len(lines) and not lines[i].strip():
            i += 1
        if i < len(lines):
            tail = lines[i].rstrip("\r\n").split("\t")
            if tail and _AGARI.match(tail[0].strip()):
                final_3f = tail[0].strip()
                weight = tail[1].strip() if len(tail) > 1 else ""
                i += 1

        entries.append({
            "finish_position": finish_position,
            "name": name,
            "time": time_value,
            "corner_positions": corner_positions,
            "final_3f": final_3f,
            "weight": weight,
        })

    entries.sort(key=lambda e: e["finish_position"])
    return entries


def time_str_to_seconds(time_str: str) -> float:
    time_str = (time_str or "").strip().replace("：", ":")
    if not time_str:
        return 0.0
    # 結果表の「1:55.5」の形式
    m = re.fullmatch(r"(\d+):(\d{1,2})(?:\.(\d+))?", time_str)
    if m:
        frac = int(m.group(3)) / 10 ** len(m.group(3)) if m.group(3) else 0.0
        return int(m.group(1)) * 60 + int(m.group(2)) + frac
    # 基準タイムの「1.56.36」の形式
    parts = time_str.split(".")
    if len(parts) == 3:
        minutes, seconds, frac = parts
        return int(minutes) * 60 + int(seconds) + int(frac) / (10 ** len(frac))
    elif len(parts) == 2:
        seconds, frac = parts
        return int(seconds) + int(frac) / (10 ** len(frac))
    return 0.0

CLASS_NAME_MAP = {
    "1勝クラス": "500万",
    "2勝クラス": "1000万",
    "3勝クラス": "1600万",
    "オープン": "OPEN",
    "OPEN": "OPEN",
}

def infer_class(text: str) -> str:
    if "新馬" in text:
        return "新馬"
    if "未勝利" in text:
        return "未勝利"
    for new_name, old_name in CLASS_NAME_MAP.items():
        if new_name in text:
            return old_name
    return "OPEN"

def infer_age_and_class(race_name: str) -> tuple[str, str]:
    race_class = infer_class(race_name)
    age = "古馬"
    if "2歳" in race_name or "２歳" in race_name:
        age = "2歳"
    elif "3歳" in race_name or "３歳" in race_name:
        age = "古馬" if "以上" in race_name else "3歳"
    return age, race_class

def age_category_from_sex_age(sex_age: str) -> str:
    m = re.search(r"(\d+)", sex_age or "")
    if not m:
        return "古馬"
    age = int(m.group(1))
    if age == 2:
        return "2歳"
    elif age == 3:
        return "3歳"
    return "古馬"