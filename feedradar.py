import os
import csv
import threading
import asyncio
import re
from urllib.parse import urlparse, parse_qs
from aiogram import Bot, Dispatcher, types
from aiogram.types import InputFile
from aiogram.utils import executor
from google_play_scraper import app as gp_app, reviews as gp_reviews
from app_store_scraper import AppStore
from flask import Flask

# Настройки бота
API_TOKEN = os.getenv("8177571130:AAGsv2MswKTQmLcyKuH76PU2yOdh8EUjUwE")  # Используем переменную окружения для токена
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# Временная папка для файлов
TEMP_FOLDER = "temp"
os.makedirs(TEMP_FOLDER, exist_ok=True)

# Инициализация Flask приложения
app = Flask(__name__)

@app.route('/')
def home():
    return "Бот работает! Отправьте ссылку на приложение в Google Play или App Store."

# Обработка команды /start
@dp.message_handler(commands=['start'])
async def send_welcome(message: types.Message):
    await message.reply("Привет! Отправь мне ссылку на приложение в Google Play или App Store, и я соберу для тебя отзывы.")

# Обработка ссылки
@dp.message_handler()
async def handle_link(message: types.Message):
    url = message.text.strip()
    if "play.google.com" in url:
        await parse_google_play(url, message)
    elif "apps.apple.com" in url:
        await parse_app_store(url, message)
    else:
        await message.reply("Неверная ссылка. Пожалуйста, отправь ссылку на Google Play или App Store.")

# Парсинг Google Play
async def parse_google_play(url, message):
    try:
        parsed_url = urlparse(url)
        query_params = parse_qs(parsed_url.query)
        app_id = query_params.get("id", [None])[0]
        
        if not app_id:
            await message.reply("Не удалось извлечь ID приложения из ссылки.")
            return

        reviews, _ = gp_reviews(app_id, lang='ru', count=100)
        csv_filename = save_to_csv(reviews, "google_play")
        await send_csv(message, csv_filename)
    except Exception as e:
        await message.reply(f"Ошибка при парсинге Google Play: {e}")

# Парсинг App Store
async def parse_app_store(url, message):
    try:
        match = re.search(r'id(\d+)', url)
        if not match:
            await message.reply("Не удалось извлечь ID приложения из ссылки.")
            return
        
        app_id = match.group(1)
        app = AppStore(country="ru", app_id=app_id)
        
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, app.review)  # Запускаем парсинг в потоке

        csv_filename = save_to_csv(app.reviews, "app_store")
        await send_csv(message, csv_filename)
    except Exception as e:
        await message.reply(f"Ошибка при парсинге App Store: {e}")

# Сохранение в CSV
def save_to_csv(data, platform):
    csv_filename = os.path.join(TEMP_FOLDER, f"{platform}_reviews.csv")
    with open(csv_filename, mode="w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file, quoting=csv.QUOTE_ALL)
        writer.writerow(["User", "Rating", "Review", "Date"])
        for item in data:
            writer.writerow([
                item.get("userName", "Unknown"),
                item.get("score", "No rating"),
                item.get("content", "").replace("\n", " "),
                item.get("at", "")
            ])
    return csv_filename

# Отправка CSV-файла
async def send_csv(message, csv_filename):
    with open(csv_filename, "rb") as file:
        await message.reply_document(InputFile(file))
    os.remove(csv_filename)

# Запуск Flask в отдельном потоке
def run_flask():
    port = int(os.getenv("PORT", 10000))  # Используем порт из переменной окружения
    app.run(host='0.0.0.0', port=port)

if __name__ == '__main__':
    # Запускаем Flask в отдельном потоке
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()

    # Запускаем бота
    executor.start_polling(dp, skip_updates=True)
