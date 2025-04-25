#!/usr/bin/env python
"""Example of using MCP decorators with McpAgent.

This example demonstrates how to create an MCP server agent using
the OpenMAS framework with the McpAgent class and MCP decorators.
"""

import asyncio
from typing import List

from pydantic import BaseModel

from openmas import McpAgent, mcp_prompt, mcp_resource, mcp_tool
from openmas.communication.mcp import McpSseCommunicator
from openmas.logging import configure_logging


# Define Pydantic models for input/output validation (optional)
class TodoItem(BaseModel):
    id: int
    text: str
    completed: bool = False


class TodoListResponse(BaseModel):
    items: List[TodoItem]
    count: int


class TodoAgent(McpAgent):
    """Agent that manages a simple to-do list using MCP.

    This agent demonstrates the use of MCP decorators to expose methods
    as tools, prompts, and resources that can be used by MCP clients.
    """

    def __init__(self, name: str):
        """Initialize the agent.

        Args:
            name: The name of the agent
        """
        super().__init__(name=name)

        # Set up the MCP communicator in server mode
        communicator = McpSseCommunicator(agent_name=self.name, service_urls={}, server_mode=True, http_port=8000)
        self.set_communicator(communicator)

        # Initialize the to-do list
        self._todos = [
            TodoItem(id=1, text="Learn OpenMAS", completed=True),
            TodoItem(id=2, text="Create MCP Agent", completed=False),
            TodoItem(id=3, text="Implement MCP tools", completed=False),
        ]

    # MCP Tool Examples

    @mcp_tool(description="Get the current to-do list")
    async def get_todos(self) -> dict:
        """Retrieve all to-do items.

        Returns:
            A dictionary containing the list of to-do items and the total count
        """
        return {"items": [todo.model_dump() for todo in self._todos], "count": len(self._todos)}

    @mcp_tool(name="add_todo", description="Add a new to-do item", output_model=TodoItem)
    async def add_todo_item(self, text: str) -> dict:
        """Add a new to-do item.

        Args:
            text: The text of the to-do item

        Returns:
            The newly created to-do item
        """
        # Generate a new ID
        new_id = max([todo.id for todo in self._todos], default=0) + 1

        # Create and add the new item
        todo = TodoItem(id=new_id, text=text, completed=False)
        self._todos.append(todo)

        return todo.model_dump()

    @mcp_tool(description="Mark a to-do item as completed")
    async def complete_todo(self, id: int) -> dict:
        """Mark a to-do item as completed.

        Args:
            id: The ID of the to-do item to mark as completed

        Returns:
            The updated to-do item or an error message
        """
        for todo in self._todos:
            if todo.id == id:
                todo.completed = True
                return {"success": True, "item": todo.model_dump()}

        return {"success": False, "error": f"Todo with ID {id} not found"}

    @mcp_tool(description="Delete a to-do item")
    async def delete_todo(self, id: int) -> dict:
        """Delete a to-do item.

        Args:
            id: The ID of the to-do item to delete

        Returns:
            Success status and optional error message
        """
        for i, todo in enumerate(self._todos):
            if todo.id == id:
                del self._todos[i]
                return {"success": True}

        return {"success": False, "error": f"Todo with ID {id} not found"}

    # MCP Prompt Examples

    @mcp_prompt(description="Generate a summary of the to-do list")
    async def todo_summary_prompt(self) -> str:
        """Generate a prompt for summarizing the current to-do list.

        Returns:
            A prompt for an LLM to generate a summary
        """
        completed = [todo for todo in self._todos if todo.completed]
        pending = [todo for todo in self._todos if not todo.completed]

        return f"""
        Please provide a summary of the following to-do list:

        Completed Tasks ({len(completed)}):
        {chr(10).join(f"- {todo.text}" for todo in completed)}

        Pending Tasks ({len(pending)}):
        {chr(10).join(f"- {todo.text}" for todo in pending)}

        Summarize the current status, progress, and what needs focus next.
        """

    @mcp_prompt(description="Generate a new to-do item description")
    async def generate_todo_prompt(self, topic: str, complexity: str = "medium") -> str:
        """Generate a prompt for creating a new to-do item.

        Args:
            topic: The general topic or area for the to-do item
            complexity: How complex the task should be (simple, medium, complex)

        Returns:
            A prompt for an LLM to generate a to-do item
        """
        return f"""
        Please create a specific, actionable to-do item related to: {topic}

        The complexity level should be: {complexity}

        The to-do item should be a single sentence that clearly describes what needs to be done.
        It should be specific enough that someone would know exactly what action to take.
        """

    # MCP Resource Examples

    @mcp_resource(uri="/todos", description="Get all to-dos in JSON format", mime_type="application/json")
    async def todos_resource(self) -> bytes:
        """Serve the current to-do list as a JSON resource.

        Returns:
            JSON representation of the to-do list
        """
        import json

        data = {
            "todos": [todo.model_dump() for todo in self._todos],
            "count": len(self._todos),
            "completed": sum(1 for todo in self._todos if todo.completed),
            "remaining": sum(1 for todo in self._todos if not todo.completed),
        }
        return json.dumps(data).encode("utf-8")

    @mcp_resource(uri="/dashboard", description="HTML dashboard for the to-do list", mime_type="text/html")
    async def dashboard_resource(self) -> bytes:
        """Serve an HTML dashboard for the to-do list.

        Returns:
            HTML content for a simple dashboard
        """
        completed = sum(1 for todo in self._todos if todo.completed)
        total = len(self._todos)
        completion_pct = (completed / total * 100) if total > 0 else 0

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Todo Dashboard</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; }}
                .dashboard {{ max-width: 800px; margin: 0 auto; }}
                .progress {{ background-color: #f0f0f0; height: 20px; border-radius: 10px; margin: 20px 0; }}
                .progress-bar {{
                    background-color: #4caf50;
                    height: 100%;
                    border-radius: 10px;
                    width: {completion_pct}%;
                }}
                .todo-list {{ list-style-type: none; padding: 0; }}
                .todo-item {{ padding: 10px; border-bottom: 1px solid #ddd; }}
                .completed {{ text-decoration: line-through; color: #888; }}
            </style>
        </head>
        <body>
            <div class="dashboard">
                <h1>Todo Dashboard</h1>
                <div class="stats">
                    <p>Completed: {completed}/{total} ({completion_pct:.1f}%)</p>
                </div>
                <div class="progress">
                    <div class="progress-bar"></div>
                </div>
                <h2>Tasks</h2>
                <ul class="todo-list">
        """

        for todo in sorted(self._todos, key=lambda t: (t.completed, t.id)):
            css_class = "todo-item completed" if todo.completed else "todo-item"
            html += f'<li class="{css_class}">{todo.text} (ID: {todo.id})</li>\n'

        html += """
                </ul>
            </div>
        </body>
        </html>
        """

        return html.encode("utf-8")

    # Example of using sample_prompt to generate todo suggestions
    @mcp_tool(description="Generate todo suggestions using LLM")
    async def generate_todo_suggestions(self, context: str, count: int = 3) -> dict:
        """Generate todo suggestions using an LLM through MCP sample_prompt.

        This demonstrates how an agent can use the sample_prompt method to
        request LLM generations through the MCP protocol.

        Args:
            context: Context about the type of tasks to generate
            count: Number of suggestions to generate (default: 3)

        Returns:
            A dictionary with generated suggestions
        """
        try:
            # Create messages for the LLM
            messages = [
                {
                    "role": "user",
                    "content": (
                        f"Generate {count} specific, actionable todo items related to: {context}. "
                        f"Each todo should be a single sentence that clearly describes what needs to be done. "
                        f"Return ONLY the numbered list of todos without any additional text."
                    ),
                }
            ]

            # Call sample_prompt on a target MCP service (replace with actual service name in real usage)
            # Note: This will only work if the agent is connected to an MCP service that
            # provides LLM capabilities through the sampling/createMessage method
            result = await self.sample_prompt(
                target_service="claude",  # This would be the actual MCP service name in real usage
                messages=messages,
                system_prompt="You are a helpful assistant that generates clear, actionable todo items.",
                temperature=0.7,
                max_tokens=250,
            )

            # Extract generated content
            generated_content = result.get("content", "")

            # Parse suggestions (simple implementation)
            suggestions = [
                line.strip()
                for line in generated_content.strip().split("\n")
                if line.strip() and not line.strip().isspace()
            ]

            return {
                "success": True,
                "suggestions": suggestions,
                "count": len(suggestions),
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "suggestions": [],
                "count": 0,
            }


async def main():
    """Run the TodoAgent example."""
    # Configure logging
    configure_logging(log_level="INFO")

    # Create and start the agent
    agent = TodoAgent("todo-agent")
    await agent.start()

    print("Todo MCP server running at http://localhost:8000/mcp")
    print("Press Ctrl+C to exit")

    try:
        # Keep the agent running until interrupted
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        # Stop the agent gracefully
        await agent.stop()
        print("Agent stopped")


if __name__ == "__main__":
    asyncio.run(main())
