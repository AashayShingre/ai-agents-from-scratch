import asyncio
import json
import os
from pathlib import Path
from contextlib import AsyncExitStack
from dotenv import load_dotenv

# Import Model Context Protocol (MCP) clients and types
from mcp import StdioServerParameters, ClientSession
from mcp.client.stdio import stdio_client

# USING YOUR EXISTING PACKAGE: No installations or package removals required
import google.generativeai as genai  # pyright: ignore[reportMissingImports]

# ---------------------------------------------------------
# SETUP & CONFIGURATION
# ---------------------------------------------------------

# Load environment variables from a local .env file
load_dotenv() 

# Safety constraint to prevent the agent from looping infinitely if it gets confused
MAX_ITERATIONS = 5

# Ensure the required API Key exists in the environment
API_KEY = os.getenv("GOOGLE_API_KEY")
if not API_KEY: 
    raise ValueError("GOOGLE_API_KEY not set. Add it to .env or your environment.")

# Configure the legacy genai package structure
genai.configure(api_key=API_KEY) 

# Using gemini-1.5-flash as the stable standard for structured reasoning loops in this SDK
MODEL_NAME = 'gemini-3.1-flash-lite'  
model = genai.GenerativeModel(MODEL_NAME)

# Determine the absolute directory path where THIS specific python file is located
BASE_DIR = Path(__file__).parent

# Load system prompt rules from file (or provide a safe backup string)
PROMPT_PATH = BASE_DIR / "prompts" / "system_prompt.txt"
if PROMPT_PATH.exists():
    system_prompt = PROMPT_PATH.read_text()
else:
    system_prompt = (
        "You are a helpful assistant. You must output raw JSON only matching this schema:\n"
        'To call a tool: {"tool_name": "name", "tool_arguments": {...}}\n'
        'To give final result: {"answer": "your message"}'
    )

# Compute absolute file paths to your individual MCP script servers. 
MCP_SERVERS = [
    str(BASE_DIR / "calculator-mcp-server.py"),
    str(BASE_DIR / "weather-mcp-server.py")
]

# GLOBAL REGISTRIES: Active connections and metadata shared across tasks
TOOL_TO_SESSION_MAP = {}  # Maps "tool_name" -> active ClientSession object for routing execution
AVAILABLE_TOOLS_DESC = [] # List of human-readable strings explaining tools to inject into Gemini's system prompt

# ---------------------------------------------------------
# HELPER FUNCTIONS
# ---------------------------------------------------------

def response_parser(response: str) -> dict: 
    """Safely converts string responses from the AI into a Python dictionary."""
    try:
        return json.loads(response)
    except json.JSONDecodeError as e:
        return {"error": str(e)}

def describe_tools(tools) -> str:
    """Formats raw MCP tool definitions into clean documentation for the system prompt."""
    lines = []
    for i, t in enumerate(tools, 1):
        props = (t.inputSchema or {}).get("properties", {})
        params = ", ".join(f"{n}: {p.get('type', '?')}" for n, p in props.items()) or "no params"
        lines.append(f"  {i}. {t.name}({params}) — {t.description or ''}")
    return "\n".join(lines)

# ---------------------------------------------------------
# SERVER INITIALIZATION (PERSISTENT CONNECTION)
# ---------------------------------------------------------

async def initialize_mcp_servers(exit_stack: AsyncExitStack): 
    """Launches external sub-process servers and keeps sessions alive via AsyncExitStack."""
    global AVAILABLE_TOOLS_DESC
    
    for server_path in MCP_SERVERS: 
        if not Path(server_path).exists():
            raise FileNotFoundError(f"Could not find MCP server script at: {server_path}")

        server_params = StdioServerParameters(
            command="python", 
            args=[server_path]
        )
        
        # Open transport streams and attach them to the stack lifecycle
        read_stream, write_stream = await exit_stack.enter_async_context(stdio_client(server_params))
        session = await exit_stack.enter_async_context(ClientSession(read_stream, write_stream))
        
        # Complete protocol handshake
        await session.initialize() 
        
        # Retrieve tools exposed by this server
        tools_response = await session.list_tools()
        tools = tools_response.tools 
        
        # Map tools to this specific active session
        for tool in tools:
            TOOL_TO_SESSION_MAP[tool.name] = session
            
        AVAILABLE_TOOLS_DESC.append(describe_tools(tools))
        print(f"[Init] Connected to server: {Path(server_path).name} (Loaded {len(tools)} tools)")

