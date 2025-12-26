# Sborka Bot

A Telegram bot for personal development coaching across four life spheres: Center (Штаб), Soul (Душа), Body (Тело), and Business (Бизнес).

## Features

- **Personality Test**: Onboarding flow with personality assessment
- **AI-Powered Curators**: Different AI personalities for each life sphere
- **Voice Recognition**: Support for voice messages up to 1 minute
- **Conversation History**: Maintains separate chat histories for each sphere
- **Auto-Summarization**: Automatic conversation summarization for context

## Tech Stack

- Python 3.10
- python-telegram-bot
- SQLAlchemy with SQLite
- Flask for webapp
- Jinja2 for templating
- Replicate API for AI (Gemini) and Speech-to-Text (Whisper)

## Project Structure

```
sborka-bot-python/
├── bot/
│   ├── __init__.py
│   ├── main.py              # Main bot entry point
│   ├── database/
│   │   ├── __init__.py
│   │   ├── models.py        # SQLAlchemy models
│   │   └── session.py       # Database session management
│   ├── handlers/
│   │   ├── __init__.py
│   │   ├── onboarding.py    # Personality test handler
│   │   ├── chat.py          # Chat message handler
│   │   ├── commands.py      # Bot commands handler
│   │   └── voice.py         # Voice message handler
│   ├── services/
│   │   ├── __init__.py
│   │   ├── ai_service.py    # Replicate AI API
│   │   ├── speech_service.py # Speech-to-text service
│   │   └── summarization_service.py
│   └── utils/
│       ├── __init__.py
│       └── helpers.py       # Utility functions
├── webapp/
│   ├── __init__.py
│   ├── app.py               # Flask webapp
│   └── templates/
│       └── curator_choice.html
├── content/
│   ├── onboarding.json      # Personality test questions
│   ├── psycotype.txt        # Psychotype analysis prompt
│   ├── recommendation.txt   # Curator recommendation prompt
│   ├── summarization.txt    # Summarization prompt
│   └── curators/
│       ├── center.txt
│       ├── business/
│       │   ├── coach.txt
│       │   └── friend.txt
│       ├── soul/
│       │   ├── empathy.txt
│       │   └── mindfulness.txt
│       └── body/
│           ├── strict.txt
│           └── relaxed.txt
├── requirements.txt
├── run_bot.py               # Bot entry point
├── run_webapp.py            # Webapp entry point
└── README.md
```

## Setup

1. **Install dependencies**:
   ```
   pip install -r requirements.txt
   ```

2. **Create `.env` file** with the following variables:
   ```
   BOT_TOKEN=your_telegram_bot_token
   WEBAPP_URL=http://127.0.0.1:5000
   USE_TG_TEST=false
   REPLICATE_TOKEN=your_replicate_token
   EXPRESS_HOST=127.0.0.1
   EXPRESS_PORT=5000
   ```

3. **Run the webapp** (in a separate terminal):
   ```
   python run_webapp.py
   ```

4. **Run the bot**:
   ```
   python run_bot.py
   ```

## Bot Commands

- `/start` - Start the bot and begin onboarding
- `/psychotype` - Retake the personality test
- `/curators` - Change curator selection
- `/help` - Show help message

## Spheres and Curators

### Center (Штаб)
- Coordinates all spheres
- No curator selection (single personality)

### Business (Бизнес)
- **coach**: Strict business coach focused on results
- **friend**: Friendly mentor with supportive approach

### Soul (Душа)
- **empathy**: Empathetic psychologist
- **mindfulness**: Mindfulness master

### Body (Тело)
- **strict**: Strict fitness trainer
- **relaxed**: Relaxed, pleasure-focused approach

## Usage Flow

1. User starts the bot with `/start`
2. User completes the personality test (10 questions)
3. AI analyzes answers and recommends curators
4. User can customize curator selection via webapp
5. User chats with different curators in topic threads:
   - Topics containing "душа" → Soul sphere
   - Topics containing "дело" → Business sphere
   - Topics containing "тело" → Body sphere
   - Topics containing "штаб" → Center sphere
   - Direct messages → Center sphere

## Voice Messages

- Maximum duration: 60 seconds
- Automatically transcribed using Whisper
- Processed as regular text messages

## Summarization

- First summarization after 3 message pairs
- Subsequent summarizations every 10 message pairs
- Summaries are used to provide context to AI curators


