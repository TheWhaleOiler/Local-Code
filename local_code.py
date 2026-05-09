import os
import time

from src.mcp.mcp import mcp_agent
os.environ['PYTHONUNBUFFERED'] = '1'

import requests
import sys

import json
from pathlib import Path

from env import OLLAMA_HOST


DEFAULT_MODEL = "ministral-3:14b" or "llama3.1:8b" or "phi3.5"
MAX_CONTEXT = 4096
COMPRESSION_THRESHOLD = 0.75  # 75%


COMPRESSION_PROMPT = """Create a concise markdown summary with these headers:

## User
Key facts about the user (name, preferences, etc.)

## Topics
Topics that were discussed

## Key Points
Important details, conclusions, or decisions

Conversation:
{context_text}

Summary:"""



def count_tokens(text: str) -> int:
    return len(text) // 4


def get_total_tokens(messages: list) -> int:
    return sum(count_tokens(m["content"]) for m in messages)


def load_context_summary() -> str:
    if Path("context_summary.md").exists():
        with open("context_summary.md") as f:
            return f.read()
    return ""


def load_prompts_from_md(filename: str) -> str:
    """Load system prompt from a markdown file."""
    if Path(filename).exists():
        with open(filename) as f:
            return f.read()

    raise Exception()


def compress_to_md(messages: list) -> str:
    import requests
    context_text = "\n".join(f"{m['role']}: {m['content']}" for m in messages)

    prompt = COMPRESSION_PROMPT.format(context_text=context_text)

    response = requests.post(
        f"{OLLAMA_HOST}/api/chat",
        json={
            "model": DEFAULT_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "options": {
                "max_tokens": 8000
            },
            "temperature": 0.1
        },
        timeout=60 * 5,
    )

    summary_parts = []
    for line in response.text.strip().split('\n'):
        if line:
            try:
                data = json.loads(line)
                msg = data.get('message', {})
                if msg.get('content'):
                    summary_parts.append(msg['content'])
                if data.get('done'):
                    break
            except:
                pass
    summary = ''.join(summary_parts)

    with open("context_summary.md", "w") as f:
        f.write(summary)

    return summary


def execute_tool(tool_name: str, args: tuple[str, str]) -> str:
    import requests
    import subprocess
    
    tool_name = tool_name.strip().lower()
    arg1, arg2 = args
    
    if tool_name == "python":
        try:
            # Pre-import common modules
            wrapped_code = f"""{arg1}"""
            result = subprocess.run(
                ["python3", "-c", wrapped_code],
                capture_output=True,
                text=True,
                timeout=30
            )
            output = result.stdout
            if result.stderr:
                output += f"Error: {result.stderr}"
            return output or "No output"
        except Exception as e:
            return f"Error: {e}"
    
    elif tool_name == "search":
        try:
            response = requests.get(arg1, timeout=30)
            return response.text[:5000]  # Limit response length
        except Exception as e:
            return f"Error: {e}"
    
    elif tool_name == "read_file":
        try:
            with open(arg1) as f:
                content = f.read()
                return content[:5000]  # Limit response length
        except Exception as e:
            return f"Error: {e}"
    
    elif tool_name == "write_file":
        try:
            path, content = arg1, arg2
            with open(path, "w") as f:
                f.write(content)
            return f"Written to {path}"
        except Exception as e:
            return f"Error: {e}"
    
    elif tool_name == "exit":
        return "EXIT"
    
    return f"Unknown tool: {tool_name}"


def extract_tool_call(_json: dict) -> tuple[str, str, str] | None:
    if _json["tool"] in ['python', 'search', 'read_file', 'write_file', 'exit']:
        return _json["tool"], _json["arg1"], _json["arg2"]
    
    return 'exit', '', ''


def get_user_confirmation(command: str) -> bool:

    if not sys.stdin.isatty():
        print(f"\nCommand:\n{command}\n[Y/N]: ", end="")

        import select
        if select.select([sys.stdin], [], [], 0)[0]:
            response = input().strip().lower()
            if response in ['y', 'yes']:
                return True
            elif response in ['n', 'no']:
                return False
        print("Y (auto)")
        return True
    while True:
        response = input(f"\n\nCommand:\n{command}\n[Y/N]: ").strip().lower()
        if response in ['y', 'yes']:
            return True
        elif response in ['n', 'no']:
            return False


