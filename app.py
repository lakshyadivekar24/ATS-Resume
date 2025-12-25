import os
import json
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
from google import genai
import PyPDF2
import docx

# 1. SETUP
load_dotenv()
client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))

app = Flask(__name__)

# Upload Folder Configuration
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# --- HELPER FUNCTIONS ---
def extract_text_from_pdf(file_path):
    text = ""
    try:
        with open(file_path, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                text += page.extract_text()
    except Exception as e:
        print(f"Error PDF: {e}")
    return text

def extract_text_from_docx(file_path):
    try:
        doc = docx.Document(file_path)
        return '\n'.join([para.text for para in doc.paragraphs])
    except Exception as e:
        print(f"Error DOCX: {e}")
        return ""

# --- AI LOGIC ---
def analyze_resume_with_ai(resume_text, jd_text):
    prompt = f"""
    Act as a Senior Technical Recruiter. Evaluate this Resume against the JD.
    
    Resume: {resume_text}
    JD: {jd_text}
    
    Output strictly JSON with these keys:
    1. "match_percentage": (integer 0-100)
    2. "missing_keywords": (list of top 5 critical missing skills)
    3. "matching_keywords": (list of top 5 skills the candidate HAS that match the JD)
    4. "profile_summary": (2 line sharp critique)
    5. "improvement_tips": (List of 3 specific, actionable tips to increase score)
    6. "interview_questions": (List of 3 technical conceptual questions based on gaps)
    """
    
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config={'response_mime_type': 'application/json'}
        )
        return json.loads(response.text)
    except Exception as e:
        return {"error": str(e)}

def evaluate_interview_answer(question, answer):
    prompt = f"""
    You are a Technical Interviewer.
    Question: "{question}"
    Candidate Answer: "{answer}"
    
    Rate and Feedback strictly in JSON:
    {{
        "rating": (integer 1-10),
        "feedback": (1 sentence constructive feedback),
        "better_answer": (A short, ideal answer example)
    }}
    """
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config={'response_mime_type': 'application/json'}
        )
        return json.loads(response.text)
    except Exception as e:
        return {"error": str(e)}

# --- ROUTES ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/analyze', methods=['POST'])
def analyze():
    resume_path = None
    jd_path = None

    try:
        # 1. Handle Resume
        if 'resume' not in request.files: return jsonify({"error": "Resume missing"})
        resume_file = request.files['resume']
        
        # Save Temporarily
        resume_path = os.path.join(app.config['UPLOAD_FOLDER'], resume_file.filename)
        resume_file.save(resume_path)
        
        resume_text = ""
        if resume_path.endswith('.pdf'): resume_text = extract_text_from_pdf(resume_path)
        elif resume_path.endswith('.docx'): resume_text = extract_text_from_docx(resume_path)
        
        # 2. Handle JD (Text OR File)
        jd_text = request.form.get('jd_text', '')
        
        if 'jd_file' in request.files and request.files['jd_file'].filename != '':
            jd_file = request.files['jd_file']
            # Save JD File Temporarily
            jd_path = os.path.join(app.config['UPLOAD_FOLDER'], jd_file.filename)
            jd_file.save(jd_path)
            
            if jd_path.endswith('.pdf'): jd_text = extract_text_from_pdf(jd_path)
            elif jd_path.endswith('.docx'): jd_text = extract_text_from_docx(jd_path)
        
        if not resume_text or not jd_text: return jsonify({"error": "Data missing (Resume or JD)"})

        # 3. Call AI
        result = analyze_resume_with_ai(resume_text, jd_text)
        
        return jsonify(result)

    except Exception as e:
        return jsonify({"error": str(e)})

    finally:
        # --- CLEANUP (AUTO DELETE) ---
        # Yeh code analysis ke baad chalega aur files delete kar dega
        if resume_path and os.path.exists(resume_path):
            os.remove(resume_path)
            print(f"Deleted: {resume_path}")
            
        if jd_path and os.path.exists(jd_path):
            os.remove(jd_path)
            print(f"Deleted: {jd_path}")

@app.route('/evaluate_answer', methods=['POST'])
def evaluate():
    data = request.json
    return jsonify(evaluate_interview_answer(data.get('question'), data.get('user_answer')))

if __name__ == '__main__':
    app.run(debug=True)