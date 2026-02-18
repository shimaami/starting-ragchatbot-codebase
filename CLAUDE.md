# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## ⚠️ IMPORTANT: Use `uv` for All Dependency Management

**Never use `pip` directly.** Always use `uv`:
- `uv sync` - Install/sync dependencies
- `uv run` - Run any Python command
- Dependencies in `pyproject.toml`, locked in `uv.lock`

## Quick Commands

**Start development server:**
```bash
./run.sh
# or manually:
cd backend && uv run uvicorn app:app --reload --port 8000
```

**Install/sync dependencies:**
```bash
uv sync
```

**Access application:**
- Web UI: `http://localhost:8000`
- API docs: `http://localhost:8000/docs` (Swagger UI)

**Test API endpoint:**
```bash
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Your question here", "session_id": null}'
```

**View course statistics:**
```bash
curl http://localhost:8000/api/courses
```

## Required Setup

1. **Environment variables:** Create `.env` file with `ANTHROPIC_API_KEY=sk-ant-...`
2. **Python version:** 3.13+ (check with `python --version`)
3. **Package manager:** `uv` must be installed
4. **Course documents:** Place `.txt` files in `docs/` folder; they auto-load on server startup

## System Architecture

This is a **Retrieval-Augmented Generation (RAG) chatbot** for educational content. The system has two main flows:

### Document Ingestion Pipeline
```
Course Files (.txt)
  ↓
DocumentProcessor (parses metadata, extracts lessons, chunks content)
  ↓
VectorStore (creates embeddings, stores in ChromaDB)
  ↓
Two ChromaDB Collections:
  - course_catalog: metadata (titles, instructors, lessons)
  - course_content: lesson chunks with embeddings
```

### Query Processing Pipeline
```
User Query (frontend)
  ↓
FastAPI /api/query endpoint
  ↓
RAGSystem.query() orchestrates:
  1. Retrieves conversation history from SessionManager
  2. Calls AIGenerator.generate_response() with Claude API
  3. Claude evaluates if search needed (tool_use decision)
  ↓
Two possible paths:

  Path A - Answer from knowledge:
    Claude → Returns answer directly (no tools called)

  Path B - Search needed:
    Claude → Calls search_course_content tool
    ↓
    ToolManager.execute_tool() → CourseSearchTool.execute()
    ↓
    VectorStore.search() (semantic search + filters)
    ↓
    Formats results with course/lesson metadata
    ↓
    Returns to Claude with search results
    ↓
    Claude generates answer using search results + history + system prompt
  ↓
Response sent to frontend with sources
  ↓
SessionManager stores exchange for conversation context
```

**Key insight:** Claude decides whether to search based on the query and system prompt. Not all queries trigger a search.

## Critical Design Patterns

### 1. **Tool-Based Search Architecture**
- Claude has access to `search_course_content` tool (defined in `search_tools.py`)
- Tool invocation is automatic (`tool_choice: auto`) - Claude decides if search is needed
- Single tool per query maximum (enforced in system prompt)
- Sources are extracted from search tool and returned to frontend

**Relevant files:** `ai_generator.py` (handles tool execution), `search_tools.py` (tool definitions), `vector_store.py` (actual search)

### 2. **Session-Based Conversation History**
- Each user gets a unique `session_id` (format: `session_N`)
- SessionManager stores messages as `Message(role, content)` objects
- History is formatted as string and included in Claude's system prompt for context
- Max history: 2 exchanges per config (prevents context bloat)
- History limits: kept at `max_history * 2` messages (auto-truncates oldest)

**Relevant file:** `session_manager.py`

### 3. **Embedding-Based Search**
- Uses Sentence-Transformers model `all-MiniLM-L6-v2` for embeddings
- ChromaDB handles vector storage and similarity search
- Search supports optional filters: `course_name` and `lesson_number`
- Returns top 5 results by default (`MAX_RESULTS` in config)
- Results preserve metadata (course title, lesson number) for context

**Relevant file:** `vector_store.py`

### 4. **Document Processing**
- Expected format: metadata in first 3 lines, then lessons (format: `Lesson N: Title`)
- Chunking is sentence-based with overlap (default: 800 char chunks, 100 char overlap)
- First chunk of each lesson includes context header: `"Lesson N content: [text]"`
- Fallback: if no lessons found, entire content is chunked as single document

**Relevant file:** `document_processor.py`

## Key Files and Responsibilities

| File | Purpose |
|------|---------|
| `backend/app.py` | FastAPI server, `/api/query` and `/api/courses` endpoints, document loading on startup |
| `backend/rag_system.py` | Main orchestrator: coordinates document processing, vector store, AI generation, sessions |
| `backend/ai_generator.py` | Claude API integration: handles tool use, conversation history in system prompt, multi-turn tool execution |
| `backend/vector_store.py` | ChromaDB wrapper: semantic search, embedding management, metadata filtering |
| `backend/document_processor.py` | Parses course files, extracts metadata, chunks text with overlap, creates Lesson/CourseChunk objects |
| `backend/session_manager.py` | In-memory conversation storage: creates sessions, stores message history, auto-truncates |
| `backend/search_tools.py` | Tool definitions: CourseSearchTool (implements search interface), ToolManager (registers/executes tools) |
| `backend/models.py` | Pydantic models: Course, Lesson, CourseChunk, Message |
| `backend/config.py` | Configuration constants: API keys, model names, chunk sizes, history limits |
| `frontend/index.html` | Web UI: chat interface with sidebar, suggested questions |
| `frontend/script.js` | Client logic: sends queries to `/api/query`, displays responses, manages session ID |

