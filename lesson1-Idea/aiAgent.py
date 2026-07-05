"""
Example 1: A tool-using AI agent backed by Gemini.

Run:
    python "aiAgent.py"

Try different prompts by uncommenting or adding calls at the bottom of this file:
    run_agent("What is the weather in Tokyo?")
    run_agent("What is the sum of temperatures in Mumbai and Delhi?")
    run_agent("Is Mumbai hotter or Bengaluru?")
"""

import google.generativeai as genai  # pyright: ignore[reportMissingImports]
import os
import requests
import json
from pathlib import Path
from dotenv import load_dotenv

from learnings.mcp.AgenticMCPUse import MAX_ITERATIONS

load_dotenv()


MAX_ITERATIONS = 5


API_KEY = os.getenv("GOOGLE_API_KEY") # load API key from environment variables
if not API_KEY:
    raise ValueError("GOOGLE_API_KEY not set. Add it to .env or your environment.")
genai.configure(api_key=API_KEY)

TOOLS = {} # global tools registry 

model = genai.GenerativeModel('gemini-3.1-flash-lite')

PROMPT_PATH = Path(__file__).parent / "prompts" / "system_prompt.txt"
system_prompt = PROMPT_PATH.read_text()


def tool(func): 
    TOOLS[func.__name__] = func 
    return func

@tool
def calculate(expr): 
    """evaluates an expression"""
    return eval(expr)

@tool
def get_weather(city: str) -> str:
    """
    Fetches the current weather for a given city using the free Open-Meteo API.
    """
    try:
        # Step 1: Geocoding - Convert city name to Latitude and Longitude
        geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={city}&count=1&language=en&format=json"
        geo_response = requests.get(geo_url).json()
        
        if not geo_response.get("results"):
            return f"Error: Could not find coordinates for the city '{city}'."
            
        location = geo_response["results"][0]
        lat = location["latitude"]
        lon = location["longitude"]
        city_name = location["name"]
        country = location.get("country", "")

        # Step 2: Fetch weather using the coordinates
        weather_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true"
        weather_response = requests.get(weather_url).json()
        
        current = weather_response.get("current_weather")
        if not current:
            return "Error: Could not retrieve weather data."

        temp = current["temperature"]
        windspeed = current["windspeed"]
        
        return f"Current weather in {city_name}, {country}: Temp: {temp}°C, Wind Speed: {windspeed} km/h."

    except Exception as e:
        return f"An error occurred while fetching the weather: {str(e)}"



def response_parser(response: str) -> dict: 
    try:
        return json.loads(response)
    except json.JSONDecodeError as e:
        print(f"Error parsing response: {e}")
        print(f"Response: {response}")
        return {f"error": {e}}


def run_agent(prompt: str, max_steps: int = MAX_ITERATIONS) -> str: 
    steps = 0
    
    # put the user prompt and system prompt into a single string 
    full_prompt = f"{system_prompt}\n\nUser Prompt: {prompt}"
    
    # create a chat session 
    chat = model.start_chat(
        history=[]
    )

    # send the initial prompt to the chat session 
    response_content = chat.send_message(full_prompt).text

    # initalize loop - 
    while steps < max_steps: 
        steps += 1 

        # parse response, and then check if its tool use or final answer 
        response = response_parser(response_content)
        print(f"Step {steps} response: {response}")
        
        if "error" in response:
            response_content = chat.send_message(f"Invalid response format when loading json: {response['error']}").text
            continue
        
        if "tool_name" in response:
            tool_name = response["tool_name"]
            tool_arguments = response["tool_arguments"]
            result = TOOLS[tool_name](**tool_arguments)
            print(f"Tool result: {result}")
            response_content = chat.send_message(f"Tool result: {result}").text
            continue 

        if "answer" in response:
            return f"Final answer: {response['answer']}"
        
        response_content = chat.send_message(f"Invalid response. Loaded json {response}, but no tool name or answer found.").text

    return "Error: Reached maximum number of steps"


if __name__ == "__main__":
    print("Running agent...")

    # print(run_agent("What is the weather in Tokyo?"))
    # print(run_agent("What is the sum of temperatures in Mumbai and Delhi?"))
    # print(run_agent("Is Mumbai hotter or Bengaluru?"))








