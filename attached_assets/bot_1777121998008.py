import csv
import json
import os
import re
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ApplicationBuilder, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', 'PUT_YOUR_TOKEN_HERE')
BASE_DIR = os.path.dirname(__file__)
CSV_PATH = os.path.join(BASE_DIR, 'places_enriched_v1.csv')
JSON_PATH = os.path.join(BASE_DIR, 'itinerary_v2.json')
USER_NOTES_PATH = os.path.join(BASE_DIR, 'user_notes.json')

with open(JSON_PATH, 'r', encoding='utf-8') as f:
    ITINERARY = json.load(f)

PLACES = list(csv.DictReader(open(CSV_PATH, encoding='utf-8')))
PLACES_BY_DAY = {}
for row in PLACES:
    PLACES_BY_DAY.setdefault(str(row['day']), []).append(row)

if os.path.exists(USER_NOTES_PATH):
    with open(USER_NOTES_PATH, 'r', encoding='utf-8') as f:
        USER_NOTES = json.load(f)
else:
    USER_NOTES = {}

MONTH_RU = {
    '05-01': '1 мая', '05-02': '2 мая', '05-03': '3 мая', '05-04': '4 мая', '05-05': '5 мая',
    '05-06': '6 мая', '05-07': '7 мая', '05-08': '8 мая', '05-09': '9 мая', '05-10': '10 мая',
    '05-11': '11 мая', '05-12': '12 мая'
}

HELP_TEXT = (
    'Можно добавлять свои пункты прямо сообщением.\n\n'
    'Формат: «добавь 7 мая посещение магазина с пряжей»\n'
    'Я сохраню это в план на нужный день и покажу в подробной версии.'
)


def save_notes():
    with open(USER_NOTES_PATH, 'w', encoding='utf-8') as f:
        json.dump(USER_NOTES, f, ensure_ascii=False, indent=2)


def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton('Сегодня кратко', callback_data='today_short')],
        [InlineKeyboardButton('Сегодня подробно', callback_data='today_full')],
        [InlineKeyboardButton('Выбрать дату', callback_data='choose_date')],
        [InlineKeyboardButton('Весь маршрут', callback_data='all_days')],
        [InlineKeyboardButton('Как добавить в план', callback_data='help_add')],
    ])


def date_menu(mode='short'):
    rows, row = [], []
    for d in ITINERARY['days']:
        label = f"{d['day']} · {MONTH_RU.get(d['date'][5:], d['date'])}"
        row.append(InlineKeyboardButton(label, callback_data=f"{mode}:{d['day']}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([
        InlineKeyboardButton('Кратко', callback_data='choose_date_short'),
        InlineKeyboardButton('Подробно', callback_data='choose_date_full')
    ])
    rows.append([InlineKeyboardButton('⬅️ Назад', callback_data='home')])
    return InlineKeyboardMarkup(rows)


def find_day(day_num):
    return next((d for d in ITINERARY['days'] if str(d['day']) == str(day_num)), None)


def short_day_text(day_obj):
    day = str(day_obj['day'])
    lines = [
        f"📅 {MONTH_RU.get(day_obj['date'][5:], day_obj['date'])} — {day_obj['title']}",
        f"🏙 {day_obj['city']}",
        '',
        day_obj['summary'],
        '',
        '⏱ План дня:'
    ]
    for item in day_obj['timeline']:
        lines.append(f"• {item['time']} — {item['activity']}")
    places = PLACES_BY_DAY.get(day, [])
    if places:
        lines += ['', '📍 Ключевые точки:']
        for p in places[:8]:
            t = f"• {p['name_en']}"
            if p.get('address'):
                t += f" — {p['address']}"
            lines.append(t)
            if p.get('map_link'):
                lines.append(f"  Карта: {p['map_link']}")
    return '\n'.join(lines)[:3900]


def food_block(day_obj):
    day = str(day_obj['day'])
    items = []
    for p in PLACES_BY_DAY.get(day, []):
        cat = (p.get('category') or '').lower()
        name = p.get('name_en', '')
        if any(k in cat for k in ['restaurant', 'cafe', 'coffee', 'bakery', 'barbecue', 'ramen', 'spa']) or any(k in name.lower() for k in ['coffee', 'ramen', 'bbq', 'spa', 'nanta', 'la yeon', 'kyoja', 'haidilao', 'bianyifang', 'siji', 'baekjeong', 'ore', 'momos', 'fritz']):
            items.append(p)
    lines = ['🍽 Еда и кофе:']
    if not items:
        lines.append('• Пока не добавлено. Можно дописать вручную сообщением в стиле: «добавь 7 мая кофе в Blue Bottle».')
    for p in items[:10]:
        line = f"• {p['name_en']}"
        if p.get('address'):
            line += f" — {p['address']}"
        lines.append(line)
        if p.get('map_link'):
            lines.append(f"  Карта: {p['map_link']}")
        if p.get('booking_link'):
            lines.append(f"  Бронь: {p['booking_link']}")
    return '\n'.join(lines)


