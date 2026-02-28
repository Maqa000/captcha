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
        image_file = request.files.get('screenshot')
        if not image_file:
            return jsonify({"error": "No screenshot provided"}), 400
            
        action_needed = request.form.get('action_needed', 'check_rods')
        
        # Конвертируем изображение в base64 для DeepSeek
        image_bytes = image_file.read()
        image_base64 = base64.b64encode(image_bytes).decode('utf-8')
        
        # Проверяем, есть ли API ключ
        if not DEEPSEEK_API_KEY:
            print("ОШИБКА: Не задан DEEPSEEK_API_KEY")
            # Возвращаем заглушку для обычного режима
            if action_needed == "check_captcha_only":
                return jsonify({"success": False, "text": ""})
            else:
                return jsonify({
                    "rods": [
                        {"slot": 1, "status": "ожидание"},
                        {"slot": 2, "status": "ожидание"},
                        {"slot": 3, "status": "ожидание"}
                    ],
                    "captcha": {"detected": False}
                })
        
        # Разные промпты в зависимости от типа запроса
        if action_needed == "check_captcha_only":
            # Специальный режим: ищем ТОЛЬКО цифры капчи
            prompt = """На этом изображении только цифры капчи. Напиши ТОЛЬКО цифры, которые видишь.
Если цифр нет, напиши "NO_DIGITS". Ответь только цифрами или NO_DIGITS."""
            
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
                "max_tokens": 50
            }
            
            try:
                headers = {
                    "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                    "Content-Type": "application/json"
                }
                
                response = requests.post(DEEPSEEK_API_URL, headers=headers, json=payload, timeout=30)
                
                if response.status_code == 200:
                    result = response.json()
                    if 'choices' in result and len(result['choices']) > 0:
                        ai_response = result['choices'][0]['message']['content'].strip()
                        print(f"DeepSeek ответил (только цифры): {ai_response}")
                        
                        # Извлекаем только цифры из ответа
                        digits = re.sub(r'[^0-9]', '', ai_response)
                        
                        if digits and len(digits) > 0:
                            return jsonify({
                                "success": True,
                                "text": digits
                            })
                    
                    return jsonify({"success": False, "text": ""})
                else:
                    print(f"Ошибка DeepSeek: {response.status_code}")
                    return jsonify({"success": False, "text": ""})
                    
            except Exception as e:
                print(f"Ошибка при запросе к DeepSeek: {e}")
                return jsonify({"success": False, "text": ""})
                
        else:
            # Обычный режим: анализируем всю сцену с удочками
            prompt = """Ты помощник для игры в рыбалку. На скриншоте видно 3 удочки.
Найди каждую удочку и определи, что написано над ней.

Варианты надписей:
- "Готово" (зеленый текст)
- "Ожидание" (серый текст)
- "CATCH REQUIRED" (синий текст)
- "Ловля..." (серый текст)

Также определи, есть ли на экране окно с капчей (обычно белое окно с надписью "Are you bot?").

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
}

Важно: верни ТОЛЬКО JSON, без пояснений."""
            
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
            
            try:
                headers = {
                    "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                    "Content-Type": "application/json"
                }
                
                response = requests.post(DEEPSEEK_API_URL, headers=headers, json=payload, timeout=30)
                
                if response.status_code == 200:
                    result = response.json()
                    if 'choices' in result and len(result['choices']) > 0:
                        ai_response = result['choices'][0]['message']['content']
                        print(f"DeepSeek ответил: {ai_response[:200]}...")
                        
                        # Парсим JSON из ответа
                        try:
                            json_match = re.search(r'\{.*\}', ai_response, re.DOTALL)
                            if json_match:
                                action_data = json.loads(json_match.group())
                            else:
                                action_data = json.loads(ai_response)
                            
                            # Проверяем и исправляем статусы
                            if 'rods' in action_data:
                                for rod in action_data['rods']:
                                    status = rod.get('status', '').lower()
                                    if 'готов' in status:
                                        rod['status'] = 'готово'
                                    elif 'ожидан' in status:
                                        rod['status'] = 'ожидание'
                                    elif 'catch' in status or 'requir' in status:
                                        rod['status'] = 'catch'
                                    elif 'ловл' in status:
                                        rod['status'] = 'ловля'
                                    else:
                                        rod['status'] = 'ожидание'
                            
                            return jsonify(action_data)
                            
                        except Exception as e:
                            print(f"Ошибка парсинга JSON: {e}")
                
                # Возвращаем заглушку в случае ошибки
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
        })

@app.route('/')
def home():
    return "Fishing Bot Server is running! Используй /analyze для отправки скриншотов"

@app.route('/ping', methods=['GET'])
def ping():
    return jsonify({"status": "ok"})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
