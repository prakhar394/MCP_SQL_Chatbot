
# MCP Agent – Refactored Chatbot UI & Agentic Architecture

This version of the chat agent keeps the **core logic and behavior identical** to the original
(MCP client, RAG + SQL tools, and multi-step LLM pipeline) but reorganizes the **UI and client-side code** so it feels
much more like a modern chatbot / agent console.

## High‑Level Architecture

The system has three main layers:

1. **Agent Orchestrator (`lily_client/client.py`)**
   - Maintains a `message_history` for the conversation.
   - Runs a multi‑step agentic loop for each user query:
     1. **Query Analysis** – `analyze_query(...)`
        - Checks whether the query is in scope (refrigerator/dishwasher parts).
        - Decides whether retrieval from tools is needed.
     2. **Retrieval Tools** – `retrieve_information(...)`
        - Calls MCP tools for:
          - RAG over repair guides / blog posts.
          - SQL over the structured parts catalog.
        - Returns a list of `ToolResult` objects that become part of the context.
     3. **Answer Drafting** – `generate_response(...)`
        - Uses the LLM with conversation history + retrieved tool results to propose an answer.
     4. **Validation Loop** – `validate_response(...)`
        - A separate “judge” model checks:
          - Is the answer appropriate?
          - Does it stay in scope (fridge / dishwasher parts)?
          - Is it hallucinated / conflicting with retrieved data?
        - If validation fails but provides feedback, a synthetic `ToolResult` with that feedback is added and the
          agent regenerates a better answer (up to a small number of attempts).
     5. **Commit to History**
        - The final answer is appended to `message_history` and returned to the UI.

   - The agent uses Pydantic models like `QueryAnalysis`, `ToolCall`, `BatchToolCall`, `ToolResult`, and
     `ResponseValidation` to make the tool‑calling logic explicit and inspectable.

2. **MCP Tool Servers (`mcp_servers/`)**
   - **RAG server**: wraps the FAISS vector stores backed by CSV‑derived content (repairs, blogs).
   - **SQL / parts server**: exposes structured queries over the parts catalog (pricing, install difficulty,
     install time, symptoms, appliance mapping, etc.).
   - The Quart app connects to these via Model Context Protocol (MCP) using the async client in `lily_client/client.py`.

3. **Web API & Chat UI (`lily_client/web`)**
   - **Quart application (`app.py`)**
     - Exposes endpoints:
       - `GET /` – serves the new chat UI.
       - `POST /api/chat` – streams the agent’s response via Server‑Sent Events (SSE).
       - `POST /api/regenerate` – streams a regenerated answer for the last query.
       - `POST /api/reset` – clears server‑side history and returns a fresh introduction message.
     - Manages a single global `MCPClient` instance and connects it to the RAG + SQL MCP servers on startup.
   - **Static assets**
     - `static/css/style.css` – new, fully redesigned styling for an agent console UI.
     - `static/js/chat.js` – new front‑end interaction logic (no inline scripts in the template).

## What is great about the UI

### 1. Modern Chatbot‑First UI

- The old Tailwind‑styled single‑column layout has been replaced with a **two‑pane agent console**:
  - **Left Sidebar**
    - Branding (“PartSelect Agent”).
    - Live‑style “Agent Status” badges for the orchestrator, RAG knowledge base, and SQL catalog.
    - Example prompts that stay within scope.
  - **Main Chat + Timeline**
    - Center: chat messages with user and agent avatars, bubbles, timing metadata, and streaming output.
    - Right: “Agent Run Timeline” panel describing the high‑level phases of each run (analysis → retrieval → draft → validation).

- Messages are rendered as **bubbles** with:
  - Role labels (“User” / “Agent”).
  - Subtle metadata (response type, duration).
  - Typing indicator with animated dots while the agent is thinking.

### 2. Clean Separation of Template, Styles, and Logic

- `templates/index.html`
  - Now only defines layout and containers.
  - Loads a single compiled stylesheet (`static/css/style.css`) and a separate script (`static/js/chat.js`).
  - No large inline `<script>` block – easier to reason about, test, and modify.

- `static/css/style.css`
  - Completely rewritten.
  - Dark, console‑style theme suitable for an AI agent dashboard.
  - Responsive layout:
    - Hides the sidebar on small screens.
    - Collapses the timeline on very narrow devices.

- `static/js/chat.js`
  - Encapsulates all client‑side behavior:
    - Renders the welcome message on load.
    - Handles the send flow via `POST /api/chat` with streaming SSE.
    - Provides a “soft regeneration” shortcut by double‑clicking the timeline panel, which calls `POST /api/regenerate` for the last user query.
    - Resets conversation using `POST /api/reset` and re‑injects the introduction.
  - Re‑implements the SSE loop with simpler, well‑named helper functions (`streamResponse`, `createMessage`, `createTypingIndicator`, etc.), while preserving the **same output contract** (`{"response": "..."}` / `{"error": "..."}` per SSE chunk).

### 3. Logic & Output Compatibility

- The **back‑end agent logic is intentionally unchanged**:
  - `MCPClient.process_query(...)` and `MCPClient.regenerate_response(...)` still implement the same multistep pipeline.
  - MCP tool servers and data ingestion are unchanged – you’ll get the same answers given the same environment and data.
  - API endpoints and SSE response format remain the same, so only the front‑end surface has been redesigned.

- This means:
  - You can still run the same import scripts / MCP servers.
  - Any Loom demo you already planned around the original behavior will still reflect what the agent is doing under the hood.

## Running the Project

From the project root (`partselect-agent-main-final/` in this refactored version):

1. **Start MCP servers** (RAG + SQL) in separate terminals as before.
2. **Install client/web dependencies**:

   ```bash
   cd lily_client
   pip install -r requirements.txt
   ```

3. **Run the Quart web app**:

   ```bash
   cd web
   python app.py
   ```

4. Open the browser at `http://localhost:5000` (or whatever host/port you configured).

You should now see the new agentic chat UI.
