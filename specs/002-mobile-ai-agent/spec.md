# Feature Specification: Mobile AI Agent & Context Engine

**Feature Branch**: `002-mobile-ai-agent`

**Created**: 2026-09-12

**Status**: Draft

**Input**: User description: "Intégration de la partie IA : agent conversationnel mobile avec sessions éphémères et contexte persistant par utilisateur (données onboarding, objectifs sport, régime alimentaire, inventaire courses/garde-manger, préférences lifestyle/musique). Support de modèles économiques et performants (Gemini Flash, DeepSeek) avec tool calling transversal et interface dédiée sur l'application mobile."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Context-Aware Mobile Assistant Interaction (Priority: P1)

As an active mobile user, I want to open the central AI assistant from the mobile app and converse naturally with an agent that already knows who I am, what my goals are, and what my day looks like, so that I get relevant advice and updates without constantly re-explaining my background.

**Why this priority**: This forms the foundational value of having an integrated AI assistant. Without awareness of the user's live schedule, pantry stock, and personal targets, the assistant is merely a generic chatbot rather than a personal life operations copilot.

**Independent Test**: Can be tested by setting up user profile targets and pantry items, asking the assistant *"What should I eat for lunch today?"*, and verifying that the response factors in current stock and dietary goals in under 3 seconds.

**Acceptance Scenarios**:

1. **Given** an authenticated user with a defined profile (e.g. muscle gain goal, vegetarian) and low pantry supplies (e.g. tofu and eggs remaining), **When** the user asks the assistant for a quick meal idea, **Then** the assistant proposes a vegetarian high-protein recipe utilizing available ingredients without asking for dietary constraints or stock details.
2. **Given** an active schedule with two pending tasks due today, **When** the user asks *"What's on my plate right now?"*, **Then** the assistant provides a concise digest mentioning the two pending tasks and the next upcoming schedule event.
3. **Given** a user chatting on mobile, **When** the user submits a message, **Then** the assistant streams the response progressively token-by-token with initial visual feedback appearing in less than 1 second.

---

### User Story 2 - Natural Language Action Execution (Priority: P1)

As a busy mobile user, I want to tell the assistant to perform life management actions (such as adding groceries, creating a task, or scheduling a fitness session) and receive instant, structured confirmation cards in the chat, so that I can manage my day hands-free and friction-free.

**Why this priority**: An agent that can only talk is passive. Enabling safe, automated mutations across tasks, meals, fitness, and groceries transforms the assistant into an active productivity driver.

**Independent Test**: Can be tested by commanding *"Add 6 eggs and almond milk to my grocery list and schedule a chest workout tomorrow at 18:00"*, verifying that the items appear in the grocery list, the event appears on the calendar, and structured confirmation cards render in the conversation.

**Acceptance Scenarios**:

1. **Given** an ongoing assistant session, **When** the user instructs *"Remind me to call the accountant on Monday at 10am"*, **Then** the assistant triggers task creation, confirms the title and due date, and displays an interactive task confirmation card.
2. **Given** an ongoing assistant session, **When** the user instructs *"Add olive oil to my shopping list"*, **Then** the grocery item is created under the user's account and confirmed visually in the message stream.
3. **Given** an action instruction that lacks a required detail (e.g., *"Schedule a workout"* without day or time), **When** the assistant processes the request, **Then** it prompts for the missing detail conversationally before committing the action.

---

### User Story 3 - Ephemeral Sessions with Persistent Identity (Priority: P2)

As a user who engages in distinct, topic-focused conversations throughout the day, I want each chat thread to be easily resettable with a clean slate, while my underlying profile, preferences, and personal facts remain permanently intact.

**Why this priority**: Users need mental clarity. Cluttering an assistant with weeks of unrelated chat history increases response latency, confuses the model, and creates cognitive overload. Keeping conversations ephemeral while identity remains persistent provides the optimal balance of speed and personalization.

**Independent Test**: Can be tested by having a conversation about a specific recipe, tapping the "New Session" button, verifying that the previous chat thread is cleared, and asking *"What are my fitness goals?"* to verify that personal context was retained.

**Acceptance Scenarios**:

1. **Given** an active chat thread with multiple messages, **When** the user taps the "New Chat" / "Reset Session" button, **Then** the conversation interface resets immediately to a blank state with initial suggestion prompts.
2. **Given** a reset session, **When** the user asks a personal question, **Then** the assistant still tailors its answer to the user's persistent profile without requiring re-onboarding.
3. **Given** a closed app, **When** the user re-opens the app during the same active day, **Then** the recent session remains visible until the user explicitly decides to reset it.

---

### User Story 4 - Profile & Lifestyle Customization (Priority: P2)

As an individual with evolving routines and preferences, I want to set up and update my profile details (dietary rules, fitness objectives, favorite music/lifestyle notes, preferred communication tone), so that the assistant's behavior closely aligns with my personal vibe and goals.

**Why this priority**: Personalization is the emotional hook that makes users love and stick with the application. Custom communication style (e.g. direct, encouraging, concise) and lifestyle awareness (e.g. music interests, sports) make interactions pleasant and tailored.

**Independent Test**: Can be tested by changing the preferred tone to "Direct & Concise" in settings, asking for a summary of the day, and verifying that the response is short and bulleted without fluff or verbose pleasantries.

**Acceptance Scenarios**:

