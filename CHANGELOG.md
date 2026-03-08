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
- SVG animations play on expand, pause on collapse, respect reduced-motion preference
- Granular ExerciseCompletion model (sets_completed, difficulty, feedback columns)
- `replace_exercise` repository function for exercise substitution
- `get_exercise_adjustment` LLM service with fallback for API failures
- Updated demo seed data with sets_completed values and difficulty ratings
