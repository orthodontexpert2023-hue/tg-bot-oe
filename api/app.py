import os
from datetime import datetime

from dotenv import load_dotenv
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse

from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove,
    InputMediaPhoto,
    InputMediaVideo,
    Update
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.redis import RedisStorage, DefaultKeyBuilder
from redis.asyncio import from_url

# =====================
# ENV
# =====================
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))
REDIS_URL = os.getenv("REDIS_URL")
BASE_URL = os.getenv("BASE_URL")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не найден")
if not CHANNEL_ID:
    raise ValueError("CHANNEL_ID не найден")
if not REDIS_URL:
    raise ValueError("REDIS_URL не найден")
if not BASE_URL:
    raise ValueError("BASE_URL не найден")
if not WEBHOOK_SECRET:
    raise ValueError("WEBHOOK_SECRET не найден")

# ❗ ВАЖНО: убрали /api
WEBHOOK_PATH = f"/webhook/{WEBHOOK_SECRET}"
WEBHOOK_URL = f"{BASE_URL}{WEBHOOK_PATH}"

# =====================
# BOT + STORAGE
# =====================
bot = Bot(token=BOT_TOKEN)

redis = from_url(REDIS_URL, encoding="utf-8", decode_responses=True)
storage = RedisStorage(
    redis=redis,
    key_builder=DefaultKeyBuilder(with_destiny=True)
)

dp = Dispatcher(storage=storage)

# =====================
# FSM
# =====================
class Form(StatesGroup):
    waiting_for_media = State()
    waiting_for_type = State()
    waiting_for_platform = State()
    waiting_for_description = State()
    waiting_for_deadline = State()
    waiting_for_comment = State()

# =====================
# START
# =====================
@dp.message(F.text == "/start")
async def start(message: Message, state: FSMContext):
    await state.clear()
    await state.set_state(Form.waiting_for_media)

    keyboard = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Это все файлы")]],
        resize_keyboard=True
    )

    await message.answer(
        "Загрузи файлы (фото, видео, документы, аудио, голосовые, кружки)\n"
        "Когда закончишь — нажми кнопку",
        reply_markup=keyboard
    )

# =====================
# ПЕРЕЗАПУСК
# =====================
@dp.message(F.text == "Загрузить новые файлы")
async def restart(message: Message, state: FSMContext):
    await state.clear()
    await state.set_state(Form.waiting_for_media)

    keyboard = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Это все файлы")]],
        resize_keyboard=True
    )

    await message.answer("Загрузи новые файлы", reply_markup=keyboard)

# =====================
# ПРИЁМ ФАЙЛОВ
# =====================
@dp.message(
    F.photo |
    F.video |
    F.document |
    F.audio |
    F.voice |
    F.video_note,
    Form.waiting_for_media
)
async def handle_media(message: Message, state: FSMContext):
    data = await state.get_data()
    media = data.get("media", [])

    file_id = None
    file_type = None

    if message.photo:
        file_id = message.photo[-1].file_id
        file_type = "photo"
    elif message.video:
        file_id = message.video.file_id
        file_type = "video"
    elif message.document:
        file_id = message.document.file_id
        file_type = "document"
    elif message.audio:
        file_id = message.audio.file_id
        file_type = "audio"
    elif message.voice:
        file_id = message.voice.file_id
        file_type = "voice"
    elif message.video_note:
        file_id = message.video_note.file_id
        file_type = "video_note"

    if file_id:
        media.append({
            "file_id": file_id,
            "type": file_type
        })

    await state.update_data(media=media)
    await message.answer("Файл добавлен 👍")

# =====================
# ЗАВЕРШЕНИЕ ФАЙЛОВ
# =====================
@dp.message(F.text == "Это все файлы", Form.waiting_for_media)
async def finish_media(message: Message, state: FSMContext):
    await state.set_state(Form.waiting_for_type)

    keyboard = ReplyKeyboardMarkup(
        keyboard=[[
            KeyboardButton(text="Сторис"),
            KeyboardButton(text="Пост"),
            KeyboardButton(text="Рилс"),
            KeyboardButton(text="Другое")
        ]],
        resize_keyboard=True
    )

    await message.answer("Тип контента?", reply_markup=keyboard)

