# AI Health Coach — TODO

## AI-Powered Clinician Dashboard

- [x] `app/db/models.py` — `ClinicianPatientSummary` + `CaseloadBriefing` cache models
- [x] `app/db/repository.py` — cache get/save functions for summaries and briefings
- [x] `app/services/risk_scoring.py` — pure `compute_risk_score()` with 7 weighted signals
- [x] `app/services/clinician_ai.py` — `generate_patient_summary()` + `generate_caseload_briefing()` with Haiku
- [x] `app/graph/prompts.py` — 3 clinician AI prompts (summary, risk explanation, caseload)
- [x] `app/api/schemas.py` — `PatientAISummaryResponse` + `CaseloadBriefingResponse`
- [x] `app/api/clinician_routes.py` — 2 new endpoints (ai-summary, caseload-briefing)
- [x] `app/static/clinician.html` — Caseload panel, risk badges on patient table, AI summary in drawer
- [x] `tests/test_api/test_clinician_ai.py` — 16 tests (risk scoring + endpoints, 126 total)

## Gamification / Badge & Achievement System

- [x] `app/services/badges.py` — badge catalog + pure `compute_badges()` function
- [x] `app/db/repository.py` — `get_completed_goal_count()` for goal-based badges
- [x] `app/api/schemas.py` — `BadgeItem` model, extend `AdherenceResponse` with `badges` + `completed_goal_count`
- [x] `app/api/routes.py` — wire badges into adherence endpoint
- [x] `app/static/index.html` — achievements CSS (scroll, glow, confetti, toast), badge rendering, celebration JS
- [x] `app/services/daily_briefing.py` — add earned badge names to LLM context
- [x] 15 tests: pure function unit tests, DB integration, endpoint integration (110 total)

## Streaming Chat Responses

- [x] Extract `_run_chat_pipeline()` shared helper from `chat()` endpoint
- [x] Add `POST /chat/stream` SSE endpoint (meta → token → done events)
- [x] Add `api.sendMessageStream()` with ReadableStream SSE parser + AbortController support
- [x] Add `addStreamingMessage()` for incremental DOM rendering
- [x] Update `sendGreeting()`, `handleSend()`, `handleDrawerSend()` to use streaming
- [x] Typing indicator hides on `onMeta`, input re-enables immediately

## Multi-Goal System with AI Exercise Generation

- [x] `Goal` model: add `target_date` column, `exercises` relationship
- [x] `Exercise` model: add `goal_id` FK, `goal` relationship
- [x] DB migrations for `target_date` and `goal_id` columns
- [x] Repository: `get_active_goals`, `update_goal`, `deactivate_goal`, `get_exercises_by_goal`, `get_daily_exercise_counts`, `bulk_create_exercises`, `deactivate_exercises_for_goal`
- [x] LLM service: `GeneratedExercise`, `ExerciseGenerationResult`, `generate_exercises_for_goal()`, `rebalance_exercises()`
- [x] Exercise generator orchestrator: `generate_and_persist_exercises()`, `remove_exercises_for_goal()`
- [x] API schemas: `CreateGoalRequest`, `UpdateGoalRequest`, `GoalResponse`, `GoalWithExercisesResponse`
- [x] API: `POST/GET /patients/{id}/goals`, `PATCH/DELETE /patients/{id}/goals/{id}`
- [x] Exercise endpoint includes `goal_id` and `goal_text` attribution
- [x] Patient status and chat responses include `goals` list
- [x] SSE meta event includes goals
- [x] Active coaching prompt updated for multi-goal + goal setting
- [x] `set_goal` tool: target_date support, max 3 enforcement, exercise generation trigger
- [x] `set_goal` bound to active coaching node
- [x] Onboarding `GoalExtraction` includes `target_date`
- [x] Demo seed: goal has target_date
- [x] 8 new tests (57 total passing)

## Frontend Multi-Goal Display + Add Goal

- [x] `state.goals` array tracks multi-goal data from backend
- [x] `api.getGoals()`, `api.createGoal()`, `api.deleteGoal()` methods
- [x] `updateGoals()` syncs goals array and updates banner + home view
- [x] `renderGoalBanner()` shows all goals with star icon, text, target date
- [x] Goal banner label switches "Current Goal" → "Your Goals" when > 1
- [x] "Add Goal" button in banner (< 3 goals) navigates to home form
- [x] Home view goal card shows multiple goals with gold bullet list
- [x] Inline "Add Goal" form (text + optional date + save/cancel)
- [x] `api.createGoal()` → refresh goals → re-render on submit
- [x] SSE meta + status handlers propagate `goals` array
- [x] `loadHome()` fetches goals in parallel with other data
- [x] CSS for multi-goal banner, home goal list, and add-goal form

## Bug Fixes: "None" Goal Display + Tool Call Crash

- [x] Guard `check_goal_extraction` to reject LLM-generated `"None"` / `"null"` strings as goals
- [x] Sanitize `current_goal` in routes.py — treat "None" / "null" / "No goals set yet" as null
- [x] Frontend guard in `updateGoal()` — filter "None" / "No goals set yet" to null
- [x] Tool execution loop in `active_coaching_node` — process `tool_use` responses with `ToolMessage` replies
- [x] `_clean_tool_orphans()` helper to strip orphaned tool_use AIMessages from corrupted state
- [x] Safety node handles list-type AIMessage content (mixed text + tool_use blocks)
- [x] Retry node cleans tool orphans before re-invocation
- [x] Routes extract text from list-type AIMessage content blocks

