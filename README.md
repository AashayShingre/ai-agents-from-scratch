# AI Agents from Scratch

A hands-on learning repo for building AI agents with Python. Each example is a self-contained script that demonstrates a core agent pattern.

It starts off as a basic idea of AI agent (An LLM with tool invoking capability).

Each lesson is self-contained in its own folder with its script and prompts.

## What's next

More examples will be added here soon as the series grows - MCP, memory, multi-agent workflows, planning, and more. Each new script will follow the same pattern: a focused example with a matching prompt file under `prompts/`.


## Setup

**Requirements:** Python 3.13+

1. Clone the repo and create a virtual environment:
  ```bash
   python -m venv .venv
   source .venv/bin/activate   # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
  ```
2. Add your Google AI API key to a `.env` file in the project root:
  ```
   GOOGLE_API_KEY=your_key_here
  ```
   Get a key from [Google AI Studio](https://aistudio.google.com/apikey).

