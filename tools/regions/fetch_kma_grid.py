#!/usr/bin/env python3
"""공공데이터포털에서 기상청 단기예보 참고문서 zip을 받아 격자_위경도 xlsx를 꺼낸다.

사용법:
    python3 tools/regions/fetch_kma_grid.py out.xlsx [--url <zip 또는 xlsx 주소>]

--url이 없으면 데이터 페이지(15084084)의 참고문서 칸에서 fn_fileDownload('FILE_…','n')을 찾아
/cmm/cmm/fileDownload.do?atchFileId=…&fileDetailSn=… 로 받는다(로그인 필요 없음).
다운로드가 잦으면 포털이 보안문자(check-limit.json의 needCaptcha)를 요구하는데, 그때는 멈추고 1로 끝낸다.
"""

import argparse
import html
import http.cookiejar
import io
import re
import sys
import urllib.parse
import urllib.request
import zipfile

PORTAL = "https://www.data.go.kr"
DATASET_PAGE = PORTAL + "/data/15084084/openapi.do"
USER_AGENT = "Mozilla/5.0 (compatible; naurylab-regions-bot; +https://naurylab.com/)"

jar = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))


def fetch(url, data=None):
    body = urllib.parse.urlencode(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers={"User-Agent": USER_AGENT, "Referer": DATASET_PAGE})
    with opener.open(req, timeout=120) as res:
        return res.read(), res.headers


def find_reference_zip(page):
    """참고문서 칸의 (파일 이름, atchFileId, fileDetailSn) 목록."""
    start = page.find("<h3>참고문서</h3>")
    if start < 0:
        raise RuntimeError("데이터 페이지에서 참고문서 칸을 찾지 못했습니다(페이지 모양이 바뀐 듯).")
    section = page[start:start + 20000]
    pattern = re.compile(
        r'<div class="file-name">\s*([^<]+?)\s*</div>.*?fn_fileDownload\(\s*\'([^\']+)\'\s*,\s*\'(\d+)\'\s*\)',
        re.S,
    )
    return [(html.unescape(n), a, s) for n, a, s in pattern.findall(section)]


def zip_name(info):
    # 포털 zip은 이름을 CP949로 넣고 UTF-8 표시(0x800)를 하지 않는다.
    if info.flag_bits & 0x800:
        return info.filename
    try:
        return info.filename.encode("cp437").decode("cp949")
    except UnicodeError:
        return info.filename


def extract_grid_xlsx(data):
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        matches = [i for i in z.infolist() if "위경도" in zip_name(i) and zip_name(i).lower().endswith(".xlsx")]
        if len(matches) != 1:
            names = ", ".join(zip_name(i) for i in z.infolist())
            raise RuntimeError(f"zip 안에서 격자_위경도 xlsx를 하나로 찾지 못했습니다: {names}")
        print(f"꺼낸 파일: {zip_name(matches[0])}")
        return z.read(matches[0])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out_xlsx")
    ap.add_argument("--url", help="참고문서 zip이나 격자_위경도 xlsx 주소(자동으로 못 찾을 때)")
    args = ap.parse_args()

    if args.url:
        data, _ = fetch(args.url)
    else:
        page, _ = fetch(DATASET_PAGE)
        files = find_reference_zip(page.decode("utf-8", "replace"))
        zips = [f for f in files if f[0].lower().endswith(".zip") and "단기예보" in f[0]]
        if len(zips) != 1:
            raise RuntimeError(f"참고문서 zip을 하나로 고르지 못했습니다: {files}")
        name, atch_file_id, detail_sn = zips[0]
        print(f"참고문서: {name} ({atch_file_id}, {detail_sn})")
        limit, _ = fetch(PORTAL + "/cmm/cmm/check-limit.json", {"atchFileId": atch_file_id, "fileDetailSn": detail_sn})
        if b'"needCaptcha":true' in limit.replace(b" ", b""):
            raise RuntimeError("포털이 보안문자를 요구합니다. 나중에 다시 돌리거나 --url로 직접 주세요.")
        query = urllib.parse.urlencode({"atchFileId": atch_file_id, "fileDetailSn": detail_sn})
        data, _ = fetch(PORTAL + "/cmm/cmm/fileDownload.do?" + query)

    if data[:2] != b"PK":
        raise RuntimeError(f"받은 파일이 zip/xlsx가 아닙니다(앞부분: {data[:80]!r}).")
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        is_xlsx = any(i.filename == "[Content_Types].xml" for i in z.infolist())
    xlsx = data if is_xlsx else extract_grid_xlsx(data)
    with open(args.out_xlsx, "wb") as f:
        f.write(xlsx)
    print(f"{args.out_xlsx}: {len(xlsx):,}바이트")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # 워크플로 로그에 이유만 짧게 남긴다.
        print(f"격자_위경도 xlsx를 받지 못했습니다: {e}", file=sys.stderr)
        sys.exit(1)
