import os
import re
from flask import Flask, request, jsonify
from google import genai
from google.genai import types

app = Flask(__name__)
client = genai.Client() # Vercel will inject your GEMINI_API_KEY environment variable here

SYSTEM_PROMPT = """
You are an expert system administrator debugging terminal errors.
Analyze the provided error log and the user's OS/Environment context.
Respond strictly in two parts:
1. A concise, 1-2 sentence explanation. Wrap the core root cause in <HL> tags.
2. If a terminal command can fix it, provide the exact command wrapped in <EXEC> tags native to the user's OS.
"""

@app.route('/api/diagnose', methods=['POST'])
def diagnose():
    data = request.get_json()
    os_context = data.get('context', '')
    error_text = data.get('error', '')
    
    prompt = f"Environment Context:\n{os_context}\n\nError Output:\n{error_text}"
    
    try:
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
        
        # We parse the regex on the server so the CLI receives perfectly clean data
        match = re.search(r'<EXEC>(.*?)</EXEC>', raw_text, re.DOTALL)
        extracted_cmd = match.group(1).strip() if match else None
        clean_explanation = re.sub(r'<EXEC>.*?</EXEC>', '', raw_text, flags=re.DOTALL).strip()
        
        return jsonify({
            "explanation": clean_explanation,
            "command": extracted_cmd
        })
    except Exception as e:
        return jsonify({"error": f"Server Error: {str(e)}"}), 500