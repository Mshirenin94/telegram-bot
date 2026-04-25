import csv
import json
import os
import re
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
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

PLACE_DETAILS = {
    'The Yard Hotel Beijing': {
        'photo': 'https://cf.bstatic.com/xdata/images/hotel/max1024x768/396543845.jpg?k=1e7c5e1bfa4136d3d0e0f02a31b5dc9b7f52a8c2b3ce0ff4e0fd0ed9d32c6fb5&o=',
        'text': 'Бутик-отель на Xianyukou Street, удобная база для первых дней в Пекине. Удобен для раннего выхода к Tiananmen, Forbidden City и прогулок по Qianmen. По смыслу это не просто ночёвка, а логистический якорь всей пекинской части маршрута.',
        'url': 'https://www.trip.com/hotels/beijing-hotel-detail-71798009/the-yard-hotel-beijingbianyifang/'
    },
    'Xianyukou Street': {
        'photo': 'https://images.unsplash.com/photo-1547981609-4b6bf67db7b8?auto=format&fit=crop&w=1200&q=80',
        'text': 'Историческая food street в районе Qianmen. Здесь удобно делать мягкий старт поездки: местные снеки, old Beijing atmosphere, Bianyifang и короткая прогулка без сложной логистики. Подходит для первого вечера после перелёта.',
        'url': 'https://ruqintravel.com/china-destination-guides/xianyukou-street/'
    },
    'Bianyifang': {
        'photo': 'https://images.unsplash.com/photo-1552566626-52f8b828add9?auto=format&fit=crop&w=1200&q=80',
        'text': 'Один из самых известных исторических ресторанов пекинской утки. Его обычно выбирают за более классическую, историческую подачу и атмосферу старого Пекина. Это хороший вариант, если хочется не просто поесть, а сразу войти в гастрономический контекст города.',
        'url': ''
    },
    'Forbidden City': {
        'photo': 'https://images.unsplash.com/photo-1584646098378-0874589d76b1?auto=format&fit=crop&w=1200&q=80',
        'text': 'Главный императорский комплекс Пекина и одна из центральных точек всей поездки. Лучше воспринимать его не как один дворец, а как большую ось с несколькими дворами, павильонами и боковыми зонами, на которые действительно нужно время.',
        'url': 'https://en.dpm.org.cn/'
    },
    'Jingshan Park': {
        'photo': 'https://images.unsplash.com/photo-1508804185872-d7badad00f7d?auto=format&fit=crop&w=1200&q=80',
        'text': 'Парк сразу за северными воротами Forbidden City. Сюда поднимаются ради лучшего панорамного вида на весь дворцовый комплекс сверху. Это короткая, но очень ценная точка после основного посещения.',
        'url': ''
    }
}

FOOD_DETAILS = {
    'Bianyifang': 'Исторический ресторан пекинской утки рядом с отелем. Хороший сценарий для первого вечера, если силы ещё есть. Ожидание — классическая кухня Пекина, более традиционная атмосфера и ощущение, что вы начали гастрономическую часть поездки правильно.',
    'Siji Minfu': 'Один из самых популярных современных вариантов пекинской утки. Обычно сюда идут за балансом между качеством, понятным сервисом и сильной репутацией среди туристов и местных.',
    'Haidilao': 'Самый известный китайский hotpot-сетап. Сильная сторона — сервис и понятный формат даже для первого знакомства с hotpot. Для вас это удобный способ поесть неостро, если взять clear broth.',
    'Myeongdong Kyoja': 'Классика Сеула для комфортного ужина: kalguksu и mandu, обычно быстро, понятно и без острого перегруза.',
    'La Yeon': 'Праздничный fine dining на день рождения. Сюда идут за атмосферой special occasion, красивой подачей и спокойным, дорогим финалом сеульской части.',
    'NANTA Theater': 'Это не еда, но вечерний anchor дня. Можно встроить ужин до или после шоу, поэтому в логике дня он часто живёт рядом с food-планом.'
}


