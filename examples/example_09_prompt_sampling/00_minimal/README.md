# Prompt & Sampling Integration Example

This example demonstrates how an OpenMAS agent can load prompts from configuration and use a sampler, driven by project YAML config.

## What it Shows
- Loading a prompt from a template file using PromptManager
- Initializing a sampler from config
- Rendering a prompt and (mock) sampling

## Running the Example

From the OpenMAS repo root:

```bash
poetry run tox -e example-09-prompt-sampling
```

## Files
- `agents/prompt_sampling_agent.py`: The agent implementation
- `openmas_project.yml`: Project config with prompt and sampling
- `prompts/summarize.txt`: The prompt template
- `test_example.py`: Integration test for this example
