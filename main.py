from pathlib import Path
import sys
import pandas as pd
import matplotlib.pyplot as plt
import datetime as datetime  


try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


PAST_DAYS = 14           
MAX_AGE_HOURS = 6        
TIMEZONE = "Asia/Almaty" 

CITIES = {
    "Astana": (51.1801, 71.4460),
    "Almaty": (43.2380, 76.9450),
}

CITY_ALIAS = {
    "Астана": "Astana", "Нур-Султан": "Astana",
    "Алматы": "Almaty", "Алма-Ата": "Almaty"
}


try:
    import requests
    def fetch_json(url: str, params: dict) -> dict:
        r = requests.get(url, params=params, timeout=30)
        r.raise_for_status()
        return r.json()
except Exception:
    
    import json
    from urllib.parse import urlencode
    from urllib.request import urlopen
    def fetch_json(url: str, params: dict) -> dict:
        full = f"{url}?{urlencode(params)}"
        with urlopen(full, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))


def load_city(name: str, lat: float, lon: float, past_days: int = PAST_DAYS) -> pd.DataFrame:
    """
    Скачивает ежедневные максимальные температуры за сегодня + past_days.
    Возвращает DataFrame: date, city, temperature.
    """
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude":  lat,
        "longitude": lon,
        "daily":     "temperature_2m_max",
        "past_days": past_days,
        "timezone":  TIMEZONE,
    }
    data = fetch_json(url, params).get("daily", {})
    return pd.DataFrame({
        "date":        data.get("time", []),
        "city":        name,
        "temperature": data.get("temperature_2m_max", []),
    })

def refresh_csv(csv_path: Path, max_age_hours: int = MAX_AGE_HOURS) -> None:
    """
    Если csv нет или он старше max_age_hours — скачиваем заново.
    """
    need_update = not csv_path.exists()
    if not need_update:
        age_h = (datetime.datetime.now() - datetime.datetime.fromtimestamp(csv_path.stat().st_mtime)).total_seconds()/3600
        need_update = age_h > max_age_hours

    if need_update:
        frames = [load_city(n, *coords) for n, coords in CITIES.items()]
        df = pd.concat(frames, ignore_index=True)
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(csv_path, index=False)
        print(f"Данные обновлены -> {csv_path} ({datetime.datetime.now():%Y-%m-%d %H:%M})")


csv_path = Path("data/Weather.csv")
if not csv_path.exists():
    csv_path = Path("data/weather.csv")
refresh_csv(csv_path)


need_cols = {"date", "city", "temperature"}
df = pd.read_csv(csv_path, dtype={"date": "string", "city": "string"})
if not need_cols.issubset(df.columns):
    raise ValueError(f"В CSV должны быть колонки: {need_cols}. Найдены: {set(df.columns)}")

df["date"] = df["date"].astype("string").str.strip()
df["city"] = df["city"].astype("string").str.strip().replace(CITY_ALIAS)

bad_tokens = {"", "...", "—", "-", "NaN", "nan", None}
df = df[~df["date"].isin(bad_tokens)].copy()

parsed_dates = pd.to_datetime(df["date"], errors="coerce", format="mixed", dayfirst=True)
bad_mask = parsed_dates.isna()
if bad_mask.any():
    print("Плохие даты (первые 10):")
    print(df.loc[bad_mask, "date"].head(10).to_string(index=False))
    df = df.loc[~bad_mask].copy()
    parsed_dates = parsed_dates[~bad_mask]

df["date"] = parsed_dates
df["temperature"] = pd.to_numeric(df["temperature"], errors="coerce")
df = df.dropna(subset=["date", "city", "temperature"])


def make_series(table: pd.DataFrame, city: str) -> pd.Series:
    part = table.loc[table["city"] == city, ["date", "temperature"]].copy()
    if part.empty:
        raise ValueError(f"Нет данных для города: {city}")
    return (part.set_index("date")["temperature"]
                .sort_index()
                .asfreq("D")
                .interpolate("time"))

s_ast = make_series(df, "Astana")
s_alm = make_series(df, "Almaty")


def season_by_month(m: int) -> str:
    if m in (12, 1, 2):  return "winter"
    if m in (6, 7, 8):   return "summer"
    return "shoulder"

last_date = min(s_ast.dropna().index.max(), s_alm.dropna().index.max())
t_ast = float(s_ast.loc[last_date])
t_alm = float(s_alm.loc[last_date])

season = season_by_month(last_date.month)
if season == "winter":
    winner = "Astana" if t_ast > t_alm else "Almaty"
    reason = "зима: теплее — комфортнее"
elif season == "summer":
    winner = "Astana" if t_ast < t_alm else "Almaty"
    reason = "лето: прохладнее — комфортнее"
else:
    target = 20.0
    winner = "Astana" if abs(t_ast - target) <= abs(t_alm - target) else "Almaty"
    reason = f"межсезонье: ближе к {target:.0f}C — комфортнее"

print(f"{last_date.date()}: Astana {t_ast:.1f}C vs Almaty {t_alm:.1f}C -> комфортнее в {winner} ({reason}).")


out = Path("plots/compare.png")
out.parent.mkdir(exist_ok=True)

fig, ax = plt.subplots(figsize=(8, 4.5))
ax.plot(s_ast.index, s_ast.values, label="Astana")
ax.plot(s_alm.index, s_alm.values, label="Almaty")
ax.set_title("Temperature (daily)")
ax.set_xlabel("date")
ax.set_ylabel("C")
ax.grid(True, alpha=0.3)
ax.legend()

fig.tight_layout()
fig.savefig(out, dpi=150, bbox_inches="tight")
print(f"OK -> {out}")

def on_key(event):
    if event.key and event.key.lower() == "q":
        plt.close(event.canvas.figure)

fig.canvas.mpl_connect("key_press_event", on_key)
plt.show()
