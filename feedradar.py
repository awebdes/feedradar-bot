import os
import csv
import threading
from aiogram import Bot, Dispatcher, types
from aiogram.types import InputFile
from aiogram.utils import executor
from google_play_scraper import app as gp_app, reviews as gp_reviews
from app_store_scraper import AppStore
from flask import Flask
from dotenv import load_dotenv

# Загружаем переменные окружения из .env
load_dotenv()

# Проверяем, что токен установлен
API_TOKEN = os.getenv("API_TOKEN")
if not API_TOKEN:
    raise ValueError("Токен не найден! Убедись, что переменная окружения API_TOKEN установлена.")

# Инициализация бота и диспетчера
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# Временная папка для файлов
TEMP_FOLDER = "temp"
if not os.path.exists(TEMP_FOLDER):
    os.makedirs(TEMP_FOLDER)

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
    url = message.text
    if "play.google.com" in url:
        await parse_google_play(url, message)
    elif "apps.apple.com" in url:
        await parse_app_store(url, message)
    else:
        await message.reply("Неверная ссылка. Пожалуйста, отправь ссылку на Google Play или App Store.")

# Парсинг Google Play
async def parse_google_play(url, message):
    try:
        app_id = url.split("id=")[1].split("&")[0]
        reviews = []
        continuation_token = None
        while True:
            batch, continuation_token = gp_reviews(app_id, lang='ru', count=100, continuation_token=continuation_token)
            reviews.extend(batch)
            if not continuation_token or len(reviews) >= 1000:  # Ограничение на 1000 отзывов
                break
        csv_filename = save_to_csv(reviews, "google_play")
        await send_csv(message, csv_filename)
    except Exception as e:
        await message.reply(f"Ошибка: {e}")

# Парсинг App Store
async def parse_app_store(url, message):
    try:
        app_id = url.split("id")[1].split("?")[0]
        app = AppStore(country="ru", app_name=app_id, app_id=app_id)
        app.review(how_many=1000)  # Получить до 1000 отзывов
        csv_filename = save_to_csv(app.reviews, "app_store")
        await send_csv(message, csv_filename)
    except Exception as e:
        await message.reply(f"Ошибка: {e}")

# Сохранение в CSV
def save_to_csv(data, platform):
    csv_filename = os.path.join(TEMP_FOLDER, f"{platform}_reviews.csv")
    with open(csv_filename, mode="w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["User", "Rating", "Review", "Date"])
        for item in data:
            writer.writerow([item.get("userName"), item.get("score"), item.get("content"), item.get("at")])
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
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.start()

    # Запускаем бота
    executor.start_polling(dp, skip_updates=True)
