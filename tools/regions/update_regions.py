#!/usr/bin/env python3
"""새로 만든 지역 CSV를 naurylab.com에 올릴 버전 파일과 regions.json으로 만든다.

사용법:
    python3 tools/regions/update_regions.py new.csv [--dir chageun/data/regions]
        [--version 2026-07] [--source-date 2026-07-01] [--summary-out summary.md]

- 지금 올라가 있는 최신 CSV(regions.json의 file)와 데이터 줄을 비교한다. 같으면 아무것도 쓰지 않고 끝낸다.
- 다르면 regions-<version>.csv를 새로 쓰고 regions.json을 고친다. 예전 CSV는 지우지 않는다.
- version과 출처 날짜는 CSV 첫 줄의 시트 이름(…_20260701)에서 읽는다. 못 읽으면 --version, --source-date로 준다.
- 검사(줄 수, 좌표 범위, 코드 중복, 부모 코드)에 걸리면 아무것도 쓰지 않고 1로 끝낸다.

바뀐 코드(renamedCodes): 없어진 옛 코드마다, 새로 생긴 같은 단계 코드 중 전체 이름(시·도 시·군·구 읍·면·동)이
같은 곳이 딱 하나면 그 코드로, 아니면 대표 좌표가 200m 안인 곳이 딱 하나면 그 코드로 잇는다.
둘 다 아니면 잇지 않는다(앱이 위 단계로 거슬러 올라가 보여 준다). 예전 버전의 연결은 그대로 두고,
값이 이번에 없어진 코드를 가리키면 새 코드로 고쳐 늘 최신 코드를 가리키게 한다.
"""

import argparse
import hashlib
import json
import math
import os
import re
import sys

SCHEMA = 1
MIN_ROWS = 3000
LAT_RANGE = (33.0, 39.0)
LON_RANGE = (124.0, 132.0)
SAME_PLACE_METERS = 200.0
SOURCE_TEMPLATE = "기상청 단기예보 조회서비스 격자·위경도 (공공데이터포털 15084084), {date}, 저작자표시"


class Region:
    __slots__ = ("code", "name", "lat", "lon", "short", "line")

    def __init__(self, code, name, lat, lon, short, line):
        self.code = code
        self.name = name
        self.lat = lat
        self.lon = lon
        self.short = short
        self.line = line


def level(code):
    """1: 시·도, 2: 시·군·구, 3: 읍·면·동."""
    if code[2:] == "0" * 8:
        return 1
    if code[5:] == "0" * 5:
        return 2
    return 3


def parent(code):
    lv = level(code)
    if lv == 3:
        return code[:5] + "0" * 5
    if lv == 2:
        return code[:2] + "0" * 8
    return None


def read_csv(path):
    """(첫 주석 줄들, 데이터 줄 목록, 원본 바이트)를 돌려준다. 칸 모양이 틀리면 ValueError."""
    with open(path, "rb") as f:
        raw = f.read()
    text = raw.decode("utf-8")
    comments = []
    regions = []
    for number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        if line.startswith("#"):
            comments.append(line)
            continue
        fields = line.split(",")
        if len(fields) not in (4, 5):
            raise ValueError(f"{path}:{number}: 칸 수가 4~5개가 아님: {line}")
        code, name = fields[0], fields[1]
        if not re.fullmatch(r"\d{10}", code):
            raise ValueError(f"{path}:{number}: 행정구역코드가 10자리 숫자가 아님: {code}")
        if not name:
            raise ValueError(f"{path}:{number}: 이름이 비어 있음")
        try:
            lat, lon = float(fields[2]), float(fields[3])
        except ValueError:
            raise ValueError(f"{path}:{number}: 좌표가 숫자가 아님: {line}")
        short = fields[4] if len(fields) == 5 else None
        regions.append(Region(code, name, lat, lon, short, line))
    return comments, regions, raw


