import csv
import json
import os
import re
import urllib.request
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', 'PUT_YOUR_TOKEN_HERE')
BASE_DIR = os.path.dirname(__file__)
ASSETS_DIR = os.path.join(BASE_DIR, 'assets')
os.makedirs(ASSETS_DIR, exist_ok=True)
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
    USER_NOTES = json.load(open(USER_NOTES_PATH, encoding='utf-8'))
else:
    USER_NOTES = {}

MONTH_RU = {'05-01':'1 мая','05-02':'2 мая','05-03':'3 мая','05-04':'4 мая','05-05':'5 мая','05-06':'6 мая','05-07':'7 мая','05-08':'8 мая','05-09':'9 мая','05-10':'10 мая','05-11':'11 мая','05-12':'12 мая'}



RU_SOURCES = {
    "Forbidden City": ["https://ru.wikipedia.org/wiki/%D0%97%D0%B0%D0%BF%D1%80%D0%B5%D1%82%D0%BD%D1%8B%D0%B9_%D0%B3%D0%BE%D1%80%D0%BE%D0%B4"],
    "Temple of Heaven": ["https://ru.wikipedia.org/wiki/%D0%A5%D1%80%D0%B0%D0%BC_%D0%9D%D0%B5%D0%B1%D0%B0"],
    "Mutianyu Great Wall": ["https://ru.wikipedia.org/wiki/%D0%92%D0%B5%D0%BB%D0%B8%D0%BA%D0%B0%D1%8F_%D0%9A%D0%B8%D1%82%D0%B0%D0%B9%D1%81%D0%BA%D0%B0%D1%8F_%D1%81%D1%82%D0%B5%D0%BD%D0%B0"],
    "Gyeongbokgung": ["https://ru.wikipedia.org/wiki/%D0%9A%D1%91%D0%BD%D0%B1%D0%BE%D0%BA%D0%BA%D1%83%D0%BD", "https://wikiway.com/south-korea/seul/dostoprimechatelnosti/dvorets-kenbokkun/"],
    "Bukchon": ["https://koreana-tour.ru/bukchon-hanok-village-seoul/"],
    "Insadong": ["https://koreana-tour.ru/insadong-seoul/"],
    "Myeongdong": ["https://koreana-tour.ru/myeongdong-seoul/"],
    "Bukhansan National Park": ["https://ru.wikipedia.org/wiki/%D0%9F%D1%83%D0%BA%D1%85%D0%B0%D0%BD%D1%81%D0%B0%D0%BD"],
    "N Seoul Tower": ["https://ru.wikipedia.org/wiki/N_Seoul_Tower"]
}

