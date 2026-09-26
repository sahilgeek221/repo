import os
import re
from flask import Flask, request, jsonify
from google import genai
from google.genai import types

app = Flask(__name__)

SYSTEM_PROMPT = """
You are an expert system administrator debugging terminal errors.
Analyze the provided error log and the user's OS/Environment context.
Respond strictly in two parts:
1. A concise, 1-2 sentence explanation. Wrap the core root cause in <HL> tags.
2. If a terminal command can fix it, provide the exact command wrapped in <EXEC> tags native to the user's OS.
"""

# Added GET method so you can test if the server is alive from your browser
@app.route('/api/diagnose', methods=['POST', 'GET'])
def diagnose():
    if request.method == 'GET':
        return jsonify({"status": "API is running. Send POST requests to use the engine."}), 200

    try:
        # 1. Safe Key Check
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            return jsonify({"error": "Server Error: GEMINI_API_KEY is missing in Vercel settings."}), 500
            
        client = genai.Client(api_key=api_key)
        
        # 2. Safe JSON Parsing
        data = request.get_json(silent=True) or {}
        os_context = data.get('context', 'Unknown OS')
        error_text = data.get('error', 'No error provided')
        
        prompt = f"Environment Context:\n{os_context}\n\nError Output:\n{error_text}"
        
        # 3. API Call
        response = client.models.generate_content(
            model='gemini-3.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                temperature=0.2,
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True)
            )
        )
        
        raw_text = response.text.strip()
        
        # 4. Regex Parsing
        match = re.search(r'<EXEC>(.*?)</EXEC>', raw_text, re.DOTALL)
        extracted_cmd = match.group(1).strip() if match else None
        clean_explanation = re.sub(r'<EXEC>.*?</EXEC>', '', raw_text, flags=re.DOTALL).strip()
        
        return jsonify({
            "explanation": clean_explanation,
            "command": extracted_cmd
        })
        
    except Exception as e:
        # If anything breaks, return the exact Python error string to the terminal
        return jsonify({"error": f"Python Exception: {str(e)}"}), 500