def validate(regions):
    errors = []
    if len(regions) <= MIN_ROWS:
        errors.append(f"데이터 줄이 {len(regions)}줄뿐임({MIN_ROWS}줄 넘어야 함)")
    codes = {}
    for r in regions:
        if r.code in codes:
            errors.append(f"코드 중복: {r.code} ({codes[r.code].name}, {r.name})")
        codes[r.code] = r
        if not (LAT_RANGE[0] <= r.lat <= LAT_RANGE[1] and LON_RANGE[0] <= r.lon <= LON_RANGE[1]):
            errors.append(f"좌표가 국내 범위 밖: {r.code} {r.name} {r.lat},{r.lon}")
        if level(r.code) == 1 and not r.short:
            errors.append(f"시·도 줄에 짧은 이름이 없음: {r.code} {r.name}")
        if level(r.code) != 1 and r.short:
            errors.append(f"시·도가 아닌 줄에 짧은 이름이 있음: {r.code} {r.name}")
    for r in regions:
        p = parent(r.code)
        if p and p not in codes:
            errors.append(f"부모 코드 {p}가 없음: {r.code} {r.name}")
    return errors


def full_name(code, by_code):
    names = []
    while code:
        names.append(by_code[code].name)
        code = parent(code)
    return " ".join(reversed(names))


def distance_m(a, b):
    # 200m를 가리는 데는 평면 근사로 충분하다.
    lat = math.radians((a.lat + b.lat) / 2)
    dy = (a.lat - b.lat) * 111_320.0
    dx = (a.lon - b.lon) * 111_320.0 * math.cos(lat)
    return math.hypot(dx, dy)


def find_renames(old, new):
    old_by = {r.code: r for r in old}
    new_by = {r.code: r for r in new}
    removed = [c for c in old_by if c not in new_by]
    added = [c for c in new_by if c not in old_by]
    added_by_level = {}
    for c in added:
        added_by_level.setdefault(level(c), []).append(c)
    added_names = {c: full_name(c, new_by) for c in added}

    renames = {}
    for c in removed:
        candidates = added_by_level.get(level(c), [])
        name = full_name(c, old_by)
        same_name = [n for n in candidates if added_names[n] == name]
        if len(same_name) == 1:
            renames[c] = same_name[0]
            continue
        near = [n for n in candidates if distance_m(old_by[c], new_by[n]) <= SAME_PLACE_METERS]
        if len(near) == 1:
            renames[c] = near[0]
    return removed, added, renames


def merge_renames(previous, renames, new_codes):
    merged = dict(previous)
    # 예전 연결이 이번에 바뀐 코드를 가리키면 새 코드로 잇는다.
    for old, target in list(merged.items()):
        while target in renames:
            target = renames[target]
        merged[old] = target
    merged.update(renames)
    # 다시 쓰이게 된 코드, 새 목록에 없는 곳을 가리키는 연결, 자기 자신을 가리키는 연결은 뺀다.
    return {
        old: target
        for old, target in sorted(merged.items())
        if old not in new_codes and target in new_codes and old != target
    }


def version_from_header(comments):
    for line in comments:
        if "격자" not in line:
            continue
        m = re.search(r"(20\d{2})(\d{2})(\d{2})\D*\)?\s*$", line)
        if m:
            y, mo, d = m.groups()
            return f"{y}-{mo}", f"{y}-{mo}-{d}"
    return None, None