PLACE_DETAILS.update({
    "The Yard Hotel Beijing": "Бутик-отель в районе Qianmen/Xianyukou, который удобен именно как логистическая база. Отсюда легко стартовать в исторический центр, быстро выходить на ужин и не тратить силы на длинные трансферы в первые дни. Главная ценность — не destination luxury, а правильное расположение внутри очень плотного пекинского блока.",
    "Xianyukou Street": "Историческая food-улица старого Пекина. Сюда стоит идти за мягким стартом поездки: утка, снеки, old Beijing atmosphere, вечерние огни и ощущение, что вы уже внутри старого города, а не просто в туристическом коридоре.",
    "Forbidden City": "Главный императорский комплекс всей поездки. Лучше воспринимать его как длинную историческую ось с воротами, парадными залами и внутренними дворами, а не как одну фото-точку. Самые важные зоны — центральная ось, большие парадные дворы, а затем более спокойные боковые блоки, если останутся силы.",
    "Jingshan Park": "Короткий, но очень ценный выход после Forbidden City. Сюда поднимаются не ради долгой прогулки, а ради панорамы на весь дворцовый массив сверху — это помогает буквально увидеть масштаб того, что вы только что прошли.",
    "Nanluoguxiang": "Один из самых известных hutong-районов Пекина, где маршрут становится менее императорским и более живым. Здесь логично гулять без жёсткой цели: кофе, маленькие магазины, боковые переулки и ощущение более бытового исторического города.",
    "Shichahai": "Озёрный и прогулочный Пекин, который хорошо работает на контрасте с дворцами и музеями. Лучше всего воспринимается как пространство для спокойного late afternoon или вечера.",
    "Mutianyu Great Wall": "Самый user-friendly участок Великой стены в вашем маршруте: удобнее по логистике, понятнее по навигации и даёт тот самый визуальный wow, ради которого вообще хочется ехать на стену.",
    "Temple of Heaven": "Сильная архитектурная точка и одновременно живой городской парк. Помимо Hall of Prayer, здесь важно смотреть и на жизнь вокруг: музыку, локальные активности и ритм пекинского утра.",
    "798 Art Zone": "Современный, индустриальный и более дизайнерский Пекин. Здесь важны не только отдельные галереи, но и сам контраст между заводской средой, contemporary art, кофейнями и concept stores.",
    "Brooklyn Blues Hotel": "Удобная центральная база в сеульской части маршрута. Практическая ценность здесь снова важнее hotel fantasy: район помогает легко связать дворцы, Ikseon-dong, Insadong и поздние ужины.",
    "Changgyeonggung": "Более спокойный и менее тяжёлый дворец, чем Gyeongbokgung. Подходит для мягкого начала дня и более камерного погружения в palace atmosphere.",
    "Gyeongbokgung": "Главный дворец сеульского блока и лучший первый royal place, если хочется почувствовать Joseon scale. Внутри особенно важны главные ворота, парадные пространства и павильоны у воды.",
    "Bukchon": "Квартал hanok-домов между дворцами, куда идут за красивой уличной фактурой и переходом между old Seoul и современной городской жизнью.",
    "Insadong": "Район для tea culture, традиционных магазинов, ремесленных деталей и более медленного культурного темпа прогулки.",
    "Myeongdong": "Не самый красивый, но очень практичный и энергичный район Сеула. Его ценность — shopping, cosmetics, street flow и удобный вечерний urban block.",
    "NANTA Theater": "Удобный формат вечернего развлечения без языкового барьера. Это не глубокий культурный ритуал, а хорошо собранный entertainment stop.",
    "Bukhansan National Park": "Городской outdoor-блок, который даёт резкий переход от плотного Сеула к воздуху, тропам и панорамам. После нескольких городских дней он особенно хорошо чувствуется телом.",
    "Bibong Peak": "Одна из самых rewarding точек хайка, когда усилие оправдывается видом. Стоит воспринимать как точку усилия и визуальной награды, а не как просто геометку на карте.",
    "Jingwansa Temple": "Храмовая тишина после outdoor-части дня. Хорошо работает как выдох после подъёма и как более медитативный контраст к city pace.",
    "Whoo Spa": "Осознанная пауза в маршруте. Это точка, куда стоит идти не за галочкой, а за восстановлением и slow luxury rhythm.",
    "COEX Mall": "Большой practical hub в Gangnam. Это скорее инфраструктурная точка с полезными функциями, магазинами и indoor comfort, чем уникальная sightseeing-достопримечательность.",
    "Starfield Library": "Короткая, но яркая визуальная stop-точка внутри COEX. Идут сюда прежде всего за ощущением масштаба, фотогеничностью и красивым indoor pause.",
    "Seongsu": "Самый lifestyle-oriented район маршрута: кофе, мода, local brands, concept stores и ощущение современного, модного Сеула.",
    "Hongdae": "Более молодой и шумный городской блок с nightlife и уличной энергией. Хорош для вечера, если хочется больше живости, чем polish.",
    "Club Evans": "Камерный джазовый финал. Его ценность в атмосфере и живом local night feel, а не в формальной роскоши.",
    "Ikseon-dong": "Один из самых приятных районов для спокойной прогулки, красивых cafe stops и birthday-friendly атмосферы.",
    "N Seoul Tower": "Классический look-out point для заката и красивого завершения дня. Идти сюда стоит за видом и mood, а не за музейной глубиной.",
    "La Yeon": "Праздничная вершина маршрута — место, где важен не только вкус, но и вся рамка вечера: сервис, pacing, occasion feel."
})

