# Feature Specification: Structured Fitness Exercise Builder & Multi-Surface Tracking

**Feature Branch**: `005-structured-fitness-exercise-builder`

**Created**: 2026-09-12

**Status**: Draft

**Input**: User description: "Séances de fitness structurées exercice par exercice (séries, répétitions, charge, durée, notes) & interfaces mobile et web. Modéliser les séances de sport comme des ensembles d'exercices structurés (nom de l'exercice, nombre de séries, répétitions cible, charge/poids, durée, temps de repos, notes spécifiques à l'exercice). Spécifier les parcours d'inspection et d'édition d'une séance sur mobile et web (visualiser chaque exercice, cocher les séries, modifier les charges). Encadrer la génération par l'IA : elle doit créer directement les exercices structurés sans noyer les informations dans un bloc de texte libre ni ajouter de conseils non sollicités. Définir les user stories (P1, P2, P3), cas limites et critères de succès mesurables."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Structured Workout Planning & Exercise Builder (Priority: P1)

As an active user planning a fitness session, I want to create and edit a workout by adding individual structured exercises with detailed parameters (exercise name, sets count, target repetitions, load/weight in kg, target duration, rest time, and technique notes), so that my session is clearly organized and actionable before starting training.

**Why this priority**: Currently, workouts flatten exercise details into an unstructured text note or simple name-only lists without sets, weights, or rest periods. Providing a granular builder is essential for serious physical training planning and constitutes the core foundation of the fitness feature.

**Independent Test**: Can be tested independently by opening the workout creation form on web or mobile, adding a multi-exercise routine (e.g. 4 sets of 10 Bench Press at 80kg with 90s rest, followed by 3 sets of 60s Plank with 45s rest), saving the session, and verifying that each exercise retains its specific parameters and sequence order.

**Acceptance Scenarios**:

1. **Given** a user opening the workout creation form on web or mobile, **When** they add an exercise configured with 4 sets, 10 target repetitions, 75 kg load, 90 seconds rest time, and note "Pause en bas de mouvement", **Then** the exercise is saved as a discrete structured item within the session displaying all specified values.
2. **Given** a workout form with multiple exercises, **When** the user adds a duration-based exercise (e.g. Plank for 3 sets of 60 seconds with 45s rest), **Then** the builder accepts time duration instead of repetition count while enforcing sets, rest time, and technique notes.
3. **Given** an existing planned workout with three exercises, **When** the user edits the session to reorder exercises, update target loads, or remove an exercise, **Then** the modified structure is updated accurately and reflected in both overview and detail views.
4. **Given** a user submitting an exercise with missing mandatory fields (such as a missing exercise name or zero sets), **When** they attempt to save, **Then** the interface prevents submission and highlights the specific field needing correction.

---

### User Story 2 - Interactive Live Workout Execution & Set-by-Set Tracking (Priority: P1)

As an athlete actively performing a workout, I want to open my scheduled session on my mobile device or web browser, view the complete exercise breakdown card-by-card, check off each set as I complete it, and adjust actual weights and reps on the fly, so that I accurately record what I actually performed without interrupting my training flow.

**Why this priority**: Training execution is real-time and physical. Users cannot navigate cumbersome forms or read dense paragraphs between sets. Fast, tactile set-by-set checkoffs and immediate load adjustment make the app a practical training companion.

**Independent Test**: Can be tested independently by launching an active workout session on mobile, checking off Set 1 of an exercise, modifying the load from 80kg to 82.5kg for Set 2, checking off remaining sets, and verifying that the completed session records the exact performed parameters.

**Acceptance Scenarios**:

1. **Given** an upcoming scheduled workout on the mobile app, **When** the user taps on the session card, **Then** the app opens a dedicated workout detail screen displaying each exercise as an expanded card showing target sets, repetitions, target load, rest interval, and technical notes.
2. **Given** an open workout session during training, **When** the user taps the checkmark on Set 1 of an exercise, **Then** the set is visually marked as completed, and the recommended rest period is highlighted to guide the user's recovery.
3. **Given** a planned exercise with 4 sets at 70 kg, **When** the user achieves 12 repetitions instead of the targeted 10 or lifts 72.5 kg on Set 3, **Then** the user can directly modify the actual performed reps or weight for that specific set without leaving the live session view.
4. **Given** a session with multiple exercises where some sets were completed, **When** the user marks the session as finished, **Then** the system prompts for overall workout feedback (actual duration, perceived effort rating from 1 to 10), marks the session status as completed, and preserves both planned targets and actual completed data.

---

### User Story 3 - Direct AI Structured Workout Generation Without Conversational Bloat (Priority: P2)

As a busy user asking the AI assistant to prepare a workout routine (e.g. "Plan a 45-minute Push session focusing on chest and shoulders"), I want the assistant to generate fully structured exercises (sets, reps, suggested weights/bodyweight, rest times, and brief form cues) directly into my schedule, accompanied by a clean, concise confirmation card without unsolicited essays, mass-gain lectures, or generic fitness disclaimers.