# ---------------------------------------------------------
# AGENT LOGIC ENGINE
# ---------------------------------------------------------

async def run_agent(query: str, max_steps: int = MAX_ITERATIONS) -> str: 
    """Executes a complete reasoning loop using the persistent MCP sessions."""
    print(f"\n" + "="*60)
    print(f"🚀 STARTING AGENT QUERY: \"{query}\"")
    print("="*60)

    steps = 0 
    tools_desc_str = "\n".join(AVAILABLE_TOOLS_DESC)
    
    # Combine system prompt guidelines and live available tools into instructions block
    full_system_context = f"{system_prompt}\n\nAvailable Tools:\n{tools_desc_str}"
    
    # Instantiate a clean, state-tracked multi-turn chat session using the legacy package layout
    # Passing system instructions inside the model initialization is how it's handled in this library version
    chat = model.start_chat(history=[])

    # For the first turn, we pass the massive system context layout combined with our core prompt
    initial_prompt = f"System Instructions:\n{full_system_context}\n\nUser Query:\n{query}"
    response_content = chat.send_message(initial_prompt).text

    while steps < max_steps: 
        steps += 1 
        
        response = response_parser(response_content)
        print(f"\n[Step {steps}] Model Output Layout: {json.dumps(response, indent=2)}")
        
        if "error" in response:
            error_msg = f"Your output wasn't valid JSON: {response['error']}. Please fix your formatting."
            print(f" -> [Feedback] Requesting JSON syntax correction...")
            response_content = chat.send_message(error_msg).text
            continue
        
        if "tool_name" in response:
            tool_name = response["tool_name"]
            tool_arguments = response["tool_arguments"]
            
            if tool_name in TOOL_TO_SESSION_MAP:
                session = TOOL_TO_SESSION_MAP[tool_name]
                print(f" -> [Action] Routing '{tool_name}' to server with parameters: {tool_arguments}")
                
                # EXECUTION: Invoke tool directly over the live protocol stream
                result = await session.call_tool(tool_name, arguments=tool_arguments)
                print(f" -> [Result] Server returned data payload: {result.content}")
                
                # Send back contents string directly to context history
                response_content = chat.send_message(f"Tool execution result: {str(result.content)}").text
            else:
                error_msg = f"The tool '{tool_name}' doesn't exist. Choose from the available options."
                print(f" -> [Feedback] Informing model of missing tool target...")
                response_content = chat.send_message(error_msg).text
            continue 

        if "answer" in response:
            print(f"\n✅ SUCCESS: Final objective resolved in {steps} steps.")
            return f"Final answer: {response['answer']}"
        
        print(f" -> [Feedback] Demanding schema correction...")
        response_content = chat.send_message("Invalid JSON format. You must provide either 'tool_name' or 'answer'.").text

    return "Error: Reached maximum agent step iterations without hitting an explicit answer."

# ---------------------------------------------------------
# APPLICATION ENTRYPOINT
# ---------------------------------------------------------

async def main(): 
    # The Stack manages our server lifetimes in the background concurrently
    async with AsyncExitStack() as stack:
        print("--- PHASE 1: Setting up Persistent Multi-Server Sessions ---")
        await initialize_mcp_servers(stack)
        
        print("\n--- PHASE 2: Executing Sequential Agent Task Pipeline ---")
        
        # Test Case 1
        res1 = await run_agent("What is the weather in Tokyo?")
        print(res1)
        
        # Test Case 2
        res2 = await run_agent("What is the sum of temperatures in Mumbai and Delhi?")
        print(res2)
    
        # Test Case 3
        res3 = await run_agent("Is Mumbai hotter or Bengaluru?") 
        print(res3)

if __name__ == "__main__": 
    print("Initializing main background system execution script...")
    asyncio.run(main())