FOOD_DETAILS.update({
    "Bianyifang": "Что брать: фирменную пекинскую утку, блинчики, scallions, cucumber и соус; если хочется попробовать более традиционный стиль, обрати внимание на skin с сахаром. По отзывам сильнее всего запоминаются исторический статус ресторана, более классическая подача утки и сам old Beijing feel.",
    "Siji Minfu": "Что брать: Peking duck как обязательную позицию, thin pancakes, duck skin with sugar, honey shrimp, mustard cabbage и один тёплый side dish. По отзывам это один из самых надёжных и понятных duck-ресторанов Пекина: crispy skin, хорошая нарезка и сильный value-for-money.",
    "Haidilao": "Что брать: tomato broth или mild broth, hand-pulled noodles, beef/lamb, leafy greens и sauce bar под себя. По отзывам сильнее всего любят сервис, скорость, sauce station и ощущение, что даже первый hotpot-опыт проходит легко и без хаоса.",
    "Myeongdong Kyoja": "Что брать: kalguksu и mandu, а если будет настроение — попробовать фирменный garlic kimchi. По отзывам людей цепляет сочетание лёгкого, но насыщенного broth, хорошей текстуры лапши и очень мясных juicy dumplings.",
    "La Yeon": "Что ожидать: fine dining с корейской рамкой, polished service и special occasion energy. В обзорах чаще выделяют galbijjim, yukjeon и в целом высокий уровень execution; сюда идут не за casual meal, а за полноценный праздничный ужин.",
    "Baekjeong": "Что брать: мясные позиции для grill, samgyeopsal/galbi-type наборы, banchan и lettuce wraps. Это скорее про lively Korean BBQ experience, чем про одно конкретное блюдо.",
    "Oreno Ramen": "Что брать: signature ramen и при желании gyoza. Это хороший быстрый lunch anchor, если хочется плотной, понятной и не слишком экспериментальной еды.",
    "Momos Coffee": "Сюда идти за specialty coffee и короткой передышкой. Главная сила точки — кофе и атмосфера, а не еда.",
    "Fritz Coffee": "Хороший coffee stop для mid-day reset: кофе, выпечка и приятная пауза внутри прогулочного ритма."
})

PHOTO_GALLERIES = {
    'The Yard Hotel Beijing': [
        'https://pplx-res.cloudinary.com/image/upload/pplx_search_images/dbb0432486dbcf6c12990fe77552547a11fb97a1.jpg',
        'https://pplx-res.cloudinary.com/image/upload/pplx_search_images/26b97d6307fb0c1c383cbc17b5b2d429d8685e38.jpg',
        'https://pplx-res.cloudinary.com/image/upload/pplx_search_images/a39bd68e482a04824759681d3ce65b3c8f5ec4d1.jpg'
    ],
    'Forbidden City': [
        'https://pplx-res.cloudinary.com/image/upload/pplx_search_images/1df3a7396c3fc0a838e51204e704f033bd0dfd5d.jpg',
        'https://pplx-res.cloudinary.com/image/upload/pplx_search_images/aa6fa001623a6439574807fd89dc8066e94f8220.jpg',
        'https://pplx-res.cloudinary.com/image/upload/pplx_search_images/11db677c789f029deca66b0dd06e139d468dd555.jpg'
    ],
    'Gyeongbokgung': [
        'https://pplx-res.cloudinary.com/image/upload/pplx_search_images/73c32cc741f973d2ae0c3be6d6e81f62ac55c730.jpg',
        'https://pplx-res.cloudinary.com/image/upload/pplx_search_images/005cd5a97cd816d2ee7e0fee2f8ae951c5af0ec8.jpg',
        'https://pplx-res.cloudinary.com/image/upload/pplx_search_images/0945b3cf42cafe9e0f6960be0e3261279da781b0.jpg'
    ],
    'Bianyifang': [
        'https://dynamic-media-cdn.tripadvisor.com/media/photo-o/04/94/de/a6/bianyi-fang-qianmen-xian.jpg?w=900&h=500&s=1'
    ]
}