**Why this priority**: The current assistant experience dumps paragraphs of generic advice and combines exercises into freeform text notes rather than structured entities. Constraining AI output to structured creation with minimal, direct conversational summaries delivers high utility and eliminates cognitive fatigue.

**Independent Test**: Can be tested independently by prompting the assistant: *"Schedule a 50-minute leg workout for tomorrow at 18:00 focusing on squats and lunges"*, verifying that a structured fitness session is created with discrete exercise records, and checking that the conversational response contains only the summary confirmation (session title, date/time, exercises count, targeted focus) in under 3 sentences with zero unsolicited nutrition advice.

**Acceptance Scenarios**:

1. **Given** a user message requesting a workout routine, **When** the assistant processes the request, **Then** it creates a session containing individual structured exercises, each with designated sets, target repetitions or duration, estimated load or bodyweight indication, and standard rest intervals.
2. **Given** a workout generated by the assistant, **When** the user inspects the created session on mobile or web, **Then** all exercises appear in the structured builder and live tracker, with zero exercise content relegated to a monolithic notes block.
3. **Given** a user asking for a workout plan, **When** the assistant responds in the chat interface, **Then** the text response is concise (maximum 3 sentences summarizing the session parameters) and displays a structured interactive workout card, omitting unsolicited advice on diet, supplements, or bulking.
4. **Given** a prompt lacking key details (e.g. *"Plan a workout"* without specifying muscle groups or duration), **When** the assistant generates the session, **Then** it applies balanced default settings based on user history or standard full-body templates without generating long preambles or rhetorical questions.

---

### User Story 4 - Historical Performance Inspection & Workout Duplication (Priority: P3)

As a user committed to long-term physical progression, I want to review past completed workouts exercise by exercise to compare loads and volume, and easily duplicate or adapt a past workout into an upcoming session, so that I can apply progressive overload consistently across weeks.

**Why this priority**: Long-term fitness results rely on progressive overload (gradually increasing weight, reps, or volume). Being able to inspect historical loads and reuse previous routines as starting templates saves time and boosts training adherence.

**Independent Test**: Can be tested independently by navigating to a completed session in history, verifying that performed loads and completed sets are visible per exercise, clicking "Duplicate to New Session", selecting a new date, and confirming that the new planned session is populated with the prior exercise template.

**Acceptance Scenarios**:

1. **Given** a previously completed workout in the history list, **When** the user inspects the workout details, **Then** the screen displays the actual completed sets, achieved weights, total session duration, and perceived effort rating.
2. **Given** a past successful workout, **When** the user selects "Duplicate as New Session", **Then** a new draft workout is instantiated for a future date with identical exercises, target sets, and loads pre-filled, ready for minor adjustments.

---

### Edge Cases

- **Partial Workout Completion**: If a user is interrupted and completes only 2 out of 5 exercises before marking the workout complete, the system marks the overall session as completed while preserving the exact status of completed sets versus unattempted sets, reflecting accurate historical completion.
- **Bodyweight vs. Weighted Bodyweight Movements**: For exercises such as pull-ups, push-ups, or dips, the load field defaults to 0 kg (indicating bodyweight) while permitting positive values for added external resistance (e.g. +10 kg weighted vest or belt) or negative values for assisted machines (e.g. -15 kg band assistance).
- **Mixed Tracking Modalities in a Single Routine**: A single workout session can freely interleave repetition-based exercises (e.g. Barbell Squats: 4 sets of 8 reps) and duration-based exercises (e.g. Plank: 3 sets of 45 seconds).
- **Intermittent Mobile Connectivity**: When an athlete checks off sets in a gym with poor or intermittent reception, state updates are captured locally in the client and synchronized cleanly upon reconnection without loss of progress.
- **Extreme or Boundary Input Values**: The system rejects invalid entries gracefully (e.g. sets <= 0, reps <= 0, negative rest time, session duration exceeding 12 hours) with clear localized validation messages next to the offending input field.
- **Legacy Unstructured Sessions**: Workouts created prior to this specification that contain only title, notes, or flat exercise strings remain readable. When opened in the editor, they display an option to convert or re-structure the legacy exercise list into modern structured entities.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST represent each workout as a session containing an ordered collection of structured exercise items rather than an unstructured text blob.
- **FR-002**: Each structured exercise MUST capture: exercise name, sequence order, tracking mode (repetitions vs duration), target sets count, target repetitions (for rep-based mode), target duration in seconds or minutes (for duration-based mode), target load/weight in kilograms, rest interval between sets in seconds, and exercise-specific technical notes.
- **FR-003**: The system MUST provide a dedicated Exercise Builder interface on web allowing users to add, edit, reorder, and remove individual exercises within a session with dedicated inputs for every parameter.
- **FR-004**: The mobile application MUST provide a dedicated workout detail screen where each exercise is rendered as an independent card displaying all its parameters (sets, target reps/duration, load, rest time, notes) instead of a collapsed single-line text summary.
- **FR-005**: The system MUST provide interactive set tracking on both mobile and web surfaces, enabling users to check off individual sets as completed during workout execution.
- **FR-006**: During live workout execution, users MUST be able to adjust the actual load lifted and actual repetitions performed for each specific set.
- **FR-007**: When marking a session as completed, the system MUST record the completion timestamp, actual duration, effort rating (1-10 scale), calories burned (optional), and the final state of all completed sets.
- **FR-008**: When requested to create or plan a fitness workout, the AI assistant MUST generate structured exercise entities with complete parameters (exercise name, sets, target reps/duration, load, rest time, form notes) directly into the session model.
- **FR-009**: The AI assistant's conversational response when creating a workout MUST be concise (maximum 3 sentences focusing on session confirmation, muscle groups targeted, and estimated duration) and MUST NOT include unsolicited essays, dietary advice, or generic mass-gain tutorials.
- **FR-010**: The system MUST validate exercise parameters at the business domain level: sets count between 1 and 50, repetitions between 1 and 1000, duration between 1 second and 3600 seconds, load between -200 kg and 1000 kg, and rest interval between 0 and 1800 seconds.
- **FR-011**: Every fitness session and exercise record MUST strictly belong to the authenticated user's tenant, and cross-tenant access attempts MUST return non-existence responses (HTTP 404).
- **FR-012**: All session schedules and timestamps MUST be stored and transmitted in UTC, and planned sessions MUST participate in non-bypassable timeline collision checks against the user's unified calendar.
- **FR-013**: The system MUST allow users to duplicate an existing or past workout session into a new planned session, copying the full exercise structure and target parameters.
- **FR-014**: The mobile and web interfaces MUST support offline or resilient set checkoff recording, ensuring training progress is preserved during momentary loss of network connectivity.
- **FR-015**: The system MUST preserve backwards compatibility for legacy fitness sessions, rendering legacy exercises without data loss and offering clean migration to structured format upon edit.

