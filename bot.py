import telebot
from telebot import types
import os
import random
from fuzzywuzzy import fuzz
from config import TOKEN, ITEMS_PER_PAGE, DATA_DIR, CATEGORY_NAMES
from nationals import get_russian_name, get_english_name

bot = telebot.TeleBot(TOKEN, parse_mode='HTML')

user_states = {}
MAIN_PHOTO = 'imgs/example.png'

def get_all_nationals():
    nationals = []
    if os.path.exists(DATA_DIR):
        for item in os.listdir(DATA_DIR):
            path = os.path.join(DATA_DIR, item)
            if os.path.isdir(path):
                nationals.append(item)
    return sorted(nationals)

def parse_item_file(filepath):
    items = []
    if not os.path.exists(filepath):
        return items
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
        return items
    
    import re
    
    pattern = r'=START=\s*{([^}]+)}\s*===([\s\S]*?)=END=\s*{[^}]+}\s*==='
    matches = re.findall(pattern, content)
    
    for match in matches:
        try:
            header_content = match[0].strip()
            description = match[1].strip()
            
            parts = header_content.split('/')
            if len(parts) < 3:
                continue
            
            name_part = parts[0].strip()
            if ':' in name_part:
                name = name_part.split(':', 1)[1].strip()
            else:
                name = name_part
            
            image = parts[1].strip()
            date_raw = parts[2].strip()
            
            if date_raw.endswith('g'):
                date = date_raw[:-1] + ' год'
            elif date_raw.endswith('gg'):
                date = date_raw[:-2] + ' гг'
            elif '.' in date_raw or len(date_raw) >= 8:
                date = date_raw
            else:
                date = date_raw
            
            items.append({
                'name': name,
                'image': image,
                'date': date,
                'description': description
            })
        except Exception as e:
            print(f"Error parsing block: {e}")
            continue
    
    return items

def get_category_items(national, category):
    filepath = os.path.join(DATA_DIR, national, category, 'list.txt')
    return parse_item_file(filepath)

def get_all_items_from_all_nationals():
    all_items = []
    nationals = get_all_nationals()
    
    for national in nationals:
        for category in CATEGORY_NAMES.keys():
            items = get_category_items(national, category)
            for idx, item in enumerate(items):
                all_items.append({
                    'name': item['name'],
                    'national': national,
                    'category': category,
                    'item_data': item
                })
    
    return all_items

def fuzzy_search(query, items, threshold=50):
    results = []
    for item in items:
        ratio = fuzz.partial_ratio(query.lower(), item.lower())
        if ratio >= threshold:
            results.append((item, ratio))
    results.sort(key=lambda x: x[1], reverse=True)
    return [item for item, _ in results]

def delete_message_safe(chat_id, message_id):
    try:
        if message_id:
            bot.delete_message(chat_id, message_id)
    except Exception as e:
        print(f"Delete message error: {e}")

def send_with_photo(chat_id, photo_path, caption, reply_markup, message_id=None, previous_photo=None):
    try:
        if not os.path.exists(photo_path):
            photo_path = MAIN_PHOTO
        
        if message_id and previous_photo and previous_photo == photo_path:
            try:
                bot.edit_message_caption(
                    caption=caption,
                    chat_id=chat_id,
                    message_id=message_id,
                    reply_markup=reply_markup
                )
                if chat_id in user_states:
                    user_states[chat_id]['last_message_id'] = message_id
                    user_states[chat_id]['last_photo'] = photo_path
                return
            except Exception as e:
                print(f"Edit caption error: {e}")
        
        if message_id:
            delete_message_safe(chat_id, message_id)
        
        with open(photo_path, 'rb') as photo:
            msg = bot.send_photo(chat_id, photo, caption=caption, reply_markup=reply_markup)
            
            if chat_id in user_states:
                user_states[chat_id]['last_message_id'] = msg.message_id
                user_states[chat_id]['last_photo'] = photo_path
    
    except Exception as e:
        print(f"Send photo error: {e}")
        msg = bot.send_message(chat_id, caption, reply_markup=reply_markup)
        if chat_id in user_states:
            user_states[chat_id]['last_message_id'] = msg.message_id
            user_states[chat_id]['last_photo'] = MAIN_PHOTO

def generate_national_quiz():
    all_items = get_all_items_from_all_nationals()
    if not all_items:
        return None
    
    correct_item = random.choice(all_items)
    correct_national = correct_item['national']
    
    all_nationals = get_all_nationals()
    if len(all_nationals) < 4:
        options = all_nationals.copy()
    else:
        options = [correct_national]
        other_nationals = [n for n in all_nationals if n != correct_national]
        options.extend(random.sample(other_nationals, min(3, len(other_nationals))))
        random.shuffle(options)
    
    return {
        'type': 'national_quiz',
        'item': correct_item,
        'correct_answer': correct_national,
        'options': options
    }

def generate_food_quiz():
    all_items = []
    nationals = get_all_nationals()
    
    for national in nationals:
        items = get_category_items(national, 'food')
        for item in items:
            all_items.append({
                'item': item,
                'national': national
            })
    
    if not all_items:
        return None
    
    correct = random.choice(all_items)
    
    if len(all_items) < 4:
        options = [item['item']['name'] for item in all_items]
    else:
        options = [correct['item']['name']]
        other_items = [item for item in all_items if item['item']['name'] != correct['item']['name']]
        options.extend([item['item']['name'] for item in random.sample(other_items, min(3, len(other_items)))])
        random.shuffle(options)
    
    return {
        'type': 'food_quiz',
        'item': correct['item'],
        'national': correct['national'],
        'correct_answer': correct['item']['name'],
        'options': options
    }

def generate_marathon_question():
    question_type = random.choice(['national', 'category', 'fact'])
    
    if question_type == 'national':
        return generate_national_quiz()
    
    elif question_type == 'category':
        all_items = get_all_items_from_all_nationals()
        if not all_items:
            return None
        
        correct_item = random.choice(all_items)
        correct_category = correct_item['category']
        
        categories = list(CATEGORY_NAMES.keys())
        if len(categories) < 4:
            options = categories.copy()
        else:
            options = [correct_category]
            other_categories = [c for c in categories if c != correct_category]
            options.extend(random.sample(other_categories, 3))
            random.shuffle(options)
        
        return {
            'type': 'category_quiz',
            'item': correct_item,
            'correct_answer': correct_category,
            'options': options
        }
    
    else:
        all_items = get_all_items_from_all_nationals()
        if not all_items:
            return None
        
        item = random.choice(all_items)
        is_true = random.choice([True, False])
        
        if is_true:
            statement = f"{item['name']} относится к культуре {get_russian_name(item['national'])}"
        else:
            nationals = get_all_nationals()
            wrong_nationals = [n for n in nationals if n != item['national']]
            if wrong_nationals:
                wrong_national = random.choice(wrong_nationals)
                statement = f"{item['name']} относится к культуре {get_russian_name(wrong_national)}"
            else:
                return generate_marathon_question()
        
        return {
            'type': 'true_false',
            'item': item,
            'statement': statement,
            'correct_answer': is_true,
            'options': ['Правда', 'Ложь']
        }

