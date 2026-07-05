import requests
from mcp.server.fastmcp import FastMCP

# Initialize the FastMCP server
mcp = FastMCP("Modular-Geo-Weather-Server")

# Weather condition translation codes
WEATHER_CODES = {
    0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Fog", 48: "Depositing rime fog",
    51: "Light drizzle", 53: "Moderate drizzle", 55: "Dense drizzle",
    61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
    71: "Slight snow fall", 73: "Moderate snow fall", 75: "Heavy snow fall",
    77: "Snow grains",
    80: "Slight rain showers", 81: "Moderate rain showers", 82: "Violent rain showers",
    85: "Slight snow showers", 86: "Heavy snow showers",
    95: "Thunderstorm", 96: "Thunderstorm with slight hail", 99: "Thunderstorm with heavy hail"
}

# --- TOOL 1: GEOCODING ---
@mcp.tool()
def get_coordinates(city: str) -> str:
    """
    Converts a city name into geographical coordinates (Latitude and Longitude).
    Use this when you need to find where a city is located on the globe.
    """
    clean_city = city.strip()
    try:
        geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={clean_city}&count=1&language=en&format=json"
        geo_response = requests.get(geo_url, timeout=10).json()
        
        if not geo_response.get("results"):
            return f"Error: Could not find coordinates for the city '{clean_city}'."
            
        location = geo_response["results"][0]
        lat = location["latitude"]
        lon = location["longitude"]
        city_name = location["name"]
        country = location.get("country", "")
        
        # Return a structured, clean string that the LLM can easily parse or read
        return f"Location: {city_name}, Country: {country} | Latitude: {lat}, Longitude: {lon}"

    except requests.exceptions.RequestException as e:
        return f"Error: Network issue connecting to geocoding service. Reason: {str(e)}"
    except Exception as e:
        return f"An error occurred while fetching coordinates. Reason: {str(e)}"


# --- TOOL 2: WEATHER BY COORDINATES ---
@mcp.tool()
def get_weather_by_coordinates(latitude: float, longitude: float, unit: str = "celsius") -> str:
    """
    Fetches the live, current weather statistics using exact Latitude and Longitude coordinates.
    
    Parameters:
    - latitude: The latitude coordinate (e.g., 40.7128).
    - longitude: The longitude coordinate (e.g., -74.0060).
    - unit: Temperature unit preference. Accepts 'celsius' or 'fahrenheit' (defaults to celsius).
    """
    unit_choice = unit.strip().lower()
    if unit_choice not in ["celsius", "fahrenheit"]:
        unit_choice = "celsius"

    try:
        weather_url = f"https://api.open-meteo.com/v1/forecast?latitude={latitude}&longitude={longitude}&current_weather=true&temperature_unit={unit_choice}"
        weather_response = requests.get(weather_url, timeout=10).json()
        
        current = weather_response.get("current_weather")
        if not current:
            return f"Error: Could not retrieve live weather statistics for coordinates ({latitude}, {longitude})."

        temp = current["temperature"]
        windspeed = current["windspeed"]
        w_code = current.get("weathercode", -1)
        
        condition = WEATHER_CODES.get(w_code, "Unknown condition")
        unit_symbol = "°C" if unit_choice == "celsius" else "°F"
        
        return f"Weather at Coordinates ({latitude}, {longitude}): Condition: {condition}, Temp: {temp}{unit_symbol}, Wind Speed: {windspeed} km/h."

    except requests.exceptions.RequestException as e:
        return f"Error: Network issue connecting to weather service. Reason: {str(e)}"
    except Exception as e:
        return f"An error occurred while processing the weather tool. Reason: {str(e)}"


if __name__ == "__main__":
    mcp.run()