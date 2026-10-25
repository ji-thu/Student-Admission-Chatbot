import json
import os
from flask import Flask, request, jsonify, render_template, session, redirect, url_for
from flask_cors import CORS
import requests
from pymongo import MongoClient
from functools import wraps
from flask import Flask, request, jsonify
from pymongo import MongoClient
from groq import Groq
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from dotenv import load_dotenv

# Google Login
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests

load_dotenv()

# --- Admin Credentials (Fixed) ---
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"

groq_client = Groq(
    api_key=os.getenv("GROQ_API_KEY")
)

MONGO_URI = os.getenv("MONGODB_URI")

client = MongoClient(MONGO_URI)
db = client["StudentChatbot"]

collection = db["intents"]
chat_collection = db["chat_history"]
log_collection = db["user_logs"]


COURSES = [
    "mca",
    "mba",
    "bca",
    "btech",
    "computer science engineering",
    "data science",
    "ai and ml",
    "civil engineering",
    "mechanical engineering",
    "electrical and electronics engineering",
    "electronics and communication engineering"
]

COURSE_KEYWORDS = {
    "mca": [
        "mca",
        "master of computer applications",
        "computer applications"
    ],

    "bca": [
        "bca",
        "bachelor of computer applications"
    ],

    "btech": [
        "btech",
        "b tech",
        "engineering",
        "bachelor of technology"
    ],

    "mba": [
        "mba",
        "master of business administration",
        "business",
        "management"
    ],

    "computer science engineering": [
        "cse",
        "computer science",
        "computer science engineering"
    ],

    "data science": [
        "data science",
        "datascience"
    ],

    "ai and ml": [
        "ai",
        "artificial intelligence",
        "machine learning",
        "ai ml",
        "ai and ml"
    ],

    "civil engineering": [
        "civil",
        "civil engineering"
    ],

    "mechanical engineering": [
        "mechanical",
        "mechanical engineering"
    ],

    "electrical and electronics engineering": [
        "eee",
        "electrical",
        "electrical engineering",
        "electrical and electronics"
    ],

    "electronics and communication engineering": [
        "ece",
        "electronics",
        "communication engineering",
        "electronics and communication"
    ]
}



def analyze_user_interest(user_id, login_time):
    login_time = datetime.strptime(login_time, "%Y-%m-%d %H:%M:%S")

    chats = chat_collection.find({
        "user_id": user_id,
        "time": {"$gte": login_time}   
    })

    full_text = " ".join([c["message"].lower() for c in chats])

    found_courses = []

    for course in COURSES:
        if course in full_text:
            found_courses.append(course)

    return found_courses if found_courses else ["general"]
    



def send_email(to_email, courses):
    course_names = ", ".join([c.upper() for c in courses])
    sender_email = "chatb844@gmail.com"
    sender_password = "zfdg pasy bsoj hhlw"

    if "general" in courses:
        subject = "MBITS Admission Details"
        body = f"""
Hello,

Thank you for interacting with the MBITS Admission Assistant.

We are excited to help you explore the wide range of academic opportunities available at MBITS. Whether you are still deciding your career path or looking for the right program, we are here to guide you.

🎓 ABOUT MBITS:
MBITS offers a variety of undergraduate and postgraduate programs designed to build strong academic foundations and practical skills. Our institution focuses on innovation, industry readiness, and overall student development.

📚 COURSES WE OFFER:
• B.Tech Programs (Various Specializations)
• MCA (Master of Computer Applications)
• BCA (Bachlor of Computer Applications)
• MBA (Master of Business Administration)
• Engineering Streams (Civil, Mechanical, Electrical, Electronics, Computer Science)

📌 ADMISSION PROCESS:
1. Visit the official website
2. Complete the online registration
3. Submit required documents
4. Participate in counseling/selection process
5. Confirm your admission

🏫 WHY CHOOSE MBITS?
• Highly qualified and supportive faculty
• Modern labs and campus infrastructure
• Strong placement assistance
• Industry-oriented curriculum
• Safe and student-friendly environment

📞 CONTACT US:
Phone: 0485 - 2837801  
Email: admissions@mbits.ac.in 
info@mbits.ac.in 

🌐 WEBSITE:
https://mbits.ac.in

We would be happy to assist you in choosing the right course and shaping your future.

Best Regards,  
MBITS Admission Team
"""
    else:
        subject = f"✨ You’re Interested in {course_names} – Let’s Get Started!"

        course_list = "\n".join([f"• {c.upper()}" for c in courses])

        body = f"""
Hello,

Thank you for interacting with the MBITS Admission Assistant.

We noticed that you have shown interest in the following course(s):

{course_list}

🎓 ABOUT THESE COURSES:
These programs are designed to provide strong academic knowledge along with practical skills required in today’s industry. Our curriculum is regularly updated to match current trends and technologies.

 ADMISSION PROCESS:
1. Register through the official website
2. Fill out the application form
3. Upload required documents
4. Attend counseling / selection process
5. Confirm admission

 WHY CHOOSE MBITS?
• Experienced faculty and industry-oriented teaching
• Modern infrastructure and labs
• Placement assistance and career support
• Friendly campus environment
• Focus on practical learning and innovation

📞 CONTACT US:
Phone: 0485 - 2837801   
Email: admissions@mbits.ac.in  
info@mbits.ac.in

🌐 WEBSITE:
https://mbits.ac.in

We are here to guide you at every step of your academic journey.

Best Regards,  
MBITS Admission Team
"""

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = sender_email
    msg["To"] = to_email

    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, to_email, msg.as_string())
        server.quit()
        print("✅ Email sent")
    except Exception as e:
        print("❌ Email error:", e)
