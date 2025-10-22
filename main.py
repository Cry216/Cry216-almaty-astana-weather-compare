from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt

import sys
try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

csv_path = 'data/Weather.csv'
if not Path(csv_path).exists():
    alt = 'data/weather.csv'
    if Path(alt).exists():
        csv_path = alt
    else:
        raise FileNotFoundError("Нужен файл data/Weather.csv (или data/weather.csv) с колонками: date, city, temperature")

df = pd.read_csv(csv_path, dtype={'date': 'string', 'city': 'string'})
need_cols = {'date', 'city', 'temperature'}
if not need_cols.issubset(df.columns):
    raise ValueError(f"В CSV должны быть колонки: {need_cols}. Найдены: {set(df.columns)}")

df['date'] = df['date'].astype('string').str.strip()
df['city'] = df['city'].astype('string').str.strip()

bad_tokens = {'', '...', '—', '-', 'NaN', 'nan', None}
df = df[~df['date'].isin(bad_tokens)].copy()

dt = pd.to_datetime(df['date'], errors='coerce', format='mixed', dayfirst=True)
bad_mask = dt.isna()
if bad_mask.any():
    print("Плохие даты (первые 10):")
    print(df.loc[bad_mask, 'date'].head(10).to_string(index=False))
    df = df.loc[~bad_mask].copy()
    dt = dt[~bad_mask]

df['date'] = dt
df['temperature'] = pd.to_numeric(df['temperature'], errors='coerce')
df = df.dropna(subset=['temperature', 'date', 'city'])

df['city'] = df['city'].str.strip()
city_map = {'Астана': 'Astana', 'Нур-Султан': 'Astana', 'Алматы': 'Almaty', 'Алма-Ата': 'Almaty'}
df['city'] = df['city'].replace(city_map)

def prepare_series(df_, city):
    part = df_.loc[df_['city'] == city, ['date', 'temperature']].copy()
    if part.empty:
        raise ValueError(f"Нет данных для города: {city}. Проверь колонку 'city' в CSV.")
    s = (part.set_index('date')['temperature']
             .sort_index()
             .asfreq('D')
             .interpolate('time'))
    return s

s_ast = prepare_series(df, 'Astana')
s_alm = prepare_series(df, 'Almaty')

def season_by_month(m: int) -> str:
    if m in (12, 1, 2):   return 'winter'
    if m in (6, 7, 8):    return 'summer'
    return 'shoulder' 

last_date = min(s_ast.dropna().index.max(), s_alm.dropna().index.max())
t_ast = float(s_ast.loc[last_date])
t_alm = float(s_alm.loc[last_date])

s = season_by_month(last_date.month)
if s == 'winter':

    winner = 'Astana' if t_ast > t_alm else 'Almaty'
    reason = 'зима: теплее — комфортнее'
elif s == 'summer':

    winner = 'Astana' if t_ast < t_alm else 'Almaty'
    reason = 'лето: прохладнее — комфортнее'
else:
    
    target = 20.0
    winner = 'Astana' if abs(t_ast - target) <= abs(t_alm - target) else 'Almaty'
    reason = f'shoulder: ближе к {target:.0f}°C — комфортнее'

print(f"{last_date.date()}: Astana {t_ast:.1f}C vs Almaty {t_alm:.1f}C -> комфортнее в {winner} ({reason}).")

Path('plots').mkdir(exist_ok=True)
plt.figure()
s_ast.plot(label='Astana')
s_alm.plot(label='Almaty')
plt.title('Temperature (daily)')
plt.legend()
plt.tight_layout()
plt.savefig('plots/compare.png', dpi=150)
print('OK -> plots/compare.png')


def on_key(event):
    if event.key and event.key.lower() == 'q':
        plt.close(event.canvas.figure)

fig = plt.gcf()
fig.canvas.mpl_connect('key_press_event', on_key)
plt.show()