PLACE_DETAILS = {
    'The Yard Hotel Beijing': 'Бутик-отель в историческом районе Qianmen, удобный как тихая база на первые дни. Его сильная сторона — не сами номера как destination experience, а сверхудачная логистика: пешая доступность до Xianyukou, Qianmen, Tiananmen и удобный старт на ранние выходы в Golden Week.',
    'Xianyukou Street': 'Историческая гастро-улица рядом с отелем. Сюда стоит идти за мягким первым вечером: локальные снеки, old Beijing mood, фонари, фасады старого города и ощущение, что поездка уже началась без тяжёлой логистики.',
    'Forbidden City': 'Главная императорская точка маршрута. Внутри стоит ждать не одну открытку, а длинную ось залов, ворот и дворов. Самое важное — идти рано, иметь заранее билет и не пытаться пройти всё в режиме галопа.',
    'Jingshan Park': 'Небольшой, но очень важный парк сразу после Forbidden City. Подъём короткий, зато сверху открывается один из лучших видов на весь дворцовый ансамбль.',
    'Nanluoguxiang': 'Самый известный hutong-район для прогулки после императорской части дня. Хорош для медленного шага, кофе, сувениров и переключения из monumental Beijing в более живой камерный город.',
    'Shichahai': 'Озёра и набережные, где хорошо встречать поздний день. Это более расслабленный Пекин: вода, лодки, прогулочный ритм и меньше императорской тяжести.',
    'Mutianyu Great Wall': 'Самый дружелюбный к путешественнику участок стены: удобная логистика, канатка, понятный маршрут и вау-эффект без слишком экстремального треккинга.',
    'Temple of Heaven': 'Одна из самых красивых императорских площадок Пекина. Сюда стоит идти не только ради архитектуры, но и ради утренней жизни парка вокруг — tai chi, музыка, локальные группы и ощущение повседневного Пекина.',
    '798 Art Zone': 'Контрастный блок маршрута: industrial heritage, contemporary art, галереи, кафе и дизайн-магазины. Даёт ощущение, что Пекин — не только династии, но и современная креативная сцена.',
    'Brooklyn Blues Hotel': 'Практичная база в Jongno, хорошо подходящая для дворцов, Ikseon-dong, Insadong и вечерних перемещений по центральному Сеулу.',
    'Changgyeonggung': 'Более спокойный дворец, чем Gyeongbokgung. Хорош для мягкого старта дня, без перегруза толпами и с более камерным ощущением.',
    'Gyeongbokgung': 'Главный королевский дворец Сеула. Ожидание — большие ворота, внутренние дворы, фотогеничность ханбока и ощущение официального церемониального центра старой Кореи.',
    'Bukchon': 'Традиционный квартал между дворцами, куда идут за атмосферой hanok-улиц и визуально красивыми проходами между старым и современным Сеулом.',
    'Insadong': 'Лучший район для tea culture, традиционных сувениров и более культурного, медленного ритма прогулки.',
    'Myeongdong': 'Центральный shopping-район для cosmetics, tax free и быстрой городской энергии. Хорош не как красивый район, а как максимально практичный shopping hub.',
    'NANTA Theater': 'Известное non-verbal шоу, которое хорошо заходит даже без корейского языка. Это не must-see high art, а скорее очень удобный и бодрый вечерний entertainment block.',
    'Bukhansan National Park': 'Главный природный выезд в рамках Сеула. После городских дней даёт очень нужный ритм воздуха, троп и панорам.',
    'Bibong Peak': 'Одна из сильных точек хайка: ощущение реального effort/reward, когда вид сверху окупает подъём.',
    'Jingwansa Temple': 'Спокойное завершение outdoor-дня, которое добавляет храмовую и медитативную ноту после трека.',
    'Whoo Spa': 'Парный spa-блок как intentional slow day. Здесь важен не только сам массаж, но и ощущение паузы между более насыщенными днями.',
    'COEX Mall': 'Большой торговый и инфраструктурный блок Gangnam, полезный как practical city-stop, а не как уникальная достопримечательность.',
    'Starfield Library': 'Визуальная точка внутри COEX, ради которой сюда чаще всего и идут: высокие стеллажи, открытое пространство и очень инстаграмный вид.',
    'Seongsu': 'Самый модный lifestyle-район маршрута. Сюда идут за кофе, concept stores, local fashion и ощущением contemporary Seoul.',
    'Hongdae': 'Более молодёжный, шумный и живой район с уличной энергией, магазинами и music/night vibe.',
    'Club Evans': 'Джазовый финал дня. Идти сюда стоит не за polished luxury, а за камерную живую музыку и ощущение local night scene.',
    'Ikseon-dong': 'Один из самых приятных прогулочных районов центрального Сеула: hanok-улочки, кафе, маленькие магазины и birthday-friendly атмосфера.',
    'N Seoul Tower': 'Классическая смотровая точка для заката и праздничного настроения, особенно если день хочется завершить красиво.',
    'La Yeon': 'Праздничная гастрономическая вершина маршрута — fine dining with occasion energy, сервисом и очень чётким special-day mood.'
}