# =====================
# ТИП
# =====================
@dp.message(Form.waiting_for_type)
async def get_type(message: Message, state: FSMContext):
    await state.update_data(content_type=message.text)
    await state.set_state(Form.waiting_for_platform)

    keyboard = ReplyKeyboardMarkup(
        keyboard=[[
            KeyboardButton(text="Инстаграм"),
            KeyboardButton(text="ВК"),
            KeyboardButton(text="Ютуб"),
            KeyboardButton(text="Телеграм"),
            KeyboardButton(text="Комбинированный")
        ]],
        resize_keyboard=True
    )

    await message.answer("Для какой соцсети?", reply_markup=keyboard)

# =====================
# ПЛАТФОРМА
# =====================
@dp.message(Form.waiting_for_platform)
async def get_platform(message: Message, state: FSMContext):
    await state.update_data(platform=message.text)
    await state.set_state(Form.waiting_for_description)

    await message.answer("Описание?", reply_markup=ReplyKeyboardRemove())

# =====================
# ОПИСАНИЕ
# =====================
@dp.message(Form.waiting_for_description)
async def get_description(message: Message, state: FSMContext):
    await state.update_data(description=message.text)
    await state.set_state(Form.waiting_for_deadline)

    await message.answer("Дедлайн?")

# =====================
# ДЕДЛАЙН
# =====================
@dp.message(Form.waiting_for_deadline)
async def get_deadline(message: Message, state: FSMContext):
    await state.update_data(deadline=message.text)
    await state.set_state(Form.waiting_for_comment)

    await message.answer("Комментарий?")

# =====================
# ФИНАЛ
# =====================
@dp.message(Form.waiting_for_comment)
async def finish(message: Message, state: FSMContext):
    await state.update_data(comment=message.text)
    data = await state.get_data()

    media = data.get("media", [])

    now = datetime.now().strftime("%d.%m.%Y %H:%M")

    text = (
        f"<b>{now}</b>\n\n"
        f"<b>Тип:</b>\n{data.get('content_type')}\n\n"
        f"<b>Платформа:</b>\n{data.get('platform')}\n\n"
        f"<b>Описание:</b>\n{data.get('description')}\n\n"
        f"<b>Дедлайн:</b>\n<u>{data.get('deadline')}</u>\n\n"
        f"<b>Комментарий:</b>\n{data.get('comment')}"
    )

    media_group = []
    other_files = []

    for item in media:
        if item["type"] in ["photo", "video"]:
            if item["type"] == "photo":
                media_group.append(InputMediaPhoto(media=item["file_id"]))
            else:
                media_group.append(InputMediaVideo(media=item["file_id"]))
        else:
            other_files.append(item)

    await bot.send_message(chat_id=CHANNEL_ID, text=text, parse_mode="HTML")

    if media_group:
        await bot.send_media_group(chat_id=CHANNEL_ID, media=media_group)

    for item in other_files:
        if item["type"] == "document":
            await bot.send_document(CHANNEL_ID, item["file_id"])
        elif item["type"] == "audio":
            await bot.send_audio(CHANNEL_ID, item["file_id"])
        elif item["type"] == "voice":
            await bot.send_voice(CHANNEL_ID, item["file_id"])
        elif item["type"] == "video_note":
            await bot.send_video_note(CHANNEL_ID, item["file_id"])

    keyboard = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Загрузить новые файлы")]],
        resize_keyboard=True
    )

    await message.answer("Отправлено в канал 🚀", reply_markup=keyboard)
    await state.clear()

# =====================
# FASTAPI
# =====================
app = FastAPI()

@app.get("/")
async def root():
    return {"ok": True, "message": "Bot is alive"}

# ❗ ВАЖНО: путь совпадает с webhook
@app.post("/webhook/{secret}")
async def telegram_webhook(secret: str, request: Request):
    if secret != WEBHOOK_SECRET:
        raise HTTPException(status_code=403, detail="Forbidden")

    data = await request.json()
    update = Update.model_validate(data)
    await dp.feed_update(bot, update)

    return JSONResponse({"ok": True})
