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
            if re.match(r"^(牡|牝|セ)\d+/", l):
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
        date_positions = [i for i, l in enumerate(block) if date_pattern.match(l)]
        if date_positions:
            first_date_idx = date_positions[0]
            second_date_idx = date_positions[1] if len(date_positions) > 1 else len(block)
            section = block[first_date_idx:second_date_idx]

            summary_lines = [l for l in section if l]
            last_race_summary = " / ".join(summary_lines[:6])

            for i4, l in enumerate(section):
                if l.startswith("3F") and i4 > 0:
                    prev_line = section[i4 - 1]
                    if position_line_pattern.match(prev_line):
                        positions = [int(p) for p in prev_line.split("\t")]
                        suggested_running_style = infer_running_style(positions[-1])
                    break

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
        })

    return entries

def parse_result_table(text: str) -> list[dict]:
    lines = [l.rstrip("\r") for l in text.split("\n")]
    entries = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        parts = line.split("\t")
        # 「着順」の行は、先頭が数字で、かつ「枠」を含む2つ目の要素がある
        if len(parts) >= 4 and parts[0].isdigit() and parts[1].startswith("枠"):
            finish_position = int(parts[0])
            umaban = parts[2].strip()
            name = parts[3].strip()

            # 名前の直後に注記(ブリンカー着用など)が別行で挟まることがあるのでスキップ
            j = i + 1
            while j < len(lines) and lines[j].strip() and not re.match(r"^(牡|牝|セ)\d+", lines[j].strip()):
                j += 1

            sex_age = lines[j].strip() if j < len(lines) else ""

            # 残りの列(負担重量・騎手・タイム・着差)を探す
            rest = lines[j+1:j+6]
            rest = [r.strip() for r in rest if r.strip()]

            time_value = ""
            for r in rest:
                if re.match(r"^\d:\d{2}\.\d$", r):
                    time_value = r
                    break

            # コーナー通過順位(数字とスペースだけの行)を探す
            corner_positions = ""
            k = j
            while k < len(lines) and k < j + 10:
                l2 = lines[k].strip()
                if re.match(r"^\d+(\s+\d+)+$", l2):
                    corner_positions = l2
                    break
                k += 1

            # 推定上り(小数点を含む数字だけの行)と、その次の馬体重を探す
            final_3f = ""
            weight = ""
            for idx3 in range(k, min(k + 4, len(lines))):
                l3 = lines[idx3].strip()
                if re.match(r"^\d{2}\.\d$", l3) and not final_3f:
                    final_3f = l3
                elif re.match(r"^\d{3,4}\([+\-0]?\d*\)$", l3):
                    weight = l3

            entries.append({
                "finish_position": finish_position,
                "name": name,
                "time": time_value,
                "corner_positions": corner_positions,
                "final_3f": final_3f,
                "weight": weight,
            })
            i = k
        else:
            i += 1

    entries.sort(key=lambda e: e["finish_position"])
    return entries

def time_str_to_seconds(time_str: str) -> float:
    time_str = time_str.strip()
    if not time_str:
        return 0.0
    parts = time_str.split(".")
    if len(parts) == 3:
        minutes, seconds, tenths = parts
        return int(minutes) * 60 + int(seconds) + int(tenths) / 10
    elif len(parts) == 2:
        seconds, tenths = parts
        return int(seconds) + int(tenths) / 10
    return 0.0

CLASS_NAME_MAP = {
    "1勝クラス": "500万",
    "2勝クラス": "1000万",
    "3勝クラス": "1600万",
    "オープン": "OPEN",
    "OPEN": "OPEN",
}

def infer_age_and_class(race_name: str) -> tuple[str, str]:
    # クラスの判定
    race_class = "OPEN"  # 重賞・特別戦などはデフォルトでOPEN扱い
    if "新馬" in race_name:
        race_class = "新馬"
    elif "未勝利" in race_name:
        race_class = "未勝利"
    else:
        for new_name, old_name in CLASS_NAME_MAP.items():
            if new_name in race_name:
                race_class = old_name
                break

    # 年齢の判定
    age = "古馬"
    if "2歳" in race_name or "２歳" in race_name:
        age = "２歳"
    elif "3歳" in race_name or "３歳" in race_name:
        if "以上" in race_name:
            age = "古馬"  # 3歳以上は年齢混合なので、便宜上「古馬」の基準タイムを使う
        else:
            age = "３歳"

    return age, race_class