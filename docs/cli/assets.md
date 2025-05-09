# Assets CLI Commands

OpenMAS provides a set of CLI commands to manage assets defined in your project.

## Overview

The `openmas assets` command group helps you:

- List all assets defined in your project and their current status
- Download assets on-demand
- Verify the integrity of downloaded assets
- Clear the asset cache when needed

## Commands

### List Assets

```bash
openmas assets list
```

Lists all assets defined in your project configuration (`openmas_project.yml`) along with their current status.

**Output example:**

```
┏━━━━━━━━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Name            ┃ Version ┃ Type       ┃ Source               ┃ Status                               ┃ Cache Path                  ┃
┡━━━━━━━━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ llama3-8b       │ 1.0     │ model      │ hf:meta-llama/...    │ ✅ Downloaded and verified           │ ~/.openmas/assets/model/... │
│ prompt-templates│ latest  │ template   │ http://example.com/..│ ❌ Not found                         │ -                           │
│ knowledge-index │ 2023-06 │ index      │ local:/opt/shared/.. │ ⚠️ Downloaded but checksum mismatch │ ~/.openmas/assets/index/... │
└─────────────────┴─────────┴────────────┴─────────────────────┴─────────────────────────────────────┴────────────────────────────┘
```

The status column shows:
- ✅ Downloaded and verified: Asset is downloaded and checksum verified (if provided)
- ⚠️ Downloaded but checksum mismatch: Asset is downloaded but checksum doesn't match
- ❌ Not found: Asset is not in cache

### Download Asset

```bash
openmas assets download <asset_name>
```

Downloads a specific asset to the cache.

**Arguments:**

| Argument | Description |
|----------|-------------|
| `asset_name` | Name of the asset to download |

**Example:**

```bash
openmas assets download llama3-8b
```

Output:
```
Downloading asset "llama3-8b" (version 1.0)...
Source: Hugging Face Hub (meta-llama/Llama-3-8B)
Progress: ████████████████████████████████ 100%
Verifying checksum... OK
Asset downloaded to: /home/user/.openmas/assets/model/llama3-8b/1.0/model.safetensors
```

The command will:
1. Check if the asset exists in the project configuration
2. Determine the appropriate downloader based on the source type
3. Download the asset to the cache
4. Verify the checksum (if provided)
5. Unpack the asset (if configured)

### Verify Asset

```bash
openmas assets verify [asset_name]
```

Verifies the integrity of one or all cached assets.

**Arguments:**

| Argument | Description |
|----------|-------------|
| `asset_name` | (Optional) Name of the asset to verify. If omitted, all cached assets are verified. |

**Examples:**

Verify a specific asset:
```bash
openmas assets verify llama3-8b
```

Output:
```
Verifying asset "llama3-8b" (version 1.0)...
Expected checksum: sha256:a1b2c3d4e5f6...
Calculated checksum: sha256:a1b2c3d4e5f6...
Result: ✅ Verification successful
```

Verify all assets:
```bash
openmas assets verify
```

Output:
```
Verifying all cached assets...

llama3-8b (version 1.0):
  Expected checksum: sha256:a1b2c3d4e5f6...
  Calculated checksum: sha256:a1b2c3d4e5f6...
  Result: ✅ Verification successful

knowledge-index (version 2023-06):
  Expected checksum: sha256:1a2b3c4d5e6f...
  Calculated checksum: sha256:9z8y7x6w5v4...
  Result: ❌ Verification failed

Summary:
  Total assets: 2
  Passed: 1
  Failed: 1
```

### Clear Cache

```bash
openmas assets clear-cache [--asset ASSET_NAME] [--all]
```

Clears the asset cache, either for a specific asset or the entire cache.

**Options:**

| Option | Description |
|--------|-------------|
| `--asset`, `-a` | Name of the asset to clear from cache |
| `--all` | Clear the entire asset cache (will prompt for confirmation) |

**Examples:**

Clear a specific asset:
```bash
openmas assets clear-cache --asset llama3-8b
```

Output:
```
Clearing asset "llama3-8b" (version 1.0) from cache...
Cache location: /home/user/.openmas/assets/model/llama3-8b/1.0
Asset cache successfully cleared.
```

Clear all assets:
```bash
openmas assets clear-cache --all
```

Output:
```
This will clear the entire asset cache at:
/home/user/.openmas/assets/

Are you sure? [y/N]: y
Clearing asset cache...
Cache successfully cleared.
```

## Environment Variables

The asset CLI commands respect the same environment variables as the core asset management system:

| Environment Variable | Description | Default |
|----------------------|-------------|---------|
| `OPENMAS_ASSETS_DIR` | Override the default asset cache directory | `~/.openmas/assets/` |
| `OPENMAS_ENV` | Environment name for loading configuration | `local` |

## Examples

**Download all assets defined in your project:**

```bash
# List all assets
openmas assets list | grep "Not found" | awk '{print $1}' > missing_assets.txt

# Download each missing asset
while read asset; do
  openmas assets download $asset
done < missing_assets.txt
```

**Verify and re-download corrupted assets:**

```bash
# Verify all assets and capture results
openmas assets verify > verification_results.txt

# Extract failed assets
grep "failed" verification_results.txt | awk '{print $1}' > failed_assets.txt

# Re-download failed assets
while read asset; do
  openmas assets clear-cache --asset $asset
  openmas assets download $asset
done < failed_assets.txt
```
