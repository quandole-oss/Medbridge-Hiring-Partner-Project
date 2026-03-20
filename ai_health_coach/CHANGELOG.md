# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

### Added

- Gamification / badge & achievement system with 10 badges computed on-the-fly from existing data
- `app/services/badges.py`: pure `compute_badges()` function with badge catalog and earned/earned_today flags
- `get_completed_goal_count()` repository function for goal-based badges
- `BadgeItem` schema and `badges`/`completed_goal_count` fields on `AdherenceResponse` (backward-compatible defaults)
- Achievements section on Home tab: horizontal scrollable badge row with gold glow for earned, greyed+lock for locked
- Badge celebration system: CSS confetti burst + gold slide-up toast with sessionStorage dedup
- Badge context added to daily briefing LLM prompt so the coach can reference achievements
- 15 new badge tests (110 total passing): pure function unit tests + DB integration + endpoint integration

- Clinician Dashboard: full clinician-facing UI with login, 5 data panels, and patient detail drawer
- `Clinician` and `ClinicalAlert` database models with `Patient.alerts` relationship
- `alert_clinician` tool now persists ClinicalAlert rows + audit log entries (was placeholder)
- DB-backed clinician authentication via `verify_clinician` dependency
- 8 clinician API endpoints: alert list/counts/patch, patient list/detail, audit log, adherence heatmap, outcome trends
- Demo clinician seed data (`Dr. Demo` with `demo-clinician-key`) and sample alerts
- `clinician.html` SPA: alerts panel with acknowledge/resolve, patients table, CSS adherence heatmap, Chart.js outcome trends, paginated audit log, patient detail slide-over drawer
- 19 new tests (93 total passing): clinician auth, alert CRUD, patient overview/detail, audit log, cross-patient analytics

- Closed-loop adaptive coaching: three integrated features that transform the app from reactive chatbot to proactive coach
- Auto exercise progression: automatically adjusts exercises when 2+ same-difficulty signals detected in 3 days
- Exercise progression service (`app/services/exercise_progression.py`): extracted adjustment pipeline, reusable by API and auto-trigger
- `get_recent_difficulty_signals()` and `get_difficulty_pattern_summary()` repository functions
- `ExerciseCompleteResponse.auto_adjusted` field notifies frontend when auto-adjustment occurs
- Auto-adjustments logged to AuditLog with `event_type="auto_exercise_adjustment"`
- Daily briefing system: personalized coaching message generated once per day, cached
- `DailyBriefing` model with unique constraint per patient per day
- `generate_daily_briefing()` service using Haiku for cost-efficient generation (~$0.001/briefing)
- `GET /patients/{id}/daily-briefing` endpoint with caching
- `DAILY_BRIEFING_PROMPT` — warm, data-driven, under 60 words
- Frontend "Today's Coach Message" card on home view with gold accent
- Weekly review protocol: structured data-driven check-in with MI techniques
- `weekly_review_node` graph node with motivational interviewing for adherence < 60%
- `WEEKLY_REVIEW_SYSTEM_PROMPT` + `MI_TECHNIQUES_SECTION` prompts
- `"weekly_review"` event type in trigger endpoint — invokes graph with `_weekly_review=True`
- `_weekly_review` transient flag in GraphState, cleared by node, defaulted to False in chat pipeline
- 20 new tests (74 total passing): exercise progression, daily briefing, weekly review

### Fixed

- Overall completion rate inflated when exercises are deactivated by progression system: `total_completed` and `total_due` now derived from the daily completions loop (same source as daily bars) instead of separate SQL queries that counted all completions regardless of date/active status
- Completion ring on Home tab now shows today's progress instead of cumulative rate; cumulative rate moved to "Overall" stat in the stats grid
- "None" goals in banner + hidden "Add Goal" button: filter sentinel goals ("None"/"null") at API layer (`_build_goal_responses`), `set_goal` tool input validation, frontend `updateGoals()`, and startup DB cleanup
- "None" goal display: guard against LLM returning literal `"None"` string in goal extraction, API response sanitization, and frontend display
- Chat crash on tool calls: `active_coaching_node` now executes tool calls in a loop (up to 3 iterations) and returns proper `ToolMessage` responses so Anthropic API history stays valid
- Orphaned tool_use recovery: `_clean_tool_orphans()` strips corrupted tool_use AIMessages from InMemorySaver state (active coaching + retry node)
- Safety node skips pure tool_use messages and extracts text from mixed content blocks
- API response extraction handles list-type AIMessage content (mixed text + tool_use blocks)

### Added

- Frontend multi-goal display: all active goals visible simultaneously in chat banner and home view
- "Add Goal" button in both chat banner and home goal card (hidden when 3 goals reached)
- Inline add-goal form on home view (goal text + optional target date + save/cancel)
- Goals array synced from SSE meta events, status responses, and dedicated getGoals API
- Multi-goal system: patients can have up to 3 concurrent active goals with optional target dates
- AI-driven exercise generation: new goals trigger LLM to generate 2-4 goal-specific exercises
- Workload balancing: exercises distributed across 7-day cycle with max 5 per day cap
- Goal attribution: each exercise indicates which goal it supports (`goal_id`, `goal_text`)
- Dual goal creation: via `POST /goals` API endpoint and through chat conversation (`set_goal` tool)
- Goal CRUD endpoints: `POST/GET /patients/{id}/goals`, `PATCH/DELETE /patients/{id}/goals/{id}`
- Exercise generation orchestrator (`app/services/exercise_generator.py`) with rebalancing
- `set_goal` tool now available in active coaching phase (not just onboarding)
- Goal extraction during onboarding now captures `target_date`
- Patient status and chat responses include `goals` list
- 8 new tests covering goal CRUD, exercise generation, attribution, and status integration
- Streaming chat responses via SSE: `POST /chat/stream` endpoint streams safe responses word-by-word
- Frontend streams tokens incrementally with `addStreamingMessage()` and SSE parser
- Typing indicator hides and input re-enables on first data (meta event), not stream end
- Adaptive Patient Memory: coach extracts and remembers patient insights across conversations
- `PatientInsight` model with confidence scoring, reinforcement tracking, and decay
- `extract_insights` graph node runs post-safety on Haiku for cheap structured extraction
- `get_patient_insights` tool injects patient context into all phase prompts
- Patient insights injected into onboarding, active coaching, and re-engagement prompts
- Confidence-based retrieval (top 10 by confidence, min 0.3 threshold)
- Automatic confidence decay for unreinforced insights, soft-delete below 0.1
- 10 new tests covering repository functions, extraction node, and graph topology
