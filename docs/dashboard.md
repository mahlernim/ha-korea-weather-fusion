# Dashboard example

[한국어](#한국어) · [English](#english)

[Home Assistant weather-card reference](https://www.home-assistant.io/dashboards/weather-forecast/)

![기본 날씨·대기질 카드 / Built-in weather and air-quality cards](images/overview-ko.png)

## 한국어

대시보드 편집 화면에서 **날씨 예보** 카드를 추가하고 Korea Weather Fusion의
날씨 엔티티를 선택하세요. 일별 예보는 오늘·내일 최고/최저기온을, 시간별 예보는
제공된 시간의 온도와 날씨 상태를 표시합니다. 예보가 없으면 원본 소스와 소스
상태를 확인하세요.

카드 아래에 통합 미세먼지·초미세먼지 센서와 소스 상태 센서를 타일 또는 엔티티
카드로 배치하면 일상적으로 필요한 정보를 한 화면에서 볼 수 있습니다. 원본
제공처 센서는 별도 진단 화면에 두는 구성을 권장합니다.

스크린샷처럼 카드 하나로 묶으려면 **수동** 카드에 아래 YAML을 붙여 넣으세요.
각 `entity`를 실제 엔티티 ID로 바꾸세요. 표시 이름은 원하는 지역명으로 바꿀 수
있습니다.

```yaml
type: vertical-stack
cards:
  - type: weather-forecast
    entity: weather.example
    name: 서울
    show_current: true
    show_forecast: true
    forecast_type: hourly
  - type: horizontal-stack
    cards:
      - type: tile
        entity: sensor.example_pm10
        name: 미세먼지 PM10
      - type: tile
        entity: sensor.example_pm25
        name: 초미세먼지 PM2.5
  - type: tile
    entity: sensor.example_source_status
    name: 소스 상태
```

아래는 기본 날씨 카드의 YAML 예시입니다. `weather.example`을 실제 날씨 엔티티
ID로 바꾸세요. 사용자 지정 카드나 추가 프런트엔드 설치는 필요하지 않습니다.

```yaml
type: weather-forecast
entity: weather.example
show_current: true
show_forecast: true
forecast_type: hourly
```

일별 범위를 표시하려면 `forecast_type: daily`로 바꾸세요. 한국의 예보 시간은
Home Assistant 화면에서 사용자의 현지 시간으로 표시될 수 있습니다.

## English

Add a **Weather forecast** card in the dashboard editor and select the Korea
Weather Fusion weather entity. Daily forecasts show today's and tomorrow's
high/low temperatures; hourly forecasts show available temperatures and
conditions. Check source status when forecasts are missing.

Place the fused PM10, PM2.5 and source-status sensors underneath using tile or
entities cards. Keep provider-specific sensors in a separate diagnostic view.

The YAML above uses a built-in card. Replace `weather.example` with your weather
entity ID; no custom frontend is required. Set `forecast_type: daily` to show the
daily range. Korea forecast times may display in the viewer's local timezone.

To reproduce the screenshot, paste the first `vertical-stack` example into a
**Manual** card. Replace every `entity` with the corresponding weather, PM10,
PM2.5 and source-status entity ID. Change the display names to your preferred
language and location.