FOOD_DETAILS = {
    'Bianyifang': 'Что брать: фирменную пекинскую утку, тонкие блинчики, сладкий bean sauce, scallions и cucumber; по отзывам людям запоминается именно исторический closed-oven style и ритуал с разделкой утки у стола, а также skin с сахаром как часть традиционной подачи. Ожидание — классическая старая школа Пекина и более исторический опыт, чем модная современная подача.',
    'Siji Minfu': 'Что брать: фирменную Peking duck, thin pancakes, duck skin with sugar, honey shrimp, tofu dish, mustard napa cabbage и vegetable side dishes; по отзывам сильнее всего хвалят crispy skin, аккуратную нарезку, разумную цену и общий balance experience/value. Это хороший выбор, если хочется самый безопасный и понятный duck dinner всей поездки.',
    'Haidilao': 'Что брать: tomato broth или clear/mild broth, hand-pulled noodles, beef/lamb, leafy greens и sauce bar под себя; в отзывах чаще всего хвалят сервис, sauce station, noodle show и то, что даже новичкам формат понятен и fun. Для вас это особенно удобно, потому что легко собрать неострую и комфортную комбинацию.',
    'Myeongdong Kyoja': 'Что брать: kalguksu и mandu; по отзывам сильнее всего хвалят light but flavorful broth, hand-cut noodles с хорошей текстурой, juicy dumplings и фирменный garlic kimchi. Это один из самых надёжных comfort meals в сеульской части маршрута.',
    'La Yeon': 'Что ожидать: refined Korean fine dining, strong service, elegant pacing; из обзоров чаще выделяют galbijjim и yukjeon как standout dishes, а сам ресторан воспринимается как special occasion destination с акцентом на высокий execution level, а не на экспериментальность.',
    'Baekjeong': 'Что брать: мясные сеты, samgyeopsal/galbi-type позиции, banchan и lettuce wraps; ожидание — lively BBQ-ужин после активного дня, где важен общий meat-and-banchan experience.',
    'Oreno Ramen': 'Что брать: signature ramen, gyoza при желании и базовые side items; это скорее точка для одного качественного, понятного lunch anchor, чем для длинного meal experience.',
    'Momos Coffee': 'Сильная specialty coffee stop, куда логично идти не за едой, а за качественным кофе и передышкой внутри прогулочного дня.',
    'Fritz Coffee': 'Хорошая coffee stop с atmosphere и понятным specialty profile; подходит как mid-day reset.'
}


def save_notes():
    with open(USER_NOTES_PATH, 'w', encoding='utf-8') as f:
        json.dump(USER_NOTES, f, ensure_ascii=False, indent=2)


def today_day(): return '1'
def tomorrow_day(): return '2'
def find_day(day_num): return next((d for d in ITINERARY['days'] if str(d['day']) == str(day_num)), None)
def linkify(text, url): return f'<a href="{url}">{text}</a>' if url else text


def download_photo(url, slug, index):
    if not url: return None
    path = os.path.join(ASSETS_DIR, f'{slug}_{index}.jpg')
    if os.path.exists(path): return path
    try:
        urllib.request.urlretrieve(url, path)
        return path
    except Exception:
        return None


def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton('🐉 Маршрут сегодня', callback_data='today_menu')],
        [InlineKeyboardButton('🕊 Маршрут завтра', callback_data='tomorrow_menu')],
        [InlineKeyboardButton('🗓 Выбрать дату', callback_data='pick_date')],
        [InlineKeyboardButton('🧭 Весь маршрут', callback_data='whole_route')],
        [InlineKeyboardButton('📝 Добавить в маршрут', callback_data='add_help')],
    ])


def info_choice_menu(prefix):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton('📌 Общая информация', callback_data=f'{prefix}:short')],
        [InlineKeyboardButton('📚 Подробная информация', callback_data=f'{prefix}:full')],
        [InlineKeyboardButton('⬅️ Назад', callback_data='home')],
    ])


def dates_menu():
    rows=[]
    for d in ITINERARY['days']:
        rows.append([InlineKeyboardButton(f'🗓 {MONTH_RU.get(d["date"][5:], d["date"])}', callback_data=f'date:{d["day"]}')])
    rows.append([InlineKeyboardButton('⬅️ Назад', callback_data='home')])
    return InlineKeyboardMarkup(rows)


def date_mode_menu(day_num):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton('📌 Общая информация', callback_data=f'dayshort:{day_num}')],
        [InlineKeyboardButton('📚 Подробная информация', callback_data=f'dayfull:{day_num}')],
        [InlineKeyboardButton('⬅️ К датам', callback_data='pick_date')],
        [InlineKeyboardButton('🏠 В меню', callback_data='home')],
    ])


def detail_menu(day_num):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton('🧭 Общий план дня', callback_data=f'section:overview:{day_num}')],
        [InlineKeyboardButton('⏰ Расписание', callback_data=f'section:schedule:{day_num}')],
        [InlineKeyboardButton('🍜 Еда', callback_data=f'section:foodmenu:{day_num}')],
        [InlineKeyboardButton('🏯 Что посещаем', callback_data=f'section:visitmenu:{day_num}')],
        [InlineKeyboardButton('⚠️ Что важно', callback_data=f'section:important:{day_num}')],
        [InlineKeyboardButton('⬅️ К выбору формата', callback_data=f'date:{day_num}')],
        [InlineKeyboardButton('🏠 В меню', callback_data='home')],
    ])


