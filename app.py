from flask import Flask, request, jsonify
import os

app = Flask(__name__)


@app.route('/analyze', methods=['POST'])
def analyze():
    # Получаем координаты от вашего клиента
    fishing_x = request.form.get('fishing_button_x', '0')
    fishing_y = request.form.get('fishing_button_y', '0')

    # Пока просто возвращаем команду кликнуть
    return jsonify({
        "action": "click",
        "x": int(fishing_x),
        "y": int(fishing_y)
    })


@app.route('/')
def home():
    return "Сервер работает!"


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)