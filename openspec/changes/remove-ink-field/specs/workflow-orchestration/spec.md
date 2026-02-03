## REMOVED Requirements

### Requirement: ~~System SHALL Run Anomaly Noting Without Blocking Annotation~~ (REMOVED)

**Removed in**: remove-ink-field
**Reason**: Anomaly notes are no longer merged into annotation outputs because the `ink` field is removed.

**Migration Path**:
- If anomaly checks are still required, run gatekeeper as a standalone check without writing `ink` to annotation outputs.

#### Scenario: Pipeline does not merge anomaly notes
- **GIVEN** an optional anomaly check runs
- **WHEN** annotation output is finalized
- **THEN** no `ink` field is merged into the output