def visit_menu(day_obj):
    rows=[[InlineKeyboardButton('🗂 Все места', callback_data=f'visitall:{day_obj["day"]}')]]
    for idx,item in enumerate(day_obj.get('visits', [])):
        rows.append([InlineKeyboardButton(f'📍 {item["name"]}', callback_data=f'visit:{day_obj["day"]}:{idx}')])
    rows.append([InlineKeyboardButton('⬅️ К подробному дню', callback_data=f'dayfull:{day_obj["day"]}')])
    return InlineKeyboardMarkup(rows)


def food_places(day_num):
    items=[]
    for idx,p in enumerate(PLACES_BY_DAY.get(str(day_num), [])):
        cat=(p.get('category') or '').lower(); name=p.get('name_en','')
        if any(k in cat for k in ['restaurant','cafe','coffee','bakery']) or any(k in name.lower() for k in ['coffee','ramen','bbq','kyoja','haidilao','bianyifang','siji','baekjeong','la yeon','ore']):
            items.append((idx,p))
    return items


def food_menu(day_num):
    rows=[[InlineKeyboardButton('🗂 Все места', callback_data=f'foodall:{day_num}')]]
    for idx,p in food_places(day_num):
        rows.append([InlineKeyboardButton(f'🍽 {p["name_en"]}', callback_data=f'food:{day_num}:{idx}')])
    rows.append([InlineKeyboardButton('⬅️ К подробному дню', callback_data=f'dayfull:{day_num}')])
    return InlineKeyboardMarkup(rows)


def short_day_text(day_obj):
    lines=[f'📅 {MONTH_RU.get(day_obj["date"][5:], day_obj["date"])} — {day_obj["title"]}', f'🏙 {day_obj["city"]}', '', day_obj['summary'], '', '⏱ План дня:']
    for item in day_obj['timeline']: lines.append(f'• {item["time"]} — {item["activity"]}')
    return '\n'.join(lines)[:3900]


def overview_text(day_obj): return f'<b>{MONTH_RU.get(day_obj["date"][5:], day_obj["date"])} — {day_obj["title"]}</b>\n{day_obj["summary"]}'

def schedule_text(day_obj):
    lines=[f'<b>Расписание — {MONTH_RU.get(day_obj["date"][5:], day_obj["date"])} </b>']
    for item in day_obj['timeline']: lines.append(f'• {item["time"]} — {item["activity"]}')
    return '\n'.join(lines)


def food_all_text(day_obj):
    lines=[f'<b>Еда — {MONTH_RU.get(day_obj["date"][5:], day_obj["date"])} </b>']
    items=food_places(day_obj['day'])
    if not items: lines.append('• В этот день отдельные food-точки пока не выделены.')
    for _,p in items:
        lines.append(f'• {linkify(p["name_en"], p.get("map_link"))} — {p.get("address","")}')
        if FOOD_DETAILS.get(p['name_en']): lines += [FOOD_DETAILS[p['name_en']], '']
    return '\n'.join(lines)


def visit_all_text(day_obj):
    lines=[f'<b>Что посещаем — {MONTH_RU.get(day_obj["date"][5:], day_obj["date"])} </b>']
    for v in day_obj.get('visits', []):
        place=next((p for p in PLACES_BY_DAY.get(str(day_obj['day']), []) if p['name_en']==v['name']), None)
        lines.append(f'• {linkify(v["name"], place.get("map_link") if place else "")} — {v["comment"]}')
        if PLACE_DETAILS.get(v['name']): lines += [PLACE_DETAILS[v['name']], '']
    user_items=USER_NOTES.get(str(day_obj['day']), [])
    if user_items: lines += ['<b>Добавлено вами:</b>'] + [f'• {x}' for x in user_items]
    return '\n'.join(lines)


def important_text(day_obj):
    lines=[f'<b>Что важно — {MONTH_RU.get(day_obj["date"][5:], day_obj["date"])} </b>']
    for n in day_obj.get('practical_notes', []): lines.append(f'• {n}')
    return '\n'.join(lines)


