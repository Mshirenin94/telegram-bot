import csv
import json
import os
import re
import time
import urllib.request

import tempfile
from anthropic import Anthropic
from openai import OpenAI
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

EXPENSES_PATH = os.path.join(BASE_DIR, 'expenses.json')
if os.path.exists(EXPENSES_PATH):
    EXPENSES = json.load(open(EXPENSES_PATH, encoding='utf-8'))
else:
    EXPENSES = {}

CITY_COORDS = {
    'Пекин': (39.9042, 116.4074, 'Asia/Shanghai'),
    'Сеул': (37.5665, 126.9780, 'Asia/Seoul'),
}

WEATHER_CODES = {
    0: 'Ясно', 1: 'В основном ясно', 2: 'Переменная облачность', 3: 'Облачно',
    45: 'Туман', 48: 'Туман с инеем',
    51: 'Морось слабая', 53: 'Морось', 55: 'Сильная морось',
    61: 'Дождь слабый', 63: 'Дождь', 65: 'Сильный дождь',
    71: 'Снег слабый', 73: 'Снег', 75: 'Сильный снег',
    80: 'Ливни слабые', 81: 'Ливни', 82: 'Сильные ливни',
    95: 'Гроза', 96: 'Гроза с градом', 99: 'Сильная гроза с градом',
}

EXCHANGE_TO_RUB = {
    'CNY': 11.5,
    'KRW': 0.063,
    'USD': 83.0,
    'RUB': 1.0,
}
EXCHANGE_LOCKED_AT = '25 апреля 2026'
CURRENCY_SYMBOLS = {'CNY': '¥', 'KRW': '₩', 'USD': '$', 'RUB': '₽'}
CURRENCY_ALIASES = [
    (re.compile(r'(?i)\bюан\w*|\bcny\b|¥'), 'CNY'),
    (re.compile(r'(?i)\bвон\w*|\bkrw\b|₩'), 'KRW'),
    (re.compile(r'(?i)\bдоллар\w*|\busd\b|\$'), 'USD'),
    (re.compile(r'(?i)\bрубл\w*|\bруб\w*|\bр\b'), 'RUB'),
]

EXPENSE_CATEGORIES = ['Еда', 'Транспорт', 'Шопинг', 'Билеты', 'Прочее']
CATEGORY_EMOJI = {'Еда': '🍜', 'Транспорт': '🚇', 'Билеты': '🎟', 'Шопинг': '🛍', 'Прочее': '✨'}
CATEGORY_HINTS = {
    'Еда': 'Примеры:\n• 200 юаней ужин в Da Dong\n• 35000 вон самгёпсаль\n• 8 долларов кофе',
    'Транспорт': 'Примеры:\n• 30 юаней такси DiDi\n• 4500 вон метро\n• 9000 вон AREX до Сеула',
    'Билеты': 'Примеры:\n• 60 юаней Запретный город\n• 15000 вон Changgyeonggung\n• 70000 вон NANTA',
    'Шопинг': 'Примеры:\n• 800 юаней сувениры\n• 45000 вон косметика\n• 1200 рублей пряжа',
    'Прочее': 'Примеры:\n• 200 юаней чаевые\n• 5000 вон камера хранения\n• 1500 рублей разное',
}

MONTH_RU = {'05-01':'1 мая','05-02':'2 мая','05-03':'3 мая','05-04':'4 мая','05-05':'5 мая','05-06':'6 мая','05-07':'7 мая','05-08':'8 мая','05-09':'9 мая','05-10':'10 мая','05-11':'11 мая','05-12':'12 мая'}



RU_SOURCES = {
    "Forbidden City": ["https://ru.wikipedia.org/wiki/%D0%97%D0%B0%D0%BF%D1%80%D0%B5%D1%82%D0%BD%D1%8B%D0%B9_%D0%B3%D0%BE%D1%80%D0%BE%D0%B4"],
    "Jingshan Park": ["https://ru.wikipedia.org/wiki/%D0%A6%D0%B7%D0%B8%D0%BD%D1%88%D0%B0%D0%BD%D1%8C_(%D0%BF%D0%B0%D1%80%D0%BA)"],
    "Nanluoguxiang": ["https://ru.wikipedia.org/wiki/%D0%A5%D1%83%D1%82%D1%83%D0%BD"],
    "Shichahai": ["https://ru.wikipedia.org/wiki/%D0%A5%D1%83%D1%82%D1%83%D0%BD"],
    "Temple of Heaven": ["https://ru.wikipedia.org/wiki/%D0%A5%D1%80%D0%B0%D0%BC_%D0%9D%D0%B5%D0%B1%D0%B0"],
    "Mutianyu Great Wall": ["https://ru.wikipedia.org/wiki/%D0%92%D0%B5%D0%BB%D0%B8%D0%BA%D0%B0%D1%8F_%D0%9A%D0%B8%D1%82%D0%B0%D0%B9%D1%81%D0%BA%D0%B0%D1%8F_%D1%81%D1%82%D0%B5%D0%BD%D0%B0"],
    "798 Art Zone": ["https://ru.wikipedia.org/wiki/798_(%D1%80%D0%B0%D0%B9%D0%BE%D0%BD_%D0%B8%D1%81%D0%BA%D1%83%D1%81%D1%81%D1%82%D0%B2)"],
    "Wangfujing": ["https://ru.wikipedia.org/wiki/%D0%92%D0%B0%D0%BD%D1%84%D1%83%D1%86%D0%B7%D0%B8%D0%BD"],
    "Changgyeonggung": ["https://ru.wikipedia.org/wiki/%D0%A7%D1%85%D0%B0%D0%BD%D0%B3%D1%91%D0%BD%D0%B3%D1%83%D0%BD"],
    "Gyeongbokgung": ["https://ru.wikipedia.org/wiki/%D0%9A%D1%91%D0%BD%D0%B1%D0%BE%D0%BA%D0%BA%D1%83%D0%BD", "https://wikiway.com/south-korea/seul/dostoprimechatelnosti/dvorets-kenbokkun/"],
    "Bukchon": ["https://koreana-tour.ru/bukchon-hanok-village-seoul/"],
    "Insadong": ["https://koreana-tour.ru/insadong-seoul/"],
    "Myeongdong": ["https://koreana-tour.ru/myeongdong-seoul/"],
    "NANTA Theater": ["https://ru.wikipedia.org/wiki/Nanta"],
    "Bukhansan National Park": ["https://ru.wikipedia.org/wiki/%D0%9F%D1%83%D0%BA%D1%85%D0%B0%D0%BD%D1%81%D0%B0%D0%BD"],
    "COEX Mall": ["https://ru.wikipedia.org/wiki/COEX"],
    "Hongdae": ["https://koreana-tour.ru/hongdae-seoul/"],
    "Ikseon-dong": ["https://koreana-tour.ru/ikseondong-seoul/"],
    "Seongsu": ["https://koreana-tour.ru/seongsu-dong-seoul/"],
    "N Seoul Tower": ["https://ru.wikipedia.org/wiki/N_Seoul_Tower"],
    "Cheonggyecheon": ["https://ru.wikipedia.org/wiki/%D0%A7%D1%85%D0%BE%D0%BD%D0%B3%D0%B5%D1%87%D1%85%D0%BE%D0%BD"]
}

