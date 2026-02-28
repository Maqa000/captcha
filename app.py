import os
import re
import base64
import json
from flask import Flask, request, jsonify
from PIL import Image, ImageEnhance, ImageOps
import io
import pytesseract
import cv2
import numpy as np

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
        
        # Конвертируем в numpy array для OpenCV
        img_np = np.array(img)
        
        # Конвертируем в оттенки серого
        if len(img_np.shape) == 3:
            gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
        else:
            gray = img_np
        
        # Применяем адаптивную пороговую обработку
        binary = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                      cv2.THRESH_BINARY, 11, 2)
        
        # Убираем шум
        denoised = cv2.medianBlur(binary, 3)
        
        # Конвертируем обратно в PIL
        result = Image.fromarray(denoised)
        
        return result
    except Exception as e:
        print(f"Ошибка обработки: {e}")
        return None

def extract_digits_with_tesseract(img):
    """Извлекает цифры с помощью Tesseract"""
    try:
        # Настройки Tesseract: только цифры
        custom_config = r'--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789'
        
        # Пробуем распознать
        text = pytesseract.image_to_string(img, config=custom_config)
        print(f"Tesseract raw: '{text}'")
        
        # Извлекаем только цифры
        digits = re.sub(r'[^0-9]', '', text)
        print(f"Извлечено цифр: '{digits}'")
        
        return digits
    except Exception as e:
        print(f"Ошибка Tesseract: {e}")
        return ""

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
        
        if action_needed == "check_captcha_only":
            # Обрабатываем изображение для Tesseract
            img = preprocess_image(image_bytes)
            
            if img:
                # Распознаем цифры
                digits = extract_digits_with_tesseract(img)
                
                if digits and len(digits) > 0:
                    return jsonify({
                        "success": True,
                        "text": digits
                    })
                else:
                    # Пробуем другой метод - ищем текст "Captcha:" и цифры после него
                    # Настройки для распознавания всего текста
                    text_config = r'--oem 3 --psm 6'
                    full_text = pytesseract.image_to_string(img, config=text_config)
                    print(f"Полный текст: '{full_text}'")
                    
                    # Ищем цифры после "Captcha:"
                    match = re.search(r'Captcha:\s*(\d+)', full_text, re.IGNORECASE)
                    if match:
                        digits = match.group(1)
                        print(f"Найдено через regex: '{digits}'")
                        return jsonify({
                            "success": True,
                            "text": digits
                        })
            
            return jsonify({"success": False, "text": ""})
            
        else:
            # Для удочек возвращаем заглушку (или можно тоже использовать Tesseract)
            return jsonify({
                "rods": [
                    {"slot": 1, "status": "ожидание"},
                    {"slot": 2, "status": "ожидание"},
                    {"slot": 3, "status": "ожидание"}
                ]
            })
        
    except Exception as e:
        print(f"Общая ошибка: {str(e)}")
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