# -----------------------------
#     RAG + MongoDB Chatbot
# -----------------------------
class RAGChatbot:
    def __init__(self, mongo_uri=None, db_name="StudentChatbot"):
        print("🤖 Initializing RAG + Generative Chatbot (MongoDB Atlas)")
        self.client = MongoClient(
            mongo_uri or os.getenv("MONGODB_URI")
        )
        self.db = self.client[db_name]
        self.collection = self.db["intents"]

        self.intents = {}
        self.intent_tools_for_prompt = []
        self.autocomplete_phrases = []
        self.reload_intents()

    # Reload data from MongoDB into memory
    def reload_intents(self):
        print("🔄 Reloading intents from MongoDB...")

        self.intents = {}
        self.intent_tools_for_prompt = []
        self.autocomplete_phrases = set()

        for doc in self.collection.find():
            key = doc.get("intent", "").lower()
            self.intents[key] = doc

            example_patterns = doc.get("patterns", [])[:2]
            if example_patterns:
                self.intent_tools_for_prompt.append(
                    f"- '{key}': Use for questions like {json.dumps(example_patterns)}"
                )

            for p in doc.get("patterns", []):
                self.autocomplete_phrases.add(p)

        self.autocomplete_phrases = sorted(list(self.autocomplete_phrases))
        print(f"✅ Loaded {len(self.intents)} intents.")

    # LLM Router to choose correct intent
    def _evaluate_intent_with_llm(self, user_input: str) -> str:
        tools_formatted = "\n".join(self.intent_tools_for_prompt)
        prompt = f"""
You are an expert at classifying a student's question into the correct category.
Available categories:
{tools_formatted}

Respond with ONLY the category name (e.g., mca, admission_process).
If no category fits, respond with 'general_fallback'.

User Question: "{user_input}"
Chosen Category:"""

        try:
            response = groq_client.chat.completions.create(
            model="openai/gpt-oss-20b",
            messages=[
                {"role": "user", "content": prompt}
            ],
            temperature=0
            )

            out = response.choices[0].message.content.strip()
            return out.lower()
        except:
            return "general_fallback"

    # Generate final answer
    def get_response(self, user_input: str):
        default_suggestions = ["Admission Process?", "Courses Offered", "Campus Facilities"]

        intent = self._evaluate_intent_with_llm(user_input)
        info = self.intents.get(intent)

        if not info or intent == "general_fallback":
            context_str = None
            suggestions = default_suggestions
        else:
            context_str = "\n".join(info.get("responses", []))
            suggestions = info.get("follow_up_suggestions", default_suggestions)

        try:
            if context_str:
                prompt = f"""
Use ONLY this information to answer:

{context_str}

Student Question: "{user_input}"
Friendly answer:"""
            else:
                prompt = f"""
You are a helpful MBITS college assistant.
Answer based on general knowledge.

Question: "{user_input}"
Answer:"""

            response = groq_client.chat.completions.create(
            model="openai/gpt-oss-20b",
            messages=[
                {"role": "user", "content": prompt}
            ]
            )

            reply = response.choices[0].message.content.strip()

            return {"reply": reply, "suggestions": suggestions}

        except Exception as e:
            print("Groq Error:", e)
            return {"reply": "Error while generating response.", "suggestions": default_suggestions}

    # Autocomplete search
    def get_autocomplete_suggestions(self, text, k=5):
        if not text:
            return []
        t = text.lower()
        return [p for p in self.autocomplete_phrases if p.lower().startswith(t)][:k]