PLACE_DETAILS = {
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
}

FOOD_DETAILS = {
    "Bianyifang": "Что брать: фирменную пекинскую утку, блинчики, scallions, cucumber и соус; если хочется попробовать более традиционный стиль, обрати внимание на skin с сахаром. По отзывам сильнее всего запоминаются исторический статус ресторана, более классическая подача утки и сам old Beijing feel.",
    "Siji Minfu": "Что брать: Peking duck как обязательную позицию, thin pancakes, duck skin with sugar, honey shrimp, mustard cabbage и один тёплый side dish. По отзывам это один из самых надёжных и понятных duck-ресторанов Пекина: crispy skin, хорошая нарезка и сильный value-for-money.",
    "Haidilao": "Что брать: tomato broth или mild broth, hand-pulled noodles, beef/lamb, leafy greens и sauce bar под себя. По отзывам сильнее всего любят сервис, скорость, sauce station и ощущение, что даже первый hotpot-опыт проходит легко и без хаоса.",
    "Myeongdong Kyoja": "Что брать: kalguksu и mandu, а если будет настроение — попробовать фирменный garlic kimchi. По отзывам людей цепляет сочетание лёгкого, но насыщенного broth, хорошей текстуры лапши и очень мясных juicy dumplings.",
    "La Yeon": "Что ожидать: fine dining с корейской рамкой, polished service и special occasion energy. В обзорах чаще выделяют galbijjim, yukjeon и в целом высокий уровень execution; сюда идут не за casual meal, а за полноценный праздничный ужин.",
    "Baekjeong": "Что брать: мясные позиции для grill, samgyeopsal/galbi-type наборы, banchan и lettuce wraps. Это скорее про lively Korean BBQ experience, чем про одно конкретное блюдо.",
    "Oreno Ramen": "Что брать: signature ramen и при желании gyoza. Это хороший быстрый lunch anchor, если хочется плотной, понятной и не слишком экспериментальной еды.",
    "Momos Coffee": "Сюда идти за specialty coffee и короткой передышкой. Главная сила точки — кофе и атмосфера, а не еда.",
    "Fritz Coffee": "Хороший coffee stop для mid-day reset: кофе, выпечка и приятная пауза внутри прогулочного ритма."
}

