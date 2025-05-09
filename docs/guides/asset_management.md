# Asset Management in OpenMAS

OpenMAS provides a robust Asset Management system to help developers manage, download, verify, and access external assets required by their agents. This guide explains how to configure and use this feature.

## Overview

The Asset Management feature allows you to:

- Declaratively define external assets required by your agents in your project configuration
- Automatically download and cache assets as needed
- Verify asset integrity with checksums
- Support various source types: HTTP, Hugging Face Hub, and local files
- Unpack archive formats when needed
- Access assets programmatically from your agents

## Configuring Assets

Assets are defined in your `openmas_project.yml` file in two main sections:

1. The global `assets` list defines all assets available to your project
2. Each agent's `required_assets` list specifies which assets that agent needs

### Global Assets Configuration

```yaml
# openmas_project.yml
name: "my_project"
version: "0.1.0"

# Define all assets used in the project
assets:
  - name: "llama3-8b"
    version: "1.0"
    asset_type: "model"
    description: "Llama 3 8B model weights"
    source:
      type: "hf"
      repo_id: "meta-llama/Llama-3-8B"
      filename: "model.safetensors"
      revision: "main"
    checksum: "sha256:a1b2c3d4e5f6..."
    unpack: false

  - name: "prompt-templates"
    version: "latest"
    asset_type: "template"
    description: "Collection of prompt templates"
    source:
      type: "http"
      url: "https://example.com/assets/prompt-templates.zip"
    checksum: "sha256:f6e5d4c3b2a1..."
    unpack: true
    unpack_format: "zip"

  - name: "knowledge-index"
    version: "2023-06"
    asset_type: "index"
    description: "Vector index of knowledge base"
    source:
      type: "local"
      path: "/opt/shared-assets/knowledge-index.bin"
    checksum: "sha256:1a2b3c4d5e6f..."
    unpack: false

# Settings for asset management
settings:
  assets:
    cache_dir: "/app/data/asset-cache"  # Optional, defaults to ~/.openmas/assets/
```

### Agent Asset Requirements

```yaml
# openmas_project.yml (continued)
agents:
  rag_agent:
    module: "agents.rag_agent"
    class: "RAGAgent"
    required_assets:
      - "llama3-8b"
      - "knowledge-index"

  template_agent:
    module: "agents.template_agent"
    class: "TemplateAgent"
    required_assets:
      - "prompt-templates"
```

## Asset Configuration Options

### Asset Configuration

| Field | Type | Description | Required |
|-------|------|-------------|----------|
| `name` | string | Unique name for the asset | Yes |
| `version` | string | Asset version | No (defaults to "latest") |
| `asset_type` | string | Type of asset (e.g., "model", "data", "template") | No (defaults to "model") |
| `source` | object | Source configuration (see below) | Yes |
| `checksum` | string | SHA256 checksum for verification (format: "sha256:<hex_digest>") | No |
| `unpack` | boolean | Whether to unpack an archive file | No (defaults to false) |
| `unpack_format` | string | Archive format ("zip", "tar", "tar.gz", "tar.bz2") | Yes if `unpack` is true |
| `description` | string | Human-readable description | No |

### Source Configurations

#### HTTP Source

```yaml
source:
  type: "http"
  url: "https://example.com/path/to/asset.file"
```

#### Hugging Face Hub Source

```yaml
source:
  type: "hf"
  repo_id: "organization/model-name"
  filename: "model.safetensors"  # File within the repo
  revision: "main"  # Optional: branch, tag, or commit hash
```

#### Local File Source

```yaml
source:
  type: "local"
  path: "/path/to/local/file.bin"  # Absolute path or relative to project root
```

## Asset Cache

By default, assets are cached in `~/.openmas/assets/`. This location follows this structure:

```
~/.openmas/assets/
  ├── model/                         # asset_type
  │   └── llama3-8b/                 # asset name
  │       └── 1.0/                   # asset version
  │           ├── model.safetensors  # the actual asset
  │           └── .asset_info.json   # metadata
  └── .locks/                        # lock files for concurrent access
```

You can override the cache location in three ways (in order of precedence):

1. Environment variable: `OPENMAS_ASSETS_DIR=/path/to/cache`
2. Project config: `settings.assets.cache_dir: "/path/to/cache"` in `openmas_project.yml`
3. Default: `~/.openmas/assets/`

## Using Assets in Agents

Agents can access their configured assets programmatically using the `asset_manager` provided by OpenMAS:

```python
from openmas.agent import BaseAgent
from pathlib import Path

class MyAgent(BaseAgent):
    async def setup(self):
        # Get path to a required asset
        model_path: Path = await self.asset_manager.get_asset_path("llama3-8b")
        self.model = load_model(model_path)

        # The asset_manager handles:
        # - Checking if the asset exists in cache
        # - Downloading if needed (with locking for concurrent access)
        # - Verifying integrity via checksum
        # - Unpacking archives if configured
        # - Returning the final path
```

The `get_asset_path()` method is asynchronous and will:

1. Look up the asset configuration by name
2. Check if it exists in the cache and is valid
3. Download it if necessary (with proper locking to prevent race conditions)
4. Verify its checksum (if provided)
5. Unpack it (if configured)
6. Return the path to the asset

## CLI Commands

OpenMAS provides CLI commands to manage assets:

```bash
# List all configured assets and their status
openmas assets list

# Download a specific asset
openmas assets download llama3-8b

# Verify asset integrity
openmas assets verify llama3-8b
openmas assets verify  # Verify all cached assets

# Clear asset cache
openmas assets clear-cache --asset llama3-8b  # Clear specific asset
openmas assets clear-cache --all  # Clear entire cache (with confirmation)
```

See the [Assets CLI documentation](../cli/assets.md) for more details.

## Concurrency and Locking

OpenMAS uses file-based locking to ensure that multiple processes can safely access the asset cache without conflicts. This is particularly important when:

- Multiple agents request the same asset simultaneously
- Multiple instances of the same agent are running across different processes
- Assets are being downloaded while others are trying to use them

The locking system is transparent to the agent code and is handled automatically by the asset manager.

## Best Practices

- **Always provide checksums** for important assets to ensure integrity
- **Consider unpacking large archives** directly in the cache to avoid duplicating storage
- **Use version tags** for assets to manage updates and ensure reproducibility
- **Set appropriate cache locations** based on your deployment environment:
  - Development: Use default or local directory
  - Docker: Mount a volume for the cache to persist between container restarts
  - Production: Consider a shared network volume for clusters
