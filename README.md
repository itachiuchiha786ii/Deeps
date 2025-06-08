# 🤖 DeepSeek AI Telegram Bot

DeepSeek AI-powered Telegram bot that:
- Accepts user prompts and replies using Novita API (like ChatGPT).
- Supports temporary message handling and instant cleanup.
- Deletes typing indicators and response messages after replying.
- Handles small and long responses differently.
- Designed for fast, lightweight, and privacy-respecting AI conversations.

---

## 🚀 Features

- 🌐 Async bot powered by `python-telegram-bot`
- 🔐 Keeps conversation memory short-lived
- 🧠 Uses `novita.ai` GPT-like API for fast response
- 🧹 Cleans up "thinking..." messages before sending the real response
- 📦 Fully container-ready and Render-deployable

---

## 🛠 Tech Stack

- Python 3.12
- python-telegram-bot
- aiohttp
- asyncio
- Novita AI API

---

## 📄 Requirements

Install dependencies:
```bash
pip install -r requirements.txt
