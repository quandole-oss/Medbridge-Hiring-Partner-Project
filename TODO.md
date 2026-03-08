# TODO

## Patient-Facing Frontend

- [x] Create `app/static/index.html` with welcome + chat screens
- [x] Modify `app/main.py` to serve static files and root route
- [x] Welcome screen: patient ID input, consent flow, error handling
- [x] Chat screen: header with phase badge, goal banner, messages, input area
- [x] Design tokens: navy/gold palette, Georgia serif, system sans-serif body
- [x] Accessibility: semantic HTML, aria attributes, focus-visible, reduced motion
- [x] Mobile: safe-area padding, dvh viewport, touch-action, 16px inputs
- [x] XSS-safe rendering: textContent only, no innerHTML
- [x] Session persistence via sessionStorage
- [x] Error toast with auto-dismiss

## Multi-View App Shell

- [x] Bottom tab bar with Home, Exercises, Coach, Settings tabs
- [x] Home dashboard with greeting, goal card, action plan, coach teaser, progress stats
- [x] Exercises view with day selector and exercise cards
- [x] Progress view with adherence ring, stats grid, milestones, daily chart
- [x] Settings view with patient info and logout
- [x] Chat drawer for non-chat tabs
- [x] Chat FAB on exercises view
- [x] Demo seed data with 5-day completion history
- [x] Desktop sidebar layout at 768px+

## Expandable Exercise Cards

- [x] Expand/collapse exercise cards with chevron toggle
- [x] Per-set checkboxes with incremental API updates
- [x] Progress dots showing sets completed in collapsed view
- [x] Difficulty selector (Too Easy / Just Right / Too Hard)
- [x] Feedback textarea for "Too Hard" exercises
- [x] AI-driven exercise adjustment endpoint
- [x] Exercise replacement via LLM structured output
- [x] Animated SVG illustrations for each exercise type
- [x] Green left border when all sets complete
- [x] Backend: ExerciseCompletion granular tracking (sets_completed, difficulty, feedback)
- [x] Backend: Exercise.replaced_by_id for substitution chains
- [x] Backend: replace_exercise repository function
- [x] Backend: get_exercise_adjustment LLM service
- [x] Seed data updated with sets_completed values

## Partial Set Completion + Day-Shifted Adjustments

- [x] Three-state set tracking: empty → complete → partial → empty per set
- [x] `set_statuses` JSON column on ExerciseCompletion model
- [x] Partial visual: gold-bordered circle with "~" tilde in set buttons
- [x] Progress dots reflect per-set state (filled / partial / empty)
- [x] Frontend `ensureSetStatuses()` backward compat from `sets_completed`
- [x] `toggleSet()` rewritten for per-set three-state cycling
- [x] API sends/receives `set_statuses` array on complete endpoint
- [x] Day-shifted adjustments: too_easy/too_hard targets a future day, not current
- [x] `find_replacement_target()` with three-tier fallback (same name → same body_part → next day)
- [x] `adjust_exercise` endpoint calculates current day and finds target on different day
- [x] Frontend shows "Exercise Updated on Day X" with old → new names
- [x] Current exercise card stays unchanged after adjustment
- [x] AI context: `set_statuses` detail passed to LLM prompt for calibration
- [x] DB migration in `init_db` for existing databases
- [x] Seed data includes partial set completions

## Future Enhancements

- [ ] Real authentication (replace hardcoded API key)
- [ ] Message history persistence / reload on refresh
- [ ] Typing indicator with streaming responses
- [ ] Dark mode support
- [ ] PWA manifest + service worker for offline shell
