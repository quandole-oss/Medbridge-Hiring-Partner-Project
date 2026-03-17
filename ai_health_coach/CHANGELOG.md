# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

### Fixed

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