def base_agent(messages: list, temperature: float = 0.2) -> dict:
    response = requests.post(
        f"{OLLAMA_HOST}/api/chat",
        json={
            "model": DEFAULT_MODEL,
            "messages": messages,
            "stream": True,
            "temperature": temperature,
        },
        stream=True,
        timeout=60 * 5,
    )

    output = []
    
    for line in response.iter_lines():
        if line:
            try:
                data = json.loads(line)
                content = data.get('message', {}).get('content', '')
                if content:
                    sys.stdout.write(content)
                    sys.stdout.flush()
                    output.append(content)
            except:
                pass
    
    result = ''.join(output)

    return {"role": "assistant", "content": result}

def tool_selection_agent(messages: list) -> dict:
   
    prompt = load_prompts_from_md("tool_selection_agent.md")
    
    full_messages = [{"role": "system", "content": prompt}]
    full_messages.extend(messages)

    return base_agent(full_messages)


def reasoning_agent(messages: list,) -> dict:

    prompt = load_prompts_from_md("reasoning_agent.md")
    
    # Build context with tool selection info
    full_messages = [{"role": "system", "content": prompt}]
    full_messages.extend(messages)

    return base_agent(full_messages)



def chat_with_reasoning(messages: list, max_iterations: int = 10) -> dict:

    for iteration in range(max_iterations):

        print(json.dumps(messages))

        # Reasoning Agent (full context + selected tool)

        reasoning_json = reasoning_agent(messages)

        messages.append(reasoning_json)
        
        print("\n--- Reasoning done ---\n")

        print(json.dumps(reasoning_json,indent=2))

        # MCP CODE

        error, tool_info = mcp_agent(reasoning_json)
        
        if(error):
            messages.append(error)
            continue
        
        if tool_info["tool"] == "exit":
            print(f"\n[Exiting with final answer]")
            return tool_info["answer"]
        
        # Execute tool
        confirmation = get_user_confirmation(f"{tool_info['tool']}({tool_info['arg1']}, {tool_info['arg2']})")
        
        if confirmation:
            result = execute_tool(tool_info["tool"], (tool_info["arg1"], tool_info["arg2"]))
            print(f"\n[Executed: {tool_info['tool']}({tool_info['arg1']}, {tool_info['arg2']})] {result}")
            
            messages.append({"role": "system", "content": f"Tool {tool_info['tool']} returned: {result}"})
        else:
            print("\n[Tool denied by user]")
            return tool_info["answer"]
        
    #success_json = success_agent([user_query,{"role": "system", "content": f"Tool {tool_name} returned: {result}"}, reasoning_json, tool_selection_json, tool_json])
    
    return tool_info["answer"]


def print_header():
    print("=" * 50)
    print(f"=== {DEFAULT_MODEL} Chat CLI ===")
    print(f"Model: {DEFAULT_MODEL} ({MAX_CONTEXT:,} context)")
    print("Type 'exit', 'quit', 'q' or '/compress' to compress context")
    print("=" * 50)
    print()


def main():
    print_header()

    if Path("context_summary.md").exists():
        Path("context_summary.md").unlink()

    summary = load_context_summary()
    if summary:
        messages = [{"role": "system", "content": f"Context summary:\n{summary}"}]
    else:
        messages = []

    while True:
        try:
            user_input = input("You: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye!")
            break

        if user_input.lower() in ["exit", "quit", "q"]:
            print("Goodbye!")
            break

        if user_input.lower() == "/compress":
            compress_to_md(messages)
            summary = load_context_summary()
            messages = [{"role": "system", "content": f"Context summary:\n{summary}"}]
            print("[Context compressed manually]")
            continue

        if not user_input:
            continue

        if get_total_tokens(messages) > int(MAX_CONTEXT * COMPRESSION_THRESHOLD):
            compress_to_md(messages)
            summary = load_context_summary()
            messages = [{"role": "system", "content": f"Context summary:\n{summary}"}]
            print("[Context compressed]")

        messages.append({"role": "user", "content": user_input})

        try:
            time_start = time.time()
            response = chat_with_reasoning(messages, max_iterations=5)
            print("\n----------")

            messages.append({"role": "assistant", "content": response})

            total = get_total_tokens(messages)

            time_end = time.time()

            print(response)

        except Exception as e:
            print(f"Error: {e}")
            
        print(f"Context: {total} ({total/MAX_CONTEXT*100:.1f}%)")
        print(f"Time: {time_end - time_start:.1f}s")

if __name__ == "__main__":
    main()
