import requests
from bs4 import BeautifulSoup

def get_bbc_seoul_weather_summary():
    url = "https://www.bbc.com/weather/1835848"
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.text, "html.parser")
    summary_tag = soup.find("div", class_="wr-day__weather-type-description")
    if summary_tag:
        return summary_tag.text.strip()
    else:
        return "No weather summary found." 

