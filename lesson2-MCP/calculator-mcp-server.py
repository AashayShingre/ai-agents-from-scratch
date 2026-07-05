import math
from mcp.server.fastmcp import FastMCP

# 1. Initialize the FastMCP server and give it a name.
# This name helps the LLM recognize what this server does.
mcp = FastMCP("Math-Calculator-Server")

# 2. Define a list of safe characters.
# If an expression contains anything else (like letters that could form malicious code), we block it.
ALLOWED_CHARS = "0123456789+-*/.() <>=!*"

# 3. Create the tool using the @mcp.tool() decorator.
# This registers the function below so the LLM can see and call it.
@mcp.tool()
def calculate(expression: str) -> str:
    """
    Evaluates mathematical and comparison expressions.
    Supports basic arithmetic (+, -, *, /), exponents (**), 
    and inequalities (<, >, <=, >=, ==, !=).
    
    Examples: 
      "10 * 5 + 2" -> "52"
      "250 < 100"   -> "False"
    """
    # Remove any accidental leading/trailing spaces from the input
    cleaned_expr = expression.strip()
    
    # --- STEP 1: SAFETY CHECK ---
    # Loop through every character. If any character is NOT in our ALLOWED_CHARS, stop immediately.
    if not all(char in ALLOWED_CHARS for char in cleaned_expr):
        return "Error: Invalid characters detected. Only numbers, standard math operators, and comparison symbols are allowed."

    # Prevent sneaky Python internal lookups (like double underscores)
    if "._" in cleaned_expr or "__" in cleaned_expr:
        return "Error: Invalid expression syntax structure."

    # --- STEP 2: EVALUATION ---
    try:
        # Create an ultra-restricted environment context.
        # By setting "__builtins__": {}, we strip away dangerous Python commands like __import__ or open()
        safe_context = {"math": math, "__builtins__": {}}
        
        # Run the math string securely and store the result
        result = eval(cleaned_expr, safe_context)
        
        # Always convert the answer to a string so it safely passes through the MCP protocol back to the LLM
        return str(result)

    # --- STEP 3: ERROR HANDLING ---
    except ZeroDivisionError:
        # Catch errors if the LLM tries to divide a number by 0
        return "Error: Division by zero is impossible."
    except Exception as e:
        # Catch any other syntax errors (like mismatched parentheses or broken math formulas)
        return f"Error: Invalid mathematical expression. Reason: {str(e)}"

# 4. Start the server
if __name__ == "__main__": 
    print("Starting MCP Calculator server")
    mcp.run()