def save_notes():
    with open(USER_NOTES_PATH, 'w', encoding='utf-8') as f:
        json.dump(USER_NOTES, f, ensure_ascii=False, indent=2)


def find_day(day_num):
    return next((d for d in ITINERARY['days'] if str(d['day']) == str(day_num)), None)


def today_day():
    return '1'


def tomorrow_day():
    return '2'


def linkify(text, url):
    return f'<a href="{url}">{text}</a>' if url else text


def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton('Маршрут сегодня', callback_data='today_menu')],
        [InlineKeyboardButton('Маршрут завтра', callback_data='tomorrow_menu')],
        [InlineKeyboardButton('Выбрать дату', callback_data='pick_date')],
        [InlineKeyboardButton('Весь маршрут', callback_data='whole_route')],
        [InlineKeyboardButton('Добавить в маршрут', callback_data='add_help')],
    ])


def info_choice_menu(prefix):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton('Общая информация', callback_data=f'{prefix}:short')],
        [InlineKeyboardButton('Подробная информация', callback_data=f'{prefix}:full')],
        [InlineKeyboardButton('⬅️ Назад', callback_data='home')],
    ])


def dates_menu():
    rows = []
    for d in ITINERARY['days']:
        rows.append([InlineKeyboardButton(MONTH_RU.get(d['date'][5:], d['date']), callback_data=f'date:{d["day"]}')])
    rows.append([InlineKeyboardButton('⬅️ Назад', callback_data='home')])
    return InlineKeyboardMarkup(rows)


def date_mode_menu(day_num):
    day_obj = find_day(day_num)
    label = MONTH_RU.get(day_obj['date'][5:], day_obj['date'])
    return InlineKeyboardMarkup([
        [InlineKeyboardButton('Общая информация', callback_data=f'dayshort:{day_num}')],
        [InlineKeyboardButton('Подробная информация', callback_data=f'dayfull:{day_num}')],
        [InlineKeyboardButton(f'⬅️ К датам ({label})', callback_data='pick_date')],
        [InlineKeyboardButton('🏠 В меню', callback_data='home')],
    ])


def detail_menu(day_num):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton('Общий маршрут', callback_data=f'section:overview:{day_num}')],
        [InlineKeyboardButton('Расписание', callback_data=f'section:schedule:{day_num}')],
        [InlineKeyboardButton('Еда', callback_data=f'section:foodmenu:{day_num}')],
        [InlineKeyboardButton('Что посещаем', callback_data=f'section:visitmenu:{day_num}')],
        [InlineKeyboardButton('Что важно', callback_data=f'section:important:{day_num}')],
        [InlineKeyboardButton('⬅️ К выбору формата', callback_data=f'date:{day_num}')],
        [InlineKeyboardButton('🏠 В меню', callback_data='home')],
    ])


def visit_menu(day_obj):
    rows = [[InlineKeyboardButton('Все места', callback_data=f'visitall:{day_obj["day"]}')]]
    for idx, item in enumerate(day_obj.get('visits', [])):
        rows.append([InlineKeyboardButton(item['name'], callback_data=f'visit:{day_obj["day"]}:{idx}')])
    rows.append([InlineKeyboardButton('⬅️ К подробному дню', callback_data=f'dayfull:{day_obj["day"]}')])
    return InlineKeyboardMarkup(rows)


def food_menu(day_num):
    rows = [[InlineKeyboardButton('Все места', callback_data=f'foodall:{day_num}')]]
    idx = 0
    for p in PLACES_BY_DAY.get(str(day_num), []):
        cat = (p.get('category') or '').lower()
        name = p.get('name_en', '')
        if any(k in cat for k in ['restaurant', 'cafe', 'coffee', 'bakery']) or any(k in name.lower() for k in ['coffee', 'ramen', 'bbq', 'kyoja', 'haidilao', 'bianyifang', 'siji', 'baekjeong', 'la yeon']):
            rows.append([InlineKeyboardButton(name, callback_data=f'food:{day_num}:{idx}')])
        idx += 1
    rows.append([InlineKeyboardButton('⬅️ К подробному дню', callback_data=f'dayfull:{day_num}')])
    return InlineKeyboardMarkup(rows)


