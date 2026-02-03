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

**Schema Validation**:
- All fields mandatory
- `timestamp` in annotations should correlate to ASR word_timestamp when available
- `content` should be user-readable in English

#### Scenario: Output excludes ink
- **GIVEN** any evaluation completes
- **WHEN** the result is finalized
- **THEN** output includes the required fields only
- **AND** output does not include an `ink` field
