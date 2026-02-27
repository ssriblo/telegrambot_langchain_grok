repository: `git@github.com:ssriblo/telegrambot_langchain_grok.git`

```
python -m venv .venv
source .venv/bin/activate
pip install aiogram langchain-community langchain-openai langchain_groq

Warp conversations and updates:
`https://app.warp.dev/session/912e6a3e-48e5-4801-a5eb-ae81ce4bfc99`

run:
python main.py              # DEBUG (максимум, по умолчанию)
python main.py --log INFO   # только INFO/WARNING/ERROR (состояния, маршруты)
python main.py --log NONE   # логирование отключено
