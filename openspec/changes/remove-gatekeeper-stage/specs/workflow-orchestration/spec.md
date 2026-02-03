## REMOVED Requirements

### ~~System SHALL run anomaly noting without blocking annotation~~ (REMOVED)

**Removed in**: remove-gatekeeper-stage
**Reason**: Gatekeeper is removed from the primary pipeline to simplify flow and avoid passing anomaly fields into annotators/models.

**Migration Path**:
- If anomaly notes are still desired, attach a static string/metadata after annotation (no model input), or run a separate offline check.

## ADDED Requirements

### Requirement: Pipeline SHALL exclude gatekeeper by default
The main pipeline SHALL execute `audio → qwen_asr → cards` without gatekeeper as a required stage.

#### Scenario: Main pipeline runs without gatekeeper
- **WHEN** the user runs the default pipeline to `cards`
- **THEN** gatekeeper is not invoked and cards still complete

### Requirement: Gatekeeper SHALL be runnable as a standalone flow
Gatekeeper SHALL be available as an optional standalone flow that does not gate or block the main pipeline.

#### Scenario: User runs gatekeeper independently
- **WHEN** the user invokes the standalone gatekeeper flow
- **THEN** anomaly notes are produced without triggering annotation
