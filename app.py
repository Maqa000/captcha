import os
import json
import base64
import re
from flask import Flask, request, jsonify
import requests
from PIL import Image
import io

app = Flask(__name__)

# Конфигурация DeepSeek
DEEPSEEK_API_KEY = os.environ.get('DEEPSEEK_API_KEY', '')
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"

@app.route('/analyze', methods=['POST'])
def analyze_screenshot():
    try:
        # Получаем изображение от клиента
        image_file = request.files['screenshot']
        action_needed = request.form.get('action_needed', 'check_rods')
        
        # Конвертируем изображение в base64 для DeepSeek
        image_bytes = image_file.read()
        image_base64 = base64.b64encode(image_bytes).decode('utf-8')
        
        # Разные промпты в зависимости от того, что ищем
        if action_needed == "check_rods":
            # Анализируем состояние всех удочек
            prompt = """Ты помощник для игры в рыбалку. На скриншоте видно 3 удочки (слота).
Найди каждую удочку и определи, что написано над ней.

Варианты надписей:
- "Готово" (готова к старту)
- "Ожидание" (ждет поклевку)
- "CATCH REQUIRED" (клюет, нужно ловить)
- "Ловля..." (процесс ловли)

Также определи:
- Есть ли на экране окно с капчей? (обычно белое окно с надписью "Are you bot? CAPTCHA")
- Если есть капча - напиши текст капчи (только цифры)

Ответь строго в формате JSON:
{
    "rods": [
        {"slot": 1, "status": "готово/ожидание/catch/ловля"},
        {"slot": 2, "status": "..."},
        {"slot": 3, "status": "..."}
    ],
    "captcha": {
        "detected": true/false,
        "text": "цифры_с_капчи_если_есть"
    }
}"""
        elif action_needed == "find_ok":
            # Ищем кнопку ОК после рыбалки
            prompt = """Найди на скриншоте кнопку ОК (или похожую кнопку закрытия окна с результатом).
Определи её координаты (центр кнопки).

Ответь строго в формате JSON:
{
    "found": true/false,
    "x": координата_X,
    "y": координата_Y
}"""
        elif action_needed == "find_catch":
            # Ищем кнопку CATCH REQUIRED
            prompt = """Найди на скриншоте кнопку с надписью "CATCH REQUIRED" или похожую.
Определи её координаты (центр кнопки).

Ответь строго в формате JSON:
{
    "found": true/false,
    "x": координата_X,
    "y": координата_Y
}"""
        else:
            # Общий анализ
            prompt = """Проанализируй скриншот игры в рыбалку.
Определи:
1. Есть ли капча? Если да - напиши цифры с капчи
2. Есть ли кнопка CATCH REQUIRED? Если да - её координаты
3. Есть ли кнопка ОК? Если да - её координаты

Ответь строго в формате JSON:
{
    "captcha": {"detected": true/false, "text": "цифры"},
    "catch": {"found": true/false, "x": 0, "y": 0},
    "ok": {"found": true/false, "x": 0, "y": 0}
}"""
        
        # Отправляем запрос к DeepSeek
        headers = {
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "deepseek-chat",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": prompt
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{image_base64}"
                            }
                        }
                    ]
                }
            ],
            "temperature": 0.1,
            "max_tokens": 300
        }
        
        print(f"Отправляю запрос к DeepSeek для {action_needed}...")
        response = requests.post(DEEPSEEK_API_URL, headers=headers, json=payload, timeout=30)
        result = response.json()
        
        # Извлекаем ответ DeepSeek
        ai_response = result['choices'][0]['message']['content']
        print(f"DeepSeek ответил: {ai_response}")
        
        # Парсим JSON из ответа
        try:
            # Ищем JSON в ответе
            json_match = re.search(r'\{.*\}', ai_response, re.DOTALL)
            if json_match:
                action_data = json.loads(json_match.group())
            else:
                action_data = json.loads(ai_response)
                
            return jsonify(action_data)
            
        except Exception as e:
            print(f"Ошибка парсинга JSON: {e}")
            return jsonify({"error": "Failed to parse AI response"}), 500
        
    except Exception as e:
        print(f"Ошибка: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/')
def home():
    return "Fishing Bot Server is running! Используй /analyze для отправки скриншотов"

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