def short_day_text(day_obj):
    lines = [
        f'📅 {MONTH_RU.get(day_obj["date"][5:], day_obj["date"])} — {day_obj["title"]}',
        f'🏙 {day_obj["city"]}',
        '',
        day_obj['summary'],
        '',
        '⏱ План дня:'
    ]
    for item in day_obj['timeline']:
        lines.append(f'• {item["time"]} — {item["activity"]}')
    return '\n'.join(lines)[:3900]


def overview_text(day_obj):
    lines = [
        f'<b>{MONTH_RU.get(day_obj["date"][5:], day_obj["date"])} — {day_obj["title"]}</b>',
        day_obj['summary']
    ]
    return '\n'.join(lines)


def schedule_text(day_obj):
    lines = [f'<b>Расписание — {MONTH_RU.get(day_obj["date"][5:], day_obj["date"])} </b>']
    for item in day_obj['timeline']:
        lines.append(f'• {item["time"]} — {item["activity"]}')
    return '\n'.join(lines)


def food_all_text(day_obj):
    lines = [f'<b>Еда — {MONTH_RU.get(day_obj["date"][5:], day_obj["date"])} </b>']
    found = False
    for p in PLACES_BY_DAY.get(str(day_obj['day']), []):
        cat = (p.get('category') or '').lower()
        name = p.get('name_en', '')
        if any(k in cat for k in ['restaurant', 'cafe', 'coffee', 'bakery']) or any(k in name.lower() for k in ['coffee', 'ramen', 'bbq', 'kyoja', 'haidilao', 'bianyifang', 'siji', 'baekjeong', 'la yeon']):
            found = True
            title = linkify(name, p.get('map_link'))
            lines.append(f'• {title} — {p.get("address", "")}'.strip())
            detail = FOOD_DETAILS.get(name)
            if detail:
                lines.append(detail)
                lines.append('')
    if not found:
        lines.append('• В этот день отдельные food-точки пока не выделены.')
    return '\n'.join(lines)


def important_text(day_obj):
    lines = [f'<b>Что важно — {MONTH_RU.get(day_obj["date"][5:], day_obj["date"])} </b>']
    for n in day_obj.get('practical_notes', []):
        lines.append(f'• {n}')
    user_items = USER_NOTES.get(str(day_obj['day']), [])
    if user_items:
        lines += ['', '<b>Добавлено вами:</b>'] + [f'• {x}' for x in user_items]
    return '\n'.join(lines)


def visit_all_text(day_obj):
    lines = [f'<b>Что посещаем — {MONTH_RU.get(day_obj["date"][5:], day_obj["date"])} </b>']
    for v in day_obj.get('visits', []):
        place = next((p for p in PLACES_BY_DAY.get(str(day_obj['day']), []) if p['name_en'] == v['name']), None)
        url = place.get('map_link') if place else ''
        lines.append(f'• {linkify(v["name"], url)} — {v["comment"]}')
    user_items = USER_NOTES.get(str(day_obj['day']), [])
    if user_items:
        lines += ['', '<b>Добавлено вами:</b>'] + [f'• {x}' for x in user_items]
    return '\n'.join(lines)


def full_route_short():
    lines = ['<b>Весь маршрут — общая информация</b>']
    for d in ITINERARY['days']:
        lines.append(f'• {MONTH_RU.get(d["date"][5:], d["date"])} — {d["title"]} ({d["city"]})')
    return '\n'.join(lines)


def full_route_full():
    lines = ['<b>Весь маршрут — подробная информация</b>']
    for d in ITINERARY['days']:
        lines.append(f'\n<b>{MONTH_RU.get(d["date"][5:], d["date"])} — {d["title"]}</b>')
        lines.append(d['summary'])
        top = ', '.join([v['name'] for v in d.get('visits', [])[:4]])
        if top:
            lines.append(f'Главные точки: {top}.')
    return '\n'.join(lines)[:3900]


async def send_html(chat, text, reply_markup=None):
    await chat.send_message(text, parse_mode=ParseMode.HTML, disable_web_page_preview=False, reply_markup=reply_markup)


