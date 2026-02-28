import os
import re
import base64
import json
from flask import Flask, request, jsonify
from PIL import Image, ImageEnhance, ImageOps
import io
import pytesseract

app = Flask(__name__)

# Путь к Tesseract в контейнере
pytesseract.pytesseract.tesseract_cmd = '/usr/bin/tesseract'

def preprocess_image(image_bytes):
    """Улучшение качества изображения для Tesseract"""
    try:
        # Открываем изображение
        img = Image.open(io.BytesIO(image_bytes))
        
        # Увеличиваем размер в 3 раза
        width, height = img.size
        img = img.resize((width * 3, height * 3), Image.Resampling.LANCZOS)
        
        # Увеличиваем контраст
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(3.0)
        
        # Увеличиваем резкость
        enhancer = ImageEnhance.Sharpness(img)
        img = enhancer.enhance(3.0)
        
        # Конвертируем в черно-белое
        img = img.convert('L')
        
        # Инвертируем если нужно (черные цифры на белом фоне)
        # img = ImageOps.invert(img)
        
        return img
    except Exception as e:
        print(f"Ошибка обработки: {e}")
        return None

@app.route('/analyze', methods=['POST'])
def analyze_screenshot():
    try:
        image_file = request.files.get('screenshot')
        if not image_file:
            return jsonify({"error": "No screenshot provided"}), 400
            
        action_needed = request.form.get('action_needed', 'check_rods')
        image_bytes = image_file.read()
        
        print(f"Получен запрос: {action_needed}")
        
        if action_needed == "check_captcha_only":
            # Обрабатываем изображение
            img = preprocess_image(image_bytes)
            
            if img:
                # Настройки Tesseract: только цифры
                custom_config = r'--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789'
                
                # Распознаем
                text = pytesseract.image_to_string(img, config=custom_config)
                print(f"Tesseract raw: '{text}'")
                
                # Извлекаем только цифры
                digits = re.sub(r'[^0-9]', '', text)
                print(f"Цифры: '{digits}'")
                
                if digits and len(digits) > 0:
                    return jsonify({
                        "success": True,
                        "text": digits
                    })
                else:
                    # Пробуем другой метод - ищем текст "Captcha:"
                    text_config = r'--oem 3 --psm 6'
                    full_text = pytesseract.image_to_string(img, config=text_config)
                    print(f"Полный текст: '{full_text}'")
                    
                    match = re.search(r'Captcha:\s*(\d+)', full_text, re.IGNORECASE)
                    if match:
                        digits = match.group(1)
                        return jsonify({
                            "success": True,
                            "text": digits
                        })
            
            return jsonify({"success": False, "text": ""})
            
        else:
            # Для удочек возвращаем заглушку
            return jsonify({
                "rods": [
                    {"slot": 1, "status": "ожидание"},
                    {"slot": 2, "status": "ожидание"},
                    {"slot": 3, "status": "ожидание"}
                ]
            })
        
    except Exception as e:
        print(f"Ошибка: {str(e)}")
        return jsonify({"success": False, "text": ""})

@app.route('/')
def home():
    return "Fishing Bot Server with Tesseract is running!"

@app.route('/ping', methods=['GET'])
def ping():
    return jsonify({"status": "ok"})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