PHOTO_GALLERIES = {
    "The Yard Hotel Beijing": [
        "https://pplx-res.cloudinary.com/image/upload/pplx_search_images/dbb0432486dbcf6c12990fe77552547a11fb97a1.jpg",
        "https://pplx-res.cloudinary.com/image/upload/pplx_search_images/26b97d6307fb0c1c383cbc17b5b2d429d8685e38.jpg",
        "https://pplx-res.cloudinary.com/image/upload/pplx_search_images/a39bd68e482a04824759681d3ce65b3c8f5ec4d1.jpg"
    ],
    "Xianyukou Street": [
        "https://www.tour-beijing.com/photos/600_400/wfj_1.jpg",
        "https://www.tour-beijing.com/photos/600_400/foot_1.jpg",
        "https://ruqintravel.com/wp-content/uploads/2024/12/Beijing-Xianyukou-7-7.webp"
    ],
    "Forbidden City": [
        "https://pplx-res.cloudinary.com/image/upload/pplx_search_images/1df3a7396c3fc0a838e51204e704f033bd0dfd5d.jpg",
        "https://pplx-res.cloudinary.com/image/upload/pplx_search_images/aa6fa001623a6439574807fd89dc8066e94f8220.jpg",
        "https://pplx-res.cloudinary.com/image/upload/pplx_search_images/11db677c789f029deca66b0dd06e139d468dd555.jpg"
    ],
    "Jingshan Park": [
        "https://www.encirclephotos.com/wp-content/uploads/China-Beijing-Forbidden-City-Pavilion-Jingshan-Park-600x403.jpg",
        "https://www.wanderinchina.com/img/forbidden-city-in-beijing-during-golden-hour-img-3_hu_27ef6a51532a717e.webp",
        "https://media.gettyimages.com/id/1279789685/photo/overview-of-the-northern-entrance-to-the-forbidden-city-from-jingshan-park.jpg?s=612x612&w=0&k=20&c=r8fbBG5E1BYZLcqZRYU5KLy3uUw8c9gOZXrv2DZT9jc="
    ],
    "Nanluoguxiang": [
        "https://live.staticflickr.com/2893/8886236759_536516d364.jpg",
        "https://ssawgardenhotelbeijing.com/wp-content/uploads/2025/08/Nanluoguxiang-and-Guozijian-Street.jpg",
        "https://media.gettyimages.com/id/620991634/photo/nanluoguxiang-beijing-china.jpg?s=612x612&w=0&k=20&c=l2bOHcM1ACP969oqtV9fqMxo6_uVMiLQ9RVhZlRuAyw="
    ],
    "Shichahai": [
        "https://media.istockphoto.com/id/1167653954/photo/shichahai-district-in-beijing.jpg?s=612x612&w=0&k=20&c=9xelZcEMkCAwGHsev4V9G7axXkP_YBF0fnHS8XZcuvk=",
        "https://media.istockphoto.com/id/1167653956/photo/shichahai-district-in-beijing.jpg?s=612x612&w=0&k=20&c=Jg8QRcJcKHcUdlMu9cOpFZty3fh8Wi1IQX7QxkBXttE=",
        "https://foyochinatrip.com/wp-content/uploads/2026/03/2_%E7%BB%93%E6%9E%9C-3.webp"
    ],
    "Mutianyu Great Wall": [
        "https://routesofchina.com/wp-content/uploads/2025/07/mutianyu-great-wall-section-1024x683.webp",
        "https://res.klook.com/image/upload/q_85/c_fill,w_1360/v1742874954/x1dmkcbypucvppewyaqu.jpg",
        "https://gohsomewhere.com/wp-content/uploads/2025/04/mutianyu-3-1024x683.avif"
    ],
    "Temple of Heaven": [
        "https://www.ancient-origins.net/sites/default/files/styles/article_image/public/field/image/Temple-of-Heaven.jpg?itok=Vd3tphER",
        "https://www.thechinajourney.com/wp-content/uploads/2025/04/Temple-of-Heaven-Beijing-Hall-of-Prayer-for-Good-Harvests-illuminated-at-night-viewed-through-open-red-palace-doors-under-a-deep-blue-sky-1024x683.webp",
        "https://preview.redd.it/30w748d0tdn31.jpg?width=640&crop=smart&auto=webp&s=12ae4e038589af446b063b10640a285e20cf66d8"
    ],
    "798 Art Zone": [
        "https://urbanchinatravelogue.com/wp-content/uploads/2025/11/beijing-798-art-district-street-candid.webp",
        "https://museumofwander.com/wp-content/uploads/2023/03/DSC00731.jpg",
        "https://familyhotelfinder.com/wp-content/uploads/Beijing-798-Art-District1-SH.jpg?w=960&h=540&func=cover"
    ],
    "Wangfujing": [
        "https://ruqintravel.com/wp-content/uploads/2024/12/Beijing-Wangfujing-Shopping-7-7.webp",
        "https://ruqintravel.com/wp-content/uploads/2024/12/Beijing-Wangfujing-Shopping-5-5.webp",
        "https://ruqintravel.com/wp-content/uploads/2024/12/Beijing-Wangfujing-Shopping-4-4.webp"
    ],
    "Brooklyn Blues Hotel": [
        "https://i2.wp.com/images.trvl-media.com/lodging/115000000/114420000/114413300/114413204/2c532251.jpg",
        "https://i2.wp.com/images.trvl-media.com/lodging/115000000/114420000/114413300/114413204/3c6996a5.jpg",
        "https://i2.wp.com/images.trvl-media.com/lodging/115000000/114420000/114413300/114413204/01f655ed.jpg"
    ],
    "Changgyeonggung": [
        "https://seoulshopper.com/cdn/shop/articles/changgyeonggung-palace-seoul8_181eed9f-d50d-4653-ac93-50723f93f579_2048x2048.jpg?v=1744950942",
        "https://farm5.staticflickr.com/4717/39673583382_fdec128149_c.jpg",
        "https://cdn.shopify.com/s/files/1/0609/9376/5551/files/changgyeonggung-palace-seoul-changgyeong-_43.jpg?v=1697613017"
    ],
    "Gyeongbokgung": [
        "https://pplx-res.cloudinary.com/image/upload/pplx_search_images/73c32cc741f973d2ae0c3be6d6e81f62ac55c730.jpg",
        "https://pplx-res.cloudinary.com/image/upload/pplx_search_images/005cd5a97cd816d2ee7e0fee2f8ae951c5af0ec8.jpg",
        "https://pplx-res.cloudinary.com/image/upload/pplx_search_images/0945b3cf42cafe9e0f6960be0e3261279da781b0.jpg"
    ],
    "Bukchon": [
        "https://www.busanpedia.com/wp-content/uploads/2024/01/bukchon-hanok-village-alleys-seoul-683x1024.jpg",
        "https://alovelettertoasia.com/wp-content/uploads/2024/06/bukchon-village-traditional-korean-house-hanok.jpg",
        "https://architectureontheroad.com/wp-content/uploads/2020/03/Seoul_hanok-villages_architecture-on-the-road-22-of-44.jpg"
    ],
    "Insadong": [
        "https://alovelettertoasia.com/wp-content/uploads/2024/03/insadong-traditional-korean-restaurant-seoul.jpg",
        "https://blogger.googleusercontent.com/img/b/R29vZ2xl/AVvXsEiCXtTxWlfNwrJUQ8yCsnfOIkz9IE6rVA5I1-rzcE9P5nKWImbYrBrSpY3Km0QMGdmv4G4P_A7CARz7WaqMr9Zx5OfKwzA0TONAc2Uc57_Y_cNvbQfKJ2cA0AqD1gJPW52tqS8HqziLvhixKBb5c1QC_K0HwniXQDVIoOBzFPbshtDcjU7XZpYtpBXub1o/w400-h400-rw/ChatGPT%20Image%202025%EB%85%84%205%EC%9B%94%2022%EC%9D%BC%20%EC%98%A4%ED%9B%84%2004_41_11.png",
        "https://travelgasm.com/images/seoul-south-korea/insadong-art-galleries-teahouses-seoul-south-korea.jpg"
    ],
    "Myeongdong": [
        "https://static.wixstatic.com/media/0505b9_a3c6ad84ba5e45a2bb61a53f4f35652b~mv2.jpg/v1/crop/x_0,y_122,w_1254,h_793/fill/w_980,h_620,al_c,q_85,usm_0.66_1.00_0.01,enc_avif,quality_auto/Myeongdong%20Shopping%20Street%20-%20Night%201-2%20landscape%20KTD%202024.jpg",
        "https://media.gettyimages.com/id/545252231/photo/the-famous-shopping-streets-of-myeong-dong.jpg?s=612x612&w=0&k=20&c=n8ODk8mE93Kmj21UmAZSSzLNMDUDwx936m1IALy1BLg=",
        "https://www.cktravels.com/wp-content/uploads/2022/12/SEOUL-MYEONGDONG-7.jpg"
    ],
    "NANTA Theater": [
        "https://cdn-imgix.headout.com/media/images/1cb6404db7908dc467fa3e3a63baf20b-23892-SeoulNightGuidedTourwithNantaPerformance--008.jpg?auto=compress,format&w=695.0400000000001&h=434.4&q=96&crop=faces&fit=crop",
        "https://res.klook.com/images/fl_lossy.progressive,q_65/c_fill,w_1147,h_750/w_70,x_13,y_13,g_south_west,l_Klook_water_br_trans_yhcmh3/activities/fxqu6xr7esm3o9gollso/NantaShowTicketinSeoul.webp",
        "https://cf.creatrip.com/original/blog/4283/81lhf6qvngb7qbgetpgt5ddz14onmo2s.png"
    ],
    "Bukhansan National Park": [
        "https://ak-d.tripcdn.com/images/1mi4w224x93rnb8is326A_W_640_0_R5_Q80.jpg?proc=source/trip",
        "https://lifeofdoing.com/wp-content/uploads/2023/08/Bukhansan-National-Park-Temple-MuseumOfWander.jpg",
        "https://ak-d.tripcdn.com/images/1mi3w224x93rn24gp24E7_W_640_0_R5_Q80.jpg?proc=source/trip"
    ],
    "Bibong Peak": [
        "https://www.ivisitkorea.com/wp-content/uploads/2023/06/Seoul-View-from-Bukhansan-National-Park.jpg",
        "https://4corners7seas.com/wp-content/uploads/2019/03/bibong-peak-33-1024x638.jpg",
        "https://4corners7seas.com/wp-content/uploads/2019/03/bibong-peak-40-1024x508.jpg"
    ],
    "Jingwansa Temple": [
        "https://i.pinimg.com/originals/5d/59/18/5d59186e08ccb77fab09b708a89b8f3c.jpg",
        "https://seoulistic.com/wp-content/uploads/2017/06/jingwansa-temple-bukhansan-buddhist-temple-in-seoul.jpg",
        "https://thesoulofseoul.net/wp-content/uploads/2013/06/Jingwansa-Temple-A-Beautiful-Temple-To-Find-On-Bukhansan-Mountain-In-Seoul-1-683x1024.jpg"
    ],
    "Whoo Spa": [
        "https://beautipin.com/cdn/shop/articles/ultra-realistic-premium-beauty-editorial-photo-of-a-korean-head-spa-in-seoul-east-asian-woman-receiving-a-waterfall-scalp-rinse-on-a-reclining-spa-bed-clean-modern-salon-interior-soft.png?crop=center&height=873&v=1776419121&width=1248",
        "https://media-cdn.tripadvisor.com/media/photo-o/12/f8/11/e3/the-spa-grand-hyatt-seoul.jpg",
        "https://beautipin.com/cdn/shop/articles/00_4ee27908-4c43-4541-bcc8-b95a638d11cc.png?crop=center&height=792&v=1749784158&width=1408"
    ],
    "COEX Mall": [
        "https://a.travel-assets.com/findyours-php/viewfinder/images/res70/343000/343336-Seoul-City.jpg?impolicy=fcrop&w=1040&h=580&q=mediumHigh",
        "https://thumbs.dreamstime.com/b/coex-starfield-mall-interior-seoul-south-korea-interior-coex-starfield-mall-gangnam-district-seoul-south-195553847.jpg",
        "https://travel-stained.com/wp-content/uploads/2018/12/1024px-COEX_Mall_Central_Plaza_Atrium_2016.jpg"
    ],
    "Starfield Library": [
        "https://kculture.com/wp-content/uploads/2026/02/2535386.jpg",
        "https://static.wixstatic.com/media/0505b9_55dfa96c937a47aa90f989aae2182446~mv2.jpg/v1/crop/x_0,y_77,w_1296,h_820/fill/w_980,h_620,al_c,q_85,usm_0.66_1.00_0.01,enc_avif,quality_auto/Stafield%20Library%201%20G8.jpg",
        "https://i1.wp.com/seoulsearching.net/wp-content/uploads/2023/09/library-005-1024x576.png?ssl=1"
    ],
    "Seongsu": [
        "https://english.seoul.go.kr/wp-content/uploads/2020/01/yeonmujang-gil-1.jpg",
        "https://english.seoul.go.kr/wp-content/uploads/2022/02/seongsu-dong-cafe-street01.jpg",
        "https://english.seoul.go.kr/wp-content/uploads/2020/01/yeonmujang-gil-4.jpg"
    ],
    "Hongdae": [
        "https://www.agoda.com/wp-content/uploads/2024/07/Hongdae-Stree-Featured-1244x700.jpg",
        "https://www.urbantravelblog.com/wp-content/uploads/2016/07/Hongdae-Streets-686x1024.jpg",
        "https://knowaboutkorea.com/_next/image?url=/images/places/hongdae.jpg&w=3840&q=75"
    ],
    "Club Evans": [
        "https://i.pinimg.com/originals/2d/a2/b0/2da2b0b9c999e439acd8c0968b7f661e.jpg",
        "https://asomemusic.com/wp-content/uploads/2025/07/jazz-bar-seoul9.jpeg",
        "https://lh3.googleusercontent.com/p/AF1QipO7WmT3dQVevh61aS3BN0-ZszIW2JQme98UT7Rm=s1600-w640"
    ],
    "Ikseon-dong": [
        "https://alovelettertoasia.com/wp-content/uploads/2024/03/ikseondong-seoul-south-korea-alley.jpg",
        "https://moving-jack.com/wp-content/uploads/2025/03/ikseon-dong-hanok-street-seoul-south-korea-culture-traditional-outfits-classic-old-asian-style-Copyright-Moving-Jack.com-10-1-682x1024.jpg",
        "https://moving-jack.com/wp-content/uploads/2025/03/ikseon-dong-hanok-street-seoul-south-korea-culture-traditional-outfits-classic-old-asian-style-Copyright-Moving-Jack.com-5-1.jpg"
    ],
    "N Seoul Tower": [
        "https://images.pexels.com/photos/20839149/pexels-photo-20839149/free-photo-of-hill-with-a-communication-tower-above-the-fog-shrouded-city.jpeg?auto=compress&cs=tinysrgb&dpr=1&w=500",
        "https://media.gettyimages.com/id/1455247670/photo/namsan-seoul-tower.jpg?s=612x612&w=0&k=20&c=MwF5qJNer4bYCIN7v9ByhSSszdvwZSLWCadLUiJ1KMs=",
        "https://plus.unsplash.com/premium_photo-1661885493074-e18964497278?fm=jpg&q=60&w=3000&ixlib=rb-4.1.0&ixid=M3wxMjA3fDB8MHxzZWFyY2h8NXx8bmFtc2FuJTIwc2VvdWwlMjB0b3dlcnxlbnwwfHwwfHx8MA=="
    ],
    "Bianyifang": [
        "https://dynamic-media-cdn.tripadvisor.com/media/photo-o/04/94/de/a6/bianyi-fang-qianmen-xian.jpg?w=900&h=500&s=1"
    ],
    "Siji Minfu": [
        "https://travelchinawith.me/wp-content/uploads/siji-minfu-dishes.jpeg",
        "https://travelchinawith.me/wp-content/uploads/siji-minfu-forbidden-city.png",
        "https://img1.boatcdn.com/user_img/qsjSWuDlTw-2JHGxbnJBzA"
    ],
    "Haidilao": [
        "https://i.pinimg.com/originals/e4/68/d0/e468d0c6766ec315e82a0c157ef426c2.jpg",
        "https://rs.wescover.com/c_limit,f_auto,q_auto,w_500/v1/wescover-user-uploaded/uhrcmfdgltv8atmumzdn",
        "https://rs.wescover.com/c_limit,f_auto,q_auto,w_500/v1/wescover-user-uploaded/ygs2d8npwhemrxgk2mew"
    ],
    "Myeongdong Kyoja": [
        "https://ittekuru.com/wp-content/uploads/2017/02/09feb16-001-south-korea-seoul-myeongdong-kyoja-kalguksu-restaurant-noodles-mandu-dumplings.jpg?w=750&h=563",
        "https://www.cktravels.com/wp-content/uploads/2023/10/kyoja-16.jpg",
        "https://www.cktravels.com/wp-content/uploads/2023/08/kyoja-2.jpg"
    ],
    "La Yeon": [
        "https://foreignerlivinginkorea.com/wp-content/uploads/2025/05/la-yeon-seoul-the-shilla.jpeg?w=866",
        "https://www.luxurytravelmagazine.com/files/593/6/76586/The_Shilla_Seoul_La_Yeon_Team_bu.jpg",
        "https://res.klook.com/images/fl_lossy.progressive,q_65/c_fill,w_1295,h_720/w_80,x_15,y_15,g_south_west,l_Klook_water_br_trans_yhcmh3/activities/lhvhj8e1lrf0auodlclw/ShillaLaYeonRestaurantReservationService.jpg"
    ],
    "Baekjeong": [
        "https://images.ctfassets.net/dsbipkqphva2/6hcNvfIoCNePROXiFpeV8K/0cde90f87e23d02b38291a41814d161a/best-korean-bbq-restaurants-seoul-lead-min.jpg?fm=webp",
        "https://indulgenteats.com/wp-content/uploads/2023/09/Seoul-Travel-Guide-Chungkiwa-Town-Korean-BBQ-Hongdae-1-min.jpeg",
        "https://indulgenteats.com/wp-content/uploads/2025/04/Best-Korean-BBQ-in-Seoul-Sancheong-Sutbul-Charcoal-Garden-Euljiro-min.jpg"
    ],
    "Oreno Ramen": [
        "https://ilseonthego.com/wp-content/uploads/2025/09/Oreno-Ramen-Best-Places-Eat-Seoul-12-768x1024.webp",
        "https://s3-media0.fl.yelpcdn.com/bphoto/ED6GHPOYExgg8czdlhXJpA/l.jpg",
        "https://preview.redd.it/oreno-ramen-in-hongdae-seoul-v0-jy7cvkpjbbzd1.jpg?width=640&crop=smart&auto=webp&s=4732223fb02d86a7f685a20c7e8fd9aa7ce1fe58"
    ]
}