async def send_day_overview_bundle(chat, day_num):
    day_obj = find_day(day_num)
    await send_html(chat, overview_text(day_obj))
    await send_html(chat, schedule_text(day_obj))
    await send_html(chat, food_all_text(day_obj))
    await send_html(chat, visit_all_text(day_obj))
    await send_html(chat, important_text(day_obj), reply_markup=detail_menu(day_num))


async def show_place_card(chat, day_num, idx):
    day_obj = find_day(day_num)
    visit = day_obj['visits'][idx]
    name = visit['name']
    detail = PLACE_DETAILS.get(name, {})
    place = next((p for p in PLACES_BY_DAY.get(str(day_num), []) if p['name_en'] == name), None)
    map_link = place.get('map_link') if place else ''
    address = place.get('address') if place else ''
    caption = f'<b>{name}</b>\n\n{visit["comment"]}'
    if detail.get('text'):
        caption += f'\n\n{detail["text"]}'
    if address:
        caption += f'\n\nАдрес: {address}'
    if map_link:
        caption += f'\nКарта: <a href="{map_link}">открыть</a>'
    if detail.get('url'):
        caption += f'\nПодробнее: <a href="{detail["url"]}">источник</a>'
    photo = detail.get('photo')
    if photo:
        await chat.send_photo(photo=photo, caption=caption[:1020], parse_mode=ParseMode.HTML)
    else:
        await chat.send_message(caption, parse_mode=ParseMode.HTML, disable_web_page_preview=False)
    await chat.send_message('Можно открыть другое место ниже.', reply_markup=visit_menu(day_obj))


async def show_food_card(chat, day_num, place_idx):
    p = PLACES_BY_DAY.get(str(day_num), [])[place_idx]
    name = p.get('name_en', '')
    title = linkify(name, p.get('map_link'))
    lines = [f'<b>{title}</b>']
    if p.get('address'):
        lines.append(f'Адрес: {p.get("address")}')
    detail = FOOD_DETAILS.get(name)
    if detail:
        lines += ['', detail]
    else:
        lines += ['', 'Это полезная food-точка дня. Её можно использовать как основной ресторанный или кофейный anchor внутри маршрута.']
    if p.get('booking_link'):
        lines.append(f'Бронь: <a href="{p.get("booking_link")}">открыть</a>')
    await chat.send_message('\n'.join(lines), parse_mode=ParseMode.HTML, disable_web_page_preview=False, reply_markup=food_menu(day_num))


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('Привет! Здесь маршрут по поездке с общей и подробной информацией.', reply_markup=main_menu())


