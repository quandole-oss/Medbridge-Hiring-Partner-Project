# Changelog

## [Unreleased]

### Added
- Patient-facing chat frontend served at `/` (no build tools required)
- Welcome screen with patient ID input and consent flow
- Real-time chat interface with coach/patient message bubbles
- Phase badge (color-coded pill: onboarding, active, dormant, re-engaging)
- Goal banner with gold accent card and slide-in animation
- Mobile-first responsive design with safe-area support
- Accessibility: semantic HTML, ARIA attributes, keyboard navigation, reduced motion
- Error toast notifications with friendly messages per HTTP status
- Session persistence via sessionStorage
- Static file serving via FastAPI (`/static` mount + `/` root route)
- Multi-view app shell with bottom tab bar (Home, Exercises, Coach, Settings)
- Home dashboard with greeting, goal card, today's action plan, coach teaser, progress stats
- Exercises view with 7-day selector and exercise program display
- Progress section with adherence ring, stats grid, milestones, daily completion chart
- Settings view with patient info and logout
- Chat drawer for quick messaging from non-chat tabs
- Chat FAB button on exercises view
- Demo seed data: fully populated patient with 5-day completion history
- Desktop sidebar layout at 768px breakpoint
- Expandable exercise cards with collapse/expand animation
- Per-set completion checkboxes with incremental tracking
- Progress dots in collapsed card view showing sets completed
- Difficulty feedback selector (Too Easy / Just Right / Too Hard)
- Feedback textarea for exercises marked "Too Hard"
- AI-driven exercise adjustment endpoint (`POST /exercises/{id}/adjust`)
- LLM-powered exercise substitution with structured output (easier/harder variations)
- Exercise replacement chain tracking via `replaced_by_id` foreign key
- Animated inline SVG illustrations for 12 exercise categories
- Granular ExerciseCompletion model (sets_completed, difficulty, feedback columns)
- `replace_exercise` repository function for exercise substitution
- `get_exercise_adjustment` LLM service with fallback for API failures
- Three-state set tracking: each set independently cycles empty → complete → partial → empty
- Partial set visual: gold-bordered circle with "~" tilde for partial completions
- Progress dots show partial state (gold border, no fill) alongside complete (gold filled)
- `set_statuses` JSON column on ExerciseCompletion for per-set status tracking
- Day-shifted exercise adjustments: too_easy/too_hard replaces exercise on a future day, not the current one
- Three-tier replacement target selection: same name on later day → same body_part on nearest future day → next day
- Adjustment result UI shows target day and old → new exercise names
- AI context enhancement: set_statuses detail passed to LLM for smarter difficulty calibration
- `find_replacement_target()` repository function with three-tier fallback logic
- DB migration in `init_db` to add `set_statuses` column to existing databases
- Demo seed data includes partial set completions

### Changed
- Exercise SVG illustrations are now static (removed CSS keyframe animations and play-state toggles)
- Slimmer stick figures: smaller joints, thinner strokes, smaller heads
- Each SVG frozen in a recognizable mid-exercise pose via static CSS transforms
- `adjust_exercise` endpoint now targets a different day instead of replacing the current exercise
- `submitAdjustment()` JS no longer swaps the current exercise card in the UI
- `mark_exercise_complete()` accepts optional `set_statuses` and derives `sets_completed` from it

### Fixed
- Exercise completion display for past days: endpoint queried today's date instead of the correct date for the requested day. Now uses `enrollment_date + (day - 1)`. (`app/api/routes.py`)
- Removed stale debug logging block from `renderExerciseList()` in frontend
