import os
import requests
from flask import Flask, request, jsonify, session
from flask_sqlalchemy import SQLAlchemy
from pypdf import PdfReader
from groq import Groq

app = Flask(__name__)
app.secret_key = "super-secret-session-key"

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

MASTER_CODE = "adc_se/4219@!2013/2011/2017/1980/1979=*/-+54564651200.0025w7612t !@#$%^&*()98&^%$#@RTgfde$%TGi eruw we 7498517y &*#&(*(*)"

# Αρχικοποίηση του Groq Client με το κλειδί σου
client = Groq(api_key="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")

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    status = db.Column(db.String(50), default='free') 

class ChatHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user_message = db.Column(db.Text, nullable=False)
    ai_response = db.Column(db.Text, nullable=False)

with app.app_context():
    db.create_all()

def call_groq_llama3(system_prompt, user_msg):
    try:
        completion = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_msg}
            ]
        )
        return completion.choices[0].message.content
    except Exception as e:
        return f"Σφάλμα επικοινωνίας με το Groq: {str(e)}"

@app.route('/')
def home():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    html_path = os.path.join(base_dir, "index.html")
    with open(html_path, "r", encoding="utf-8") as f:
        return f.read()

@app.route('/login', methods=['POST'])
def login():
    data = request.json
    email = data.get("email")
    if not email: return jsonify({"error": "Missing email"}), 400
    user = User.query.filter_by(email=email).first()
    if not user:
        user = User(email=email, status='free')
        db.session.add(user)
        db.session.commit()
    session['user_id'] = user.id
    return jsonify({"message": "Success", "status": user.status})

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'user_id' not in session: return jsonify({"error": "Unauthorized"}), 401
    if 'file' not in request.files: return jsonify({"error": "No file"}), 400
    file = request.files['file']
    if file.filename == '': return jsonify({"error": "Empty filename"}), 400
    file_content = ""
    if file.filename.endswith('.txt'): file_content = file.read().decode('utf-8')
    elif file.filename.endswith('.pdf'):
        reader = PdfReader(file)
        for page in reader.pages: file_content += page.extract_text() + "\n"
    else: return jsonify({"error": "Invalid format"}), 400
    ai_reply = call_groq_llama3("Είσαι το MAG AI. Κάνε σύνοψη στα Ελληνικά.", file_content)
    history_entry = ChatHistory(user_id=session['user_id'], user_message=f"[Αρχείο: {file.filename}]", ai_response=ai_reply)
    db.session.add(history_entry)
    db.session.commit()
    return jsonify({"response": ai_reply, "id": history_entry.id})

@app.route('/chat', methods=['POST'])
def chat():
    if 'user_id' not in session: return jsonify({"error": "Unauthorized"}), 401
    data = request.json
    user_msg = data.get("message", "").strip()
    user = User.query.get(session['user_id'])
    if "ποιος ειναι ο κωδικος" in user_msg.lower() or MASTER_CODE in user_msg:
        if user_msg != MASTER_CODE: return jsonify({"response": "Δεν ξέρω."})
    if user_msg == MASTER_CODE:
        user.status = 'admin'
        db.session.commit()
        return jsonify({"response": "Ο κωδικός έγινε δεκτός!"})
    max_lines = 50 if user.status == 'free' else 70 if user.status == '5euro' else 100 if user.status == '12euro' else 5000
    ai_reply = call_groq_llama3(f"Είσαι το MAG AI. Απάντησε στα Ελληνικά έως {max_lines} σειρές.", user_msg)
    history_entry = ChatHistory(user_id=user.id, user_message=user_msg, ai_response=ai_reply)
    db.session.add(history_entry)
    db.session.commit()
    return jsonify({"response": ai_reply, "id": history_entry.id})

@app.route('/history', methods=['GET'])
def get_history():
    if 'user_id' not in session: return jsonify({"error": "Unauthorized"}), 401
    history = ChatHistory.query.filter_by(user_id=session['user_id']).order_by(ChatHistory.id.desc()).all()
    return jsonify({"history": [{"id": h.id, "user": h.user_message, "ai": h.ai_response} for h in history]})

# Διόρθωση εκκίνησης για να ακούει στη σωστή θύρα του Render
port = int(os.environ.get("PORT", 5000))
app.run(host="0.0.0.0", port=port)
