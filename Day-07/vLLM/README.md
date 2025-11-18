# vLLM Documentation Repository

This directory contains the official documentation from the [vLLM project](https://github.com/vllm-project/vllm), synchronized using Git sparse-checkout to only include the `/docs` folder.

## Current Status

- **Total markdown files**: 161
- **Source**: https://github.com/vllm-project/vllm/tree/main/docs
- **Branch**: main
- **Last updated**: Check with `git log -1`

## Directory Structure

```
vllm_docs/
├── docs/
│   ├── api/              # API reference documentation
│   ├── cli/              # Command-line interface docs
│   ├── configuration/    # Configuration guides
│   ├── contributing/     # Contributing guidelines
│   ├── deployment/       # Deployment strategies
│   ├── design/           # Design documents and architecture
│   ├── features/         # Feature-specific documentation
│   ├── getting_started/  # Installation and quickstart
│   ├── models/           # Supported models documentation
│   ├── serving/          # Serving and inference guides
│   ├── training/         # Training-related docs
│   └── usage/            # Usage guides and FAQs
├── update_docs.sh        # Update script
└── README.md            # This file
```

## 🔄 Updating Documentation

### Option 1: Using the Update Script (Recommended)

Simply run the update script:

```bash
./vllm_docs/update_docs.sh
```

This script will:
- Fetch the latest changes from the vLLM repository
- Show you what has changed
- Update the documentation to the latest version
- Display statistics about the documentation

### Option 2: Manual Git Update

```bash
cd reference_file/vllm_docs
git fetch origin main
git reset --hard origin/main
```

### Option 3: Check for Updates Without Applying

```bash
cd reference_file/vllm_docs
git fetch origin main
git log HEAD..origin/main --oneline -- docs/
```

## Technical Details

This repository uses **Git sparse-checkout** to efficiently download only the `/docs` folder from the vLLM repository without cloning the entire codebase.

### Configuration

- **Remote**: https://github.com/vllm-project/vllm.git
- **Sparse-checkout pattern**: `docs/*`
- **Depth**: Shallow clone (depth=1) for efficiency

### Manual Setup (if needed)

If you need to recreate this setup from scratch:

```bash
mkdir -p reference_file/vllm_docs
cd reference_file/vllm_docs
git init
git remote add origin https://github.com/vllm-project/vllm.git
git config core.sparseCheckout true
echo "docs/*" > .git/info/sparse-checkout
git pull origin main --depth=1
```

## Using the Documentation

### For RAG (Retrieval-Augmented Generation)

These markdown files are perfect for building a RAG system:

1. **Text Extraction**: All files are in markdown format, easy to parse
2. **Structured Content**: Well-organized by topic
3. **Rich Information**: Comprehensive coverage of vLLM features

### Example: Building a Vector Database

```python
# Example using LangChain and ChromaDB
from langchain.document_loaders import DirectoryLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.embeddings import OpenAIEmbeddings
from langchain.vectorstores import Chroma

# Load all markdown files
loader = DirectoryLoader(
    'reference_file/vllm_docs/docs',
    glob="**/*.md",
    show_progress=True
)
documents = loader.load()

# Split documents into chunks
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=200
)
chunks = text_splitter.split_documents(documents)

# Create vector store
vectorstore = Chroma.from_documents(
    documents=chunks,
    embedding=OpenAIEmbeddings(),
    persist_directory="./vllm_docs_vectorstore"
)
```

## 🔍 Useful Commands

### Search for specific topics

```bash
# Find all documentation about "quantization"
grep -r "quantization" docs/ --include="*.md"

# Find specific configuration options
grep -r "tensor_parallel" docs/ --include="*.md"
```

### List all sections

```bash
ls -la docs/
```

### Count files by directory

```bash
find docs/ -type f -name "*.md" | sed 's|/[^/]*$||' | sort | uniq -c | sort -rn
```

## Notes

- This is a **read-only mirror** of the official vLLM documentation
- Do not make changes to files in this directory as they will be overwritten on update
- For the most up-to-date documentation, always run the update script
- The main repository may have additional content (images, code examples) not included here

## Links

- **vLLM GitHub**: https://github.com/vllm-project/vllm
- **vLLM Documentation Site**: https://docs.vllm.ai/
- **vLLM Blog**: https://blog.vllm.ai/

## Troubleshooting

### "Not a git repository" error

Run the manual setup commands above to reinitialize the repository.

### Merge conflicts

Since this is a read-only mirror, always use `--hard` reset:

```bash
git fetch origin main
git reset --hard origin/main
```

### Slow updates

The initial clone uses `--depth=1` for a shallow clone. Subsequent updates should be fast.