### Key Entities *(include if feature involves data)*

- **FitnessSession**: Represents a scheduled, in-progress, or completed workout routine. Key attributes include: user identity (tenant isolation), title, session type (strength, cardio, mobility, recovery, mixed), planned datetime (UTC), scheduled duration, session status (planned, in_progress, completed, skipped), overall workout note, completion metrics (completed timestamp, actual duration, effort rating 1-10, calories burned), and an ordered collection of WorkoutExercise items.
- **WorkoutExercise**: Represents a discrete exercise within a session. Key attributes include: exercise name, order index, tracking mode (repetition-based or duration-based), target sets count, target repetitions per set, target duration per set, target load (in kg, where 0 indicates bodyweight), rest time between sets (in seconds), exercise-specific technical notes, and an array of individual set execution records.
- **ExerciseSetRecord**: Represents the tracking state of an individual set within an exercise. Key attributes include: set index (e.g. set 1, 2, 3), target repetitions/duration, actual repetitions/duration performed, target load, actual load used, and completion flag (checked vs unchecked).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can construct and save a 5-exercise structured workout (including sets, reps, weight, and rest intervals) on the web builder in under 90 seconds.
- **SC-002**: 100% of fitness workouts generated by the AI assistant produce structured exercise items, with 0% of exercise details stored exclusively in an unstructured text note block.
- **SC-003**: The conversational response length from the AI assistant during workout creation is reduced by at least 60% compared to prior unconstrained text generations, containing 0 unsolicited nutrition, mass-gain, or generic disclaimer paragraphs.
- **SC-004**: Users on mobile can inspect the complete structured parameters of any scheduled exercise in 1 tap from the main fitness screen, replacing the former single-line concatenated text display.
- **SC-005**: 95% of users conducting live workouts on mobile can check off a completed set and record load adjustments in 2 taps or fewer without navigating away from the active session view.
- **SC-006**: 100% of historical legacy workout records remain readable and displayable without crash, error, or data corruption.

## Assumptions

- **Target Device Experience**: Mobile tracking is optimized for one-handed thumb interaction during active gym workouts with prominent tap targets (minimum 44x44 points) for checking off sets.
- **Unit System**: Kilograms (kg) is the standard metric unit for load/weight, and seconds are the standard unit for rest intervals. Imperial conversions (pounds) are deferred to user-level localization preferences if requested in the future.
- **Rest Interval Guidance**: A visual rest counter or badge indicates elapsed or target rest time following set completion; background audio chime or push notifications are deferred as future progressive enhancements.
- **Calendar Integration**: Fitness sessions continue to sync with the central calendar hub as defined in the AdamHUB constitution, respecting UTC formatting and non-bypassable slot collision checks.
- **AI Tool Calling**: The assistant leverages structured action calls (`fitness.create_session`, `fitness.update_session`) passing structured exercise payloads rather than relying on unstructured text synthesis.