## Fix: Filter "None" Goals from Display + Restore "Add Goal" Button

- [x] Backend: filter "None"/"null" goals in `_build_goal_responses()` so they never reach frontend
- [x] Backend: validate `set_goal` tool input — reject "None"/"null"/"" sentinel values
- [x] Frontend: filter goals array in `updateGoals()` before storing in state
- [x] Startup cleanup: `_cleanup_invalid_goals()` deactivates "None"/"null" goals on every boot

## Closed-Loop Adaptive Coaching

### Auto Exercise Progression
- [x] Extract `perform_exercise_adjustment()` service from `adjust_exercise` endpoint
- [x] Add `get_recent_difficulty_signals()` to repository (filter by exercise, difficulty, date range)
- [x] Add `get_difficulty_pattern_summary()` to repository (aggregate feedback counts)
- [x] Add `check_and_auto_adjust()` — triggers adjustment on 2+ same-signal completions in 3 days
- [x] Wire auto-adjust into `toggle_exercise_complete` endpoint
- [x] Auto-adjustments logged to AuditLog with `event_type="auto_exercise_adjustment"`
- [x] `ExerciseCompleteResponse` includes optional `auto_adjusted` field
- [x] 7 new tests (difficulty signals, threshold logic, API integration)

### Daily Briefing
- [x] `DailyBriefing` model with unique constraint per patient per day
- [x] Repository: `get_daily_briefing()`, `save_daily_briefing()`
- [x] `generate_daily_briefing()` service — Haiku-powered, one-per-day cached
- [x] `DAILY_BRIEFING_PROMPT` in prompts.py (warm, data-driven, <60 words)
- [x] `DailyBriefingResponse` schema
- [x] `GET /patients/{id}/daily-briefing` endpoint
- [x] Frontend: `api.getDailyBriefing()` method
- [x] Frontend: briefing fetched in `loadHome()` parallel Promise.all
- [x] Frontend: "Today's Coach Message" card with gold accent
- [x] 5 new tests (save/get, endpoint 404, cached, fresh generation)

### Weekly Review
- [x] `_weekly_review` flag in `GraphState` (transient, follows `_safety_verdict` pattern)
- [x] `WEEKLY_REVIEW_SYSTEM_PROMPT` + `MI_TECHNIQUES_SECTION` in prompts.py
- [x] `weekly_review_node` — structured review with MI for low adherence
- [x] Graph wiring: `route_by_phase` checks `_weekly_review` first, routes through safety
- [x] `"weekly_review"` event type in `trigger_event` endpoint
- [x] `_weekly_review=False` passed in `_run_chat_pipeline` to prevent stale flag
- [x] 8 new tests (routing with flag, node output, MI inclusion, error handling)

## Clinician Dashboard

- [x] `Clinician` model: clinician_id, name, email, api_key, is_active
- [x] `ClinicalAlert` model: alert_id, patient_id, alert_type, urgency, reason, status, context, timestamps
- [x] `Patient.alerts` relationship
- [x] Repository: `create_clinical_alert`, `get_alerts`, `get_alert_by_id`, `update_alert_status`, `count_open_alerts`
- [x] Repository: `get_all_patients`, `get_patient_audit_log`, `get_adherence_heatmap_data`, `get_all_outcome_trends`
- [x] Rewrite `alert_clinician` tool to persist ClinicalAlert + audit log (sync→async bridge)
- [x] `verify_clinician` auth dependency (DB-backed API key lookup)
- [x] Schemas: AlertResponse, UpdateAlertRequest, AlertCountResponse, PatientOverviewItem/Response, AuditEventResponse, PatientDetailResponse, AdherenceHeatmapCell/Response, PatientOutcomeTrend, OutcomeTrendsResponse, PatientInsightResponse
- [x] 8 clinician endpoints: alerts list/counts/patch, patients list/detail, audit-log, adherence-heatmap, outcome-trends
- [x] `clinician_routes.py` router wired into `main.py`
- [x] `seed_demo_clinician()` + seed demo alerts for demo-patient
- [x] `/clinician` route serves clinician dashboard HTML
- [x] `clinician.html`: login flow, 5 panels (alerts, patients, adherence heatmap, outcome trends, audit log), patient detail drawer
- [x] 19 new tests: auth (valid/invalid/inactive), alert CRUD (list/filter/counts/patch), patient overview, patient detail, audit log, heatmap, outcome trends

## Adaptive Patient Memory

- [x] PatientInsight DB model with confidence, category, reinforcement tracking
- [x] Repository functions: get, upsert, decay insights
- [x] `get_patient_insights` retrieval tool (follows get_adherence_summary pattern)
- [x] `extract_insights` graph node (Haiku-powered, post-safety extraction)
- [x] Graph wiring: check_goal_extraction → extract_insights → END
- [x] Prompt integration: {patient_insights} in onboarding, active, re_engaging prompts
- [x] Phase node changes: all 3 nodes call insights tool and inject into prompts
- [x] Tests: 10 new tests (repository, node, topology)