def save_notes():
    with open(USER_NOTES_PATH, 'w', encoding='utf-8') as f:
        json.dump(USER_NOTES, f, ensure_ascii=False, indent=2)


def save_expenses():
    with open(EXPENSES_PATH, 'w', encoding='utf-8') as f:
        json.dump(EXPENSES, f, ensure_ascii=False, indent=2)


def detect_currency(text):
    for rx, code in CURRENCY_ALIASES:
        if rx.search(text):
            return code
    return None


def parse_expense(text):
    m = re.match(r'^\s*(\d+(?:[.,]\d+)?)\s+(.+)$', text)
    if not m:
        return None
    amount = float(m.group(1).replace(',', '.'))
    rest = m.group(2).strip()
    cur = detect_currency(rest)
    if not cur:
        return None
    comment = rest
    for rx, _ in CURRENCY_ALIASES:
        comment = rx.sub('', comment)
    comment = re.sub(r'\s+', ' ', comment).strip(' .,;:-')
    return amount, cur, comment


def normalize_city(city):
    return 'Сеул' if 'Сеул' in city else 'Пекин'


def add_expense(day_num, amount, currency, comment, category='Прочее'):
    rub = round(amount * EXCHANGE_TO_RUB.get(currency, 1.0), 2)
    item = {
        'amount': amount, 'currency': currency, 'rub': rub,
        'comment': comment, 'category': category, 'ts': time.time(),
    }
    EXPENSES.setdefault(str(day_num), []).append(item)
    save_expenses()
    return rub, item


