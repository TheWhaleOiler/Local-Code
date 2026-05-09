
import json


def mcp_agent(input_dict: dict) -> tuple[dict | None, dict]:
    reasoning_context_json = None

    try:
        reasoning_context_json = json.loads(input_dict["content"])
        print(json.dumps(reasoning_context_json,indent=2))
    except Exception as e:
        return {"role": "system", "content": f"[Error parsing context json: {e}]"}, {}

    # Extract tool call
    try:
        tool_call = validate_tool_call(reasoning_context_json)
        reasoning_context_json["tool"] = tool_call
    except Exception as e:
        return {{"role": "system", "content": f"[Error parsing tool call: {e}]"}}, {}

    return None, reasoning_context_json
    

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


def validate_tool_call(_json: dict) -> str:
    if _json["tool"] in ['python', 'search', 'read_file', 'write_file', 'exit']:
        for i in ["tool", "arg1", "arg2"]:
            if i not in _json:
                raise Exception(f"Missing key {i} in tool call")
        return _json["tool"]
            
    return 'exit'