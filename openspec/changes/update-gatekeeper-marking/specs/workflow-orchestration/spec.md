## ADDED Requirements

### Requirement: System SHALL Run Anomaly Noting Without Blocking Annotation

The system SHALL run anomaly noting as a non-blocking check. Annotation MUST proceed regardless of anomaly results, and any available anomaly note SHALL be merged into the annotation output `ink` field.

#### Scenario: Gatekeeper notes audio anomaly
- **GIVEN** anomaly check notes `audio_anomaly`
- **WHEN** the annotation pipeline runs for a student
- **THEN** annotation completes and output includes `"ink": "audio_anomaly"`