def undo_last_expense():
    best = None
    for day, items in EXPENSES.items():
        for i, it in enumerate(items):
            ts = it.get('ts', 0)
            if best is None or ts > best[0]:
                best = (ts, day, i)
    if best is None:
        return None
    _, day, idx = best
    removed = EXPENSES[day].pop(idx)
    if not EXPENSES[day]:
        del EXPENSES[day]
    save_expenses()
    return day, removed


def expenses_summary_text():
    lines = [
        '<b>Расходы по дням</b>',
        f'<i>Курс зафиксирован {EXCHANGE_LOCKED_AT}: 1 ¥ = {EXCHANGE_TO_RUB["CNY"]} ₽, 1 ₩ = {EXCHANGE_TO_RUB["KRW"]} ₽, 1 $ = {EXCHANGE_TO_RUB["USD"]} ₽</i>',
        ''
    ]
    city_total = 0.0
    grand = 0.0
    prev_city = None
    for d in ITINERARY['days']:
        cur_city = normalize_city(d['city'])
        if prev_city is not None and cur_city != prev_city:
            lines.append(f'<b>Итого по городу {prev_city}: {city_total:.0f} ₽</b>')
            lines.append('')
            city_total = 0.0
        items = EXPENSES.get(str(d['day']), [])
        if items:
            day_sum = sum(it['rub'] for it in items)
            lines.append(f'<b>{MONTH_RU.get(d["date"][5:], d["date"])} (день {d["day"]}, {d["city"]}) — {day_sum:.0f} ₽</b>')
            for it in items:
                sym = CURRENCY_SYMBOLS.get(it['currency'], it['currency'])
                tail = f' — {it["comment"]}' if it.get('comment') else ''
                cat = it.get('category', 'Прочее')
                cat_label = f"{CATEGORY_EMOJI.get(cat, '')} {cat}"
                lines.append(f'• {cat_label}: {it["amount"]:g} {sym}{tail}  ({it["rub"]:.0f} ₽)')
            city_total += day_sum
            grand += day_sum
        prev_city = cur_city
    if prev_city is not None:
        lines.append(f'<b>Итого по городу {prev_city}: {city_total:.0f} ₽</b>')
    lines.append('')
    if grand > 0:
        lines.append(f'<b>Всего за поездку: {grand:.0f} ₽</b>')
        cat_totals = {c: 0.0 for c in EXPENSE_CATEGORIES}
        for items in EXPENSES.values():
            for it in items:
                c = it.get('category', 'Прочее')
                if c not in cat_totals:
                    cat_totals[c] = 0.0
                cat_totals[c] += it.get('rub', 0.0)
        lines.append('')
        lines.append('<b>По категориям:</b>')
        for c in EXPENSE_CATEGORIES:
            total = cat_totals.get(c, 0.0)
            if total > 0:
                share = total / grand * 100
                lines.append(f'• {CATEGORY_EMOJI.get(c, "")} {c}: {total:.0f} ₽ ({share:.0f}%)')
    else:
        lines.append('Пока ничего не добавлено. Открой «Добавить расход» и напиши, например: 200 юаней ужин')
    return '\n'.join(lines)


