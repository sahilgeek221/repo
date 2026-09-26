import os
import re
import time
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
   
   CRITICAL RULES FOR COMMANDS:
   - For missing packages/ports: Provide standard terminal fixes (pip, kill, etc).
   - For source code syntax errors: Do NOT suggest opening notepad, nano, or vim. You must provide a command that completely overwrites the buggy file with the corrected code.
   - Example for Windows/Linux: echo '#include <stdio.h>...' > filename.c
"""	

@app.route('/api/diagnose', methods=['POST', 'GET'])
def diagnose():
    if request.method == 'GET':
        return jsonify({"status": "API is running."}), 200

    try:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            return jsonify({"error": "Missing GEMINI_API_KEY"}), 500
            
        client = genai.Client(api_key=api_key)
        data = request.get_json(silent=True) or {}
        
        prompt = f"Environment Context:\n{data.get('context', '')}\n\nError Output:\n{data.get('error', '')}"
        
        # --- NEW RETRY LOGIC ---
        MAX_RETRIES = 3
        response = None
        
        for attempt in range(MAX_RETRIES):
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
                break  # If successful, break out of the loop
            except Exception as e:
                if "503" in str(e) and attempt < MAX_RETRIES - 1:
                    time.sleep(1.5 ** attempt) # Sleep 1s, then 1.5s
                    continue
                else:
                    raise e # If it's not a 503 or we are out of retries, crash normally

        # -----------------------
        
        raw_text = response.text.strip()
        match = re.search(r'<EXEC>(.*?)</EXEC>', raw_text, re.DOTALL)
        
        return jsonify({
            "explanation": re.sub(r'<EXEC>.*?</EXEC>', '', raw_text, flags=re.DOTALL).strip(),
            "command": match.group(1).strip() if match else None
        })
        
    except Exception as e:
        return jsonify({"error": f"Server Error: {str(e)}"}), 500
