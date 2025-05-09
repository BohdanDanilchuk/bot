import streamlit as st
import asyncio
import random
from datetime import datetime, timedelta
from telethon import TelegramClient
from telethon.tl.types import Chat, Channel
import pytz

# 📌 Інтерфейс для введення Telegram API доступу
st.sidebar.header("🔐 Telegram API доступ")
api_id = st.sidebar.text_input("API ID", value="", type="default")
api_hash = st.sidebar.text_input("API Hash", value="", type="password")
session_name = 'userbot_session'

# Перевірка наявності API ID та API Hash
if not api_id or not api_hash:
    st.error("❌ Введіть API ID та API Hash у лівій панелі.")
    st.stop()


st.title("🔍 Сканування Telegram груп за ключовими словами та датами")
st.markdown("Знаходить повідомлення з ключовими словами у всіх групах, де ви є учасником. Працює з фільтром по датах.")

uploaded_file = st.file_uploader("Завантажити файл з ключовими словами (.txt)", type=["txt"])

if uploaded_file is not None:
    keywords_input = uploaded_file.getvalue().decode("utf-8")
else:
    keywords_input = st.text_input("Ключові слова (через кому):", "")

# Вибір режиму пошуку за датами
search_mode = st.radio("🔍 Режим пошуку за датою:", ("Одна дата", "Діапазон дат"))

if search_mode == "Одна дата":
    single_date = st.date_input("Оберіть дату", datetime.today())
    start_date = datetime.combine(single_date, datetime.min.time())
    end_date = start_date + timedelta(days=1)
else:
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Початкова дата", datetime.today() - timedelta(days=7))
    with col2:
        end_date = st.date_input("Кінцева дата", datetime.today())
    start_date = datetime.combine(start_date, datetime.min.time())
    end_date = datetime.combine(end_date, datetime.max.time())

# Локалізація дат до Europe/Kiev
local_tz = pytz.timezone('Europe/Kiev')
start_date = local_tz.localize(start_date)
end_date = local_tz.localize(end_date)

if st.button("🔍 Сканувати всі групи"):
    if uploaded_file is not None:
        keywords = [k.strip().lower() for k in keywords_input.split("\n") if k.strip()]
    else:
        keywords = [k.strip().lower() for k in keywords_input.split(",")]

    st.write(f"📝 Шукаємо за ключовими словами: {keywords}")
    placeholder = st.empty()  # Місце для лічильника

    async def main_with_progress():
        found_count = 0
        client = TelegramClient(session_name, api_id, api_hash)
        await client.start()

        dialogs = await client.get_dialogs()
        groups = [
            (dialog.name, dialog.entity)
            for dialog in dialogs
            if isinstance(dialog.entity, (Chat, Channel)) and (
                getattr(dialog.entity, 'megagroup', False) or isinstance(dialog.entity, Chat)
            )
        ]

        wait_interval = 1

        for group_name, entity in groups:
            try:
                async for message in client.iter_messages(entity):
                    if message.date is None:
                        continue

                    msg_date = message.date.astimezone(local_tz)

                    # Пропускаємо повідомлення, що новіші за кінець
                    if msg_date > end_date:
                        continue

                    # Зупиняємо цикл, якщо повідомлення старше початку
                    if msg_date < start_date:
                        break

                    if message.text:
                        message_text = message.text.strip().lower()
                        if any(k in message_text for k in keywords):
                            sender = await message.get_sender()
                            if sender:
                                author = f"@{sender.username}" if sender.username else (f"{sender.first_name or 'Анонім'}")
                            else:
                                author = "Анонім"

                            found_count += 1
                            placeholder.info(f"🔎 Знайдено повідомлень: {found_count}")

                            msg_to_save = (
                                f"📍 Група: {group_name}\n"
                                f"👤 Від: {author}\n"
                                f"📅 Дата: {msg_date.strftime('%Y-%m-%d %H:%M')}\n"
                                f"📩 Повідомлення:\n{message.text}"
                            )
                            try:
                                await client.send_message("me", msg_to_save)
                                await asyncio.sleep(wait_interval)
                                wait_interval = min(wait_interval * 1.5, 10)
                            except Exception as send_error:
                                print(f"❌ Не вдалося надіслати повідомлення: {send_error}")
                                await asyncio.sleep(10)
                                try:
                                    await client.send_message("me", msg_to_save)
                                except Exception as retry_error:
                                    print(f"❌ Повторна спроба не вдалася: {retry_error}")
            except Exception as e:
                print(f"⚠️ Помилка у {group_name}: {e}")

        await client.disconnect()
        return found_count

    with st.spinner("Сканування..."):
        found_count = asyncio.run(main_with_progress())

    st.success(f"✅ Завершено! Усього знайдено {found_count} повідомлень.")
