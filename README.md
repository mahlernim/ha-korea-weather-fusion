# Korea Weather Fusion

[한국어](#한국어) · [English](#english) · [대시보드 예시 / Dashboard](docs/dashboard.md)

[![HACS validation](https://github.com/mahlernim/korea-weather-fusion/actions/workflows/hacs.yml/badge.svg)](https://github.com/mahlernim/korea-weather-fusion/actions/workflows/hacs.yml)
[![Hassfest](https://github.com/mahlernim/korea-weather-fusion/actions/workflows/hassfest.yml/badge.svg)](https://github.com/mahlernim/korea-weather-fusion/actions/workflows/hassfest.yml)
[![Tests](https://github.com/mahlernim/korea-weather-fusion/actions/workflows/tests.yml/badge.svg)](https://github.com/mahlernim/korea-weather-fusion/actions/workflows/tests.yml)

## 한국어

Korea Weather Fusion은 대한민국 날씨와 대기질 정보를 Home Assistant에서 한눈에
볼 수 있도록 기상청, 네이버 날씨, 웨더아이의 정보를 결합하는 사용자 지정
통합 구성요소입니다.

![서울의 시간별 날씨 예보, 미세먼지와 소스 상태를 표시한 Home Assistant 기본 카드](docs/images/overview-ko.png)

서울·강남구를 선택한 실제 화면입니다. 기본 **날씨 예보**·**타일** 카드만
사용하며 별도 프런트엔드 설치는 필요하지 않습니다. 표시 값은 조회 시점에 따라
달라집니다. [같은 구성 만들기](docs/dashboard.md#한국어)

### 주요 기능

| 정보 | 표시 방식 |
| --- | --- |
| 현재 날씨·기온·습도·풍속 | 기본 날씨 엔티티와 개별 센서 |
| 미세먼지·초미세먼지 | 최신성과 우선순위에 따라 선택한 통합 값 |
| 오늘·내일 예보 | 실제 날짜가 있는 최고·최저기온 |
| 시간별 예보 | 네이버의 향후 온도·날씨, 3·6·9·12시간 텍스트 센서 |
| 소스 상태 | 정상 / 이전 데이터 사용 / 일부 데이터 없음 / 사용 가능한 데이터 없음 |

한 소스에 문제가 생겨도 다른 정상 소스를 계속 사용합니다. 이전 정보는 유효
시간 안에서만 사용하며, 웨더아이의 유효한 마지막 정보는 재시작 후에도 유지합니다.

### 요구 사항

- Home Assistant 2026.3.0 이상
- 기상청, 네이버, 웨더아이 웹사이트에 접속할 수 있는 네트워크

API 키나 별도 계정은 필요하지 않습니다.

### 설치

#### HACS 사용자 지정 저장소

1. HACS에서 **사용자 지정 저장소**를 엽니다.
2. `https://github.com/mahlernim/korea-weather-fusion`을 추가하고 유형으로
   **Integration**을 선택합니다.
3. Korea Weather Fusion을 다운로드하고 Home Assistant를 다시 시작합니다.
4. **설정 > 기기 및 서비스 > 통합 구성 요소 추가**에서 **한국 날씨 통합** 또는
   **Korea Weather Fusion**을 검색하세요.

[![Home Assistant에서 통합구성요소 추가](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=weather_fusion)

#### 수동 설치

이 저장소의 `custom_components/weather_fusion` 폴더를 Home Assistant의 같은
경로에 복사한 뒤 Home Assistant를 다시 시작합니다.

#### 기존 사용자 업데이트

HACS에서 업데이트를 다운로드한 뒤 Home Assistant를 다시 시작하세요. 기존
설정과 엔티티 ID는 유지되며 v0.8.0의 날씨·소스 상태 엔티티가 추가됩니다.
통합을 삭제하거나 다시 만들 필요는 없습니다.

### 처음 설정하기

**시·도 → 예보 지역 → 대기 측정소 → 소스 확인 → 저장** 순서로 진행합니다.

1. 시·도를 선택한 뒤 목록에서 모니터링할 예보 지역을 선택합니다.
2. 해당 지역에서 사용할 웨더아이 대기 측정소를 선택합니다. 목록 순서는 실제
   거리 순서를 의미하지 않습니다.
3. 지역 확인 화면에서 기상청 지역, 네이버 검색어, 웨더아이 예보 지역과
   대기 측정소를 확인합니다. 각 소스의 연결·필수 데이터·예보 날짜를 검사합니다.
4. 정상인 경우 저장합니다. 일부 소스에 문제가 있으면 실패한 검사만 다시
   시도하거나 지역을 수정하세요. 사용할 수 있는 데이터가 있으면 누락 항목을
   확인하고 **제한 모드**에 동의한 뒤 저장할 수도 있습니다.

<p><img src="docs/images/setup-ko.png" width="360" alt="시·도 선택 / Province selection"> <img src="docs/images/setup-station-ko.png" width="360" alt="대기 측정소 선택 / Air station selection"></p>

<details>
<summary>저장 전 소스 확인 화면 / Source review before saving</summary>

<img src="docs/images/setup-review-ko.png" width="520" alt="지역별 조회 대상과 소스 검사 결과를 확인하는 Home Assistant 설정 화면">

</details>

지역 코드나 검색어를 직접 찾을 필요는 없습니다. 목록에 없는 지역이나 특별한
설정이 필요한 경우에만 **고급 수동 설정**을 선택해 기존의 세부 식별자를 직접
입력할 수 있습니다.

설치 후에는 통합 항목의 **재구성** 메뉴나 기존 **구성** 메뉴에서 지역을 바꿀 수
있습니다. 저장된 측정소가 기본 선택되며 기존 엔티티 ID는 유지됩니다.
고급 수동 설정에도 동일한 소스 검사가 적용됩니다. 네이버 대기질은 선택
소스이므로 해당 카드가 없어도 나머지 필수 검사가 정상이면 저장할 수 있습니다.

### 제공 엔티티

기본 엔티티에는 통합 기온, 습도, 풍속, 미세먼지, 초미세먼지, 오늘·내일
최고/최저기온, 시간대별 텍스트 예보와 데이터 최신 상태가 포함됩니다. 각
제공처의 원본 값은 진단용으로 함께 제공되며, 일부 상세 대기오염 항목은
기본적으로 비활성화되어 있습니다. 기존 엔티티를 삭제하거나 다시 만들 필요는
없습니다.

날씨 엔티티는 현재 날씨와 오늘·내일 최고/최저기온, 네이버가 제공하는 향후
시간별 예보를 제공합니다. 시간별 온도가 없으면 해당 시간은 생략하고, 확인할
수 없는 날씨 상태는 추정하지 않습니다. 일별 예보에는 최고/최저기온만 포함됩니다.
예보 날짜와 시간은 한국 시간을 기준으로 해석합니다.

소스 상태는 **정상**, **이전 데이터 사용**, **일부 데이터 없음**, **사용 가능한 데이터 없음**으로
표시됩니다. 이전 데이터도 유효 시간 내에서만 사용합니다. 상태 엔티티의 속성에서
누락된 관측값과 텍스트 예보를 확인할 수 있습니다.

[기본 카드로 대시보드 만들기](docs/dashboard.md#한국어)를 참고하세요.

### 문제 해결

- 설정 중 오류가 표시되면 지역을 확인하거나 소스 검사를 다시 시도하세요.
  제한 모드에서는 정상 데이터만 제공하며, 소스가 복구되면 자동으로 사용합니다.
  사용할 수 있는 데이터가 전혀 없으면 저장할 수 없습니다.
- 값이 `사용할 수 없음`이면 인터넷 연결과 선택한 지역을 확인하세요.
- 한 제공처의 값만 없으면 해당 제공처의 지역 페이지에서 같은 정보가 보이는지
  확인하세요.
- 네이버가 일부 지역 검색에서 미세먼지 카드를 제공하지 않을 수 있습니다. 이
  경우에도 기상청과 웨더아이 대기질을 이용한 통합 값은 계속 제공됩니다.
- 지역 설정을 수정한 뒤에는 통합구성요소가 자동으로 다시 로드됩니다.
- 웹 제공처의 화면 구조가 바뀌면 일부 값이 일시적으로 제공되지 않을 수
  있습니다. 지속되는 문제는 GitHub Issues에 보고해 주세요.
- 통합 항목에서 진단 정보를 내려받아 문제 보고에 첨부할 수 있습니다. 진단
  파일에는 소스 상태·시간·누락 항목을 포함하고 검색어·정확한 지역·원본 HTML은
  포함하지 않습니다. 문제 보고는 한국어와 영어 모두 가능합니다.

### 개인정보와 한계

Korea Weather Fusion은 입력한 검색어와 지역 식별자를 각 날씨 제공처에 직접
전송합니다. 별도의 중계 서버나 계정 로그인을 사용하지 않습니다. 이 프로젝트는
기상청, 네이버 또는 웨더아이의 공식 제품이 아니며 각 제공처와 제휴하지
않습니다. 제공처 웹페이지의 변경이나 이용 제한에 따라 기능이 달라질 수
있습니다.

---

## English

Korea Weather Fusion is a Home Assistant custom integration for Korean weather and
air quality. It combines data from KMA (`weather.go.kr`), Naver Weather, and
Weatheri into a practical set of everyday entities.

The screenshot above shows real Seoul/Gangnam data using built-in weather and tile
cards. No custom frontend is required. Readings vary with the query time.

### Features

- Combines fresh current temperature, humidity, and wind observations.
- Selects air quality and daily highs/lows using freshness-aware priorities.
- Provides Naver text forecasts for 3, 6, 9, and 12 hours ahead.
- Adds a native weather entity with dated daily and hourly forecasts for standard
  Home Assistant weather cards.
- Exposes source-specific KMA, Naver, and Weatheri diagnostics.
- Keeps healthy sources usable when another source temporarily fails.
- Retains valid Weatheri data across Home Assistant restarts.
- Offers province, forecast-area and air-station dropdowns, then previews actual
  source locations and checks before saving. Air-station changes preserve the
  selected weather area.

### Requirements

- Home Assistant 2026.3.0 or newer
- Network access to KMA, Naver, and Weatheri websites

No API key or separate account is required.

### Installation

#### HACS custom repository

1. Open **Custom repositories** in HACS.
2. Add `https://github.com/mahlernim/korea-weather-fusion` as an **Integration**.
3. Download Korea Weather Fusion and restart Home Assistant.
4. Go to **Settings > Devices & services > Add integration > Korea Weather Fusion**.

[![Add integration to Home Assistant](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=weather_fusion)

#### Manual installation

Copy `custom_components/weather_fusion` from this repository to the same path
under your Home Assistant configuration directory, then restart Home Assistant.

#### Upgrading

Download the update in HACS and restart Home Assistant. Existing settings and
entity IDs remain; v0.8.0 adds weather and source-status entities. There is no need
to delete or recreate the integration.

### First-time setup

1. Choose a province and forecast area, then a Weatheri air-quality station.
   Station ordering is not a distance ranking.
2. Review the KMA area, Naver query, Weatheri forecast area and air station. The
   integration checks required data, forecast dates and air-quality freshness.
3. Save when ready. If a source fails, retry failed checks or edit the location.
   You can explicitly accept limited mode when some usable data remains; missing
   sources return automatically when they recover.

No location codes or search queries are normally required. Naver air is optional;
its missing card does not prevent saving when the other required checks pass.

Choose **Advanced manual setup** only for an unsupported location or a special
configuration that needs explicit provider selectors. Manual setup uses the same
live validation and review screen.

You can later change them from **Settings > Devices & services > Korea Weather Fusion
> Configure**, or use the integration entry's **Reconfigure** menu. The saved
station remains selected, and existing entity IDs stay stable.

### Weather cards and source status

The native weather entity provides current weather, today's and tomorrow's
high/low temperatures, and available future Naver hourly forecasts. Missing hourly
temperatures are omitted; unknown conditions are never guessed. Daily forecasts
contain high/low temperatures only. Provider dates and times are interpreted in
Korea time, including when Home Assistant uses another timezone.

The source-status sensor distinguishes fresh data, valid cached data, degraded
coverage and unavailable data. Its attributes list missing observations and text
forecasts. Existing sensors remain available for dashboards and automations;
there is no need to recreate them.

See the [dashboard example using built-in cards](docs/dashboard.md#english).

### Troubleshooting

- If setup reports an error, check the location or retry failed checks. Limited
  mode requires explicit acceptance and at least some usable data.
- If values are unavailable later, check network access and the selected location.
- If only one source is missing, confirm that source's public location page
  still shows the requested information.
- Naver does not expose its PM card for every local search. KMA and Weatheri air
  quality remain available to the fused entities when that happens.
- Source websites can change their page structure or temporarily limit access.
  Report persistent problems through GitHub Issues.
- Download integration diagnostics for a bug report. They include source status,
  timestamps and missing fields, but omit queries, precise locations and raw HTML.
  Reports in Korean or English are welcome.

### Privacy and limitations

Korea Weather Fusion sends the configured queries and location identifiers directly
to the three weather providers. It uses no relay server and requires no account
login. This independent project is not affiliated with KMA, Naver, or Weatheri.
Availability may change when a provider changes its public website or access
policy.

## License

[MIT](LICENSE)
