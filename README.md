# LexiBridge AI

LexiBridge AI is a course-oriented terminology standardization platform for Sino-foreign cooperative education.

The current version is a local MVP. It supports teacher-side material upload, term extraction, teacher review, student glossary viewing, student feedback, glossary export, and course knowledge-base management.

## 1. Current Version

Version: v0.1 local MVP

Current status:

- Runs locally on Windows
- Backend: Flask
- Frontend: single-page HTML/CSS/JavaScript
- Database: SQLite
- Knowledge base: document upload + text chunking + keyword search
- Git branch for development: dev
- Stable backup branch: stable-v0.1

## 2. Project Structure

Current structure:

```text
LexiBridge-AI/
├── .gitignore
├── README.md
├── backend/
│   ├── app.py
│   ├── requirements.txt
│   └── .venv/
├── frontend/
│   └── index.html
└── docs/
    └── project-structure-plan.md
3. Backend Setup

Open PowerShell and go to the backend folder:

cd C:\Users\12751\Desktop\LexiBridge-AI\backend

Activate the virtual environment:

.\.venv\Scripts\Activate.ps1

If PowerShell blocks script execution, use:

Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.\.venv\Scripts\Activate.ps1

Install dependencies if needed:

pip install -r requirements.txt

Start the backend:

python app.py

If successful, the backend should run at:

http://127.0.0.1:5000
4. Backend Test

Open this URL in a browser:

http://127.0.0.1:5000/api/test

Expected result:

{
  "status": "success"
}

The actual response may contain additional fields such as project name and message.

5. Frontend Usage

Open the frontend file in a browser:

C:\Users\12751\Desktop\LexiBridge-AI\frontend\index.html

The frontend currently connects to the local backend API.

If the backend is not running, frontend API functions will fail.

6. Current Main Features

Teacher side:

Upload PDF, DOCX, and PPTX course materials
Extract candidate English terms
Review and approve terms
Batch approve terms
Delete incorrect candidate terms
View student feedback
Mark feedback as resolved
Edit terms according to feedback
Upload course knowledge-base documents
Search knowledge-base chunks
Check knowledge evidence during term review

Student side:

View approved glossary
Filter by course and chapter
Search terms
Mark favorite terms
Mark mastered and unmastered terms
View learning progress
Submit feedback
Export current glossary
Export favorite, mastered, and unmastered terms

Knowledge-base system:

Upload PDF, DOCX, and PPTX reference materials
Parse document text
Split text into KnowledgeChunk records
Search knowledge chunks by keyword
Provide evidence for teacher review
7. Important Notes

This is still a local MVP.

It is not yet a production system.

Current limitations:

No real login system
No real teacher/student permission control
SQLite is used locally
Uploaded files are stored locally
AI API is not yet connected
Knowledge search is keyword-based, not vector-based
Complex formulas, scanned PDFs, and image-based slides are not fully supported
The frontend is still a single index.html file
8. Development Rules

Before changing code, always check:

git status

Before adding a major feature, make sure the current version is committed.

After each small stable step, commit changes with a clear message.

Example:

git add README.md
git commit -m "docs: add README startup guide"
9. Branches

Current branches:

master       Initial stable commit
stable-v0.1  Stable backup of the v0.1 local MVP
dev          Development branch

Continue development on:

dev
10. Next Engineering Goals

Planned next steps:

Improve project documentation
Extract configuration
Add real login and role permissions
Prepare cloud deployment
Upgrade database from SQLite to PostgreSQL
Add AI provider architecture
Add RAG-based term suggestion
Add semantic knowledge-base search
Improve frontend structure
Prepare online beta version
