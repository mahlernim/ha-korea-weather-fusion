# Weather Fusion 0.6.0

## 한국어

기상청, 네이버 날씨, 웨더아이의 날씨·대기질 정보를 하나의 Home
Assistant 통합구성요소에서 확인할 수 있는 첫 공개 준비 버전입니다.

- 현재 기온·습도·풍속은 사용할 수 있는 최신 소스를 결합합니다.
- 미세먼지와 일 최고·최저기온은 우선순위와 최신성 기준으로 선택합니다.
- 각 원본 소스의 진단 엔티티를 제공하여 값을 비교할 수 있습니다.
- 일시적인 통신 실패에는 마지막 정상 값을 유효 시간 동안 유지합니다.
- 모든 지역 식별자는 설정 화면에서 입력하고 나중에 변경할 수 있습니다.

Home Assistant 2026.3.0 이상이 필요합니다. 처음 설치한 뒤
**설정 > 기기 및 서비스 > 통합구성요소 추가**에서 Weather Fusion을
추가하고 각 서비스의 지역 식별자를 입력하세요.

## English

This is the first public-ready version of Weather Fusion, combining Korean
weather and air-quality data from KMA, Naver Weather, and Weatheri in one Home
Assistant integration.

- Current temperature, humidity, and wind combine available fresh sources.
- Air quality and daily highs/lows use freshness-aware source priorities.
- Source-specific diagnostic entities make comparisons and troubleshooting easy.
- Temporary connection failures retain the last valid value within its freshness window.
- All location selectors are entered and maintained through the integration UI.

Home Assistant 2026.3.0 or newer is required. After installation, add Weather
Fusion from **Settings > Devices & services > Add integration** and enter the
location selectors requested for each service.