def generate_match_pairs():
    all_items = get_all_items_from_all_nationals()
    if len(all_items) < 4:
        return None
    
    selected_items = []
    used_nationals = set()
    
    random.shuffle(all_items)
    for item in all_items:
        if item['national'] not in used_nationals:
            selected_items.append(item)
            used_nationals.add(item['national'])
            if len(selected_items) == 4:
                break
    
    if len(selected_items) < 4:
        selected_items = random.sample(all_items, min(4, len(all_items)))
    
    return {
        'type': 'match_pairs',
        'items': selected_items,
        'matches_found': [],
        'current_item': None
    }

def create_main_menu():
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton('🎮 Игры', callback_data='games_menu'),
        types.InlineKeyboardButton('🔍 Поиск по названию', callback_data='search_name'),
        types.InlineKeyboardButton('🌍 Выбрать национальность', callback_data='select_national'),
        types.InlineKeyboardButton('📂 Выбрать категорию', callback_data='select_category'),
        types.InlineKeyboardButton('📞 Контакты', callback_data='contacts'),
        types.InlineKeyboardButton('💬 Обратная связь', callback_data='feedback')
    )
    return markup

def create_games_menu():
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton('🌍 Угадай национальность', callback_data='game_national_quiz'),
        types.InlineKeyboardButton('🍲 Угадай блюдо', callback_data='game_food_quiz'),
        types.InlineKeyboardButton('🏆 Культурный марафон', callback_data='game_marathon'),
        types.InlineKeyboardButton('🎯 Найди пару', callback_data='game_match_pairs'),
        types.InlineKeyboardButton('⚡ Блиц-викторина', callback_data='game_blitz'),
        types.InlineKeyboardButton('🏠 Главное меню', callback_data='main_menu')
    )
    return markup

def create_quiz_answer_buttons(options, question_id, quiz_type='national'):
    markup = types.InlineKeyboardMarkup(row_width=1)
    
    for idx, option in enumerate(options):
        if quiz_type == 'national':
            text = get_russian_name(option)
        elif quiz_type == 'category':
            text = CATEGORY_NAMES.get(option, option)
        else:
            text = option
        
        markup.add(types.InlineKeyboardButton(
            text,
            callback_data=f'answer_{question_id}_{idx}'
        ))
    
    markup.add(types.InlineKeyboardButton('❌ Выход', callback_data='games_menu'))
    return markup

def create_match_pairs_menu(game_data):
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    items = game_data['items']
    matches_found = game_data.get('matches_found', [])
    current_item = game_data.get('current_item')
    
    for idx, item in enumerate(items):
        if idx in matches_found:
            continue
        
        emoji = '🔸' if current_item == idx else '◦'
        text = f"{emoji} {item['name']}"
        markup.add(types.InlineKeyboardButton(
            text,
            callback_data=f'match_select_item_{idx}'
        ))
    
    nationals = [item['national'] for item in items]
    for idx, national in enumerate(nationals):
        if idx in matches_found:
            continue
        
        text = f"➜ {get_russian_name(national)}"
        markup.add(types.InlineKeyboardButton(
            text,
            callback_data=f'match_select_nat_{idx}'
        ))
    
    markup.row(types.InlineKeyboardButton('🏠 Главное меню', callback_data='main_menu'))
    
    return markup

def create_search_type_menu():
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton('🌍 Искать национальность', callback_data='search_type_national'),
        types.InlineKeyboardButton('📋 Искать элементы', callback_data='search_type_items'),
        types.InlineKeyboardButton('🏠 Главное меню', callback_data='main_menu')
    )
    return markup

def create_nationals_menu(page=0, selected_nationals=None):
    if selected_nationals is None:
        selected_nationals = []
    
    nationals = get_all_nationals()
    start_idx = page * ITEMS_PER_PAGE
    end_idx = start_idx + ITEMS_PER_PAGE
    page_nationals = nationals[start_idx:end_idx]
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    
    for national in page_nationals:
        ru_name = get_russian_name(national)
        if national in selected_nationals:
            text = f'◦ {ru_name} ◦'
        else:
            text = ru_name
        markup.add(types.InlineKeyboardButton(text, callback_data=f'natselect_{national}'))
    
    nav_buttons = []
    if page > 0:
        nav_buttons.append(types.InlineKeyboardButton('◀️', callback_data=f'natpage_{page-1}'))
    
    if selected_nationals:
        nav_buttons.append(types.InlineKeyboardButton('Далее', callback_data='natcontinue'))
    else:
        if end_idx < len(nationals):
            nav_buttons.append(types.InlineKeyboardButton('Далее', callback_data=f'natpage_{page+1}'))
        else:
            nav_buttons.append(types.InlineKeyboardButton('Далее', callback_data='natpage_0'))
    
    nav_buttons.append(types.InlineKeyboardButton('Отмена', callback_data='main_menu'))
    
    if end_idx < len(nationals):
        nav_buttons.append(types.InlineKeyboardButton('▶️', callback_data=f'natpage_{page+1}'))
    
    if nav_buttons:
        markup.row(*nav_buttons)
    
    markup.add(types.InlineKeyboardButton('🔍 Поиск по названию', callback_data='search_national'))
    
    return markup

def create_categories_menu(national=None):
    markup = types.InlineKeyboardMarkup(row_width=1)
    
    for cat_key, cat_name in CATEGORY_NAMES.items():
        callback = f'cat_{cat_key}' if not national else f'natcat_{national}_{cat_key}'
        markup.add(types.InlineKeyboardButton(cat_name, callback_data=callback))
    
    if national:
        markup.add(types.InlineKeyboardButton('⬅️ К национальностям', callback_data='select_national'))
    
    markup.add(types.InlineKeyboardButton('🏠 Главное меню', callback_data='main_menu'))
    
    return markup