# -----------------------------------------------------
#                  FLASK APPLICATION
# -----------------------------------------------------

app = Flask(__name__, template_folder="templates")
CORS(app)

CHAT_HISTORY_DIR = "chat_histories"
app.config["SECRET_KEY"] = "your-super-secret-key"
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")


# --------------------------
#      Chat history system
# --------------------------
def init_storage():
    if not os.path.exists(CHAT_HISTORY_DIR):
        os.makedirs(CHAT_HISTORY_DIR)
        print("📁 Chat history directory created.")

def get_file(user_id):
    return os.path.join(CHAT_HISTORY_DIR, f"{user_id}.jsonl")

def save_chat(user_id, role, msg):
    chat_collection.insert_one({
        "user_id": user_id,
        "role": role,
        "message": msg,
        "time": datetime.now()
    })


def load_chat(user_id):
    chats = chat_collection.find({"user_id": user_id}).sort("_id", 1)
    return [
        {"role": c["role"], "message": c["message"]}
        for c in chats
    ]


# ------------------------------
#   Initialize Chatbot (MongoDB)
# ------------------------------
bot = RAGChatbot()




# --------------------------
#      Authentication
# --------------------------
@app.route("/")
def login_page():
    if "user" in session:
        return redirect("/chat_page")
    return render_template("login.html")

@app.route("/login", methods=["POST"])
def login():
    data = request.json
    token = data.get("token")
    try:
        idinfo = id_token.verify_oauth2_token(
        token,
        google_requests.Request(),
        GOOGLE_CLIENT_ID
        )

        login_time = datetime.now()

        session["user"] = {
            "id": idinfo["sub"],
            "name": idinfo["name"],
            "email": idinfo["email"],
            "login_time": login_time.strftime("%Y-%m-%d %H:%M:%S")
        }

        log_collection.insert_one({
            "user_id": idinfo["sub"],
            "email": idinfo["email"],
            "name": idinfo["name"],
            "action": "login",
            "time": login_time.strftime("%Y-%m-%d %H:%M:%S")
        })

        return jsonify({"success": True})
    except:
        return jsonify({"error": "Login failed"}), 401
    


# --------------------------
#   Guest Login Route
# --------------------------
@app.route("/guest_login", methods=["POST"])
def guest_login():
    # Create guest session without saving anything
    session["guest"] = True
    return jsonify({"success": True})



@app.route("/logout")
def logout():
    if "user" in session:
        user_id = session["user"]["id"]
        email = session["user"]["email"]
        login_time = session["user"]["login_time"]

        courses = analyze_user_interest(user_id,login_time)

        send_email(email, courses)

    session.pop("user", None)
    session.pop("guest", None)

    return redirect("/")



# --------------------------
#     User Info Route
# --------------------------
@app.route("/getuserinfo")
def get_user_info():
    # If logged-in user → return full info
    if "user" in session:
        return jsonify({
            "id": session["user"]["id"],
            "name": session["user"]["name"],
            "email": session["user"]["email"],
            "guest": False
        })
    
    # If guest user → return guest info
    if "guest" in session:
        return jsonify({
            "id": "guest_user",
            "name": "Guest User",
            "email": None,
            "guest": True
        })

    # If no session → redirect
    return jsonify({"error": "Not logged in"}), 401

    


# In app.py, under the "Authentication" section:




# --------------------------
#       Admin Login
# --------------------------

@app.route('/admin')
def admin_page():
    return render_template('admin.html')

@app.route("/admin_login") # Corresponds to your admin_login.html
def admin_login_page():
    if session.get("admin_logged_in"):
        return render_template("admin_login.html") # Redirect to the main admin route if already logged in
    return render_template("admin_login.html") 

@app.route("/admin_auth", methods=["POST"])
def admin_authenticate():
    data = request.json
    username = data.get("username")
    password = data.get("password")

    if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
        session["admin_logged_in"] = True
        return jsonify({"success": True})
    else:
        return jsonify({"error": "Invalid username or password"}), 401
    

