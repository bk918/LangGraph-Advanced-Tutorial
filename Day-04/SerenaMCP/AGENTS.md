# SerenaMCP - Advanced Coding Agent Toolkit

## Overview

SerenaMCP is a powerful **Model Context Protocol (MCP) server** that transforms any LLM into a fully-featured coding agent capable of working directly on codebases. Unlike traditional coding assistants, Serena leverages Language Server Protocol (LSP) to provide **semantic code understanding and editing** at the symbol level, making it extremely efficient for large and complex projects.

## Key Features

### **Semantic Code Analysis**

- **Symbol-based Operations**: Find, edit, and navigate code using symbol names rather than text patterns
- **Language Server Integration**: Supports 16+ programming languages through unified LSP interface
- **Context-Aware Editing**: Precise code modifications without reading entire files

### **Advanced Tool System**

- **MCP Protocol**: Compatible with Claude, VSCode, Cursor, ChatGPT, and other MCP clients
- **Extensible Architecture**: Easy to add new tools and language support
- **Performance Optimized**: Efficient token usage and fast operations

### **Memory & Learning**

- **Project Knowledge**: Persistent memory system for project-specific information
- **Onboarding Process**: Automatic codebase learning and documentation
- **Context Preservation**: Maintains conversation state across sessions

## Architecture

### Core Components

#### **SerenaAgent** - Central Orchestrator

- **Project Management**: Handles multiple projects with individual configurations
- **Tool Coordination**: Manages 40+ specialized tools for different coding tasks
- **Language Server Management**: Coordinates LSP connections and symbol analysis
- **Memory System**: Maintains project knowledge and conversation context

#### **SolidLanguageServer** - LSP Abstraction Layer

- **Unified Interface**: Single API for 16+ programming languages
- **Symbol Analysis**: Advanced code understanding and navigation
- **Performance Optimization**: Caching and incremental analysis
- **Error Recovery**: Automatic language server restart on failures

#### **Tool System** - Specialized Functionality

- **File Operations**: Read, write, search, and modify files
- **Symbol Operations**: Find, edit, and navigate code symbols
- **Memory Management**: Store and retrieve project knowledge
- **Configuration Tools**: Project activation and mode switching

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
- **R** - languageserver R package
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

## Installation & Setup

### Quick Start

```bash
# Install Serena MCP server
uvx --from git+https://github.com/oraios/serena serena start-mcp-server

# Activate your project
# Serena will automatically detect language and create configuration
```

### Integration Options

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

## Tool Categories

### File Operations

- `read_file` - Read file contents (partial or complete)
- `create_text_file` - Create new files or overwrite existing ones
- `list_dir` - List directory contents with filtering
- `find_file` - Search for files using glob patterns
- `replace_regex` - Regex-based file modifications
- `search_for_pattern` - Advanced text pattern searching

### Symbol Analysis

- `find_symbol` - Global symbol search with name/path patterns
- `find_referencing_symbols` - Find all references to a symbol
- `get_symbols_overview` - Get top-level symbols in a file
- `replace_symbol_body` - Replace entire symbol definitions
- `insert_after_symbol` - Insert code after symbol definitions
- `insert_before_symbol` - Insert code before symbol definitions

### Memory & Knowledge

- `write_memory` - Store project-specific knowledge
- `read_memory` - Retrieve stored information
- `list_memories` - Browse available memories
- `delete_memory` - Remove outdated knowledge

### Project Management

- `activate_project` - Switch between projects
- `get_current_config` - View current configuration
- `switch_modes` - Change operational modes
- `onboarding` - Analyze and learn about new projects

## Configuration System

### Configuration Hierarchy

1. **Command-line Arguments** (highest priority)
2. **Project Configuration** (`.serena/project.yml`)
3. **User Configuration** (`~/.serena/serena_config.yml`)
4. **Context/Modes** (lowest priority)

### Contexts (Operating Environments)

- `desktop-app` - General desktop applications (default)
- `ide-assistant` - IDE integrations (VSCode, Cursor)
- `agent` - Custom agent frameworks (Agno)
- `codex` - OpenAI Codex CLI
- `chatgpt` - ChatGPT via mcpo bridge
- `oaicompat-agent` - OpenAI-compatible agents

### Modes (Operational Patterns)

- `planning` - Analysis and planning tasks
- `editing` - Direct code modification
- `interactive` - Back-and-forth conversation
- `one-shot` - Single response completion
- `onboarding` - Project learning phase
- `no-onboarding` - Skip learning phase

## Advanced Features

### Performance Optimizations

