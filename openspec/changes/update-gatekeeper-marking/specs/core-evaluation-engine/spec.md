## MODIFIED Requirements

### Requirement: System SHALL Return Structured Evaluation Report

All evaluations SHALL return a consistent JSON structure suitable for parsing and downstream processing.

**Required Fields**:
- `final_grade_suggestion` (string): A/B/C grade
- `mistake_count` (object): Count of each error type
  ```json
  {
    "MEANING_ERROR": int,
    "NO_ANSWER": int
  }
  ```
- `annotations` (array): List of errors with explanations
  ```json
  [
    {
      "error_type": "PRONUNCIATION_ERROR",
      "content": "Description of the error",
      "timestamp": 1200
    }
  ]
  ```
- `ink` (string): Anomaly note for teacher review
  - `normal` (no anomaly)
  - `wrong_questionbank` (question bank mismatch)
  - `audio_anomaly` (missing/abnormal audio)

**Schema Validation**:
- All fields mandatory
- `timestamp` in annotations should correlate to ASR word_timestamp when available
- `content` should be user-readable in English
- `ink` is not used for grading, only for anomaly highlighting

#### Scenario: Ink wrong question bank
- **GIVEN** anomaly check notes `wrong_questionbank`
- **WHEN** evaluation result is finalized
- **THEN** output includes `"ink": "wrong_questionbank"`

#### Scenario: Ink normal when no note
- **GIVEN** anomaly check reports no note
- **WHEN** evaluation result is finalized
- **THEN** output includes `"ink": "normal"`