def create_items_menu(national, category, page=0, selected_idx=None):
    items = get_category_items(national, category)
    
    if not items:
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton('⬅️ К категориям', callback_data=f'nat_{national}'),
            types.InlineKeyboardButton('🏠 Главное меню', callback_data='main_menu')
        )
        return markup
    
    start_idx = page * ITEMS_PER_PAGE
    end_idx = start_idx + ITEMS_PER_PAGE
    page_items = items[start_idx:end_idx]
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    
    for idx, item in enumerate(page_items):
        real_idx = start_idx + idx
        if selected_idx is not None and selected_idx == real_idx:
            text = f"◦ {item['name']} ◦"
        else:
            text = item['name']
        markup.add(types.InlineKeyboardButton(text, callback_data=f'item_{national}_{category}_{real_idx}'))
    
    nav_buttons = []
    if page > 0:
        nav_buttons.append(types.InlineKeyboardButton('◀️', callback_data=f'itempage_{national}_{category}_{page-1}'))
    
    nav_buttons.append(types.InlineKeyboardButton('Далее', callback_data=f'itempage_{national}_{category}_{page+1}' if end_idx < len(items) else f'itempage_{national}_{category}_0'))
    nav_buttons.append(types.InlineKeyboardButton('Отмена', callback_data=f'nat_{national}'))
    
    if end_idx < len(items):
        nav_buttons.append(types.InlineKeyboardButton('▶️', callback_data=f'itempage_{national}_{category}_{page+1}'))
    
    if nav_buttons:
        markup.row(*nav_buttons)
    
    markup.add(types.InlineKeyboardButton('🔍 Поиск', callback_data=f'search_items_{national}_{category}'))
    markup.row(
        types.InlineKeyboardButton('⬅️ К категориям', callback_data=f'nat_{national}'),
        types.InlineKeyboardButton('🏠 Главное меню', callback_data='main_menu')
    )
    
    return markup

