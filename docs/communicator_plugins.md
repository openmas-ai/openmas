# Communicator Plugin System

SimpleMAS provides a robust system for discovering and using communicator plugins. This allows for extending the framework with custom communication methods, both as installable packages (via entry points) and as local project extensions.

## Types of Plugins

The communicator plugin system supports three types of plugin sources:

1. **Built-in Communicators**: These are included with the SimpleMAS package (`HttpCommunicator`, etc.)
2. **Entry Point Plugins**: These are installed packages that register communicators via the `simple_mas.communicators` entry point
3. **Local Extensions**: These are project-local communicator implementations found in directories specified in `extension_paths`

## Using Communicator Plugins

To use a specific communicator in your agent, you can:

1. **Set it in the configuration**:

```python
config = {
    "name": "my_agent",
    "communicator_type": "my_custom_communicator",
    "extension_paths": ["./my_extensions"]  # Optional: For local extensions
}
agent = MyAgent(config=config)
```

2. **Pass it directly to the constructor**:

```python
from my_package import MyCustomCommunicator

agent = MyAgent(
    name="my_agent",
    communicator_class=MyCustomCommunicator
)
```

## Creating Communicator Plugins

There are two ways to create and distribute communicator plugins:

### 1. As an Installable Package (Entry Points)

To create a communicator plugin as an installable package:

1. Create a subclass of `BaseCommunicator`:

```python
from simple_mas.communication import BaseCommunicator

class MyCustomCommunicator(BaseCommunicator):
    async def send_request(self, target_service, method, params=None, response_model=None, timeout=None):
        # Your implementation here
        ...

    async def send_notification(self, target_service, method, params=None):
        # Your implementation here
        ...

    async def register_handler(self, method, handler):
        # Your implementation here
        ...

    async def start(self):
        # Your implementation here
        ...

    async def stop(self):
        # Your implementation here
        ...
```

2. Register it as an entry point in your package's `pyproject.toml`:

```toml
[project.entry-points."simple_mas.communicators"]
my_communicator = "my_package.module:MyCustomCommunicator"
```

Or in `setup.py`:

```python
setup(
    # ...
    entry_points={
        'simple_mas.communicators': [
            'my_communicator = my_package.module:MyCustomCommunicator',
        ],
    },
    # ...
)
```

### 2. As a Local Extension

To create a communicator as a local extension:

1. Create a Python file in your project directory (e.g., `./extensions/my_communicator.py`):

```python
from simple_mas.communication import BaseCommunicator

class MyLocalCommunicator(BaseCommunicator):
    # Implementation as above
    ...
```

2. Specify the extension path in your agent configuration:

```python
config = {
    "name": "my_agent",
    "communicator_type": "my_communicator",  # Uses the filename without .py
    "extension_paths": ["./extensions"]
}
agent = MyAgent(config=config)
```

## Discovery Order

When resolving a communicator type, SimpleMAS uses the following order:

1. Check if a communicator class is directly provided to the agent constructor
2. Look for the type in the registry (built-ins and entry points)
3. Search local extension paths for matching communicator implementations

## Environment Configuration

You can also configure the communicator type and extension paths through environment variables:

```bash
export COMMUNICATOR_TYPE=my_communicator
export EXTENSION_PATHS='["./extensions", "./plugins"]'  # JSON array
```

For agent-specific configuration with a prefix:

```bash
export MYAGENT_COMMUNICATOR_TYPE=my_communicator
export MYAGENT_EXTENSION_PATHS='["./extensions"]'
```

Then initialize the agent with:

```python
agent = MyAgent(env_prefix="MYAGENT")
```