def full_route_short():
    lines=['<b>Весь маршрут — общая информация</b>']
    for d in ITINERARY['days']: lines.append(f'• {MONTH_RU.get(d["date"][5:], d["date"])} — {d["title"]} ({d["city"]})')
    return '\n'.join(lines)


def full_route_full():
    lines=['<b>Весь маршрут — подробная информация</b>']
    for d in ITINERARY['days']:
        lines += [f'\n<b>{MONTH_RU.get(d["date"][5:], d["date"])} — {d["title"]}</b>', d['summary']]
        top=', '.join([v['name'] for v in d.get('visits', [])[:4]])
        if top: lines.append(f'Главные точки: {top}.')
    return '\n'.join(lines)[:3900]


async def send_html(chat, text, reply_markup=None):
    await chat.send_message(text, parse_mode=ParseMode.HTML, disable_web_page_preview=False, reply_markup=reply_markup)


async def send_day_bundle(chat, day_num):
    d=find_day(day_num)
    await send_html(chat, overview_text(d))
    await send_html(chat, schedule_text(d))
    await send_html(chat, food_all_text(d))
    await send_html(chat, visit_all_text(d))
    await send_html(chat, important_text(d), reply_markup=detail_menu(day_num))


async def send_gallery(chat, place_name):
    gallery = PHOTO_GALLERIES.get(place_name, [])
    if not gallery:
        return False
    slug = re.sub(r'[^a-z0-9]+','_', place_name.lower())
    sent = 0
    for i, url in enumerate(gallery[:6], start=1):
        path = download_photo(url, slug, i)
        if path and os.path.exists(path):
            with open(path, 'rb') as img:
                await chat.send_photo(photo=img)
                sent += 1
    return sent > 0


async def show_place_card(chat, day_num, idx):
    d=find_day(day_num); visit=d['visits'][idx]; name=visit['name']
    place=next((p for p in PLACES_BY_DAY.get(str(day_num), []) if p['name_en']==name), None)
    text=[f'<b>{name}</b>', '', visit['comment']]
    if PLACE_DETAILS.get(name): text += ['', PLACE_DETAILS[name]]
    if place and place.get('address'): text += ['', f'Адрес: {place.get("address")}']
    if place and place.get('map_link'): text.append(f'Карта: <a href="{place.get("map_link")}">открыть</a>')
    for src in RU_SOURCES.get(name, []):
        text.append(f'Источник RU: <a href="{src}">открыть</a>')
    await send_gallery(chat, name)
    await chat.send_message('\n'.join(text), parse_mode=ParseMode.HTML, disable_web_page_preview=False, reply_markup=visit_menu(d))


async def show_food_card(chat, day_num, idx):
    p=PLACES_BY_DAY.get(str(day_num), [])[idx]; name=p['name_en']
    lines=[f'<b>{linkify(name, p.get("map_link"))}</b>']
    if p.get('address'): lines.append(f'Адрес: {p.get("address")}')
    lines += ['', FOOD_DETAILS.get(name, 'Это одна из основных food-точек дня. Сюда стоит идти как на якорный приём пищи или coffee stop внутри маршрута.')]
    if p.get('booking_link'): lines.append(f'Бронь: <a href="{p.get("booking_link")}">открыть</a>')
    await send_gallery(chat, name)
    await chat.send_message('\n'.join(lines), parse_mode=ParseMode.HTML, disable_web_page_preview=False, reply_markup=food_menu(day_num))


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('Привет! Здесь маршрут по поездке с более детальными местами, едой и фото.', reply_markup=main_menu())