async def on_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data
    if data == 'home':
        await q.edit_message_text('Главное меню', reply_markup=main_menu())
    elif data == 'today_menu':
        await q.edit_message_text('Маршрут сегодня:', reply_markup=info_choice_menu('today'))
    elif data == 'tomorrow_menu':
        await q.edit_message_text('Маршрут завтра:', reply_markup=info_choice_menu('tomorrow'))
    elif data == 'pick_date':
        await q.edit_message_text('Выбери дату:', reply_markup=dates_menu())
    elif data == 'whole_route':
        await q.edit_message_text('Весь маршрут:', reply_markup=info_choice_menu('route'))
    elif data == 'add_help':
        await q.edit_message_text('Напиши сообщением, например: «добавь 7 мая посещение магазина с пряжей». Я сохраню это в план нужного дня.', reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🏠 В меню', callback_data='home')]]))
    elif data == 'today:short':
        await q.edit_message_text(short_day_text(find_day(today_day())), reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('Подробная информация', callback_data=f'dayfull:{today_day()}')],[InlineKeyboardButton('🏠 В меню', callback_data='home')]]))
    elif data == 'today:full':
        await q.edit_message_text('Отправляю подробную информацию о дне отдельными сообщениями…', reply_markup=detail_menu(today_day()))
        await send_day_overview_bundle(q.message.chat, today_day())
    elif data == 'tomorrow:short':
        await q.edit_message_text(short_day_text(find_day(tomorrow_day())), reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('Подробная информация', callback_data=f'dayfull:{tomorrow_day()}')],[InlineKeyboardButton('🏠 В меню', callback_data='home')]]))
    elif data == 'tomorrow:full':
        await q.edit_message_text('Отправляю подробную информацию о дне отдельными сообщениями…', reply_markup=detail_menu(tomorrow_day()))
        await send_day_overview_bundle(q.message.chat, tomorrow_day())
    elif data.startswith('date:'):
        day_num = data.split(':', 1)[1]
        day_obj = find_day(day_num)
        await q.edit_message_text(f'Дата: {MONTH_RU.get(day_obj["date"][5:], day_obj["date"])}', reply_markup=date_mode_menu(day_num))
    elif data.startswith('dayshort:'):
        day_num = data.split(':', 1)[1]
        await q.edit_message_text(short_day_text(find_day(day_num)), reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('Подробная информация', callback_data=f'dayfull:{day_num}')],[InlineKeyboardButton('⬅️ К датам', callback_data='pick_date')],[InlineKeyboardButton('🏠 В меню', callback_data='home')]]))
    elif data.startswith('dayfull:'):
        day_num = data.split(':', 1)[1]
        await q.edit_message_text('Подробный день открыт. Выбери раздел или сразу читай пакет общего маршрута ниже.', reply_markup=detail_menu(day_num))
        await send_day_overview_bundle(q.message.chat, day_num)
    elif data == 'route:short':
        await q.edit_message_text(full_route_short(), parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('Подробная информация', callback_data='route:full')],[InlineKeyboardButton('🏠 В меню', callback_data='home')]]))
    elif data == 'route:full':
        await q.edit_message_text(full_route_full(), parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('Общая информация', callback_data='route:short')],[InlineKeyboardButton('🏠 В меню', callback_data='home')]]))
    elif data.startswith('section:'):
        _, section, day_num = data.split(':', 2)
        day_obj = find_day(day_num)
        if section == 'overview':
            await q.edit_message_text('Отправляю общий маршрут дня отдельными сообщениями…', reply_markup=detail_menu(day_num))
            await send_day_overview_bundle(q.message.chat, day_num)
        elif section == 'schedule':
            await q.edit_message_text(schedule_text(day_obj), parse_mode=ParseMode.HTML, reply_markup=detail_menu(day_num))
        elif section == 'foodmenu':
            await q.edit_message_text('Выбери food-точку:', reply_markup=food_menu(day_num))
        elif section == 'important':
            await q.edit_message_text(important_text(day_obj), parse_mode=ParseMode.HTML, reply_markup=detail_menu(day_num))
        elif section == 'visitmenu':
            await q.edit_message_text('Выбери место:', reply_markup=visit_menu(day_obj))
    elif data.startswith('foodall:'):
        day_num = data.split(':', 1)[1]
        await q.edit_message_text(food_all_text(find_day(day_num)), parse_mode=ParseMode.HTML, disable_web_page_preview=False, reply_markup=food_menu(day_num))
    elif data.startswith('food:'):
        _, day_num, idx = data.split(':', 2)
        await q.edit_message_text('Открываю место по еде…', reply_markup=food_menu(day_num))
        await show_food_card(q.message.chat, day_num, int(idx))
    elif data.startswith('visitall:'):
        day_num = data.split(':', 1)[1]
        await q.edit_message_text(visit_all_text(find_day(day_num)), parse_mode=ParseMode.HTML, disable_web_page_preview=False, reply_markup=visit_menu(find_day(day_num)))
    elif data.startswith('visit:'):
        _, day_num, idx = data.split(':', 2)
        await q.edit_message_text('Открываю карточку места…', reply_markup=visit_menu(find_day(day_num)))
        await show_place_card(q.message.chat, day_num, int(idx))


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
    await update.message.reply_text(f'Добавил в маршрут на {day_num} мая:\n• {content}')


if __name__ == '__main__':
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CallbackQueryHandler(on_button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, parse_add_request))
    app.run_polling()
