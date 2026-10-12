#!/usr/bin/env python3
"""기상청 단기예보 격자·위경도 엑셀에서 홈 날씨 지역 목록(CSV)을 만든다.

원본: 공공데이터포털 "기상청_단기예보 ((구)_동네예보) 조회서비스"(15084084) 참고문서
      "기상청41_단기예보 조회서비스_오픈API활용가이드_격자_위경도(2607).xlsx"
      이용허락범위: 저작자표시. 자세한 내용은 docs/data-sources/korea-regions.md.

사용법(openpyxl 필요):
    python3 scripts/build-korea-regions.py 격자_위경도.xlsx \
        > data/weather/src/main/assets/weather/korea_regions.csv

출력 한 줄은 `code,name,lat,lon[,short]`이다.
- code: 행정구역코드(10자리). 부모는 코드로 정해진다(읍·면·동 → 앞 5자리+00000, 시·군·구 → 앞 2자리+00000000).
- name: 그 단계의 이름(1단계·2단계·3단계 중 마지막 칸). 원본 그대로 둔다(예: 수원시장안구).
- lat, lon: 원본의 위도·경도(초/100)를 소수 넷째 자리(약 10m)로 줄인 값.
- short: 시·도 줄에만 붙는 짧은 이름(서울특별시 → 서울).
"""

import hashlib
import sys

import openpyxl

# 시·도 짧은 이름. 원본에 새 시·도가 생기면 여기에 더해야 스크립트가 멈추지 않는다.
SHORT_NAMES = {
    "서울특별시": "서울",
    "부산광역시": "부산",
    "대구광역시": "대구",
    "인천광역시": "인천",
    "대전광역시": "대전",
    "울산광역시": "울산",
    "세종특별자치시": "세종",
    "경기도": "경기",
    "강원특별자치도": "강원",
    "충청북도": "충북",
    "충청남도": "충남",
    "전북특별자치도": "전북",
    "전남광주통합특별시": "전남광주",
    "경상북도": "경북",
    "경상남도": "경남",
    "제주특별자치도": "제주",
}

# 육지 행정구역이 아닌 관측 지점(이어도 해양과학기지)은 좌표가 0이라 뺀다.
SKIPPED_PROVINCES = {"이어도"}


def cell(value):
    return "" if value is None else str(value).strip()


def main(path):
    with open(path, "rb") as f:
        digest = hashlib.sha256(f.read()).hexdigest()
    sheet = openpyxl.load_workbook(path, read_only=True).worksheets[0]
    rows = list(sheet.iter_rows(values_only=True))
    header = [cell(v) for v in rows[0]]
    col = {name: header.index(name) for name in ("행정구역코드", "1단계", "2단계", "3단계", "경도(초/100)", "위도(초/100)")}
    print("# 기상청 단기예보 조회서비스 격자_위경도 (" + sheet.title + ")")
    print("# 출처: 공공데이터포털 15084084, 이용허락범위 저작자표시. sha256 " + digest)
    print("# code,name,lat,lon[,short]")
    for row in rows[1:]:
        code = cell(row[col["행정구역코드"]])
        levels = [cell(row[col[name]]) for name in ("1단계", "2단계", "3단계")]
        if not code or levels[0] in SKIPPED_PROVINCES:
            continue
        name = [level for level in levels if level][-1]
        lat = round(float(row[col["위도(초/100)"]]), 4)
        lon = round(float(row[col["경도(초/100)"]]), 4)
        fields = [code, name, f"{lat:.4f}", f"{lon:.4f}"]
        if not levels[1]:
            fields.append(SHORT_NAMES[name])
        print(",".join(fields))


if __name__ == "__main__":
    main(sys.argv[1])
