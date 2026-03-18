import asyncio
import os
from datetime import datetime

from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove,
    InputMediaPhoto,
    InputMediaVideo
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv

# =====================
# ENV
# =====================
load_dotenv("t.env")

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

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
# RUN
# =====================
async def main():
    await dp.start_polling(bot)


import asyncio

async def keep_alive():
    while True:
        await asyncio.sleep(3600)

async def main():
    await asyncio.gather(
        dp.start_polling(bot),
        keep_alive()
    )

if __name__ == "__main__":
    asyncio.run(main())
