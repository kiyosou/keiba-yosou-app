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
    waku_pattern = re.compile(r"^枠\d+[^\t]*\t(\d+)\t?$")
    date_pattern = re.compile(r"^(\d{4}年\d{1,2}月\d{1,2}日)\t(.+)$")
    position_line_pattern = re.compile(r"^\d+(\t\d+)*$")

    start_indices = [i for i, l in enumerate(lines) if waku_pattern.match(l.strip())]
    entries = []

    for k, start in enumerate(start_indices):
        end = start_indices[k + 1] if k + 1 < len(start_indices) else len(lines)
        block = [l.strip() for l in lines[start:end]]

        m = waku_pattern.match(block[0])
        horse_number = m.group(1)

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