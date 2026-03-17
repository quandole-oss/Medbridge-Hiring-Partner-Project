# AI Health Coach — TODO

## Streaming Chat Responses

- [x] Extract `_run_chat_pipeline()` shared helper from `chat()` endpoint
- [x] Add `POST /chat/stream` SSE endpoint (meta → token → done events)
- [x] Add `api.sendMessageStream()` with ReadableStream SSE parser + AbortController support
- [x] Add `addStreamingMessage()` for incremental DOM rendering
- [x] Update `sendGreeting()`, `handleSend()`, `handleDrawerSend()` to use streaming
- [x] Typing indicator hides on `onMeta`, input re-enables immediately

## Adaptive Patient Memory

- [x] PatientInsight DB model with confidence, category, reinforcement tracking
- [x] Repository functions: get, upsert, decay insights
- [x] `get_patient_insights` retrieval tool (follows get_adherence_summary pattern)
- [x] `extract_insights` graph node (Haiku-powered, post-safety extraction)
- [x] Graph wiring: check_goal_extraction → extract_insights → END
- [x] Prompt integration: {patient_insights} in onboarding, active, re_engaging prompts
- [x] Phase node changes: all 3 nodes call insights tool and inject into prompts
- [x] Tests: 10 new tests (repository, node, topology)
