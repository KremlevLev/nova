from openai import OpenAI

# Инициализация клиента с настройками OpenRouter
client = OpenAI(
    base_url="https://openrouter.ai",
    api_key="YOUR_OPENROUTER_API_KEY",
)

completion = client.chat.completions.create(
    # Указывайте любую модель из каталога OpenRouter
    model="google/gemini-2.5-flash", 
    messages=[
        {"role": "user", "content": "Привет! Напиши одну короткую фразу."}
    ],
    # Необязательные заголовки для включения вашего приложения в рейтинг OpenRouter
    extra_headers={
        "HTTP-Referer": "https://your-site.com", 
        "X-Title": "My Awesome App",
    }
)

print(completion.choices[0].message.content)
