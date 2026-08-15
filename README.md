# Korea Weather Fusion

[![HACS validation](https://github.com/mahlernim/korea-weather-fusion/actions/workflows/hacs.yml/badge.svg)](https://github.com/mahlernim/korea-weather-fusion/actions/workflows/hacs.yml)
[![Hassfest](https://github.com/mahlernim/korea-weather-fusion/actions/workflows/hassfest.yml/badge.svg)](https://github.com/mahlernim/korea-weather-fusion/actions/workflows/hassfest.yml)
[![Tests](https://github.com/mahlernim/korea-weather-fusion/actions/workflows/tests.yml/badge.svg)](https://github.com/mahlernim/korea-weather-fusion/actions/workflows/tests.yml)

## 한국어

Korea Weather Fusion은 대한민국 날씨와 대기질 정보를 Home Assistant에서 한눈에
볼 수 있도록 기상청, 네이버 날씨, 웨더아이의 정보를 결합하는 사용자 지정
통합구성요소입니다.

![Korea Weather Fusion 날씨 요약 예시](docs/images/overview-ko.png)

### 주요 기능

- 현재 기온·습도·풍속은 사용할 수 있는 최신 소스를 결합합니다.
- 미세먼지와 오늘·내일 최고/최저기온은 최신성과 우선순위에 따라 선택합니다.
- 3·6·9·12시간 후의 네이버 날씨 예보를 제공합니다.
- 기상청, 네이버, 웨더아이 원본 값을 별도 진단 엔티티로 확인할 수 있습니다.
- 한 소스에 일시적인 문제가 생겨도 다른 정상 소스의 값은 계속 사용합니다.
- 웨더아이의 마지막 정상 정보는 Home Assistant 재시작 후에도 유효 시간 동안
  사용할 수 있습니다.
- 한국 예보 지역과 가까운 대기 측정소를 목록에서 선택하면 세 소스의 설정을
  자동으로 찾고 확인합니다.

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
4. **설정 > 기기 및 서비스 > 통합구성요소 추가 > Korea Weather Fusion**을
   선택합니다.

[![Home Assistant에서 통합구성요소 추가](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=weather_fusion)

#### 수동 설치

이 저장소의 `custom_components/weather_fusion` 폴더를 Home Assistant의 같은
경로에 복사한 뒤 Home Assistant를 다시 시작합니다.

### 처음 설정하기

![Korea Weather Fusion 설정 예시](docs/images/setup-ko.png)

1. 목록에서 모니터링할 한국 예보 지역을 선택합니다.
2. 해당 지역에서 사용할 수 있는 웨더아이 대기 측정소를 선택합니다.
3. 통합구성요소가 기상청 지역, 네이버 검색 지역, 웨더아이 예보와 대기질을
   자동으로 연결하고 필수 응답을 확인한 뒤 설정을 저장합니다.

지역 코드나 검색어를 직접 찾을 필요는 없습니다. 목록에 없는 지역이나 특별한
설정이 필요한 경우에만 **고급 수동 설정**을 선택해 기존의 세부 식별자를 직접
입력할 수 있습니다.

설치 후 지역을 바꾸려면 **설정 > 기기 및 서비스 > Korea Weather Fusion > 구성**을
선택합니다. 지역을 변경해도 기존 Korea Weather Fusion 엔티티 ID는 유지됩니다.

### 제공 엔티티

기본 엔티티에는 통합 기온, 습도, 풍속, 미세먼지, 초미세먼지, 오늘·내일
최고/최저기온, 시간대별 텍스트 예보와 데이터 최신 상태가 포함됩니다. 각
제공처의 원본 값은 진단용으로 함께 제공되며, 일부 상세 대기오염 항목은
기본적으로 비활성화되어 있습니다.

### 문제 해결

- 설정 중 오류가 표시되면 해당 제공처가 일시적으로 응답하지 않는지 확인한 뒤
  다시 시도하세요. 불완전한 설정은 저장되지 않습니다.
- 값이 `사용할 수 없음`이면 인터넷 연결과 선택한 지역을 확인하세요.
- 한 제공처의 값만 없으면 해당 제공처의 지역 페이지에서 같은 정보가 보이는지
  확인하세요.
- 네이버가 일부 지역 검색에서 미세먼지 카드를 제공하지 않을 수 있습니다. 이
  경우에도 기상청과 웨더아이 대기질을 이용한 통합 값은 계속 제공됩니다.
- 지역 설정을 수정한 뒤에는 통합구성요소가 자동으로 다시 로드됩니다.
- 웹 제공처의 화면 구조가 바뀌면 일부 값이 일시적으로 제공되지 않을 수
  있습니다. 지속되는 문제는 GitHub Issues에 보고해 주세요.

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

![Korea Weather Fusion overview example](docs/images/overview-ko.png)

### Features

- Combines fresh current temperature, humidity, and wind observations.
- Selects air quality and daily highs/lows using freshness-aware priorities.
- Provides Naver text forecasts for 3, 6, 9, and 12 hours ahead.
- Exposes source-specific KMA, Naver, and Weatheri diagnostics.
- Keeps healthy sources usable when another source temporarily fails.
- Retains valid Weatheri data across Home Assistant restarts.
- Offers guided Korean location and nearby air-station dropdowns, then resolves
  and validates all three providers automatically.

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

### First-time setup

![Korea Weather Fusion setup example](docs/images/setup-ko.png)

Choose a Korean forecast location, then choose a nearby Weatheri air-quality
station. The integration automatically resolves the KMA area and Naver queries,
checks the required live responses from all three providers, and saves the setup
only when it is usable. No location codes or search queries are normally required.

Choose **Advanced manual setup** only for an unsupported location or a special
configuration that needs explicit provider selectors.

You can later change them from **Settings > Devices & services > Korea Weather Fusion
> Configure**. Existing Korea Weather Fusion entity IDs remain stable.

### Troubleshooting

- If setup reports an error, retry after checking whether the named provider is
  temporarily unavailable. An incomplete setup is not saved.
- If values are unavailable later, check network access and the selected location.
- If only one source is missing, confirm that source's public location page
  still shows the requested information.
- Naver does not expose its PM card for every local search. KMA and Weatheri air
  quality remain available to the fused entities when that happens.
- Source websites can change their page structure or temporarily limit access.
  Report persistent problems through GitHub Issues.

### Privacy and limitations

Korea Weather Fusion sends the configured queries and location identifiers directly
to the three weather providers. It uses no relay server and requires no account
login. This independent project is not affiliated with KMA, Naver, or Weatheri.
Availability may change when a provider changes its public website or access
policy.

## License

[MIT](LICENSE)
