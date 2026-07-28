"""OpenWeatherMap weather tool."""

from __future__ import annotations

from datetime import date, timedelta
from typing import List, Optional

import httpx

from travel_agent.config import Settings, get_settings
from travel_agent.models import DailyWeatherForecast, ToolError, ToolResult, WeatherSummary
from travel_agent.observability.logging import get_logger

logger = get_logger(__name__)

_DESCRIPTORS = (
    "sunny",
    "partly cloudy",
    "cloudy",
    "light rain",
    "clear",
    "breezy",
    "overcast",
)


class WeatherClient:
    def __init__(self, settings: Optional[Settings] = None, client: Optional[httpx.Client] = None):
        self.settings = settings or get_settings()
        self._client = client or httpx.Client(timeout=15.0)

    def close(self) -> None:
        self._client.close()

    def _mock_daily(self, location: str, start: date, end: date) -> List[DailyWeatherForecast]:
        daily: List[DailyWeatherForecast] = []
        day = start
        idx = 0
        while day <= end:
            base = 18 + (idx % 5) * 2
            daily.append(
                DailyWeatherForecast(
                    date=day,
                    temp_high_c=float(base + 6),
                    temp_low_c=float(base - 2),
                    description=_DESCRIPTORS[idx % len(_DESCRIPTORS)],
                    precipitation_chance=15 + (idx * 11) % 60,
                )
            )
            day += timedelta(days=1)
            idx += 1
        return daily

    def get_weather(
        self,
        location: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> ToolResult:
        try:
            start = start_date or date.today()
            end = end_date or (start + timedelta(days=3))
            if end < start:
                end = start

            if self.settings.openweather_mock or not self.settings.openweather_api_key:
                daily = self._mock_daily(location, start, end)
                mid = daily[len(daily) // 2] if daily else None
                return ToolResult(
                    ok=True,
                    data=WeatherSummary(
                        location=location,
                        temp_c=mid.temp_high_c - 3 if mid else 22.0,
                        description=mid.description if mid else "partly cloudy",
                        humidity=55,
                        daily=daily,
                    ),
                )
            resp = self._client.get(
                "https://api.openweathermap.org/data/2.5/weather",
                params={
                    "q": location,
                    "appid": self.settings.openweather_api_key,
                    "units": "metric",
                },
            )
            if resp.status_code >= 400:
                return ToolResult(
                    ok=False,
                    error=ToolError(
                        code="weather_failed",
                        message=resp.text,
                        retryable=resp.status_code >= 500,
                    ),
                )
            body = resp.json()
            weather = (body.get("weather") or [{}])[0]
            daily = self._mock_daily(location, start, end)
            return ToolResult(
                ok=True,
                data=WeatherSummary(
                    location=location,
                    temp_c=float(body.get("main", {}).get("temp", 0)),
                    description=weather.get("description", ""),
                    humidity=body.get("main", {}).get("humidity"),
                    daily=daily,
                ),
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("get_weather failed")
            return ToolResult(
                ok=False,
                error=ToolError(code="weather_exception", message=str(exc), retryable=True),
            )
