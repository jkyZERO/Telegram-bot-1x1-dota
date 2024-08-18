import telebot
from telebot import types
import sqlite3
import random

TOKEN = '6804675917:AAGeINfOY3gPRJLCyNQQBdpbfUVFecPLcY4'
ADMIN_ID = '5282827432'  # Замените на ID администратора
DISCORD_LINK = 'https://discord.gg/wBvkhhVxSk'  # Замените на вашу ссылку
bot = telebot.TeleBot(TOKEN)

users_searching = []
active_chats = {}

# Инициализация базы данных с миграцией
conn = sqlite3.connect('users.db', check_same_thread=False)
cursor = conn.cursor()

# Проверяем, существует ли столбец rating_confirmed
cursor.execute("PRAGMA table_info(users)")
columns = [column[1] for column in cursor.fetchall()]

if 'rating_confirmed' not in columns:
    cursor.execute("ALTER TABLE users ADD COLUMN rating_confirmed BOOLEAN DEFAULT 0")
    conn.commit()

cursor.execute('''CREATE TABLE IF NOT EXISTS users 
                  (id INTEGER PRIMARY KEY, rating INTEGER DEFAULT 0, rating_confirmed BOOLEAN DEFAULT 0)''')
conn.commit()

def create_main_markup():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("Поиск"), types.KeyboardButton("Профиль"))
    markup.add(types.KeyboardButton("Дискорд"), types.KeyboardButton("Связь с админом"))
    return markup

def create_search_markup():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("Отменить поиск"))
    return markup

@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    cursor.execute("INSERT OR IGNORE INTO users (id) VALUES (?)", (user_id,))
    conn.commit()
    
    bot.send_message(user_id, "Привет! Используй кнопки для навигации.", reply_markup=create_main_markup())

@bot.message_handler(func=lambda message: message.text == "Профиль")
def profile(message):
    user_id = message.from_user.id
    cursor.execute("SELECT rating, rating_confirmed FROM users WHERE id = ?", (user_id,))
    result = cursor.fetchone()
    rating, confirmed = result if result else (0, False)
    
    status = "подтвержден" if confirmed else "не подтвержден"
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("Изменить рейтинг", callback_data="change_rating"))
    
    bot.send_message(user_id, f"Ваш текущий рейтинг: {rating} ({status})", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "change_rating")
def change_rating_callback(call):
    bot.answer_callback_query(call.id)
    bot.send_message(call.from_user.id, "Введите ваш новый рейтинг:")
    bot.register_next_step_handler(call.message, save_new_rating)

def save_new_rating(message):
    try:
        new_rating = int(message.text)
        user_id = message.from_user.id
        cursor.execute("UPDATE users SET rating = ?, rating_confirmed = 0 WHERE id = ?", (new_rating, user_id))
        conn.commit()
        bot.send_message(user_id, f"Ваш новый рейтинг: {new_rating}. Пожалуйста, отправьте скриншот для подтверждения.")
        bot.register_next_step_handler(message, process_rating_screenshot)
    except ValueError:
        bot.send_message(message.from_user.id, "Пожалуйста, введите корректное число.")

