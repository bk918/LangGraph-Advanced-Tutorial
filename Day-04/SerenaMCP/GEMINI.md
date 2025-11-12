# Project Overview

This project, `serena-agent`, is a powerful **Model Context Protocol (MCP) server** that transforms any LLM into a fully-featured coding agent capable of working directly on codebases. Unlike traditional coding assistants, Serena leverages the Language Server Protocol (LSP) to provide **semantic code understanding and editing** at the symbol level, making it extremely efficient for large and complex projects.

## Key Features

### 🧠 **Semantic Code Analysis**

- **Symbol-based Operations**: Find, edit, and navigate code using symbol names rather than text patterns.
- **Language Server Integration**: Supports 16+ programming languages through a unified LSP interface.
- **Context-Aware Editing**: Precise code modifications without reading entire files.

### 🔧 **Advanced Tool System**

- **MCP Protocol**: Compatible with Claude, VSCode, Cursor, ChatGPT, and other MCP clients.
- **Extensible Architecture**: Easy to add new tools and language support.
- **Performance Optimized**: Efficient token usage and fast operations.

### 💾 **Memory & Learning**

- **Project Knowledge**: Persistent memory system for project-specific information.
- **Onboarding Process**: Automatic codebase learning and documentation.
- **Context Preservation**: Maintains conversation state across sessions.

## Architecture

Serena is a dual-layer coding agent toolkit.

### Core Components

**1. SerenaAgent (`src/serena/agent.py`)**
- Central orchestrator managing projects, tools, and user interactions.
- Coordinates language servers, memory persistence, and the MCP server interface.
- Manages the tool registry and context/mode configurations.

**2. SolidLanguageServer (`src/solidlsp/ls.py`)**
- A unified wrapper around Language Server Protocol (LSP) implementations.
- Provides a language-agnostic interface for symbol operations.
- Handles caching, error recovery, and the lifecycle of multiple language servers.

**3. Tool System (`src/serena/tools/`)**
- **file_tools.py** - File system operations, search, regex replacements.
- **symbol_tools.py** - Language-aware symbol finding, navigation, and editing.
- **memory_tools.py** - Project knowledge persistence and retrieval.
- **config_tools.py** - Project activation, mode switching.
- **workflow_tools.py** - Onboarding and meta-operations.

**4. Configuration System (`src/serena/config/`)**
- **Contexts** - Define tool sets for different environments (e.g., `desktop-app`, `agent`, `ide-assistant`).
- **Modes** - Operational patterns (e.g., `planning`, `editing`, `interactive`, `one-shot`).
- **Projects** - Per-project settings and language server configurations.

### Architecture Layers

```
┌─────────────────────────┐
│      MCP Server         │  ← FastMCP Framework
├─────────────────────────┤
│     SerenaAgent         │  ← Core Orchestrator
├─────────────────────────┤
│   Tool System          │  ← 40+ Specialized Tools
│  • File Tools          │  ← File Operations
│  • Symbol Tools        │  ← Symbol Analysis/Editing
│  • Memory Tools        │  ← Knowledge Management
│  • Config Tools        │  ← Project Management
├─────────────────────────┤
│   Language Server       │  ← LSP Protocol Layer
│   • 16+ Languages      │  ← Multi-language Support
│   • Symbol Cache       │  ← Performance Optimization
│   • Error Recovery     │  ← Reliability Features
├─────────────────────────┤
│   Configuration         │  ← YAML-based Settings
│   • Contexts/Modes     │  ← Environment Adaptation
│   • Project Configs    │  ← Per-project Settings
└─────────────────────────┘
```

## Supported Languages

Serena provides out-of-the-box support for:

- **Python** - Full Jedi LSP integration
- **TypeScript/JavaScript** - TypeScript LSP with JS support
- **PHP** - Intelephense LSP (premium features with license key)
- **Go** - gopls language server
- **R** - `languageserver` R package
- **Rust** - rust-analyzer from toolchain
- **C/C++** - clangd language server
- **Zig** - ZLS (Zig Language Server)
- **C#** - OmniSharp LSP
- **Ruby** - ruby-lsp (with Solargraph fallback)
- **Swift** - sourcekit-lsp
- **Kotlin** - kotlin-lsp (pre-alpha)
- **Java** - Eclipse JDT Language Server
- **Clojure** - clojure-lsp
- **Dart** - dart-ls
- **Bash** - bash-language-server
- **Lua** - lua-language-server (auto-download)
- **Nix** - nixd language server
- **Elixir** - NextLS (Windows not supported)
- **Erlang** - erlang_ls (experimental)
- **AL** - AL Language extension for Dynamics 365

