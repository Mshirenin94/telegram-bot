import csv
import json
import os
from datetime import datetime
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ApplicationBuilder, CallbackQueryHandler, CommandHandler, ContextTypes

def _clean_token(raw: str) -> str:
    t = (raw or '').strip().strip('"').strip("'")
    for prefix in ('HTTP API:', 'HTTP API', 'Bot:', 'Token:'):
        if t.lower().startswith(prefix.lower()):
            t = t[len(prefix):].strip()
    return t


TOKEN = _clean_token(os.getenv('TELEGRAM_BOT_TOKEN', 'PUT_YOUR_TOKEN_HERE'))
CSV_PATH = os.path.join(os.path.dirname(__file__), 'places_enriched_v1.csv')
JSON_PATH = os.path.join(os.path.dirname(__file__), 'itinerary_mvp.json')

with open(JSON_PATH, 'r', encoding='utf-8') as f:
    ITINERARY = json.load(f)

PLACES = list(csv.DictReader(open(CSV_PATH, encoding='utf-8')))
PLACES_BY_DAY = {}
for row in PLACES:
    PLACES_BY_DAY.setdefault(str(row['day']), []).append(row)

MONTH_RU = {
    '05-01': '1 мая', '05-02': '2 мая', '05-03': '3 мая', '05-04': '4 мая', '05-05': '5 мая',
    '05-06': '6 мая', '05-07': '7 мая', '05-08': '8 мая', '05-09': '9 мая', '05-10': '10 мая',
    '05-11': '11 мая', '05-12': '12 мая'
}


def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton('Сегодня', callback_data='today')],
        [InlineKeyboardButton('Выбрать дату', callback_data='choose_date')],
        [InlineKeyboardButton('Весь маршрут', callback_data='all_days')],
        [InlineKeyboardButton('Полезные ссылки', callback_data='links')],
    ])


def date_menu():
    days = ITINERARY['days']
    rows = []
    row = []
    for d in days:
        label = f"{d['day']} · {MONTH_RU.get(d['date'][5:], d['date'])}"
        row.append(InlineKeyboardButton(label, callback_data=f"day:{d['day']}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton('⬅️ Назад', callback_data='home')])
    return InlineKeyboardMarkup(rows)


def format_day(day_obj):
    day = str(day_obj['day'])
    lines = []
    lines.append(f"📅 {MONTH_RU.get(day_obj['date'][5:], day_obj['date'])} — {day_obj['title']}")
    lines.append(f"🏙 {day_obj['city']}")
    lines.append('')
    lines.append(day_obj['summary'])
    lines.append('')
    lines.append('⏱ План дня:')
    for item in day_obj['timeline']:
        lines.append(f"• {item['time']} — {item['activity']}")

    places = PLACES_BY_DAY.get(day, [])
    if places:
        lines.append('')
        lines.append('📍 Ключевые точки:')
        for p in places[:8]:
            line = f"• {p['name_en']}"
            if p['address']:
                line += f" — {p['address']}"
            lines.append(line)
            if p.get('map_link'):
                lines.append(f"  Карта: {p['map_link']}")
            if p.get('booking_link'):
                lines.append(f"  Бронь: {p['booking_link']}")

    if day_obj.get('notes'):
        lines.append('')
        lines.append('📝 Важно:')
        for n in day_obj['notes'][:5]:
            lines.append(f"• {n}")

    text = '\n'.join(lines)
    if len(text) > 3900:
        text = text[:3850] + '\n\n…сообщение сокращено'
    return text


def all_days_text():
    lines = ['🗺 Весь маршрут:']
    for d in ITINERARY['days']:
        lines.append(f"• {d['day']} мая / {MONTH_RU.get(d['date'][5:], d['date'])} — {d['title']}")
    return '\n'.join(lines)


def links_text():
    lines = ['🔗 Полезные ссылки:']
    picked = []
    for p in PLACES:
        if p.get('booking_link'):
            picked.append((p['name_en'], 'Бронь', p['booking_link']))
        elif p.get('map_link') and p['map_provider'] == 'KakaoMap':
            picked.append((p['name_en'], 'Карта', p['map_link']))
    seen = set()
    for name, kind, link in picked:
        if name in seen:
            continue
        seen.add(name)
        lines.append(f"• {name} — {kind}: {link}")
        if len(lines) > 20:
            break
    return '\n'.join(lines)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = 'Привет! Я бот-помощник по маршруту Пекин → Сеул. Выбери действие в меню ниже.'
    await update.message.reply_text(text, reply_markup=main_menu())


async def show_day(target, day_num: str):
    day_obj = next((d for d in ITINERARY['days'] if str(d['day']) == str(day_num)), None)
    if not day_obj:
        await target.edit_message_text('Не нашёл день маршрута.', reply_markup=main_menu())
        return
    await target.edit_message_text(
        format_day(day_obj),
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('⬅️ К датам', callback_data='choose_date')],[InlineKeyboardButton('🏠 В меню', callback_data='home')]])
    )


async def on_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data
    if data == 'home':
        await q.edit_message_text('Главное меню', reply_markup=main_menu())
    elif data == 'choose_date':
        await q.edit_message_text('Выбери дату:', reply_markup=date_menu())
    elif data == 'all_days':
        await q.edit_message_text(all_days_text(), reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🏠 В меню', callback_data='home')]]))
    elif data == 'links':
        await q.edit_message_text(links_text(), reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🏠 В меню', callback_data='home')]]))
    elif data == 'today':
        day_num = 1
        await show_day(q, str(day_num))
    elif data.startswith('day:'):
        await show_day(q, data.split(':', 1)[1])


def build_itinerary():
    pass


if __name__ == '__main__':
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CallbackQueryHandler(on_button))
    app.run_polling()