@bot.message_handler(commands=['start'])
def start_handler(message):
    delete_message_safe(message.chat.id, message.message_id)
    
    user_states[message.chat.id] = {'last_photo': MAIN_PHOTO}
    
    welcome_text = (
        '🌟 <b>Добро пожаловать в Этносферу!</b>\n\n'
        'Цифровая платформа народной культуры России.\n\n'
        '📍 <b>Здесь вы найдете:</b>\n'
        '• Информацию о традициях народов Мирнинского района\n'
        '• Национальную кухню и рецепты\n'
        '• Традиционные костюмы и орнаменты\n'
        '• События и праздники\n'
        '• Увлекательные игры и викторины\n\n'
        '👇 <b>Выберите действие из меню ниже:</b>'
    )
    
    send_with_photo(message.chat.id, MAIN_PHOTO, welcome_text, create_main_menu())

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    chat_id = call.message.chat.id
    data = call.data
    
    if chat_id not in user_states:
        user_states[chat_id] = {}
    
    last_photo = user_states[chat_id].get('last_photo', MAIN_PHOTO)
    last_msg_id = user_states[chat_id].get('last_message_id', call.message.message_id)
    
    try:
        
        if data == 'games_menu':
            text = (
                '🎮 <b>Игры и викторины</b>\n\n'
                'Проверьте свои знания о культуре народов!\n\n'
                '👇 Выберите игру:'
            )
            send_with_photo(chat_id, MAIN_PHOTO, text, create_games_menu(), last_msg_id, last_photo)
        
        elif data == 'game_national_quiz':
            quiz = generate_national_quiz()
            if not quiz:
                bot.answer_callback_query(call.id, '❌ Недостаточно данных для игры')
                return
            
            user_states[chat_id]['current_quiz'] = quiz
            user_states[chat_id]['quiz_score'] = 0
            user_states[chat_id]['quiz_total'] = 0
            
            item = quiz['item']
            cat_name = CATEGORY_NAMES.get(item['category'], item['category'])
            
            text = (
                f'🌍 <b>Угадай национальность</b>\n\n'
                f'📂 Категория: {cat_name}\n'
                f'📌 Элемент: {item["name"]}\n\n'
                f'📝 Описание:\n{item["item_data"]["description"][:200]}...\n\n'
                f'❓ К какой национальности относится этот элемент культуры?'
            )
            
            markup = create_quiz_answer_buttons(quiz['options'], 'national', 'national')
            send_with_photo(chat_id, MAIN_PHOTO, text, markup, last_msg_id, last_photo)
        
        elif data == 'game_food_quiz':
            quiz = generate_food_quiz()
            if not quiz:
                bot.answer_callback_query(call.id, '❌ Недостаточно данных для игры')
                return
            
            user_states[chat_id]['current_quiz'] = quiz
            user_states[chat_id]['quiz_score'] = 0
            user_states[chat_id]['quiz_total'] = 0
            
            item = quiz['item']
            photo_path = os.path.join(DATA_DIR, quiz['national'], 'food', item['image'])
            
            text = (
                f'🍲 <b>Угадай блюдо</b>\n\n'
                f'❓ Как называется это блюдо?'
            )
            
            markup = create_quiz_answer_buttons(quiz['options'], 'food', 'food')
            send_with_photo(chat_id, photo_path, text, markup, last_msg_id, last_photo)
        
        elif data == 'game_marathon':
            user_states[chat_id]['marathon'] = {
                'score': 0,
                'question_num': 0,
                'total_questions': 10
            }
            
            question = generate_marathon_question()
            if not question:
                bot.answer_callback_query(call.id, '❌ Недостаточно данных для игры')
                return
            
            user_states[chat_id]['current_quiz'] = question
            
            text = (
                f'🏆 <b>Культурный марафон</b>\n\n'
                f'📊 Вопрос 1/10\n'
                f'⭐ Очки: 0\n\n'
            )
            
            if question['type'] == 'national_quiz':
                item = question['item']
                cat_name = CATEGORY_NAMES.get(item['category'], item['category'])
                text += (
                    f'📂 {cat_name}: {item["name"]}\n\n'
                    f'❓ К какой национальности относится?'
                )
                markup = create_quiz_answer_buttons(question['options'], 'marathon', 'national')
            
            elif question['type'] == 'category_quiz':
                item = question['item']
                text += (
                    f'📌 {item["name"]}\n'
                    f'🌍 {get_russian_name(item["national"])}\n\n'
                    f'❓ К какой категории относится?'
                )
                markup = create_quiz_answer_buttons(question['options'], 'marathon', 'category')
            
            else:
                text += f'❓ {question["statement"]}\n\n'
                markup = create_quiz_answer_buttons(question['options'], 'marathon', 'tf')
            
            send_with_photo(chat_id, MAIN_PHOTO, text, markup, last_msg_id, last_photo)
        
        elif data == 'game_match_pairs':
            game_data = generate_match_pairs()
            if not game_data:
                bot.answer_callback_query(call.id, '❌ Недостаточно данных для игры')
                return
            
            user_states[chat_id]['match_game'] = game_data
            
            text = (
                f'🎯 <b>Найди пару</b>\n\n'
                f'Сопоставьте элементы культуры с национальностями!\n\n'
                f'1️⃣ Выберите элемент\n'
                f'2️⃣ Выберите национальность\n\n'
                f'✅ Найдено пар: 0/4'
            )
            
            markup = create_match_pairs_menu(game_data)
            send_with_photo(chat_id, MAIN_PHOTO, text, markup, last_msg_id, last_photo)
        
        elif data == 'game_blitz':
            user_states[chat_id]['blitz'] = {
                'score': 0,
                'question_num': 0,
                'total_questions': 5
            }
            
            question = generate_marathon_question()
            if not question:
                bot.answer_callback_query(call.id, '❌ Недостаточно данных для игры')
                return
            
            user_states[chat_id]['current_quiz'] = question
            
            text = f'⚡ <b>Блиц-викторина</b>\n\n📊 Вопрос 1/5\n⭐ Очки: 0\n\n'
            
            if question['type'] == 'national_quiz':
                item = question['item']
                text += f'❓ Национальность элемента "{item["name"]}"?'
                markup = create_quiz_answer_buttons(question['options'], 'blitz', 'national')
            elif question['type'] == 'category_quiz':
                item = question['item']
                text += f'❓ Категория элемента "{item["name"]}"?'
                markup = create_quiz_answer_buttons(question['options'], 'blitz', 'category')
            else:
                text += f'❓ {question["statement"]}'
                markup = create_quiz_answer_buttons(question['options'], 'blitz', 'tf')
            
            send_with_photo(chat_id, MAIN_PHOTO, text, markup, last_msg_id, last_photo)
        
        elif data.startswith('answer_'):
            parts = data.split('_')
            quiz_type = parts[1]
            answer_idx = int(parts[2])
            
            current_quiz = user_states[chat_id].get('current_quiz')
            if not current_quiz:
                bot.answer_callback_query(call.id, '❌ Ошибка')
                return
            
            selected_option = current_quiz['options'][answer_idx]
            correct_answer = current_quiz['correct_answer']
            
            if quiz_type == 'national' or quiz_type == 'food':
                is_correct = selected_option == correct_answer
            elif quiz_type == 'marathon' or quiz_type == 'blitz':
                if current_quiz['type'] == 'true_false':
                    is_correct = (selected_option == 'Правда') == correct_answer
                else:
                    is_correct = selected_option == correct_answer
            else:
                is_correct = False
            
            if quiz_type == 'marathon':
                marathon = user_states[chat_id].get('marathon', {})
                marathon['question_num'] += 1
                
                if is_correct:
                    marathon['score'] += 10
                    result_emoji = '✅'
                    result_text = 'Правильно!'
                else:
                    result_emoji = '❌'
                    result_text = 'Неправильно!'
                
                user_states[chat_id]['marathon'] = marathon
                
                if marathon['question_num'] >= marathon['total_questions']:
                    final_score = marathon['score']
                    max_score = marathon['total_questions'] * 10
                    
                    if final_score >= max_score * 0.8:
                        grade = '🏆 Отлично!'
                    elif final_score >= max_score * 0.6:
                        grade = '🥈 Хорошо!'
                    elif final_score >= max_score * 0.4:
                        grade = '🥉 Неплохо!'
                    else:
                        grade = '📚 Есть что подтянуть!'
                    
                    text = (
                        f'🏆 <b>Марафон завершён!</b>\n\n'
                        f'{grade}\n\n'
                        f'📊 Ваш результат: {final_score}/{max_score} очков\n'
                        f'✅ Правильных ответов: {final_score//10}/{marathon["total_questions"]}\n\n'
                        f'Отличная работа! Продолжайте изучать культуру народов! 🎓'
                    )
                    
                    markup = types.InlineKeyboardMarkup()
                    markup.add(types.InlineKeyboardButton('🔄 Играть снова', callback_data='game_marathon'))
                    markup.add(types.InlineKeyboardButton('🎮 Другие игры', callback_data='games_menu'))
                    markup.add(types.InlineKeyboardButton('🏠 Главное меню', callback_data='main_menu'))
                    
                    send_with_photo(chat_id, MAIN_PHOTO, text, markup, last_msg_id, last_photo)
                else:
                    question = generate_marathon_question()
                    if not question:
                        bot.answer_callback_query(call.id, '❌ Ошибка генерации вопроса')
                        return
                    
                    user_states[chat_id]['current_quiz'] = question
                    
                    text = (
                        f'🏆 <b>Культурный марафон</b>\n\n'
                        f'{result_emoji} {result_text}\n\n'
                        f'📊 Вопрос {marathon["question_num"]+1}/{marathon["total_questions"]}\n'
                        f'⭐ Очки: {marathon["score"]}\n\n'
                    )
                    
                    if question['type'] == 'national_quiz':
                        item = question['item']
                        cat_name = CATEGORY_NAMES.get(item['category'], item['category'])
                        text += f'📂 {cat_name}: {item["name"]}\n\n❓ К какой национальности относится?'
                        markup = create_quiz_answer_buttons(question['options'], 'marathon', 'national')
                    elif question['type'] == 'category_quiz':
                        item = question['item']
                        text += f'📌 {item["name"]}\n🌍 {get_russian_name(item["national"])}\n\n❓ К какой категории относится?'
                        markup = create_quiz_answer_buttons(question['options'], 'marathon', 'category')
                    else:
                        text += f'❓ {question["statement"]}'
                        markup = create_quiz_answer_buttons(question['options'], 'marathon', 'tf')
                    
                    send_with_photo(chat_id, MAIN_PHOTO, text, markup, last_msg_id, last_photo)
            
            elif quiz_type == 'blitz':
                blitz = user_states[chat_id].get('blitz', {})
                blitz['question_num'] += 1
                
                if is_correct:
                    blitz['score'] += 20
                    result_emoji = '✅'
                    result_text = 'Верно!'
                else:
                    result_emoji = '❌'
                    result_text = 'Ошибка!'
                
                user_states[chat_id]['blitz'] = blitz
                
                if blitz['question_num'] >= blitz['total_questions']:
                    final_score = blitz['score']
                    max_score = blitz['total_questions'] * 20
                    
                    text = (
                        f'⚡ <b>Блиц завершён!</b>\n\n'
                        f'📊 Результат: {final_score}/{max_score} очков\n'
                        f'✅ Правильных: {final_score//20}/{blitz["total_questions"]}\n\n'
                        f'Молодец! ⭐'
                    )
                    
                    markup = types.InlineKeyboardMarkup()
                    markup.add(types.InlineKeyboardButton('🔄 Ещё раз', callback_data='game_blitz'))
                    markup.add(types.InlineKeyboardButton('🎮 Другие игры', callback_data='games_menu'))
                    markup.add(types.InlineKeyboardButton('🏠 Главное меню', callback_data='main_menu'))
                    
                    send_with_photo(chat_id, MAIN_PHOTO, text, markup, last_msg_id, last_photo)
                else:
                    question = generate_marathon_question()
                    user_states[chat_id]['current_quiz'] = question
                    
                    text = f'⚡ <b>Блиц-викторина</b>\n\n{result_emoji} {result_text}\n\n📊 Вопрос {blitz["question_num"]+1}/{blitz["total_questions"]}\n⭐ Очки: {blitz["score"]}\n\n'
                    
                    if question['type'] == 'national_quiz':
                        item = question['item']
                        text += f'❓ Национальность "{item["name"]}"?'
                        markup = create_quiz_answer_buttons(question['options'], 'blitz', 'national')
                    elif question['type'] == 'category_quiz':
                        item = question['item']
                        text += f'❓ Категория "{item["name"]}"?'
                        markup = create_quiz_answer_buttons(question['options'], 'blitz', 'category')
                    else:
                        text += f'❓ {question["statement"]}'
                        markup = create_quiz_answer_buttons(question['options'], 'blitz', 'tf')
                    
                    send_with_photo(chat_id, MAIN_PHOTO, text, markup, last_msg_id, last_photo)
            
            else:
                if is_correct:
                    if current_quiz['type'] == 'national_quiz':
                        item = current_quiz['item']
                        correct_name = get_russian_name(correct_answer)
                        text = (
                            f'✅ <b>Правильно!</b>\n\n'
                            f'📌 {item["name"]} действительно относится к культуре {correct_name}.\n\n'
                            f'Хотите узнать больше?'
                        )
                    else:
                        text = f'✅ <b>Правильно!</b>\n\nЭто действительно {correct_answer}!'
                    
                    result_emoji = '✅'
                else:
                    if current_quiz['type'] == 'national_quiz':
                        correct_name = get_russian_name(correct_answer)
                        text = (
                            f'❌ <b>Неправильно!</b>\n\n'
                            f'Правильный ответ: {correct_name}'
                        )
                    else:
                        text = f'❌ <b>Неправильно!</b>\n\nПравильный ответ: {correct_answer}'
                    
                    result_emoji = '❌'
                
                markup = types.InlineKeyboardMarkup()
                markup.add(types.InlineKeyboardButton('🔄 Ещё вопрос', callback_data=f'game_{quiz_type}_quiz'))
                markup.add(types.InlineKeyboardButton('🎮 Другие игры', callback_data='games_menu'))
                markup.add(types.InlineKeyboardButton('🏠 Главное меню', callback_data='main_menu'))
                
                send_with_photo(chat_id, MAIN_PHOTO, text, markup, last_msg_id, last_photo)
        
        elif data.startswith('match_select_'):
            game_data = user_states[chat_id].get('match_game')
            if not game_data:
                bot.answer_callback_query(call.id, '❌ Ошибка')
                return
            
            select_type = data.split('_')[2]
            idx = int(data.split('_')[3])
            
            if select_type == 'item':
                game_data['current_item'] = idx
                bot.answer_callback_query(call.id, f'Выбран элемент. Теперь выберите национальность.')
                
                matches_found = len(game_data.get('matches_found', []))
                text = (
                    f'🎯 <b>Найди пару</b>\n\n'
                    f'Элемент выбран! Теперь выберите национальность.\n\n'
                    f'✅ Найдено пар: {matches_found}/4'
                )
                
                markup = create_match_pairs_menu(game_data)
                bot.edit_message_caption(
                    caption=text,
                    chat_id=chat_id,
                    message_id=last_msg_id,
                    reply_markup=markup
                )
            
            elif select_type == 'nat':
                current_item_idx = game_data.get('current_item')
                if current_item_idx is None:
                    bot.answer_callback_query(call.id, '⚠️ Сначала выберите элемент!')
                    return
                
                items = game_data['items']
                if items[current_item_idx]['national'] == items[idx]['national']:
                    game_data['matches_found'].append(current_item_idx)
                    game_data['current_item'] = None
                    
                    matches_found = len(game_data['matches_found'])
                    
                    if matches_found >= 4:
                        text = (
                            f'🎉 <b>Поздравляем!</b>\n\n'
                            f'Вы нашли все пары! 🎯\n\n'
                            f'Отличное знание культур народов! ⭐'
                        )
                        
                        markup = types.InlineKeyboardMarkup()
                        markup.add(types.InlineKeyboardButton('🔄 Играть снова', callback_data='game_match_pairs'))
                        markup.add(types.InlineKeyboardButton('🎮 Другие игры', callback_data='games_menu'))
                        markup.add(types.InlineKeyboardButton('🏠 Главное меню', callback_data='main_menu'))
                        
                        send_with_photo(chat_id, MAIN_PHOTO, text, markup, last_msg_id, last_photo)
                    else:
                        bot.answer_callback_query(call.id, '✅ Правильно!')
                        
                        text = (
                            f'🎯 <b>Найди пару</b>\n\n'
                            f'✅ Правильно!\n\n'
                            f'Найдено пар: {matches_found}/4'
                        )
                        
                        markup = create_match_pairs_menu(game_data)
                        bot.edit_message_caption(
                            caption=text,
                            chat_id=chat_id,
                            message_id=last_msg_id,
                            reply_markup=markup
                        )
                else:
                    game_data['current_item'] = None
                    bot.answer_callback_query(call.id, '❌ Неправильно! Попробуйте ещё раз.')
                    
                    matches_found = len(game_data.get('matches_found', []))
                    text = (
                        f'🎯 <b>Найди пару</b>\n\n'
                        f'❌ Неправильно! Попробуйте снова.\n\n'
                        f'✅ Найдено пар: {matches_found}/4'
                    )
                    
                    markup = create_match_pairs_menu(game_data)
                    bot.edit_message_caption(
                        caption=text,
                        chat_id=chat_id,
                        message_id=last_msg_id,
                        reply_markup=markup
                    )
        
        elif data == 'main_menu':
            text = (
                '🌟 <b>Добро пожаловать в Этносферу!</b>\n\n'
                'Цифровая платформа народной культуры России.\n\n'
                '📍 <b>Здесь вы найдете:</b>\n'
                '• Информацию о традициях народов Мирнинского района\n'
                '• Национальную кухню и рецепты\n'
                '• Традиционные костюмы и орнаменты\n'
                '• События и праздники\n'
                '• Увлекательные игры и викторины\n\n'
                '👇 <b>Выберите действие из меню ниже:</b>'
            )
            send_with_photo(chat_id, MAIN_PHOTO, text, create_main_menu(), last_msg_id, last_photo)
        
        elif data == 'search_name':
            text = (
                '🔍 <b>Поиск по названию</b>\n\n'
                '👇 Что вы хотите найти?'
            )
            send_with_photo(chat_id, MAIN_PHOTO, text, create_search_type_menu(), last_msg_id, last_photo)
        
        elif data == 'search_type_national':
            text = '🔍 <b>Поиск национальности</b>\n\nВведите название национальности:'
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton('❌ Отмена', callback_data='main_menu'))
            
            user_states[chat_id]['search_mode'] = 'national'
            send_with_photo(chat_id, MAIN_PHOTO, text, markup, last_msg_id, last_photo)
        
        elif data == 'search_type_items':
            text = '🔍 <b>Поиск элементов</b>\n\nВведите название (например: щи, кокошник, хоровод):'
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton('❌ Отмена', callback_data='main_menu'))
            
            user_states[chat_id]['search_mode'] = 'all_items'
            send_with_photo(chat_id, MAIN_PHOTO, text, markup, last_msg_id, last_photo)
        
        elif data == 'select_national':
            text = '🌍 <b>Выберите национальность:</b>\n\nНажмите на название для выбора, затем "Далее"'
            user_states[chat_id]['selected_nationals'] = []
            user_states[chat_id]['nat_page'] = 0
            send_with_photo(chat_id, MAIN_PHOTO, text, create_nationals_menu(0, []), last_msg_id, last_photo)
        
        elif data.startswith('natselect_'):
            national = data[10:]
            selected = user_states[chat_id].get('selected_nationals', [])
            page = user_states[chat_id].get('nat_page', 0)
            
            if national in selected:
                selected.remove(national)
            else:
                selected.append(national)
            
            user_states[chat_id]['selected_nationals'] = selected
            
            bot.edit_message_reply_markup(
                chat_id=chat_id,
                message_id=last_msg_id,
                reply_markup=create_nationals_menu(page, selected)
            )
        
        elif data.startswith('natpage_'):
            page = int(data.split('_')[1])
            selected = user_states[chat_id].get('selected_nationals', [])
            user_states[chat_id]['nat_page'] = page
            bot.edit_message_reply_markup(
                chat_id=chat_id,
                message_id=last_msg_id,
                reply_markup=create_nationals_menu(page, selected)
            )
        
        elif data == 'natcontinue':
            selected = user_states[chat_id].get('selected_nationals', [])
            if not selected:
                bot.answer_callback_query(call.id, 'Выберите хотя бы одну национальность')
                return
            
            if len(selected) == 1:
                national = selected[0]
                ru_name = get_russian_name(national)
                
                photo_path = f'regionals/{national}/preview.png'
                if not os.path.exists(photo_path):
                    photo_path = MAIN_PHOTO
                
                text = f'📋 <b>{ru_name}</b>\n\n👇 Выберите категорию для просмотра:'
                send_with_photo(chat_id, photo_path, text, create_categories_menu(national), last_msg_id, last_photo)
            else:
                text = '📋 <b>Выбрано национальностей:</b> {}\n\n👇 Выберите категорию:'.format(len(selected))
                markup = types.InlineKeyboardMarkup(row_width=1)
                for cat_key, cat_name in CATEGORY_NAMES.items():
                    markup.add(types.InlineKeyboardButton(cat_name, callback_data=f'multicat_{cat_key}'))
                markup.add(types.InlineKeyboardButton('⬅️ К национальностям', callback_data='select_national'))
                markup.add(types.InlineKeyboardButton('🏠 Главное меню', callback_data='main_menu'))
                
                send_with_photo(chat_id, MAIN_PHOTO, text, markup, last_msg_id, last_photo)
        
        elif data.startswith('nat_'):
            national = data[4:]
            ru_name = get_russian_name(national)
            
            photo_path = f'regionals/{national}/preview.png'
            if not os.path.exists(photo_path):
                photo_path = MAIN_PHOTO
            
            text = f'📂 <b>{ru_name}</b>\n\n👇 Выберите категорию для просмотра:'
            send_with_photo(chat_id, photo_path, text, create_categories_menu(national), last_msg_id, last_photo)
        
        elif data.startswith('natcat_'):
            parts = data.split('_')
            national = parts[1]
            category = parts[2]
            
            ru_name = get_russian_name(national)
            cat_name = CATEGORY_NAMES.get(category, category)
            
            items = get_category_items(national, category)
            
            photo_path = f'regionals/{national}/{category}/preview.png'
            if not os.path.exists(photo_path):
                photo_path = MAIN_PHOTO
            
            if not items:
                text = f'📂 <b>{ru_name} - {cat_name}</b>\n\n❌ Список пуст. Данные еще не добавлены.'
            else:
                text = f'📂 <b>{ru_name} - {cat_name}</b>\n\n👇 Выберите элемент из списка:'
            
            send_with_photo(chat_id, photo_path, text, create_items_menu(national, category, 0), last_msg_id, last_photo)
        
        elif data.startswith('itempage_'):
            parts = data.split('_')
            national = parts[1]
            category = parts[2]
            page = int(parts[3])
            
            bot.edit_message_reply_markup(
                chat_id=chat_id,
                message_id=last_msg_id,
                reply_markup=create_items_menu(national, category, page)
            )
        
        elif data.startswith('item_'):
            parts = data.split('_')
            national = parts[1]
            category = parts[2]
            item_idx = int(parts[3])
            
            items = get_category_items(national, category)
            if item_idx >= len(items):
                bot.answer_callback_query(call.id, '❌ Элемент не найден')
                return
            
            item = items[item_idx]
            
            photo_path = os.path.join(DATA_DIR, national, category, item['image'])
            if not os.path.exists(photo_path):
                photo_path = MAIN_PHOTO
            
            text = (
                f"📌 <b>{item['name']}</b>\n"
                f"📅 {item['date']}\n\n"
                f"{item['description']}"
            )
            
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton('⬅️ Назад к списку', callback_data=f'natcat_{national}_{category}'))
            markup.add(types.InlineKeyboardButton('🏠 Главное меню', callback_data='main_menu'))
            
            send_with_photo(chat_id, photo_path, text, markup, last_msg_id, last_photo)
        
        elif data.startswith('searchitem_'):
            parts = data.split('_')
            national = parts[1]
            category = parts[2]
            item_idx = int(parts[3])
            
            items = get_category_items(national, category)
            if item_idx >= len(items):
                bot.answer_callback_query(call.id, '❌ Элемент не найден')
                return
            
            item = items[item_idx]
            
            photo_path = os.path.join(DATA_DIR, national, category, item['image'])
            if not os.path.exists(photo_path):
                photo_path = MAIN_PHOTO
            
            ru_name = get_russian_name(national)
            cat_name = CATEGORY_NAMES.get(category, category)
            
            text = (
                f"📌 <b>{item['name']}</b>\n"
                f"🌍 {ru_name}\n"
                f"📂 {cat_name}\n"
                f"📅 {item['date']}\n\n"
                f"{item['description']}"
            )
            
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton('⬅️ К списку', callback_data=f'natcat_{national}_{category}'))
            markup.add(types.InlineKeyboardButton('🔍 Новый поиск', callback_data='search_name'))
            markup.add(types.InlineKeyboardButton('🏠 Главное меню', callback_data='main_menu'))
            
            send_with_photo(chat_id, photo_path, text, markup, last_msg_id, last_photo)
        
        elif data == 'select_category':
            text = '📂 <b>Выберите категорию:</b>'
            send_with_photo(chat_id, MAIN_PHOTO, text, create_categories_menu(), last_msg_id, last_photo)
        
        elif data.startswith('multicat_'):
            category = data[9:]
            selected = user_states[chat_id].get('selected_nationals', [])
            cat_name = CATEGORY_NAMES.get(category, category)
            
            all_items = []
            for national in selected:
                items = get_category_items(national, category)
                for idx, item in enumerate(items):
                    all_items.append({
                        'name': item['name'],
                        'national': national,
                        'category': category,
                        'idx': idx
                    })
            
            if not all_items:
                text = f'📋 <b>{cat_name}</b>\n\n❌ Список пуст. Данные еще не добавлены.'
                markup = types.InlineKeyboardMarkup()
                markup.add(types.InlineKeyboardButton('⬅️ Назад', callback_data='natcontinue'))
                markup.add(types.InlineKeyboardButton('🏠 Главное меню', callback_data='main_menu'))
                send_with_photo(chat_id, MAIN_PHOTO, text, markup, last_msg_id, last_photo)
            else:
                markup = types.InlineKeyboardMarkup(row_width=1)
                for item in all_items[:20]:
                    ru_name = get_russian_name(item['national'])
                    text_btn = f"{item['name']} - {ru_name}"
                    markup.add(types.InlineKeyboardButton(text_btn, callback_data=f"item_{item['national']}_{category}_{item['idx']}"))
                
                markup.add(types.InlineKeyboardButton('⬅️ Назад', callback_data='natcontinue'))
                markup.add(types.InlineKeyboardButton('🏠 Главное меню', callback_data='main_menu'))
                
                text = f'📋 <b>{cat_name}</b>\nНайдено: {len(all_items)}\n\n👇 Выберите элемент:'
                send_with_photo(chat_id, MAIN_PHOTO, text, markup, last_msg_id, last_photo)
        
        elif data.startswith('cat_'):
            category = data[4:]
            cat_name = CATEGORY_NAMES.get(category, category)
            
            text = (
                f'📋 <b>{cat_name}</b>\n\n'
                'Сначала выберите национальность через главное меню.'
            )
            
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton('🌍 Выбрать национальность', callback_data='select_national'))
            markup.add(types.InlineKeyboardButton('🏠 Главное меню', callback_data='main_menu'))
            
            send_with_photo(chat_id, MAIN_PHOTO, text, markup, last_msg_id, last_photo)
        
        elif data == 'contacts':
            text = (
                '📞 <b>Контакты</b>\n\n'
                '🏛 <b>Владелец, помощники</b>\n'
                '💼 Usernames: @ewinnery, @znalwgx, @prophetaBM\n'
                '📧 Email: andrejvoron2n@gmail.com\n\n'
                '🌍 <b>МАОУ Сош N7</b>\n'
            )
            
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton('🏠 Главное меню', callback_data='main_menu'))
            
            send_with_photo(chat_id, MAIN_PHOTO, text, markup, last_msg_id, last_photo)
        
        elif data == 'feedback':
            text = (
                '💬 <b>Обратная связь</b>\n\n'
                'Для отправки отзыва или предложения напишите сообщение в чат.\n'
                'Мы обязательно рассмотрим ваше обращение!'
            )
            
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton('🏠 Главное меню', callback_data='main_menu'))
            
            user_states[chat_id]['waiting_feedback'] = True
            send_with_photo(chat_id, MAIN_PHOTO, text, markup, last_msg_id, last_photo)
        
        elif data.startswith('search_'):
            search_type = data[7:]
            
            text = '🔍 <b>Поиск</b>\n\nВведите поисковый запрос:'
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton('❌ Отмена', callback_data='main_menu'))
            
            user_states[chat_id]['search_type'] = search_type
            send_with_photo(chat_id, MAIN_PHOTO, text, markup, last_msg_id, last_photo)
        
        bot.answer_callback_query(call.id)
    
    except Exception as e:
        print(f"Callback error: {e}")
        import traceback
        traceback.print_exc()
        bot.answer_callback_query(call.id, '❌ Произошла ошибка')

