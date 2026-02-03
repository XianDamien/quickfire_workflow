## ADDED Requirements

### Requirement: Sync audio annotation SHALL propagate ink
The system SHALL accept gatekeeper `ink` values during synchronous audio annotation and persist them in `4_llm_annotation.json`.

#### Scenario: Audio anomaly ink propagated
- **GIVEN** gatekeeper notes `audio_anomaly`
- **WHEN** synchronous audio annotation completes
- **THEN** output includes `"ink": "audio_anomaly"`
