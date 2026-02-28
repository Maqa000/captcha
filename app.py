import os
import json
import base64
import re
from flask import Flask, request, jsonify
import requests
from PIL import Image, ImageEnhance
import io

app = Flask(__name__)

# Конфигурация DeepSeek
DEEPSEEK_API_KEY = os.environ.get('DEEPSEEK_API_KEY', '')
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"

def preprocess_image(image_bytes):
    """Улучшение качества изображения"""
    try:
        img = Image.open(io.BytesIO(image_bytes))
        
        # Увеличиваем размер для лучшего распознавания
        width, height = img.size
        img = img.resize((width * 3, height * 3), Image.Resampling.LANCZOS)
        
        # Увеличиваем контраст
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(4.0)
        
        # Увеличиваем резкость
        enhancer = ImageEnhance.Sharpness(img)
        img = enhancer.enhance(4.0)
        
        # Конвертируем в черно-белое
        img = img.convert('L')
        
        # Инвертируем если нужно (черные цифры на белом фоне)
        # img = ImageOps.invert(img)
        
        output = io.BytesIO()
        img.save(output, format='PNG')
        return output.getvalue()
    except Exception as e:
        print(f"Ошибка обработки: {e}")
        return image_bytes

@app.route('/analyze', methods=['POST'])
def analyze_screenshot():
    try:
        image_file = request.files.get('screenshot')
        if not image_file:
            return jsonify({"error": "No screenshot provided"}), 400
            
        action_needed = request.form.get('action_needed', 'check_rods')
        image_bytes = image_file.read()
        
        print(f"Получен запрос: {action_needed}")
        print(f"Размер изображения: {len(image_bytes)} байт")
        
        if not DEEPSEEK_API_KEY:
            print("ОШИБКА: Не задан DEEPSEEK_API_KEY")
            if action_needed == "check_captcha_only":
                return jsonify({"success": False, "text": ""})
            else:
                return jsonify({
                    "rods": [
                        {"slot": 1, "status": "ожидание"},
                        {"slot": 2, "status": "ожидание"},
                        {"slot": 3, "status": "ожидание"}
                    ]
                })
        
        if action_needed == "check_captcha_only":
            # Обрабатываем изображение
            processed_bytes = preprocess_image(image_bytes)
            
            # Конвертируем в base64
            base64_image = base64.b64encode(processed_bytes).decode('utf-8')
            data_url = f"data:image/png;base64,{base64_image}"
            
            # Формируем сообщение с изображением как часть текста
            prompt = f"""Посмотри на это изображение. На нём есть текст "Captcha:" и после него цифры.
Изображение: {data_url}

Напиши ТОЛЬКО эти цифры, ничего больше.
Например, если видишь "Captcha: 1702", напиши "1702" """
            
            payload = {
                "model": "deepseek-chat",
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "temperature": 0.0,
                "max_tokens": 10
            }
            
            try:
                headers = {
                    "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                    "Content-Type": "application/json"
                }
                
                print("Отправляю запрос к DeepSeek...")
                print(f"Промпт длина: {len(prompt)} символов")
                
                response = requests.post(DEEPSEEK_API_URL, headers=headers, json=payload, timeout=30)
                
                print(f"Статус ответа DeepSeek: {response.status_code}")
                
                if response.status_code == 200:
                    result = response.json()
                    print(f"Ответ DeepSeek: {json.dumps(result, indent=2)}")
                    
                    if 'choices' in result and len(result['choices']) > 0:
                        ai_response = result['choices'][0]['message']['content'].strip()
                        print(f"Текст ответа: '{ai_response}'")
                        
                        # Извлекаем цифры
                        digits = re.sub(r'[^0-9]', '', ai_response)
                        print(f"Цифры: '{digits}'")
                        
                        if digits and len(digits) > 0:
                            return jsonify({
                                "success": True,
                                "text": digits
                            })
                        else:
                            return jsonify({"success": False, "text": ""})
                    else:
                        print("Нет поля choices")
                        return jsonify({"success": False, "text": ""})
                else:
                    print(f"Ошибка DeepSeek: {response.status_code}")
                    print(f"Текст ошибки: {response.text}")
                    return jsonify({"success": False, "text": ""})
                    
            except Exception as e:
                print(f"Ошибка при запросе: {e}")
                return jsonify({"success": False, "text": ""})
                
        else:
            # Обычный режим для удочек
            base64_image = base64.b64encode(image_bytes).decode('utf-8')
            data_url = f"data:image/png;base64,{base64_image}"
            
            prompt = f"""Ты помощник для игры в рыбалку. На скриншоте видно 3 удочки.
Изображение: {data_url}

Найди каждую удочку и определи, что написано над ней.

Варианты надписей:
- "Готово"
- "Ожидание"
- "CATCH REQUIRED"
- "Ловля..."

Ответь строго в формате JSON:
{{
    "rods": [
        {{"slot": 1, "status": "готово"}},
        {{"slot": 2, "status": "ожидание"}},
        {{"slot": 3, "status": "ловля"}}
    ]
}}"""
            
            payload = {
                "model": "deepseek-chat",
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
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
                        
                        try:
                            json_match = re.search(r'\{.*\}', ai_response, re.DOTALL)
                            if json_match:
                                action_data = json.loads(json_match.group())
                            else:
                                action_data = json.loads(ai_response)
                            
                            if 'rods' in action_data:
                                for rod in action_data['rods']:
                                    status = rod.get('status', '').lower()
                                    if 'готов' in status:
                                        rod['status'] = 'готово'
                                    elif 'ожидан' in status:
                                        rod['status'] = 'ожидание'
                                    elif 'catch' in status:
                                        rod['status'] = 'catch'
                                    elif 'ловл' in status:
                                        rod['status'] = 'ловля'
                                    else:
                                        rod['status'] = 'ожидание'
                            
                            return jsonify(action_data)
                            
                        except Exception as e:
                            print(f"Ошибка парсинга JSON: {e}")
                
                return jsonify({
                    "rods": [
                        {"slot": 1, "status": "ожидание"},
                        {"slot": 2, "status": "ожидание"},
                        {"slot": 3, "status": "ожидание"}
                    ]
                })
                    
            except Exception as e:
                print(f"Ошибка при запросе: {e}")
                return jsonify({
                    "rods": [
                        {"slot": 1, "status": "ожидание"},
                        {"slot": 2, "status": "ожидание"},
                        {"slot": 3, "status": "ожидание"}
                    ]
                })
        
    except Exception as e:
        print(f"Общая ошибка: {str(e)}")
        if action_needed == "check_captcha_only":
            return jsonify({"success": False, "text": ""})
        else:
            return jsonify({
                "rods": [
                    {"slot": 1, "status": "ожидание"},
                    {"slot": 2, "status": "ожидание"},
                    {"slot": 3, "status": "ожидание"}
                ]
            })

@app.route('/')
def home():
    return "Fishing Bot Server is running!"

@app.route('/ping', methods=['GET'])
def ping():
    return jsonify({"status": "ok"})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
