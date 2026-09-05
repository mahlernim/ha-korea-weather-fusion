# Korea Weather Fusion 0.8.0

## 한국어

Home Assistant 기본 날씨 카드에서 현재 날씨와 시간별·일별 예보를 볼 수 있습니다.
지역 설정은 시·도부터 단계별로 선택하고, 실제 조회 지역과 소스 검사 결과를
확인한 뒤 저장하도록 개선했습니다.

![기본 날씨 카드와 대기질·소스 상태](https://raw.githubusercontent.com/mahlernim/ha-korea-weather-fusion/v0.8.0/docs/images/overview-ko.png)

- **날씨 카드와 소스 상태:** 기본 `weather` 엔티티와 소스 상태 센서를 추가했습니다.
  기존 센서와 엔티티 ID는 유지합니다.
- **설정·재구성:** 대기 측정소를 바꿔도 날씨 지역을 유지합니다. 실패한 소스만
  다시 검사하고, 일부 데이터만 사용할 때는 제한 모드에 명시적으로 동의합니다.
  네이버 대기질은 선택 항목이므로 해당 카드가 없어도 나머지 정상 데이터를
  사용할 수 있습니다. Home Assistant의 서비스 통합 분류도 바로잡았습니다.
- **예보 정확성·복구:** 실제 한국 날짜와 시간을 유지해 오래된 ‘오늘/내일’ 예보가
  현재 값으로 선택되는 문제를 수정했습니다. 빈 표 셀·소수 기온·일부 오염물질
  누락 처리와 재시도·종료 시 정리를 개선했습니다.
- **문서:** 한국어 중심 안내와 영어 설명, 실제 설정 화면, 기본 카드 YAML 예시를
  포함했습니다. [설정 스크린샷과 사용법](https://github.com/mahlernim/ha-korea-weather-fusion/tree/v0.8.0#한국어)

**업데이트:** Home Assistant **2026.3.0 이상**이 필요합니다. HACS에서 업데이트를
다운로드한 뒤 Home Assistant를 다시 시작하세요. 통합을 삭제하거나 다시 만들
필요는 없습니다. 지역 변경은 통합 항목의 **재구성** 또는 **구성**에서 진행합니다.

일별 예보는 오늘·내일 최고/최저기온을 제공합니다. 시간별 온도가 없으면 해당
시간은 생략하며 확인할 수 없는 날씨 상태는 추정하지 않습니다.

## English

Use native Home Assistant weather cards for current weather and dated hourly/daily
forecasts. Guided setup now walks through province, forecast area and air station,
then reviews actual source locations and live checks before saving.

- Adds a native `weather` entity and source-status sensor while preserving existing
  sensors and entity IDs.
- Preserves the weather area when changing air stations, retries failed checks and
  requires explicit limited-mode acceptance when required data is missing. Naver
  air remains optional. Corrects the integration's Home Assistant service category.
- Retains actual Korean forecast dates and times so stale relative-day values do
  not override current forecasts. Improves empty-cell, decimal-temperature and
  partial-pollutant parsing, retry handling and shutdown cleanup.
- Includes Korean-first documentation, equivalent English guidance, real setup
  screenshots and a dashboard example using only built-in cards.

**Upgrade:** Requires Home Assistant **2026.3.0+**. Download the update in HACS and
restart Home Assistant. Do not recreate the integration; settings and entity IDs
remain. Use **Reconfigure** or **Configure** to change location.

Daily forecasts contain today's and tomorrow's high/low temperatures only. Hourly
entries without a temperature are omitted, and unknown conditions are not guessed.

**Validation / 검증:** 55 tests on each of Home Assistant 2026.3.0 and 2026.9.0,
Ruff, HACS validation and Hassfest. Screenshots show a real Seoul/Gangnam example
in Home Assistant 2026.9.0; provider readings vary over time.