async def fetch_weather_async(lat, lon, tz, date):
    import asyncio
    url = (
        f'https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}'
        f'&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,weathercode'
        f'&timezone={tz}&start_date={date}&end_date={date}'
    )
    def _get():
        with urllib.request.urlopen(url, timeout=8) as r:
            return json.loads(r.read())
    return await asyncio.to_thread(_get)


async def weather_text(day_obj):
    from datetime import datetime
    cities = [c.strip() for c in day_obj['city'].split('/')]
    blocks = [f'<b>🌤 Погода — {MONTH_RU.get(day_obj["date"][5:], day_obj["date"])}</b>']
    for city in cities:
        coords = CITY_COORDS.get(city)
        if not coords:
            continue
        lat, lon, tz = coords
        try:
            data = await fetch_weather_async(lat, lon, tz, day_obj['date'])
            d = data.get('daily', {})
            tmax = d.get('temperature_2m_max', [None])
            tmin = d.get('temperature_2m_min', [None])
            prcp = d.get('precipitation_sum', [None])
            wc = d.get('weathercode', [None])
            if not tmax or tmax[0] is None:
                blocks.append(f'\n<b>{city}:</b> прогноз пока недоступен (дата за пределами 16-дневного окна).')
            else:
                desc = WEATHER_CODES.get(wc[0], '—')
                blocks.append(
                    f'\n<b>{city}:</b> {desc}\n'
                    f'• Температура: {tmin[0]:.0f}°…{tmax[0]:.0f}°\n'
                    f'• Осадки: {prcp[0]:.1f} мм'
                )
        except Exception:
            blocks.append(f'\n<b>{city}:</b> не удалось получить прогноз.')
    now = datetime.now(_city_tz(day_obj['city'])).strftime('%H:%M')
    blocks.append(f'\n<i>Обновлено в {now}. Прогноз обновляется при каждом запросе.</i>')
    return '\n'.join(blocks)


_ANTHROPIC_CLIENT = None

def get_anthropic_client():
    global _ANTHROPIC_CLIENT
    if _ANTHROPIC_CLIENT is None:
        _ANTHROPIC_CLIENT = Anthropic(
            api_key=os.environ.get('AI_INTEGRATIONS_ANTHROPIC_API_KEY'),
            base_url=os.environ.get('AI_INTEGRATIONS_ANTHROPIC_BASE_URL'),
        )
    return _ANTHROPIC_CLIENT


_OPENAI_CLIENT = None

def get_openai_client():
    global _OPENAI_CLIENT
    if _OPENAI_CLIENT is None:
        _OPENAI_CLIENT = OpenAI(
            api_key=os.environ.get('AI_INTEGRATIONS_OPENAI_API_KEY'),
            base_url=os.environ.get('AI_INTEGRATIONS_OPENAI_BASE_URL'),
        )
    return _OPENAI_CLIENT


async def transcribe_voice(file_path: str) -> str:
    import asyncio
    client = get_openai_client()
    def _call():
        with open(file_path, 'rb') as f:
            r = client.audio.transcriptions.create(
                model='gpt-4o-mini-transcribe',
                file=f,
            )
        return getattr(r, 'text', '') or ''
    return await asyncio.to_thread(_call)


def build_trip_context():
    parts = ['=== Маршрут по дням ===']
    for d in ITINERARY['days']:
        parts.append(f"\n— День {d['day']} ({d['date']}, {d['city']}): {d.get('title','')}")
        if d.get('summary'):
            parts.append(f"  Кратко: {d['summary']}")
        if d.get('timeline'):
            parts.append("  План дня:")
            for t in d['timeline']:
                parts.append(f"    • {t.get('time','')}: {t.get('activity','')}")
        if d.get('visits'):
            parts.append("  Места:")
            for v in d['visits']:
                cmt = v.get('comment') or ''
                parts.append(f"    • {v.get('name','')} — {cmt}")
        if d.get('food_places'):
            parts.append("  Еда:")
            for f in d['food_places']:
                cmt = f.get('comment') or ''
                parts.append(f"    • {f.get('name','')} — {cmt}")
        if d.get('practical_notes'):
            parts.append("  Важно:")
            for n in d['practical_notes']:
                parts.append(f"    • {n}")
    parts.append('\n=== База адресов и ссылок на карты (из CSV) ===')
    for r in PLACES:
        line = f"[День {r.get('day','?')}, {r.get('city','')}] {r.get('name_en','')}"
        if r.get('name_local'):
            line += f" / {r['name_local']}"
        if r.get('address'):
            line += f" — адрес: {r['address']}"
        if r.get('map_link'):
            line += f" — карта: {r['map_link']}"
        parts.append(line)
    return '\n'.join(parts)


SYSTEM_PROMPT_BASE = (
    "Ты — личный помощник в путешествии по Пекину и Сеулу 1–12 мая 2026 года. "
    "Отвечай по-русски, кратко, по делу, по пунктам.\n\n"
    "ВАЖНО: у тебя ВСЕГДА есть полный маршрут путешественника в системном контексте ниже — "
    "с отелями, ресторанами, адресами и ссылками на карты. Используй этот контекст в ПЕРВУЮ очередь. "
    "Если спрашивают про отель / место / ресторан из маршрута — найди его в контексте и дай готовый ответ "
    "(название, адрес, ссылку на карту, если есть).\n\n"
    "НЕ ОТКАЗЫВАЙ фразами «я не могу искать в интернете» или «у меня нет доступа к картам». "
    "Ты МОЖЕШЬ строить URL-ы для поиска по картам — это просто текст. Используй такие шаблоны:\n"
    "  • Amap (Пекин/Китай): https://uri.amap.com/search?keyword=<название через +>\n"
    "  • Naver Maps (Сеул/Корея): https://map.naver.com/p/search/<название через %20>\n"
    "  • Google Maps (универсально): https://www.google.com/maps/search/?api=1&query=<название через +>\n"
    "Подставляй название места и сразу давай готовую кликабельную ссылку.\n\n"
    "Если спрашивают как сказать что-то на китайском/корейском — давай иероглифы/хангыль + транскрипцию (пиньинь/романизация) + перевод.\n"
    "Если спрашивают как доехать — давай конкретный маршрут (метро/такси/автобус), примерное время и стоимость в местной валюте.\n"
    "Если путешественник потерялся — спроси что видно вокруг (вывески/ориентиры) и подскажи ближайшее метро.\n"
    "Если действительно не знаешь факт — честно скажи и предложи где проверить."
)


ASK_HISTORY_MAX = 20  # last N messages kept (user + assistant combined)


