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
        else:
            prompt = """Проанализируй скриншот игры в рыбалку.
Определи:
1. Есть ли капча? Если да - напиши цифры с капчи

Ответь строго в формате JSON:
{
    "captcha": {"detected": true/false, "text": "цифры"}
}"""
        
        # Проверяем, есть ли API ключ
        if not DEEPSEEK_API_KEY:
            print("ОШИБКА: Не задан DEEPSEEK_API_KEY")
            return jsonify({
                "rods": [
                    {"slot": 1, "status": "ожидание"},
                    {"slot": 2, "status": "ожидание"},
                    {"slot": 3, "status": "ожидание"}
                ],
                "captcha": {"detected": False}
            })
        
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
        
        try:
            response = requests.post(DEEPSEEK_API_URL, headers=headers, json=payload, timeout=30)
            
            # Проверяем статус ответа
            if response.status_code != 200:
                print(f"DeepSeek вернул ошибку: {response.status_code} - {response.text}")
                return jsonify({
                    "rods": [
                        {"slot": 1, "status": "ожидание"},
                        {"slot": 2, "status": "ожидание"},
                        {"slot": 3, "status": "ожидание"}
                    ],
                    "captcha": {"detected": False}
                })
            
            result = response.json()
            
            # Проверяем, есть ли поле choices
            if 'choices' not in result:
                print(f"Ошибка: в ответе нет поля 'choices'. Ответ: {result}")
                return jsonify({
                    "rods": [
                        {"slot": 1, "status": "ожидание"},
                        {"slot": 2, "status": "ожидание"},
                        {"slot": 3, "status": "ожидание"}
                    ],
                    "captcha": {"detected": False}
                })
            
            # Извлекаем ответ DeepSeek
            ai_response = result['choices'][0]['message']['content']
            print(f"DeepSeek ответил: {ai_response[:200]}...")
            
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
                # Возвращаем заглушку
                return jsonify({
                    "rods": [
                        {"slot": 1, "status": "ожидание"},
                        {"slot": 2, "status": "ожидание"},
                        {"slot": 3, "status": "ожидание"}
                    ],
                    "captcha": {"detected": False}
                })
                
        except requests.exceptions.Timeout:
            print("Таймаут при запросе к DeepSeek")
            return jsonify({
                "rods": [
                    {"slot": 1, "status": "ожидание"},
                    {"slot": 2, "status": "ожидание"},
                    {"slot": 3, "status": "ожидание"}
                ],
                "captcha": {"detected": False}
            })
            
        except Exception as e:
            print(f"Ошибка при запросе к DeepSeek: {e}")
            return jsonify({
                "rods": [
                    {"slot": 1, "status": "ожидание"},
                    {"slot": 2, "status": "ожидание"},
                    {"slot": 3, "status": "ожидание"}
                ],
                "captcha": {"detected": False}
            })
        
    except Exception as e:
        print(f"Общая ошибка: {str(e)}")
        return jsonify({
            "rods": [
                {"slot": 1, "status": "ожидание"},
                {"slot": 2, "status": "ожидание"},
                {"slot": 3, "status": "ожидание"}
            ],
            "captcha": {"detected": False}
        }), 200  # Возвращаем 200 с заглушкой, чтобы клиент не падал

@app.route('/')
def home():
    return "Fishing Bot Server is running! Используй /analyze для отправки скриншотов"

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
