# Korea Weather Fusion 0.7.0

## 한국어

지역 코드와 검색어를 직접 찾지 않아도 되는 새로운 안내식 설정을 추가했습니다.

- 172개 한국 예보 지역을 검색 가능한 목록에서 선택할 수 있습니다.
- 선택한 지역에서 사용할 수 있는 웨더아이 대기 측정소만 표시합니다.
- 측정소 선택을 이용해 기상청 지역과 네이버 날씨·대기질 검색 지역을 더
  구체적으로 맞춥니다.
- 설정을 저장하기 전에 기상청, 네이버, 웨더아이의 필수 응답을 확인합니다.
- 기존 사용자는 지역 식별자와 엔티티 ID를 그대로 유지하며 업데이트할 수
  있습니다.
- 목록에 없는 지역을 위한 고급 수동 설정도 계속 제공합니다.

네이버는 일부 지역 검색에서 미세먼지 카드를 제공하지 않을 수 있습니다. 이
경우에도 기상청과 웨더아이 대기질을 이용한 통합 값은 계속 제공됩니다.

Home Assistant 2026.3.0 이상이 필요합니다. 업데이트 후 기존 설정을 다시 만들
필요는 없습니다. 지역을 바꾸려면 통합구성요소의 **구성**을 선택하세요.

## English

This release adds guided setup without requiring users to find provider codes or
construct search queries manually.

- Choose from 172 searchable Korean forecast locations.
- See only the Weatheri air stations available for the selected area.
- Use the station choice to refine the KMA area and Naver weather and air queries.
- Validate required live responses from KMA, Naver, and Weatheri before saving.
- Upgrade existing installations without changing provider selectors or entity IDs.
- Keep Advanced manual setup for unsupported or specialized locations.

Naver does not expose its PM card for every local search. KMA and Weatheri air
quality remain available to the fused entities when that happens.

Home Assistant 2026.3.0 or newer is required. Existing users do not need to
recreate the integration after updating. Use **Configure** to change location.