def process_rating_screenshot(message):
    if message.content_type == 'photo':
        file_info = bot.get_file(message.photo[-1].file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        user_id = message.from_user.id
        
        cursor.execute("SELECT rating FROM users WHERE id = ?", (user_id,))
        rating = cursor.fetchone()[0]
        
        bot.send_photo(ADMIN_ID, downloaded_file, caption=f"Скриншот для подтверждения рейтинга от пользователя {user_id}. Заявленный рейтинг: {rating}")
        bot.send_message(user_id, "Скриншот отправлен администратору на проверку. Ожидайте подтверждения.")
    else:
        bot.send_message(message.from_user.id, "Пожалуйста, отправьте изображение.")

@bot.message_handler(commands=['confirm_rating'])
def confirm_rating(message):
    if str(message.from_user.id) == ADMIN_ID:
        try:
            _, user_id = message.text.split()
            user_id = int(user_id)
            cursor.execute("UPDATE users SET rating_confirmed = 1 WHERE id = ?", (user_id,))
            conn.commit()
            bot.send_message(ADMIN_ID, f"Рейтинг пользователя {user_id} подтвержден.")
            bot.send_message(user_id, "Ваш рейтинг был подтвержден администратором.")
        except:
            bot.send_message(ADMIN_ID, "Используйте формат: /confirm_rating [id пользователя]")
    else:
        bot.send_message(message.from_user.id, "У вас нет прав для выполнения этой команды.")

@bot.message_handler(func=lambda message: message.text == "Поиск")
def search(message):
    user_id = message.from_user.id
    if user_id in users_searching:
        bot.send_message(user_id, "Вы уже в поиске. Нажмите 'Отменить поиск', если хотите прекратить поиск.")
    elif user_id in active_chats:
        bot.send_message(user_id, "Вы уже в чате. Завершите текущий чат, чтобы начать новый поиск.")
    else:
        users_searching.append(user_id)
        bot.send_message(user_id, "Поиск начат. Ожидайте...", reply_markup=create_search_markup())
        find_match(user_id)

@bot.message_handler(func=lambda message: message.text == "Отменить поиск")
def cancel_search(message):
    user_id = message.from_user.id
    if user_id in users_searching:
        users_searching.remove(user_id)
        bot.send_message(user_id, "Поиск отменен.", reply_markup=create_main_markup())
    else:
        bot.send_message(user_id, "Вы не находитесь в поиске.")

def find_match(user_id):
    if len(users_searching) > 1:
        partner_id = random.choice([u for u in users_searching if u != user_id])
        users_searching.remove(user_id)
        users_searching.remove(partner_id)
        active_chats[user_id] = partner_id
        active_chats[partner_id] = user_id
        
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add(types.KeyboardButton("Завершить чат"))
        
        for uid in [user_id, partner_id]:
            cursor.execute("SELECT rating, rating_confirmed FROM users WHERE id = ?", (active_chats[uid],))
            partner_rating, partner_confirmed = cursor.fetchone()
            status = "подтвержден" if partner_confirmed else "не подтвержден"
            bot.send_message(uid, f"Собеседник найден! Рейтинг собеседника: {partner_rating} ({status})", reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == "Завершить чат")
def end_chat(message):
    user_id = message.from_user.id
    if user_id in active_chats:
        partner_id = active_chats[user_id]
        del active_chats[user_id]
        del active_chats[partner_id]
        
        bot.send_message(user_id, "Чат завершен.", reply_markup=create_main_markup())
        bot.send_message(partner_id, "Собеседник завершил чат.", reply_markup=create_main_markup())
    else:
        bot.send_message(user_id, "У вас нет активного чата.")

@bot.message_handler(func=lambda message: message.from_user.id in active_chats)
def handle_chat(message):
    user_id = message.from_user.id
    partner_id = active_chats[user_id]
    bot.send_message(partner_id, f"Собеседник: {message.text}")

@bot.message_handler(func=lambda message: message.text == "Дискорд")
def discord(message):
    bot.send_message(message.chat.id, f"Присоединяйтесь к нашему Дискорд-серверу: {DISCORD_LINK}")

@bot.message_handler(func=lambda message: message.text == "Связь с админом")
def contact_admin(message):
    bot.send_message(message.chat.id, "Чтобы связаться с администратором, отправьте ваше сообщение. Оно будет переслано администратору.")
    bot.register_next_step_handler(message, forward_to_admin)

def forward_to_admin(message):
    user_id = message.from_user.id
    bot.send_message(ADMIN_ID, f"Сообщение от пользователя {user_id}:\n\n{message.text}")
    bot.send_message(user_id, "Ваше сообщение отправлено администратору. Ожидайте ответа.")

bot.polling()