# Building and Running

The project uses `uv` for dependency management and `hatchling` for building. The `pyproject.toml` file defines the project's dependencies and scripts.

## Key Commands

- **Install dependencies:**
  ```bash
  uv pip install -e .
  ```

- **Run the MCP server:**
  ```bash
  uv run serena-mcp-server --project <path_or_name>
  ```

- **Run tests:**
  ```bash
  # Run tests with default markers (excludes java/rust by default)
  uv run poe test

  # Run specific language tests
  uv run poe test -m "python or go"
  ```
  Available pytest markers for selective testing: `python`, `go`, `java`, `rust`, `typescript`, `php`, `csharp`, `elixir`, `terraform`, `clojure`, `swift`, `bash`, `ruby`, `ruby_solargraph`, `snapshot`.

- **Lint and format:**
  ```bash
  # Check code style without fixing
  uv run poe lint

  # Format code (BLACK + RUFF)
  uv run poe format
  ```

- **Type-check:**
    ```bash
    uv run poe type-check
    ```

- **Index a project:**
    ```bash
    uv run index-project
    ```

## Integration Options

#### **Claude Code Integration**

```bash
claude mcp add serena -- uvx --from git+https://github.com/oraios/serena serena start-mcp-server --context ide-assistant --project $(pwd)
```

#### **VSCode/Cursor Integration**

```json
{
  "mcpServers": {
    "serena": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/oraios/serena", "serena", "start-mcp-server", "--context", "ide-assistant"]
    }
  }
}
```

#### **ChatGPT Integration (via mcpo)**

```bash
mcpo add serena -- uvx --from git+https://github.com/oraios/serena serena start-mcp-server --context chatgpt
```

# Development Conventions

- **Coding Style:** The project uses `black` for code formatting and `ruff` for linting. The configurations are defined in `pyproject.toml`.
- **Typing:** The project uses type hints and `mypy` for static type checking.
- **Testing:** The project uses `pytest` for testing. Tests are located in the `test` directory. The tests are categorized by language server using pytest markers.

## Configuration Hierarchy

Configuration is loaded from (in order of precedence):
1. Command-line arguments to `serena-mcp-server`
2. Project-specific `.serena/project.yml`
3. User config `~/.serena/serena_config.yml`
4. Active modes and contexts

## Adding New Languages
1. Create a language server class in `src/solidlsp/language_servers/`.
2. Add it to the `Language` enum in `src/solidlsp/ls_config.py`.
3. Update the factory method in `src/solidlsp/ls.py`.
4. Create a test repository in `test/resources/repos/<language>/`.
5. Write a test suite in `test/solidlsp/<language>/`.
6. Add a pytest marker to `pyproject.toml`.

## Adding New Tools
1. Inherit from the `Tool` base class in `src/serena/tools/tools_base.py`.
2. Implement the required methods and parameter validation.
3. Register the tool in the appropriate tool registry.
4. Add the tool to context/mode configurations.

## Documentation and Internationalization

This project has undergone a comprehensive documentation effort to add detailed Korean docstrings and comments to the entire Python codebase (`src/**/*.py`). This makes the project highly accessible to Korean-speaking developers.

**Key Highlights:**
- **Extensive Korean Documentation:** Over 90% of the core Python source code is now documented in Korean, including file-level, class-level, and function-level docstrings.
- **Improved Readability & Maintainability:** The Korean comments clarify the purpose, architecture, and implementation details of each module.
- **Developer Onboarding:** The detailed documentation significantly lowers the barrier for new developers to understand the project's complex architecture.

**Well-Documented Core Modules:**
The commenting effort has particularly focused on clarifying the core logic of the agent. Key modules that are now thoroughly documented in Korean include:
- `src/serena/agent.py`: The central orchestrator of the Serena agent.
- `src/serena/tools/tools_base.py`: The base classes and structure for the entire tool system.
- `src/solidlsp/ls.py`: The abstraction layer for interacting with various Language Server Protocols.
- `src/serena/project.py`: The project management system.
- `src/serena/config/serena_config.py`: The core configuration management for the agent.

This systematic documentation, guided by the plan in `docs/commenting-plan.md`, ensures that the project is not only powerful in its features but also transparent and easy to contribute to.
