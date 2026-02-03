## 1. Implementation
- [ ] 1.1 Update gemini-audio `run_archive_student` signature to accept `ink` and pass it into `AnnotatorInput`/`AnnotatorOutput`.
- [ ] 1.2 Add `ink` to the gemini-audio `4_llm_annotation.json` payload.
- [ ] 1.3 Manual test: run a real-audio batch with gatekeeper anomalies and confirm output includes the expected `ink` value.