@bot.message_handler(func=lambda message: True)
def text_handler(message):
    chat_id = message.chat.id
    
    delete_message_safe(chat_id, message.message_id)
    
    if chat_id in user_states:
        state = user_states[chat_id]
        last_photo = state.get('last_photo', MAIN_PHOTO)
        last_msg_id = state.get('last_message_id')
        
        if state.get('waiting_feedback'):
            text = '✅ <b>Спасибо за ваш отзыв!</b>\n\nМы его обязательно рассмотрим.'
            send_with_photo(chat_id, MAIN_PHOTO, text, create_main_menu(), last_msg_id, last_photo)
            user_states[chat_id] = {'last_photo': MAIN_PHOTO}
            return
        
        if 'search_mode' in state:
            query = message.text
            
            if state['search_mode'] == 'national':
                nationals = get_all_nationals()
                ru_nationals = [get_russian_name(n) for n in nationals]
                
                found_ru = fuzzy_search(query, ru_nationals, threshold=50)
                found = [get_english_name(n) for n in found_ru]
                
                if found:
                    markup = types.InlineKeyboardMarkup(row_width=1)
                    for nat in found[:10]:
                        ru_name = get_russian_name(nat)
                        markup.add(types.InlineKeyboardButton(ru_name, callback_data=f'nat_{nat}'))
                    markup.add(types.InlineKeyboardButton('🏠 Главное меню', callback_data='main_menu'))
                    
                    text = f'🔍 <b>Результаты поиска</b>\n\nНайдено национальностей: {len(found)}'
                    send_with_photo(chat_id, MAIN_PHOTO, text, markup, last_msg_id, last_photo)
                else:
                    text = '❌ <b>Ничего не найдено</b>\n\nПопробуйте другой запрос.'
                    send_with_photo(chat_id, MAIN_PHOTO, text, create_main_menu(), last_msg_id, last_photo)
            
            elif state['search_mode'] == 'all_items':
                all_items = get_all_items_from_all_nationals()
                
                item_names = [item['name'] for item in all_items]
                
                found_names = fuzzy_search(query, item_names, threshold=50)
                
                if found_names:
                    found_items = []
                    seen = set()
                    for name in found_names:
                        for item in all_items:
                            key = f"{item['name']}_{item['national']}_{item['category']}"
                            if item['name'] == name and key not in seen:
                                found_items.append(item)
                                seen.add(key)
                    
                    markup = types.InlineKeyboardMarkup(row_width=1)
                    
                    for item in found_items[:20]:
                        ru_name = get_russian_name(item['national'])
                        text_btn = f"{item['name']} - {ru_name}"
                        
                        items_in_cat = get_category_items(item['national'], item['category'])
                        idx = next((i for i, it in enumerate(items_in_cat) if it['name'] == item['name']), 0)
                        
                        callback = f"searchitem_{item['national']}_{item['category']}_{idx}"
                        markup.add(types.InlineKeyboardButton(text_btn, callback_data=callback))
                    
                    markup.add(types.InlineKeyboardButton('🔍 Новый поиск', callback_data='search_name'))
                    markup.add(types.InlineKeyboardButton('🏠 Главное меню', callback_data='main_menu'))
                    
                    text = f'🔍 <b>Результаты поиска "{query}"</b>\n\nНайдено элементов: {len(found_items)}\n\n👇 Выберите элемент:'
                    send_with_photo(chat_id, MAIN_PHOTO, text, markup, last_msg_id, last_photo)
                else:
                    text = '❌ <b>Ничего не найдено</b>\n\nПопробуйте другой запрос.'
                    send_with_photo(chat_id, MAIN_PHOTO, text, create_main_menu(), last_msg_id, last_photo)
            
            user_states[chat_id] = {'last_photo': MAIN_PHOTO}
            return
        
        if 'search_type' in state:
            query = message.text
            
            if state['search_type'] == 'national' or state['search_type'] == 'name':
                nationals = get_all_nationals()
                ru_nationals = [get_russian_name(n) for n in nationals]
                
                found_ru = fuzzy_search(query, ru_nationals, threshold=50)
                found = [get_english_name(n) for n in found_ru]
                
                if found:
                    markup = types.InlineKeyboardMarkup(row_width=1)
                    for nat in found[:10]:
                        ru_name = get_russian_name(nat)
                        markup.add(types.InlineKeyboardButton(ru_name, callback_data=f'nat_{nat}'))
                    markup.add(types.InlineKeyboardButton('🏠 Главное меню', callback_data='main_menu'))
                    
                    text = f'🔍 <b>Результаты поиска</b>\n\nНайдено: {len(found)}'
                    send_with_photo(chat_id, MAIN_PHOTO, text, markup, last_msg_id, last_photo)
                else:
                    text = '❌ <b>Ничего не найдено</b>\n\nПопробуйте другой запрос.'
                    send_with_photo(chat_id, MAIN_PHOTO, text, create_main_menu(), last_msg_id, last_photo)
            
            elif state['search_type'].startswith('items_'):
                parts = state['search_type'].split('_')
                national = parts[1]
                category = parts[2]
                
                items = get_category_items(national, category)
                item_names = [item['name'] for item in items]
                
                found_names = fuzzy_search(query, item_names, threshold=50)
                
                if found_names:
                    markup = types.InlineKeyboardMarkup(row_width=1)
                    for item_name in found_names[:10]:
                        for idx, item in enumerate(items):
                            if item['name'] == item_name:
                                markup.add(types.InlineKeyboardButton(item_name, callback_data=f'item_{national}_{category}_{idx}'))
                                break
                    markup.add(types.InlineKeyboardButton('⬅️ К списку', callback_data=f'natcat_{national}_{category}'))
                    markup.add(types.InlineKeyboardButton('🏠 Главное меню', callback_data='main_menu'))
                    
                    text = f'🔍 <b>Результаты поиска</b>\n\nНайдено: {len(found_names)}'
                    send_with_photo(chat_id, MAIN_PHOTO, text, markup, last_msg_id, last_photo)
                else:
                    text = '❌ <b>Ничего не найдено</b>\n\nПопробуйте другой запрос.'
                    send_with_photo(chat_id, MAIN_PHOTO, text, create_main_menu(), last_msg_id, last_photo)
            
            user_states[chat_id] = {'last_photo': MAIN_PHOTO}
            return
    
    text = '❓ Используйте команду /start для начала работы с ботом.'
    if chat_id not in user_states:
        user_states[chat_id] = {}
    last_msg_id = user_states[chat_id].get('last_message_id')
    last_photo = user_states[chat_id].get('last_photo', MAIN_PHOTO)
    send_with_photo(chat_id, MAIN_PHOTO, text, create_main_menu(), last_msg_id, last_photo)

if __name__ == '__main__':
    print('Бот запущен...')
    print('Все обработчики загружены!')
    print(f'Найдено национальностей: {len(get_all_nationals())}')
    bot.infinity_polling()