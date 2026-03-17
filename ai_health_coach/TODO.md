# AI Health Coach — TODO

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

## Adaptive Patient Memory

- [x] PatientInsight DB model with confidence, category, reinforcement tracking
- [x] Repository functions: get, upsert, decay insights
- [x] `get_patient_insights` retrieval tool (follows get_adherence_summary pattern)
- [x] `extract_insights` graph node (Haiku-powered, post-safety extraction)
- [x] Graph wiring: check_goal_extraction → extract_insights → END
- [x] Prompt integration: {patient_insights} in onboarding, active, re_engaging prompts
- [x] Phase node changes: all 3 nodes call insights tool and inject into prompts
- [x] Tests: 10 new tests (repository, node, topology)
