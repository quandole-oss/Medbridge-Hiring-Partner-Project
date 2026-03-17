# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

### Added

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