## Configuration

**Key settings** (in `backend/config.py`):
- `ANTHROPIC_MODEL`: Claude Sonnet 4 (claude-sonnet-4-20250514)
- `EMBEDDING_MODEL`: all-MiniLM-L6-v2
- `CHUNK_SIZE`: 800 characters
- `CHUNK_OVERLAP`: 100 characters
- `MAX_RESULTS`: 5 search results per query
- `MAX_HISTORY`: 2 conversation exchanges
- `CHROMA_PATH`: ./chroma_db (persisted vector database)

## Important Implementation Details

### Claude System Prompt
Located in `ai_generator.py:8-30`. Contains:
- Search tool usage guidelines (max 1 search per query)
- Response protocol (general knowledge vs course-specific)
- Formatting requirements (brief, concise, no meta-commentary)

**Important:** Modify this if you need to change Claude's behavior without changing code logic.

### Tool Execution Flow (Multi-Turn)
1. Claude returns `stop_reason="tool_use"` with tool call in content
2. `AIGenerator._handle_tool_execution()` extracts tool use block
3. Tool is executed and results formatted
4. Claude is called AGAIN with tool results added to messages
5. Second response (from step 4) is the final response to user

**Relevant code:** `ai_generator.py:89-135`

### Session Lifecycle
```
1. User sends first message (no session_id)
2. /api/query creates new session via session_manager.create_session()
3. Session ID returned to frontend in QueryResponse
4. Frontend stores session_id and includes in subsequent requests
5. SessionManager retrieves history for that session
6. After each query, add_exchange() stores the Q&A pair
7. Session persists in-memory during server runtime (lost on restart)
```

## Common Development Tasks

### Managing Dependencies
- **Add a dependency:** Edit `pyproject.toml`, then run `uv sync`
- **Update dependencies:** `uv sync --upgrade`
- **Run a script:** `uv run python script.py` (not `python script.py`)
- **Install tools:** Always use `uv run` prefix
- Never use `pip`, `pip3`, or `python -m pip`

### Add a New Course Document
1. Create `.txt` file in `docs/` folder with format:
   ```
   Course Title: My Course
   Course Link: https://example.com
   Course Instructor: Instructor Name

   Lesson 0: Introduction
   Lesson Link: https://example.com/lesson0
   [lesson content]

   Lesson 1: Main Topic
   [lesson content]
   ```
2. Restart server - documents auto-load in `app.py` startup event
3. Test with `/api/courses` endpoint

### Modify Claude's Behavior
Edit `AIGenerator.SYSTEM_PROMPT` in `ai_generator.py`. Examples:
- Change response style (concise vs detailed)
- Add/remove constraints on tool usage
- Adjust search decision logic instructions

### Adjust Search Quality
Modify in `backend/config.py`:
- `CHUNK_SIZE`/`CHUNK_OVERLAP`: Larger chunks = more context, smaller = more precise chunks
- `MAX_RESULTS`: Return more/fewer search results
- Or modify embedding model in `VectorStore.__init__()` (requires re-embedding all documents)

### Debug a Query
1. Add `print()` statements in `rag_system.query()` to log conversation history
2. Check `/api/courses` to verify documents loaded
3. Use `/docs` Swagger UI to manually test `/api/query` with specific queries
4. Enable hot-reload: server auto-restarts on file changes in `backend/`

### Add a Filter to Search
Extend `CourseSearchTool.get_tool_definition()` to add new parameter (e.g., `date_range`), update `execute()` method signature, then modify `VectorStore.search()` to apply the filter.

## Testing Strategy

No automated tests exist. Manual testing approaches:

**API Testing:**
```bash
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"query":"What is lesson 0 about?", "session_id":null}'
```

**Multi-turn Conversation:**
1. Send query 1, capture returned `session_id`
2. Send query 2 with that `session_id`
3. Check that Claude references context from query 1

**Search Verification:**
1. Query for specific course content
2. Check `/docs` response shows sources
3. Verify sources match expected lessons

## Deployment Notes

- **Vector database:** Persisted in `backend/chroma_db/` - required for consistent search
- **Session data:** In-memory only - lost on server restart (consider adding persistence if needed)
- **CORS:** Enabled for all origins (`allow_origins=["*"]`)
- **Hot reload:** Enabled by default (development mode)

## Dependencies

Key packages (see `pyproject.toml` for full list):
- `fastapi` - Web framework
- `uvicorn` - ASGI server
- `chromadb` - Vector database
- `sentence-transformers` - Embeddings
- `anthropic` - Claude API client

No external services required except Anthropic API.
