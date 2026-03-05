# utils.py
import requests

def get_elevation_google(lat, lon, api_key):
    url = f"https://maps.googleapis.com/maps/api/elevation/json?locations={lat},{lon}&key={api_key}"
    response = requests.get(url)
    data = response.json()
    if data["status"] == "OK":
        return data["results"][0]["elevation"]
    else:
        print("Elevation API 오류:", data["status"])
        return None
