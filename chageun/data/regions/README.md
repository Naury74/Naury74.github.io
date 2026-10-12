# 차근 날씨 지역 목록

차근 앱 홈 날씨의 "지역 직접 고르기"에 쓰는 전국 행정구역(시·도 → 시·군·구 → 읍·면·동)과 대표 좌표다.
앱 안에도 같은 목록이 들어 있고, 앱은 여기 올린 파일로 앱 업데이트 없이 새 목록을 받는다.

- https://naurylab.com/chageun/data/regions/regions.json
- https://naurylab.com/chageun/data/regions/regions-2026-07.csv

## 파일

### `regions.json`

지금 쓸 목록을 가리킨다. 앱은 이 파일만 확인하고, `version`이 가진 것보다 크면 `file`을 받는다.

```json
{
  "schema": 1,
  "version": "2026-07",
  "file": "regions-2026-07.csv",
  "sha256": "7b8f9ae4738af5459292c8d367261f755a7738506bbbcb9cde44ee84a09ef813",
  "rows": 3836,
  "source": "기상청 단기예보 조회서비스 격자·위경도 (공공데이터포털 15084084), 2026-07-01, 저작자표시",
  "renamedCodes": {}
}
```

| 칸 | 뜻 |
| --- | --- |
| `schema` | 이 JSON 모양의 판. 모양을 바꾸면 올린다. 앱은 모르는 판이면 무시한다. |
| `version` | 원본 시트 날짜의 `YYYY-MM`. 글자 순서로 비교한다. |
| `file` | 같은 폴더의 CSV 이름(`regions-<version>.csv`). |
| `sha256` | CSV 파일 바이트 전체의 sha256(소문자 16진수). 앱은 받은 파일과 맞지 않으면 버린다. |
| `rows` | `#`로 시작하지 않는 데이터 줄 수. |
| `source` | 출처 표시 문구. |
| `renamedCodes` | 없어진 옛 코드 → 이어 쓸 새 코드. 버전이 바뀌어도 예전 연결을 남기고, 값은 늘 최신 목록에 있는 코드다. 여기 없는 옛 코드는 앱이 위 단계(시·군·구, 시·도)로 거슬러 올라가 보여 준다. |

### `regions-<version>.csv`

UTF-8, 줄 끝 `\n`. `#`로 시작하는 줄은 주석(원본 시트 이름과 xlsx sha256)이고, 나머지는 `code,name,lat,lon[,short]`이다.

- `code`: 행정구역코드 10자리. 부모는 코드로 정한다(읍·면·동 → 앞 5자리+`00000`, 시·군·구 → 앞 2자리+`00000000`).
- `name`: 그 단계 이름. 원본 그대로다(`수원시장안구`).
- `lat`, `lon`: 대표 좌표, 소수 넷째 자리.
- `short`: 시·도 줄에만 있는 짧은 이름(`서울`).

한 번 올린 CSV는 고치거나 지우지 않는다. 새 목록은 새 이름(새 `version`)으로 올리고 `regions.json`만 바꾼다.

## 출처와 이용허락

- 제공: 기상청
- 원본: 공공데이터포털 [기상청_단기예보 ((구)_동네예보) 조회서비스](https://www.data.go.kr/data/15084084/openapi.do)(15084084)
  참고문서 zip 안의 `…격자_위경도(YYMM).xlsx`
- 이용허락범위: 저작자표시. 2026-07 목록은 `기상청41_단기예보 조회서비스_오픈API활용가이드_2609.zip` 안의
  `…격자_위경도(2607).xlsx`(시트 `최종 업데이트 파일_20260701`, sha256 `746b5e5b…a003c1`)로 만들었다.
- 바꾼 것: 행정구역코드·이름·위도·경도만 남기고 좌표를 소수 넷째 자리로 줄였다. 시·도 짧은 이름을 붙였고, 좌표가 0인 이어도 두 줄을 뺐다.

## 갱신

`.github/workflows/update-chageun-regions.yml`이 매달 2일 03:00(KST)에 돈다.

1. `tools/regions/fetch_kma_grid.py`: 데이터 페이지의 참고문서 칸에서 zip 다운로드 주소
   (`/cmm/cmm/fileDownload.do?atchFileId=…&fileDetailSn=…`)를 찾아 받고, 격자_위경도 xlsx를 꺼낸다. 로그인은 필요 없다.
2. `tools/regions/build-korea-regions.py`: xlsx를 CSV로 바꾼다(앱 저장소 `scripts/build-korea-regions.py`와 같은 파일).
3. `tools/regions/update_regions.py`: 지금 올라가 있는 CSV와 데이터 줄을 비교한다. 같으면 조용히 끝난다.
   다르면 검사(데이터 3,000줄 넘음, 좌표 위도 33–39·경도 124–132, 코드 중복 없음, 모든 시·군·구와 읍·면·동에 부모 있음)를
   거쳐 새 CSV와 `regions.json`을 쓰고 바뀐 내용을 요약한다. 검사에 걸리면 실패로 끝난다.
4. 바뀐 게 있으면 `chageun-regions/<version>` 브랜치로 "차근 지역 목록 <version> 갱신" PR을 연다. 사람이 요약을 보고 합친다.

`renamedCodes`는 없어진 옛 코드마다 새로 생긴 같은 단계 코드 중 전체 이름(시·도 시·군·구 읍·면·동)이 같은 곳이 하나뿐이면,
아니면 대표 좌표가 200m 안인 곳이 하나뿐이면 잇는다.

### 손으로 돌리기

자동 다운로드가 막히면(페이지 모양이 바뀌었거나 포털이 보안문자를 요구할 때) 공공데이터포털 페이지의 참고문서를 받아
xlsx를 꺼낸 뒤 아래처럼 돌린다. Actions 탭에서 "차근 지역 목록 갱신"을 수동 실행하며 `xlsx_url`에 zip이나 xlsx 주소를 줘도 된다.

```sh
pip install openpyxl
python3 tools/regions/fetch_kma_grid.py /tmp/grid.xlsx            # 또는 직접 받은 xlsx를 쓴다
python3 tools/regions/build-korea-regions.py /tmp/grid.xlsx > /tmp/new.csv
python3 tools/regions/update_regions.py /tmp/new.csv               # 저장소 루트에서
```

새 시·도가 생기면 `build-korea-regions.py`가 짧은 이름을 몰라 멈춘다. 그때는 `SHORT_NAMES`에 더하고 앱 저장소의 같은 스크립트도 고친다.
원본 시트 날짜가 그대로인데 데이터만 바뀌었으면 `update_regions.py`가 멈추니 `--version`으로 다음 버전을 준다.