@app.route("/admin_logout")
def admin_logout():
    session.pop("admin_logged_in", None)
    return redirect("/admin_login")

# --------------------------
#        Chat Route
# --------------------------
@app.route("/chat_page")
def chat_page():
    # Allow both logged-in users and guests
    if "user" not in session and "guest" not in session:
        return redirect("/")
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    if "user" in session:
        # Logged-in user
        user_id = session["user"]["id"]
        user_name = session["user"]["name"]
        is_guest = False
    else:
        # Guest mode
        user_id = "guest_user"
        user_name = "Guest"
        is_guest = True

    user_msg = request.json.get("message")

    if not is_guest:
        log_collection.insert_one({
            "user_id": user_id,
            "email": session["user"]["email"],
            "name": session["user"]["name"],
            "action": "chat",
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })

    # Save only for logged-in users
    if not is_guest:
        save_chat(user_id, "user", user_msg)

    bot_reply = bot.get_response(user_msg)
    reply_msg = bot_reply["reply"]

    if not is_guest:
        save_chat(user_id, "bot", reply_msg)

    return jsonify(bot_reply)



# --------------------------
#      Chat History
# --------------------------
@app.route("/get_history")
def get_history():
    # Guests = no chat history at all
    if "guest" in session:
        return jsonify([])

    if "user" not in session:
        return jsonify([])

    user_id = session["user"]["id"]
    return jsonify(load_chat(user_id))


# --------------------------
#     Autocomplete API
# --------------------------
@app.route("/autocomplete")
def autocomplete():
    if "user" not in session:
        return jsonify([])

    q = request.args.get("query", "")
    return jsonify(bot.get_autocomplete_suggestions(q))


# -----------------------------------------------------
#               ADMIN PANEL (CRUD)
# -----------------------------------------------------


@app.route("/admin/intents", methods=["GET"])
def get_intents():
    return jsonify(list(bot.collection.find({}, {"_id": 0})))

@app.route("/admin/intents", methods=["POST"])
def add_intent():
    data = request.json
    data["intent"] = data["intent"].lower()
    bot.collection.replace_one({"intent": data["intent"]}, data, upsert=True)
    bot.reload_intents()
    return jsonify({"message": "Intent added/updated"})

@app.route("/admin/intents/<intent>", methods=["PUT"])
def update_intent(intent):
    bot.collection.update_one({"intent": intent.lower()}, {"$set": request.json})
    bot.reload_intents()
    return jsonify({"message": "Intent updated"})

@app.route("/admin/intents/<intent>", methods=["DELETE"])
def delete_intent(intent):
    bot.collection.delete_one({"intent": intent.lower()})
    bot.reload_intents()
    return jsonify({"message": "Intent deleted"})

@app.route("/admin/users")
def get_users():
    users = list(log_collection.find({}, {"_id":0}))

    unique = {}

    for u in users:
        email = u.get("email")
        if not email:
            continue

        time_str = u.get("time")
        try:
            current_time = datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")
        except:
            current_time = datetime.min

        if email not in unique:
            unique[email] = u
        else:
            old_time_str = unique[email].get("time")
            try:
                old_time = datetime.strptime(old_time_str, "%Y-%m-%d %H:%M:%S")
            except:
                old_time = datetime.min

            if current_time > old_time:
                unique[email] = u

    return jsonify(list(unique.values()))

@app.route("/admin/top-topics")
def top_topics():
    chats = chat_collection.find()
    topic_count = {}

    for chat in chats:
        if chat.get("role") != "user":
            continue

        msg = (chat.get("message") or "").lower()

        for course, keywords in COURSE_KEYWORDS.items():
            for word in keywords:
                if word in msg:
                    topic_count[course] = topic_count.get(course, 0) + 1
                    break

    sorted_topics = sorted(topic_count.items(), key=lambda x: x[1], reverse=True)

    return jsonify(sorted_topics[:10])

# --- ADMIN PAGE ROUTE ---


def admin_required(f):
    """Decorator to protect admin routes."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("admin_logged_in"):
            # Redirect to the admin login page if session key is missing
            return redirect(url_for("admin_login_page")) 
        return f(*args, **kwargs)
    return decorated_function







# -----------------------------------------------------
#                    START SERVER
# -----------------------------------------------------
if __name__ == "__main__":
    print("🚀 Chatbot Server Running on http://localhost:5000")
    app.run(host="0.0.0.0", port=5000, debug=True)
