# HNI CRM Option A

A simple local CRM that runs on Windows with one setup flow.

## Features
- Login
- Dashboard
- Contacts
- CSV import
- Campaign creation and launch to opted-in contacts
- Local inbox
- Projects library
- ROI calculator

## Login
- Email: admin@local.crm
- Password: admin123

## Windows setup
1. Extract the zip.
2. Open the folder.
3. Click the address bar in File Explorer.
4. Type `cmd` and press Enter.
5. Run:

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

6. Open:
http://127.0.0.1:5000

## Notes
- This runs locally on your laptop.
- Campaign sending is simulated inside the local inbox.
- It does not scrape social platforms or send unsolicited messages.