def visit_block(day_obj):
    lines = ['🏛 Что посещаем:']
    for item in day_obj.get('visits', []):
        lines.append(f"• {item['name']} — {item['comment']}")
    user_items = USER_NOTES.get(str(day_obj['day']), [])
    if user_items:
        lines.append('')
        lines.append('➕ Добавлено вами:')
        for x in user_items:
            lines.append(f"• {x}")
    return '\n'.join(lines)


def timeline_block(day_obj):
    lines = ['⏰ Расписание по часам:']
    for item in day_obj['timeline']:
        lines.append(f"• {item['time']} — {item['activity']}")
    return '\n'.join(lines)


def detailed_parts(day_obj):
    header = f"📅 {MONTH_RU.get(day_obj['date'][5:], day_obj['date'])} — {day_obj['title']}\n🏙 {day_obj['city']}\n\n{day_obj['summary']}"
    parts = [header, timeline_block(day_obj), food_block(day_obj), visit_block(day_obj)]
    notes = day_obj.get('practical_notes', [])
    if notes:
        extra = ['📝 Что важно:'] + [f"• {n}" for n in notes]
        user_items = USER_NOTES.get(str(day_obj['day']), [])
        if user_items:
            extra += ['', '➕ Ваши добавления в план:'] + [f"• {x}" for x in user_items]
        parts.append('\n'.join(extra))
    return parts


def all_days_text():
    lines = ['🗺 Весь маршрут:']
    for d in ITINERARY['days']:
        lines.append(f"• {MONTH_RU.get(d['date'][5:], d['date'])} — {d['title']} ({d['city']})")
    return '\n'.join(lines)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        'Привет! Я бот-помощник по маршруту Пекин → Сеул.\n\n'
        'Есть краткая версия дня и подробная версия по блокам.',
        reply_markup=main_menu()
    )


async def send_short(target, day_num):
    day_obj = find_day(day_num)
    if not day_obj:
        await target.edit_message_text('Не нашёл день маршрута.', reply_markup=main_menu())
        return
    await target.edit_message_text(
        short_day_text(day_obj),
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton('Сегодня подробно', callback_data=f'full:{day_num}')],
            [InlineKeyboardButton('⬅️ К датам', callback_data='choose_date')],
            [InlineKeyboardButton('🏠 В меню', callback_data='home')],
        ])
    )


async def send_full_message(chat, day_num):
    day_obj = find_day(day_num)
    if not day_obj:
        await chat.send_message('Не нашёл день маршрута.')
        return
    for part in detailed_parts(day_obj):
        if len(part) <= 4000:
            await chat.send_message(part)
        else:
            chunks = [part[i:i+3800] for i in range(0, len(part), 3800)]
            for c in chunks:
                await chat.send_message(c)
    await chat.send_message('Открыть другой день можно через /start или кнопки меню.')


async def on_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data
    if data == 'home':
        await q.edit_message_text('Главное меню', reply_markup=main_menu())
    elif data == 'choose_date':
        await q.edit_message_text('Выбери дату. По умолчанию открыт краткий режим.', reply_markup=date_menu('short'))
    elif data == 'choose_date_short':
        await q.edit_message_text('Выбери дату для краткой версии:', reply_markup=date_menu('short'))
    elif data == 'choose_date_full':
        await q.edit_message_text('Выбери дату для подробной версии:', reply_markup=date_menu('full'))
    elif data == 'all_days':
        await q.edit_message_text(all_days_text(), reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🏠 В меню', callback_data='home')]]))
    elif data == 'help_add':
        await q.edit_message_text(HELP_TEXT, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🏠 В меню', callback_data='home')]]))
    elif data == 'today_short':
        await send_short(q, '1')
    elif data == 'today_full':
        await q.edit_message_text('Отправляю подробную версию дня отдельными сообщениями…', reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🏠 В меню', callback_data='home')]]))
        await send_full_message(q.message.chat, '1')
    elif data.startswith('short:'):
        await send_short(q, data.split(':', 1)[1])
    elif data.startswith('full:'):
        day_num = data.split(':', 1)[1]
        await q.edit_message_text('Отправляю подробную версию дня отдельными сообщениями…', reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🏠 В меню', callback_data='home')]]))
        await send_full_message(q.message.chat, day_num)


async def parse_add_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or '').strip()
    m = re.match(r'(?i)^добав[ьй]\s+(\d{1,2})\s+мая\s+(.+)$', text)
    if not m:
        return
    day_num, content = m.group(1), m.group(2).strip()
    if not find_day(day_num):
        await update.message.reply_text('Не вижу такого дня в маршруте. Поддерживаются даты с 1 по 12 мая.')
        return
    USER_NOTES.setdefault(str(int(day_num)), []).append(content)
    save_notes()
    await update.message.reply_text(
        f'Добавил в план на {day_num} мая:\n• {content}\n\nТеперь это будет видно в кнопке «Сегодня подробно» для этого дня.'
    )


if __name__ == '__main__':
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CallbackQueryHandler(on_button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, parse_add_request))
    app.run_polling()