async def ask_ai(question: str, history: list | None = None) -> tuple[str, list]:
    import asyncio
    client = get_anthropic_client()
    today = today_day()
    cur_day = next((d for d in ITINERARY['days'] if str(d['day']) == today), ITINERARY['days'][0])
    system = (
        SYSTEM_PROMPT_BASE
        + f"\n\nКонтекст поездки:\n{build_trip_context()}"
        + f"\n\nСегодня по часовому поясу путешественника — день {cur_day['day']} ({cur_day['date']}, {cur_day['city']})."
    )
    history = list(history or [])
    history.append({"role": "user", "content": question})
    trimmed = history[-ASK_HISTORY_MAX:]
    def _call():
        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=8192,
            system=system,
            messages=trimmed,
        )
        parts = []
        for block in msg.content:
            if getattr(block, 'type', None) == 'text':
                parts.append(block.text)
        return '\n'.join(parts).strip() or '(пустой ответ от помощника)'
    answer = await asyncio.to_thread(_call)
    history.append({"role": "assistant", "content": answer})
    return answer, history[-ASK_HISTORY_MAX:]


def ask_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton('🧹 Сбросить разговор', callback_data='ask:reset')],
        [InlineKeyboardButton('🏠 Выйти из режима помощника', callback_data='ask:stop')],
    ])


def chunk_text(text, n=3800):
    return [text[i:i+n] for i in range(0, len(text), n)]


def _city_tz(city):
    from zoneinfo import ZoneInfo
    return ZoneInfo('Asia/Seoul') if 'Сеул' in city else ZoneInfo('Asia/Shanghai')


def today_day():
    from datetime import datetime
    from zoneinfo import ZoneInfo
    for d in ITINERARY['days']:
        if datetime.now(_city_tz(d['city'])).strftime('%Y-%m-%d') == d['date']:
            return str(d['day'])
    today_kst = datetime.now(ZoneInfo('Asia/Seoul')).strftime('%Y-%m-%d')
    if today_kst < ITINERARY['days'][0]['date']:
        return str(ITINERARY['days'][0]['day'])
    return str(ITINERARY['days'][-1]['day'])


def tomorrow_day():
    today = today_day()
    days = [str(d['day']) for d in ITINERARY['days']]
    try:
        idx = days.index(today)
        return days[idx + 1] if idx < len(days) - 1 else today
    except ValueError:
        return today
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
        [InlineKeyboardButton('💰 Расходы', callback_data='expenses_menu')],
        [InlineKeyboardButton('🤖 Спросить помощника', callback_data='ask:start')],
    ])


def expenses_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton('➕ Добавить расход', callback_data='exp:add')],
        [InlineKeyboardButton('📊 Сколько потратили', callback_data='exp:show')],
        [InlineKeyboardButton('↩️ Отменить последний расход', callback_data='exp:undo')],
        [InlineKeyboardButton('🏠 В меню', callback_data='home')],
    ])


def add_expense_menu():
    rows = [[InlineKeyboardButton(f'{CATEGORY_EMOJI[c]} {c}', callback_data=f'exp:cat:{c}')] for c in EXPENSE_CATEGORIES]
    rows.append([InlineKeyboardButton('⬅️ Назад', callback_data='expenses_menu')])
    return InlineKeyboardMarkup(rows)


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
        [InlineKeyboardButton('🌤 Погода', callback_data=f'section:weather:{day_num}')],
        [InlineKeyboardButton('⬅️ К выбору формата', callback_data=f'date:{day_num}')],
        [InlineKeyboardButton('🏠 В меню', callback_data='home')],
    ])


def visit_menu(day_obj):
    rows=[[InlineKeyboardButton('🗂 Все места', callback_data=f'visitall:{day_obj["day"]}')]]
    for idx,item in enumerate(day_obj.get('visits', [])):
        rows.append([InlineKeyboardButton(f'📍 {item["name"]}', callback_data=f'visit:{day_obj["day"]}:{idx}')])
    rows.append([InlineKeyboardButton('⬅️ К подробному дню', callback_data=f'dayfull:{day_obj["day"]}')])
    return InlineKeyboardMarkup(rows)


FOOD_KEYWORDS = [
    'coffee','cafe','tea house',' tea ','ramen','bbq','kyoja','haidilao','bianyifang',
    'siji','baekjeong','la yeon','oreno','samgyetang','tosokchon','maple tree',
    'damtak','menya','market','fritz','momos','voyage','metal hands','barista',
    'da dong','jungsik','mingles','layered','anthracite','onion'
]


def food_places(day_num):
    items=[]
    for idx,p in enumerate(PLACES_BY_DAY.get(str(day_num), [])):
        name=(p.get('name_en','') or '').lower()
        if any(k in name for k in FOOD_KEYWORDS):
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
    context.user_data['ask_mode'] = False
    context.user_data['ask_history'] = []
    await update.message.reply_text('Привет! Здесь маршрут по поездке с более детальными местами, едой и фото.', reply_markup=main_menu())


