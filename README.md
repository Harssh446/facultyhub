# FacultyHub — AI Faculty & Student Productivity Portal

A compact Flask + JSON version of the FacultyHub project. The UI styling is retained from the supplied FacultyHub stylesheet while the project structure is simplified into one database JSON file and one reusable portal template.

## Core requirements covered

- Faculty and student login with role-based access
- Attendance management, history and CSV export
- Internal assessment / marks entry, student view and CSV export
- AI-assisted question generation and faculty question bank
- Automatic question paper generation with print / PDF browser output
- Student quizzes with automatic scoring and stored attempts
- Assignment creation, file submission, evaluation, marks and feedback
- Student performance analytics and Green / Amber / Red risk indicators
- Timetable display
- AI lesson-plan generation with local Ollama support and fallback
- AI student progress summaries
- Faculty academic report and exportable CSV reports

## Project structure

```text
FacultyHub/
├── app.py
├── ai.py
├── storage.py
├── seed.py
├── requirements.txt
├── .env.example
├── README.md
├── data/
│   ├── db.json
│   └── uploads/
├── templates/
│   ├── base.html
│   ├── login.html
│   └── portal.html
└── static/
    └── style.css
```

The separate attendance/marks/questions/etc. JSON files were consolidated into `data/db.json` to reduce project clutter. Uploaded assignment files are stored in `data/uploads/` at runtime.

## Windows PowerShell setup

```powershell
cd FacultyHub
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
python app.py
```

Open `http://127.0.0.1:5000`.

## Demo accounts

- Faculty: `faculty` / `faculty123`
- Student: `fh001` / `student123`

Change the passwords after first login if this is used beyond a demo.

## Optional AI

If Ollama is running locally, set `OLLAMA_URL` and `OLLAMA_MODEL` in `.env`. If Ollama is unavailable, the portal automatically uses built-in fallback generation so the academic workflows still function.