def write_json(path, data):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def summarize(version, old_version, old, new, removed, added, renames, changed_coords, renamed_names):
    new_by = {r.code: r for r in new}
    old_by = {r.code: r for r in old}
    lines = [
        f"차근 지역 목록 {old_version} → {version}",
        "",
        f"- 지역 수: {len(old):,} → {len(new):,}",
        f"- 새로 생긴 코드: {len(added):,}",
        f"- 없어진 코드: {len(removed):,} (그중 새 코드로 이은 것 {len(renames):,}, 잇지 못한 것 {len(removed) - len(renames):,})",
        f"- 코드는 그대로이고 이름이 바뀐 곳: {len(renamed_names):,}, 좌표가 바뀐 곳: {len(changed_coords):,}",
    ]
    notable_added = [c for c in added if level(c) < 3]
    notable_removed = [c for c in removed if level(c) < 3]
    if notable_added:
        lines += ["", "새 시·도, 시·군·구:"]
        lines += [f"- {c} {full_name(c, new_by)}" for c in notable_added]
    if notable_removed:
        lines += ["", "없어진 시·도, 시·군·구:"]
        for c in notable_removed:
            to = renames.get(c)
            suffix = f" → {to} {full_name(to, new_by)}" if to else " (잇지 않음)"
            lines.append(f"- {c} {full_name(c, old_by)}{suffix}")
    unmapped = [c for c in removed if c not in renames and level(c) == 3]
    if unmapped:
        lines += ["", f"잇지 못한 읍·면·동 {len(unmapped):,}곳(앞 20곳):"]
        lines += [f"- {c} {full_name(c, old_by)}" for c in unmapped[:20]]
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser(description="차근 지역 목록 새 버전 만들기")
    ap.add_argument("new_csv")
    ap.add_argument("--dir", default="chageun/data/regions")
    ap.add_argument("--version", help="YYYY-MM. 없으면 CSV 첫 줄의 시트 날짜에서 읽는다")
    ap.add_argument("--source-date", help="YYYY-MM-DD. 없으면 CSV 첫 줄의 시트 날짜에서 읽는다")
    ap.add_argument("--summary-out", help="바뀐 내용 요약을 이 파일에도 쓴다(PR 본문용)")
    args = ap.parse_args()

    try:
        comments, new, new_raw = read_csv(args.new_csv)
    except (ValueError, UnicodeDecodeError) as e:
        print(f"새 CSV를 읽지 못했습니다: {e}", file=sys.stderr)
        return 1

    errors = validate(new)
    if errors:
        print(f"새 CSV 검사에서 {len(errors)}건이 걸렸습니다:", file=sys.stderr)
        for e in errors[:50]:
            print(f"  - {e}", file=sys.stderr)
        return 1

    json_path = os.path.join(args.dir, "regions.json")
    with open(json_path, encoding="utf-8") as f:
        current = json.load(f)
    if current.get("schema") != SCHEMA:
        print(f"regions.json schema {current.get('schema')}는 이 스크립트가 모릅니다", file=sys.stderr)
        return 1
    _, old, _ = read_csv(os.path.join(args.dir, current["file"]))

    if [r.line for r in old] == [r.line for r in new]:
        print(f"바뀐 것 없음: 최신 {current['version']}와 데이터가 같습니다.")
        return 0

    header_version, header_date = version_from_header(comments)
    version = args.version or header_version
    source_date = args.source_date or header_date
    if not version or not re.fullmatch(r"\d{4}-\d{2}", version) or not source_date:
        print("버전을 정하지 못했습니다. --version YYYY-MM --source-date YYYY-MM-DD로 주세요.", file=sys.stderr)
        return 1
    if version <= current["version"]:
        print(
            f"데이터는 바뀌었는데 버전 {version}이 지금 버전 {current['version']}보다 크지 않습니다. "
            "원본 시트 날짜를 확인하고 --version으로 새 버전을 주세요.",
            file=sys.stderr,
        )
        return 1
    file_name = f"regions-{version}.csv"
    out_csv = os.path.join(args.dir, file_name)
    if os.path.exists(out_csv):
        print(f"{out_csv}가 이미 있습니다. 올린 파일은 바꾸지 않습니다.", file=sys.stderr)
        return 1

    removed, added, renames = find_renames(old, new)
    old_by = {r.code: r for r in old}
    changed_coords = []
    renamed_names = []
    for r in new:
        o = old_by.get(r.code)
        if not o:
            continue
        if o.name != r.name:
            renamed_names.append(r.code)
        if (o.lat, o.lon) != (r.lat, r.lon):
            changed_coords.append(r.code)
    new_codes = {r.code for r in new}
    merged = merge_renames(current.get("renamedCodes", {}), renames, new_codes)

    with open(out_csv, "wb") as f:
        f.write(new_raw)
    write_json(
        json_path,
        {
            "schema": SCHEMA,
            "version": version,
            "file": file_name,
            "sha256": hashlib.sha256(new_raw).hexdigest(),
            "rows": len(new),
            "source": SOURCE_TEMPLATE.format(date=source_date),
            "renamedCodes": merged,
        },
    )

    summary = summarize(
        version, current["version"], old, new, removed, added, renames, changed_coords, renamed_names
    )
    print(summary, end="")
    if args.summary_out:
        with open(args.summary_out, "w", encoding="utf-8") as f:
            f.write(summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