1. **Given** a user completing onboarding or updating settings, **When** they specify their dietary restrictions, fitness goals, and lifestyle notes, **Then** these preferences are saved to their user profile and immediately reflected in all subsequent assistant interactions.
2. **Given** a user who sets their assistant tone preference (e.g. "Encouraging & Enthusiastic" vs "Direct & Minimalist"), **When** the assistant generates messages, **Then** its phrasing and greeting match the chosen tone.

---

### Edge Cases

- **Network Interruption During Streaming**: If network connectivity drops while a response is streaming, the client indicates the interruption and provides a "Retry" button without duplicating executed actions.
- **Action Execution Failure**: If an action fails (e.g., database constraint or invalid parameter), the assistant informs the user politely in natural language and offers an alternative rather than crashing or showing a raw error code.
- **Destructive Commands**: If a user asks to delete all tasks or wipe data, the assistant MUST require explicit user confirmation before executing any destructive action.
- **Empty User Profile**: If a new user has not completed onboarding, the assistant gracefully falls back to sensible defaults and subtly invites the user to complete their profile for better recommendations.
- **Concurrent Requests**: If the user sends a new message while a previous response is still generating, the ongoing generation is gracefully aborted and the new request takes precedence.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST maintain a persistent User Profile entity per tenant containing dietary preferences, fitness goals, lifestyle notes, and communication style.
- **FR-002**: The system MUST dynamically generate a real-time context snapshot for each assistant interaction, compiling the current timestamp, top priority tasks, upcoming calendar events, next planned meal, and low pantry stock items.
- **FR-003**: The assistant MUST operate in isolated sessions where chat history can be reset by the user without modifying or deleting the persistent User Profile or database records.
- **FR-004**: The system MUST stream assistant responses in real time to the mobile client using a progressive event stream (Server-Sent Events).
- **FR-005**: The assistant MUST support automated execution of authorized actions across tasks, groceries, meal plans, and fitness schedules through structured action calling.
- **FR-006**: When an action is executed by the assistant, the mobile interface MUST render a distinct, interactive confirmation card highlighting what was created or changed.
- **FR-007**: The system MUST enforce strict multi-tenant data isolation; an assistant session MUST NEVER access, leak, or mutate data belonging to any other user.
- **FR-008**: The assistant configuration MUST support interchangeable AI models (e.g. Gemini 2.0 Flash, DeepSeek, or other low-latency models via standard provider configuration) without client-side modifications.
- **FR-009**: The mobile application MUST provide a dedicated full-screen or modal interface for the assistant accessible directly via the central navigation button.
- **FR-010**: Users MUST be able to view, edit, and update their persistent profile and lifestyle preferences at any time from the mobile application.
- **FR-011**: The system MUST execute an asynchronous background memory extraction task upon completion of assistant response streaming, identifying new or revised long-term user facts (health, nutrition, sports, habits, preferences) and updating the persistent `UserMemory` store without increasing user response latency.
- **FR-012**: The database persistence layer for both development and production MUST strictly use PostgreSQL running via Podman, eliminating SQLite from the application lifecycle.
- **FR-013**: Users MUST be able to view and dismiss/archive individual remembered facts from their profile settings to maintain full transparency and privacy control.

### Key Entities *(include if feature involves data)*

- **UserProfile**: Represents long-term user context and identity. Includes tenant ID, dietary preferences (allergies, restrictions), fitness goals (focus, frequency), lifestyle notes (music, habits, personal details), preferred AI tone, and onboarding status.
- **UserMemory**: Represents discrete, extracted long-term user facts and observations across conversations (`user_id`, `category`, `fact`, `confidence`, `is_active`, `source`, `created_at`, `updated_at`).
- **AssistantSession**: Represents a lightweight conversational thread. Associated with a tenant, holding ephemeral message history (role, content, optional tool call metadata, timestamp). Can be archived or cleared on demand.
- **ContextSnapshot**: Ephemeral runtime data structure assembled on the fly for prompt injection. Aggregates live data (current time, active tasks, upcoming events, next meal, critical pantry stock, active user memories) into a concise representation for the model.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The assistant starts streaming visible response tokens to the mobile user in less than 1.2 seconds from message dispatch under normal network conditions.
- **SC-002**: 100% of user profile preferences and active memories are accurately reflected in assistant answers and recommendations without manual re-entry.
- **SC-003**: The asynchronous memory extractor accurately identifies durable user facts with over 90% precision without adding any latency to the conversational stream.
- **SC-004**: Multi-domain action commands (e.g. adding a grocery item or creating a task) are executed successfully with correct parameters in over 95% of first-attempt requests.
- **SC-005**: Tapping the session reset button clears the conversation view in under 200 milliseconds while leaving 100% of persistent profile data and memories intact.
- **SC-006**: Zero data leakage or cross-tenant contamination across assistant queries in multi-tenant environments.
- **SC-007**: 100% of dev and test flows execute against PostgreSQL managed via Podman with zero SQLite divergence.

## Assumptions

- The mobile application connects to the backend API with an authenticated user session (JWT bearer token or equivalent).
- Development containers and PostgreSQL services are managed using Podman (`podman compose` / `podman run`).
- External AI model requests are mediated exclusively through the backend API to protect provider keys and enforce tenancy constraints.
- Conversation history is maintained in the active mobile session for immediate continuity and can be wiped locally or remotely without affecting core domain data.
- Read and create actions are executed automatically by the assistant; mass deletions or irreversible operations require explicit interactive user confirmation before execution.
