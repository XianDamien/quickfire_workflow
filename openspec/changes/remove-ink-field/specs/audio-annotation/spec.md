## REMOVED Requirements

### Requirement: ~~Sync audio annotation SHALL propagate ink~~ (REMOVED)

**Removed in**: remove-ink-field
**Reason**: Ink marking is removed from evaluation outputs and is no longer propagated by audio annotation.

**Migration Path**:
- No migration required; audio annotation outputs no longer include `ink`.

#### Scenario: Audio annotation does not emit ink
- **GIVEN** synchronous audio annotation completes
- **WHEN** output JSON is written
- **THEN** the output does not include an `ink` field