- **Symbol Caching**: Reduces language server overhead
- **Incremental Analysis**: Only processes changed code
- **Async Processing**: Non-blocking operations
- **Connection Pooling**: Efficient LSP connections

### Error Handling

- **Graceful Degradation**: Partial functionality on errors
- **Automatic Recovery**: Language server restart on crashes
- **Comprehensive Logging**: Detailed diagnostic information
- **Configuration Validation**: Prevents invalid setups

### Memory System

- **Markdown-based Storage**: Human-readable knowledge files
- **Contextual Retrieval**: Relevant information discovery
- **Persistent Learning**: Retains project knowledge across sessions
- **Onboarding Automation**: Automatic codebase analysis

## Comparison with Alternatives

### Advantages over Subscription Agents

- **Zero API Costs**: No usage-based billing
- **Self-hosted**: Complete data privacy
- **Framework Agnostic**: Works with any LLM
- **IDE Independent**: Not tied to specific editors

### Advantages over Traditional Tools

- **Semantic Understanding**: Symbol-level code comprehension
- **Multi-language Support**: 16+ languages in single tool
- **Persistent Memory**: Learns and remembers project context
- **Extensible Architecture**: Easy to add new capabilities

### Performance Benefits

- **Reduced Token Usage**: Efficient symbol-based operations
- **Faster Searches**: LSP-powered fast code navigation
- **Scalable**: Handles large codebases efficiently
- **Concurrent**: Multi-file operations in parallel

## Development & Extensibility

### Adding New Tools

```python
from serena.tools import Tool

class MyCustomTool(Tool):
    def apply(self, parameter: str) -> str:
        # Implement your tool logic here
        return "Tool result"
```

### Adding Language Support

1. Implement LSP client wrapper
2. Add language server configuration
3. Create test cases
4. Update documentation

### Custom Contexts/Modes

Create YAML configuration files in `~/.serena/` directory:

```yaml
# Custom context
name: my-context
prompt: "Custom instructions for my workflow"
excluded_tools: ["some_tool"]
included_optional_tools: ["my_custom_tool"]

# Custom mode
name: my-mode
prompt: "Mode-specific instructions"
```

## Use Cases

### Large Codebase Refactoring

- **Symbol Navigation**: Find all usages of functions/classes
- **Batch Editing**: Modify multiple files simultaneously
- **Impact Analysis**: Understand change consequences
- **Safe Modifications**: Precise symbol-level changes

### Multi-language Projects

- **Unified Interface**: Single tool for multiple languages
- **Cross-language References**: Navigate between languages
- **Consistent Operations**: Same commands across languages
- **Language-specific Optimization**: Tailored for each language

### Codebase Learning

- **Automated Onboarding**: Learn new codebases quickly
- **Knowledge Persistence**: Retain learning across sessions
- **Contextual Memory**: Project-specific information storage
- **Progressive Understanding**: Build knowledge over time

### Team Development

- **Shared Knowledge**: Team-wide project memory
- **Consistent Standards**: Enforce coding standards
- **Workflow Automation**: Automate repetitive tasks
- **Quality Assurance**: Integrated testing and validation

## Future Roadmap

### Planned Features

- **Debug Adapter Protocol**: Integrated debugging capabilities
- **Advanced LSP Features**: More language server functionality
- **VSCode Integration**: Direct IDE plugin
- **Performance Monitoring**: Real-time operation tracking
- **Custom Language Servers**: User-defined language support

### Extensibility Improvements

- **Plugin Architecture**: Third-party tool ecosystem
- **API Expansion**: More integration options
- **Performance Enhancements**: Faster operations
- **Enterprise Features**: Team and organization support

## Contributing

### Development Setup

```bash
git clone https://github.com/oraios/serena
cd serena
uv install  # Python package management
```

### Testing

```bash
# Run all tests
uv run poe test

# Run language-specific tests
uv run poe test -m "python"

# Run integration tests
uv run poe test:int
```

### Code Quality

```bash
# Format code
uv run poe format

# Type checking
uv run poe type-check

# Lint code
uv run poe lint
```

## License

SerenaMCP is released under the MIT License, making it free to use, modify, and distribute in both personal and commercial projects.

## Support

- **Documentation**: Comprehensive README with examples
- **Issues**: GitHub issue tracker for bug reports
- **Discussions**: Community discussions for questions
- **Sponsors**: GitHub Sponsors for development support

---

*SerenaMCP represents a new paradigm in coding assistance, combining the power of modern LLMs with the precision of language servers to create a truly intelligent coding companion.*
