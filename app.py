from flask import Flask, request, jsonify
import requests
import os

app = Flask(__name__)

GEMINI_API_KEY = 'YOUR_NEW_GEMINI_KEY_HERE'  # paste here, never commit to git

@app.route('/validate', methods=['POST'])
def validate():
    idea = request.json.get('idea')
    if not idea:
        return jsonify({'error': 'No idea provided'}), 400
    
    try:
        response = requests.post(
            'https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key=' + GEMINI_API_KEY,
            headers={'Content-Type': 'application/json'},
            json={
                'contents': [{
                    'parts': [{
                        'text': f'Score this business idea viability from 1-10 (10=highly viable). Give brief reason. Idea: {idea}'
                    }]
                }]
            }
        )
        response.raise_for_status()
        data = response.json()
        text = data['candidates'][0]['content']['parts'][0]['text']
        return jsonify({'result': text})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(port=5000, debug=True)