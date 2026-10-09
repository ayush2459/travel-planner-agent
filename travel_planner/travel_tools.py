"""Optional live weather and currency helpers using public APIs; failures degrade gracefully."""
from __future__ import annotations
import requests

TIMEOUT = 8

WEATHER_CODES = {
    0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Fog", 48: "Depositing rime fog", 51: "Light drizzle", 53: "Moderate drizzle",
    55: "Dense drizzle", 56: "Freezing drizzle", 57: "Dense freezing drizzle",
    61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain", 66: "Freezing rain",
    67: "Heavy freezing rain", 71: "Slight snow", 73: "Moderate snow", 75: "Heavy snow",
    77: "Snow grains", 80: "Rain showers", 81: "Moderate rain showers", 82: "Violent rain showers",
    85: "Snow showers", 86: "Heavy snow showers", 95: "Thunderstorm",
    96: "Thunderstorm with hail", 99: "Thunderstorm with heavy hail",
}

def current_weather(city: str) -> dict:
    city = city.strip()
    if not city:
        raise ValueError("Enter a city name.")
    geo = requests.get("https://geocoding-api.open-meteo.com/v1/search", params={"name": city, "count": 1, "language": "en", "format": "json"}, timeout=TIMEOUT)
    geo.raise_for_status()
    places = geo.json().get("results") or []
    if not places:
        raise ValueError(f"Could not find a location for '{city}'.")
    place = places[0]
    weather = requests.get("https://api.open-meteo.com/v1/forecast", params={"latitude": place["latitude"], "longitude": place["longitude"], "current": "temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m", "timezone": "auto"}, timeout=TIMEOUT)
    weather.raise_for_status()
    current = weather.json().get("current") or {}
    code = current.get("weather_code")
    return {
        "place": ", ".join(filter(None, [place.get("name"), place.get("admin1"), place.get("country")])),
        "timezone": place.get("timezone"),
        "weather_description": WEATHER_CODES.get(code, "Conditions unavailable"),
        "source": "Open-Meteo current conditions",
        **current,
    }

def convert_currency(amount: float, base: str, target: str) -> dict:
    if amount < 0:
        raise ValueError("Amount cannot be negative.")
    base, target = base.upper().strip(), target.upper().strip()
    if base == target:
        return {"amount": amount, "base": base, "target": target, "rate": 1.0, "converted": amount, "date": "same currency"}
    response = requests.get(f"https://api.frankfurter.dev/v1/latest", params={"base": base, "symbols": target}, timeout=TIMEOUT)
    response.raise_for_status()
    payload = response.json()
    rate = (payload.get("rates") or {}).get(target)
    if rate is None:
        raise ValueError(f"No conversion rate returned for {base} to {target}.")
    return {"amount": amount, "base": base, "target": target, "rate": float(rate), "converted": float(amount) * float(rate), "date": payload.get("date", "unknown")}


def format_weather_summary(weather: dict) -> str:
    """Format a current-weather snapshot for chat context and user-facing output."""
    place = weather.get("place") or "Destination"
    temp = weather.get("temperature_2m")
    feels = weather.get("apparent_temperature")
    description = weather.get("weather_description") or "Conditions unavailable"
    humidity = weather.get("relative_humidity_2m")
    wind = weather.get("wind_speed_10m")
    rain = weather.get("precipitation")
    stamp = weather.get("time") or "observation time unavailable"
    zone = weather.get("timezone") or "local time"
    temp_text = f"{temp}°C" if temp is not None else "unavailable"
    feels_text = f"{feels}°C" if feels is not None else "unavailable"
    humidity_text = f"{humidity}%" if humidity is not None else "unavailable"
    wind_text = f"{wind} km/h" if wind is not None else "unavailable"
    rain_text = f"{rain} mm" if rain is not None else "unavailable"
    return (
        f"Current weather for {place}: {description}. Temperature: {temp_text}; "
        f"feels like: {feels_text}; humidity: {humidity_text}; wind: {wind_text}; "
        f"precipitation: {rain_text}. Observation time: {stamp} ({zone}). "
        "Source: Open-Meteo current conditions. This is current weather, not a forecast."
    )
