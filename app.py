from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3, os, csv, io, random
from datetime import datetime

app = Flask(__name__)
app.secret_key = "change-me-in-production"
DB_PATH = os.path.join(os.path.dirname(__file__), "crm.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE,
        password TEXT,
        name TEXT
    );
    CREATE TABLE IF NOT EXISTS contacts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        phone TEXT NOT NULL,
        city TEXT,
        email TEXT,
        source TEXT,
        budget_band TEXT,
        buyer_type TEXT,
        preferred_asset TEXT,
        consent_status TEXT DEFAULT 'opted_in',
        hni_score INTEGER DEFAULT 0,
        status TEXT DEFAULT 'new',
        tags TEXT DEFAULT '',
        notes TEXT DEFAULT '',
        created_at TEXT
    );
    CREATE TABLE IF NOT EXISTS conversations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        contact_id INTEGER,
        last_message TEXT,
        updated_at TEXT,
        FOREIGN KEY(contact_id) REFERENCES contacts(id)
    );
    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        conversation_id INTEGER,
        sender TEXT,
        message_text TEXT,
        created_at TEXT,
        FOREIGN KEY(conversation_id) REFERENCES conversations(id)
    );
    CREATE TABLE IF NOT EXISTS campaigns (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        segment TEXT,
        template_text TEXT,
        status TEXT DEFAULT 'draft',
        created_at TEXT
    );
    CREATE TABLE IF NOT EXISTS projects (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        developer TEXT,
        location TEXT,
        ticket_size TEXT,
        appreciation_thesis TEXT,
        expected_roi TEXT,
        brochure_link TEXT
    );
    CREATE TABLE IF NOT EXISTS roi_calculations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        contact_id INTEGER,
        project_id INTEGER,
        purchase_price REAL,
        years INTEGER,
        expected_exit_value REAL,
        profit REAL,
        irr REAL,
        created_at TEXT
    );
    """)
    conn.commit()

    # default user
    c.execute("SELECT COUNT(*) FROM users")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO users (email,password,name) VALUES (?,?,?)",
                  ("admin@local.crm","admin123","Admin"))

    # seed projects
    c.execute("SELECT COUNT(*) FROM projects")
    if c.fetchone()[0] == 0:
        projects = [
            ("DLF The Arbour","DLF","Sector 63, Gurgaon","7–12 Cr","Low-density luxury, early-stage repricing, strong resale demand","18–22% in 3 years","https://example.com/brochure1"),
            ("Oberoi Gurgaon Launch","Oberoi Realty","Gurgaon","6–10 Cr","Brand premium, first-entry buzz, likely strong investor pull","16–20% in 3 years","https://example.com/brochure2"),
            ("Golf Course Extension Premium","Premium Developer","GCRE, Gurgaon","4–7 Cr","Infra tailwinds + premium inventory","15–18% in 3 years","https://example.com/brochure3"),
        ]
        c.executemany("""INSERT INTO projects
            (name,developer,location,ticket_size,appreciation_thesis,expected_roi,brochure_link)
            VALUES (?,?,?,?,?,?,?)""", projects)

    # seed contacts
    c.execute("SELECT COUNT(*) FROM contacts")
    if c.fetchone()[0] == 0:
        contacts = [
            ("Aman Khanna","+919999000001","Delhi","aman.khanna@example.com","Referral","5-7 Cr","investor","apartment","opted_in",91,"hot","gcre,investor","Interested in appreciation-led options",now()),
            ("Rhea Mehta","+919999000002","Mumbai","rhea.mehta@example.com","Instagram Lead","7-15 Cr","nri","apartment","opted_in",88,"contacted","nri,luxury","Asked for ROI deck",now()),
            ("Kabir Sethi","+919999000003","Gurgaon","kabir.sethi@example.com","Website","3-5 Cr","end-user","floor","opted_in",74,"new","end-user","Looking at move-in timeline 6 months",now()),
        ]
        c.executemany("""INSERT INTO contacts
        (name,phone,city,email,source,budget_band,buyer_type,preferred_asset,consent_status,hni_score,status,tags,notes,created_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", contacts)
        conn.commit()

        # seed conversations
        c.execute("SELECT id, name FROM contacts")
        for row in c.fetchall():
            c.execute("INSERT INTO conversations (contact_id,last_message,updated_at) VALUES (?,?,?)",
                      (row["id"], f"Started thread with {row['name']}", now()))
            conv_id = c.lastrowid
            c.execute("INSERT INTO messages (conversation_id,sender,message_text,created_at) VALUES (?,?,?,?)",
                      (conv_id, "system", f"Lead imported and conversation created for {row['name']}.", now()))
        conn.commit()
    conn.close()

def require_login():
    return "user_id" in session

def score_contact(name, city, budget_band, buyer_type, tags):
    score = 40
    if budget_band and ("7" in budget_band or "15" in budget_band or "Cr" in budget_band):
        score += 20
    if buyer_type and buyer_type.lower() in ["investor", "nri"]:
        score += 15
    if city and city.lower() in ["delhi", "gurgaon", "mumbai", "dubai", "london", "singapore"]:
        score += 10
    if tags and any(k in tags.lower() for k in ["luxury","business","founder","investor","nri"]):
        score += 10
    return min(score, 99)

@app.route("/")
def index():
    if not require_login():
        return redirect(url_for("login"))
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM contacts")
    total_contacts = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM contacts WHERE status='hot'")
    hot_leads = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM conversations")
    conversations = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM campaigns")
    campaigns = c.fetchone()[0]
    c.execute("SELECT * FROM contacts ORDER BY hni_score DESC LIMIT 5")
    top_contacts = c.fetchall()
    c.execute("SELECT * FROM campaigns ORDER BY id DESC LIMIT 5")
    recent_campaigns = c.fetchall()
    conn.close()
    return render_template("dashboard.html", total_contacts=total_contacts, hot_leads=hot_leads,
                           conversations=conversations, campaigns=campaigns,
                           top_contacts=top_contacts, recent_campaigns=recent_campaigns)

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email","").strip()
        password = request.form.get("password","").strip()
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE email=? AND password=?", (email, password))
        user = c.fetchone()
        conn.close()
        if user:
            session["user_id"] = user["id"]
            session["user_name"] = user["name"]
            return redirect(url_for("index"))
        flash("Invalid login details.")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/contacts", methods=["GET","POST"])
def contacts():
    if not require_login():
        return redirect(url_for("login"))
    conn = get_db()
    c = conn.cursor()
    if request.method == "POST":
        name = request.form.get("name","").strip()
        phone = request.form.get("phone","").strip()
        city = request.form.get("city","").strip()
        email = request.form.get("email","").strip()
        source = request.form.get("source","Manual").strip()
        budget_band = request.form.get("budget_band","").strip()
        buyer_type = request.form.get("buyer_type","").strip()
        preferred_asset = request.form.get("preferred_asset","").strip()
        consent_status = request.form.get("consent_status","opted_in").strip()
        tags = request.form.get("tags","").strip()
        notes = request.form.get("notes","").strip()
        score = score_contact(name, city, budget_band, buyer_type, tags)
        c.execute("""INSERT INTO contacts
            (name,phone,city,email,source,budget_band,buyer_type,preferred_asset,consent_status,hni_score,status,tags,notes,created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (name,phone,city,email,source,budget_band,buyer_type,preferred_asset,consent_status,score,"new",tags,notes,now()))
        contact_id = c.lastrowid
        c.execute("INSERT INTO conversations (contact_id,last_message,updated_at) VALUES (?,?,?)",
                  (contact_id, "Conversation created", now()))
        conv_id = c.lastrowid
        c.execute("INSERT INTO messages (conversation_id,sender,message_text,created_at) VALUES (?,?,?,?)",
                  (conv_id, "system", f"New contact {name} added.", now()))
        conn.commit()
        flash("Contact added.")
        conn.close()
        return redirect(url_for("contacts"))

    search = request.args.get("search","").strip()
    if search:
        c.execute("""SELECT * FROM contacts
                     WHERE name LIKE ? OR city LIKE ? OR phone LIKE ? OR tags LIKE ?
                     ORDER BY hni_score DESC, id DESC""",
                  (f"%{search}%", f"%{search}%", f"%{search}%", f"%{search}%"))
    else:
        c.execute("SELECT * FROM contacts ORDER BY hni_score DESC, id DESC")
    rows = c.fetchall()
    conn.close()
    return render_template("contacts.html", contacts=rows, search=search)

@app.route("/contacts/import", methods=["GET","POST"])
def contacts_import():
    if not require_login():
        return redirect(url_for("login"))
    preview = []
    imported = None
    if request.method == "POST":
        file = request.files.get("csv_file")
        if not file:
            flash("Please upload a CSV file.")
            return redirect(url_for("contacts_import"))
        content = file.read().decode("utf-8", errors="ignore")
        stream = io.StringIO(content)
        reader = csv.DictReader(stream)
        rows = list(reader)
        action = request.form.get("action","preview")
        if action == "preview":
            preview = rows[:10]
        else:
            conn = get_db()
            c = conn.cursor()
            count = 0
            for row in rows:
                name = (row.get("name") or row.get("Name") or "").strip()
                phone = (row.get("phone") or row.get("Phone") or "").strip()
                if not name or not phone:
                    continue
                city = (row.get("city") or row.get("City") or "").strip()
                email = (row.get("email") or row.get("Email") or "").strip()
                source = (row.get("source") or row.get("Source") or "CSV Upload").strip()
                budget_band = (row.get("budget_band") or row.get("Budget") or "").strip()
                buyer_type = (row.get("buyer_type") or row.get("Buyer Type") or "investor").strip()
                preferred_asset = (row.get("preferred_asset") or row.get("Preferred Asset") or "apartment").strip()
                consent_status = (row.get("consent_status") or row.get("Consent") or "opted_in").strip()
                tags = (row.get("tags") or row.get("Tags") or "").strip()
                notes = (row.get("notes") or row.get("Notes") or "").strip()
                score = score_contact(name, city, budget_band, buyer_type, tags)

                c.execute("SELECT id FROM contacts WHERE phone=?", (phone,))
                existing = c.fetchone()
                if existing:
                    continue

                c.execute("""INSERT INTO contacts
                    (name,phone,city,email,source,budget_band,buyer_type,preferred_asset,consent_status,hni_score,status,tags,notes,created_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (name,phone,city,email,source,budget_band,buyer_type,preferred_asset,consent_status,score,"new",tags,notes,now()))
                contact_id = c.lastrowid
                c.execute("INSERT INTO conversations (contact_id,last_message,updated_at) VALUES (?,?,?)",
                          (contact_id, "Conversation created", now()))
                conv_id = c.lastrowid
                c.execute("INSERT INTO messages (conversation_id,sender,message_text,created_at) VALUES (?,?,?,?)",
                          (conv_id, "system", f"Imported contact {name} from CSV.", now()))
                count += 1
            conn.commit()
            conn.close()
            imported = count
            flash(f"Imported {count} contacts.")
    return render_template("import_contacts.html", preview=preview, imported=imported)

@app.route("/campaigns", methods=["GET","POST"])
def campaigns():
    if not require_login():
        return redirect(url_for("login"))
    conn = get_db()
    c = conn.cursor()
    if request.method == "POST":
        name = request.form.get("name","").strip()
        segment = request.form.get("segment","all").strip()
        template_text = request.form.get("template_text","").strip()
        c.execute("INSERT INTO campaigns (name,segment,template_text,status,created_at) VALUES (?,?,?,?,?)",
                  (name,segment,template_text,"draft",now()))
        conn.commit()
        flash("Campaign created.")
        conn.close()
        return redirect(url_for("campaigns"))
    c.execute("SELECT * FROM campaigns ORDER BY id DESC")
    rows = c.fetchall()
    conn.close()
    return render_template("campaigns.html", campaigns=rows)

@app.route("/campaigns/<int:campaign_id>/launch")
def launch_campaign(campaign_id):
    if not require_login():
        return redirect(url_for("login"))
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM campaigns WHERE id=?", (campaign_id,))
    campaign = c.fetchone()
    if not campaign:
        conn.close()
        flash("Campaign not found.")
        return redirect(url_for("campaigns"))

    segment = campaign["segment"]
    if segment == "hot":
        c.execute("SELECT * FROM contacts WHERE status='hot' AND consent_status='opted_in'")
    elif segment == "investor":
        c.execute("SELECT * FROM contacts WHERE buyer_type='investor' AND consent_status='opted_in'")
    elif segment == "nri":
        c.execute("SELECT * FROM contacts WHERE buyer_type='nri' AND consent_status='opted_in'")
    else:
        c.execute("SELECT * FROM contacts WHERE consent_status='opted_in'")
    contacts = c.fetchall()

    sent = 0
    for contact in contacts:
        c.execute("SELECT * FROM conversations WHERE contact_id=?", (contact["id"],))
        conv = c.fetchone()
        if not conv:
            c.execute("INSERT INTO conversations (contact_id,last_message,updated_at) VALUES (?,?,?)",
                      (contact["id"], "Campaign conversation", now()))
            conv_id = c.lastrowid
        else:
            conv_id = conv["id"]

        message = campaign["template_text"].replace("{name}", contact["name"]).replace("{city}", contact["city"] or "")
        c.execute("INSERT INTO messages (conversation_id,sender,message_text,created_at) VALUES (?,?,?,?)",
                  (conv_id, "campaign", message, now()))
        c.execute("UPDATE conversations SET last_message=?, updated_at=? WHERE id=?",
                  (message, now(), conv_id))
        sent += 1

    c.execute("UPDATE campaigns SET status='launched' WHERE id=?", (campaign_id,))
    conn.commit()
    conn.close()
    flash(f"Campaign launched to {sent} opted-in contacts.")
    return redirect(url_for("campaigns"))

@app.route("/inbox")
def inbox():
    if not require_login():
        return redirect(url_for("login"))
    conn = get_db()
    c = conn.cursor()
    c.execute("""SELECT conversations.*, contacts.name AS contact_name, contacts.city, contacts.hni_score
                 FROM conversations
                 JOIN contacts ON contacts.id = conversations.contact_id
                 ORDER BY conversations.updated_at DESC""")
    conversations = c.fetchall()
    selected_id = request.args.get("conversation_id")
    selected = None
    messages = []
    ai_suggestion = ""
    if selected_id:
        c.execute("""SELECT conversations.*, contacts.name AS contact_name, contacts.city, contacts.budget_band,
                            contacts.buyer_type, contacts.hni_score, contacts.tags
                     FROM conversations
                     JOIN contacts ON contacts.id = conversations.contact_id
                     WHERE conversations.id=?""", (selected_id,))
        selected = c.fetchone()
        c.execute("SELECT * FROM messages WHERE conversation_id=? ORDER BY id ASC", (selected_id,))
        messages = c.fetchall()
        if selected:
            ai_suggestion = (
                f"Hi {selected['contact_name'].split()[0]}, based on your {selected['budget_band']} profile, "
                f"I’ve shortlisted 2 Gurgaon options with strong upside and cleaner entry points. "
                f"Want a quick ROI snapshot and 30-sec breakdown video?"
            )
    elif conversations:
        first_id = conversations[0]["id"]
        return redirect(url_for("inbox", conversation_id=first_id))
    conn.close()
    return render_template("inbox.html", conversations=conversations, selected=selected, messages=messages, ai_suggestion=ai_suggestion)

@app.route("/inbox/<int:conversation_id>/send", methods=["POST"])
def send_message(conversation_id):
    if not require_login():
        return redirect(url_for("login"))
    text = request.form.get("message_text","").strip()
    if text:
        conn = get_db()
        c = conn.cursor()
        c.execute("INSERT INTO messages (conversation_id,sender,message_text,created_at) VALUES (?,?,?,?)",
                  (conversation_id, "advisor", text, now()))
        c.execute("UPDATE conversations SET last_message=?, updated_at=? WHERE id=?",
                  (text, now(), conversation_id))
        conn.commit()
        conn.close()
        flash("Message sent in local inbox.")
    return redirect(url_for("inbox", conversation_id=conversation_id))

@app.route("/projects")
def projects():
    if not require_login():
        return redirect(url_for("login"))
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM projects ORDER BY id DESC")
    rows = c.fetchall()
    conn.close()
    return render_template("projects.html", projects=rows)

@app.route("/roi", methods=["GET","POST"])
def roi():
    if not require_login():
        return redirect(url_for("login"))
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id,name FROM contacts ORDER BY name")
    contacts = c.fetchall()
    c.execute("SELECT id,name,expected_roi FROM projects ORDER BY name")
    projects = c.fetchall()
    result = None
    if request.method == "POST":
        contact_id = int(request.form.get("contact_id"))
        project_id = int(request.form.get("project_id"))
        purchase_price = float(request.form.get("purchase_price"))
        years = int(request.form.get("years"))
        growth = float(request.form.get("growth_rate"))
        expected_exit_value = round(purchase_price * ((1 + growth/100) ** years), 2)
        profit = round(expected_exit_value - purchase_price, 2)
        irr = round((((expected_exit_value / purchase_price) ** (1/years)) - 1) * 100, 2)
        c.execute("""INSERT INTO roi_calculations
                  (contact_id,project_id,purchase_price,years,expected_exit_value,profit,irr,created_at)
                  VALUES (?,?,?,?,?,?,?,?)""",
                  (contact_id, project_id, purchase_price, years, expected_exit_value, profit, irr, now()))
        conn.commit()
        result = {"expected_exit_value": expected_exit_value, "profit": profit, "irr": irr}
        flash("ROI calculation saved.")
    conn.close()
    return render_template("roi.html", contacts=contacts, projects=projects, result=result)

if __name__ == "__main__":
    init_db()
    app.run(debug=True)
