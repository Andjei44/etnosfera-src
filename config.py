import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv('BOT_TOKEN')
ITEMS_PER_PAGE = 4
DATA_DIR = 'regionals'

CATEGORIES = [
    'bludo',
    'kostyum', 
    'info',
    'ornament',
    'events'
]

CATEGORY_NAMES = {
    'bludo': 'Национальная кухня',
    'kostyum': 'Национальные костюмы',
    'info': 'Информация о народе',
    'ornament': 'Узоры и орнаменты',
    'events': 'События и люди'
}