async def on_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q=update.callback_query; await q.answer(); data=q.data
    if data=='home': await q.edit_message_text('Главное меню', reply_markup=main_menu())
    elif data=='today_menu': await q.edit_message_text('Маршрут сегодня:', reply_markup=info_choice_menu('today'))
    elif data=='tomorrow_menu': await q.edit_message_text('Маршрут завтра:', reply_markup=info_choice_menu('tomorrow'))
    elif data=='pick_date': await q.edit_message_text('Выбери дату:', reply_markup=dates_menu())
    elif data=='whole_route': await q.edit_message_text('Весь маршрут:', reply_markup=info_choice_menu('route'))
    elif data=='add_help': await q.edit_message_text('Напиши сообщением, например: «добавь 7 мая посещение магазина с пряжей».', reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🏠 В меню', callback_data='home')]]))
    elif data=='today:short': await q.edit_message_text(short_day_text(find_day(today_day())), reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('📚 Подробная информация', callback_data=f'dayfull:{today_day()}')],[InlineKeyboardButton('🏠 В меню', callback_data='home')]]))
    elif data=='today:full': await q.edit_message_text('Подробная информация на сегодня. Выбери раздел ниже.', reply_markup=detail_menu(today_day()))
    elif data=='tomorrow:short': await q.edit_message_text(short_day_text(find_day(tomorrow_day())), reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('📚 Подробная информация', callback_data=f'dayfull:{tomorrow_day()}')],[InlineKeyboardButton('🏠 В меню', callback_data='home')]]))
    elif data=='tomorrow:full': await q.edit_message_text('Подробная информация на завтра. Выбери раздел ниже.', reply_markup=detail_menu(tomorrow_day()))
    elif data.startswith('date:'):
        day_num=data.split(':',1)[1]
        await q.edit_message_text(f'Дата: {MONTH_RU.get(find_day(day_num)["date"][5:], find_day(day_num)["date"])}', reply_markup=date_mode_menu(day_num))
    elif data.startswith('dayshort:'):
        day_num=data.split(':',1)[1]
        await q.edit_message_text(short_day_text(find_day(day_num)), reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('📚 Подробная информация', callback_data=f'dayfull:{day_num}')],[InlineKeyboardButton('⬅️ К датам', callback_data='pick_date')],[InlineKeyboardButton('🏠 В меню', callback_data='home')]]))
    elif data.startswith('dayfull:'):
        day_num=data.split(':',1)[1]
        await q.edit_message_text('Подробная информация по дню. Выбери нужный раздел.', reply_markup=detail_menu(day_num))
    elif data=='route:short':
        await q.edit_message_text(full_route_short(), parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('📚 Подробная информация', callback_data='route:full')],[InlineKeyboardButton('🏠 В меню', callback_data='home')]]))
    elif data=='route:full':
        await q.edit_message_text(full_route_full(), parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('📌 Общая информация', callback_data='route:short')],[InlineKeyboardButton('🏠 В меню', callback_data='home')]]))
    elif data.startswith('section:'):
        _, section, day_num = data.split(':',2); d=find_day(day_num)
        if section=='overview':
            await q.edit_message_text('Отправляю общий план дня отдельными сообщениями…', reply_markup=detail_menu(day_num))
            await send_day_bundle(q.message.chat, day_num)
        elif section=='schedule': await q.edit_message_text(schedule_text(d), parse_mode=ParseMode.HTML, reply_markup=detail_menu(day_num))
        elif section=='foodmenu': await q.edit_message_text('Выбери место по еде:', reply_markup=food_menu(day_num))
        elif section=='visitmenu': await q.edit_message_text('Выбери место:', reply_markup=visit_menu(d))
        elif section=='important': await q.edit_message_text(important_text(d), parse_mode=ParseMode.HTML, reply_markup=detail_menu(day_num))
    elif data.startswith('foodall:'):
        day_num=data.split(':',1)[1]
        await q.edit_message_text(food_all_text(find_day(day_num)), parse_mode=ParseMode.HTML, disable_web_page_preview=False, reply_markup=food_menu(day_num))
    elif data.startswith('food:'):
        _, day_num, idx = data.split(':',2)
        await q.edit_message_text('Открываю место по еде…', reply_markup=food_menu(day_num))
        await show_food_card(q.message.chat, day_num, int(idx))
    elif data.startswith('visitall:'):
        day_num=data.split(':',1)[1]
        await q.edit_message_text(visit_all_text(find_day(day_num)), parse_mode=ParseMode.HTML, disable_web_page_preview=False, reply_markup=visit_menu(find_day(day_num)))
    elif data.startswith('visit:'):
        _, day_num, idx = data.split(':',2)
        await q.edit_message_text('Открываю карточку места…', reply_markup=visit_menu(find_day(day_num)))
        await show_place_card(q.message.chat, day_num, int(idx))


async def parse_add_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text=(update.message.text or '').strip()
    m=re.match(r'(?i)^добав[ьй]\s+(\d{1,2})\s+мая\s+(.+)$', text)
    if not m: return
    day_num, content = m.group(1), m.group(2).strip()
    if not find_day(day_num):
        await update.message.reply_text('Не вижу такого дня в маршруте. Поддерживаются даты с 1 по 12 мая.')
        return
    USER_NOTES.setdefault(str(int(day_num)), []).append(content)
    save_notes()
    await update.message.reply_text(f'Добавил в маршрут на {day_num} мая:\n• {content}')


if __name__ == '__main__':
    app=ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CallbackQueryHandler(on_button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, parse_add_request))
    app.run_polling()