async def on_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q=update.callback_query; await q.answer(); data=q.data
    if data=='home': await q.edit_message_text('Главное меню', reply_markup=main_menu())
    elif data=='today_menu': await q.edit_message_text('Маршрут сегодня:', reply_markup=info_choice_menu('today'))
    elif data=='tomorrow_menu': await q.edit_message_text('Маршрут завтра:', reply_markup=info_choice_menu('tomorrow'))
    elif data=='pick_date': await q.edit_message_text('Выбери дату:', reply_markup=dates_menu())
    elif data=='whole_route': await q.edit_message_text('Весь маршрут:', reply_markup=info_choice_menu('route'))
    elif data=='add_help': await q.edit_message_text('Напиши сообщением, например: «добавь 7 мая посещение магазина с пряжей».', reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🏠 В меню', callback_data='home')]]))
    elif data=='expenses_menu': await q.edit_message_text('Раздел расходов:', reply_markup=expenses_menu())
    elif data=='exp:add':
        await q.edit_message_text(
            'Выбери категорию расхода:',
            reply_markup=add_expense_menu()
        )
    elif data.startswith('exp:cat:'):
        cat = data.split(':', 2)[2]
        if cat not in EXPENSE_CATEGORIES:
            cat = 'Прочее'
        context.user_data['expense_category'] = cat
        hint = CATEGORY_HINTS.get(cat, '')
        text = (
            f'<b>Категория: {CATEGORY_EMOJI.get(cat, "")} {cat}</b>\n\n'
            'Напиши сумму и валюту следующим сообщением, например:\n'
            f'{hint}\n\n'
            'Понимаемые валюты: юани/¥, воны/₩, доллары/$, рубли.\n'
            f'Курс зафиксирован {EXCHANGE_LOCKED_AT}: 1 ¥ = {EXCHANGE_TO_RUB["CNY"]} ₽, 1 ₩ = {EXCHANGE_TO_RUB["KRW"]} ₽, 1 $ = {EXCHANGE_TO_RUB["USD"]} ₽\n\n'
            'Расход уйдёт в текущий день поездки и в эту категорию.'
        )
        await q.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=add_expense_menu())
    elif data=='exp:show':
        await q.edit_message_text(expenses_summary_text(), parse_mode=ParseMode.HTML, reply_markup=expenses_menu())
    elif data=='exp:undo':
        result = undo_last_expense()
        if result is None:
            await q.edit_message_text('Нечего отменять — расходов пока нет.', reply_markup=expenses_menu())
        else:
            day, it = result
            sym = CURRENCY_SYMBOLS.get(it.get('currency'), it.get('currency', ''))
            cat = it.get('category', 'Прочее')
            cat_label = f"{CATEGORY_EMOJI.get(cat, '')} {cat}"
            cmt = f' — {it.get("comment")}' if it.get('comment') else ''
            await q.edit_message_text(
                f'Отменён последний расход (день {day}, {cat_label}):\n'
                f'{it.get("amount"):g} {sym}{cmt}  ({it.get("rub"):.0f} ₽)',
                reply_markup=expenses_menu()
            )
    elif data == 'ask:start':
        context.user_data['ask_mode'] = True
        context.user_data['ask_history'] = []
        await q.edit_message_text(
            '<b>🤖 Режим помощника включён</b>\n\n'
            'Спроси меня что угодно по поездке: как доехать, что сказать таксисту, '
            'перевести меню, что делать если потерялись, объяснить иероглифы и т.п.\n\n'
            'Я помню наш разговор и понимаю уточняющие вопросы вроде «а как туда доехать?».\n\n'
            '🎤 Можно прислать <b>голосовое сообщение</b> вместо текста — распознаю и отвечу.\n\n'
            '<i>Чтобы выйти — нажми кнопку ниже или /menu. Чтобы начать новый разговор — «Сбросить разговор».</i>',
            parse_mode=ParseMode.HTML,
            reply_markup=ask_menu()
        )
    elif data == 'ask:reset':
        context.user_data['ask_history'] = []
        await q.edit_message_text(
            '<b>🧹 Контекст разговора сброшен.</b>\n\nПомощник забыл предыдущие сообщения. Задавай новый вопрос.',
            parse_mode=ParseMode.HTML,
            reply_markup=ask_menu()
        )
    elif data == 'ask:stop':
        context.user_data['ask_mode'] = False
        context.user_data['ask_history'] = []
        await q.edit_message_text('Готово, вышли из режима помощника.', reply_markup=main_menu())
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
        elif section=='weather':
            try:
                text = await weather_text(d)
                await q.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=detail_menu(day_num))
            except Exception:
                pass
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
    if context.user_data.get('ask_mode'):
        try:
            await update.message.chat.send_action('typing')
        except Exception:
            pass
        try:
            history = context.user_data.get('ask_history', [])
            answer, new_history = await ask_ai(text, history)
            context.user_data['ask_history'] = new_history
        except Exception as e:
            await update.message.reply_text(
                f'Помощник временно недоступен: {e}',
                reply_markup=ask_menu()
            )
            return
        chunks = chunk_text(answer)
        for i, ch in enumerate(chunks):
            await update.message.reply_text(
                ch,
                reply_markup=ask_menu() if i == len(chunks) - 1 else None
            )
        return
    parsed = parse_expense(text)
    if parsed:
        amount, cur, comment = parsed
        category = context.user_data.get('expense_category', 'Прочее')
        day_num = today_day()
        rub, _ = add_expense(day_num, amount, cur, comment, category)
        sym = CURRENCY_SYMBOLS.get(cur, cur)
        cmt = f' — {comment}' if comment else ''
        cat_label = f"{CATEGORY_EMOJI.get(category, '')} {category}"
        await update.message.reply_text(
            f'Добавил расход в день {day_num} ({cat_label}): {amount:g} {sym}{cmt}\n= {rub:.0f} ₽',
            reply_markup=expenses_menu()
        )
        return
    m=re.match(r'(?i)^добав[ьй]\s+(\d{1,2})\s+мая\s+(.+)$', text)
    if not m: return
    day_num, content = m.group(1), m.group(2).strip()
    if not find_day(day_num):
        await update.message.reply_text('Не вижу такого дня в маршруте. Поддерживаются даты с 1 по 12 мая.')
        return
    USER_NOTES.setdefault(str(int(day_num)), []).append(content)
    save_notes()
    await update.message.reply_text(f'Добавил в маршрут на {day_num} мая:\n• {content}')


async def on_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('ask_mode'):
        await update.message.reply_text(
            'Голосовые сообщения работают только в режиме помощника. '
            'Открой главное меню (/menu) → «🤖 Спросить помощника» и пришли голосовое снова.',
            reply_markup=main_menu()
        )
        return
    voice = update.message.voice or update.message.audio
    if not voice:
        return
    try:
        await update.message.chat.send_action('typing')
    except Exception:
        pass
    tmp_path = None
    try:
        tg_file = await voice.get_file()
        with tempfile.NamedTemporaryFile(suffix='.ogg', delete=False) as tf:
            tmp_path = tf.name
        await tg_file.download_to_drive(tmp_path)
        try:
            text = (await transcribe_voice(tmp_path)).strip()
        except Exception as e:
            await update.message.reply_text(
                f'Не получилось распознать голос: {e}',
                reply_markup=ask_menu()
            )
            return
        if not text:
            await update.message.reply_text(
                'Не услышал текста в голосовом. Попробуй записать ещё раз.',
                reply_markup=ask_menu()
            )
            return
        await update.message.reply_text(f'🎤 <i>Распознал:</i> {text}', parse_mode=ParseMode.HTML)
        try:
            history = context.user_data.get('ask_history', [])
            answer, new_history = await ask_ai(text, history)
            context.user_data['ask_history'] = new_history
        except Exception as e:
            await update.message.reply_text(
                f'Помощник временно недоступен: {e}',
                reply_markup=ask_menu()
            )
            return
        chunks = chunk_text(answer)
        for i, ch in enumerate(chunks):
            await update.message.reply_text(
                ch,
                reply_markup=ask_menu() if i == len(chunks) - 1 else None
            )
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try: os.remove(tmp_path)
            except Exception: pass


if __name__ == '__main__':
    app=ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('menu', start))
    app.add_handler(CallbackQueryHandler(on_button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, parse_add_request))
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, on_voice))
    app.run_polling()
