# LexiBridge AI Project Structure Plan

## 1. Current Project Status

The project has completed the v0.1 local MVP.

Current completed features:

- Teacher uploads course materials
- System extracts candidate terms
- Teacher reviews and approves terms
- Student views approved glossary
- Student submits feedback
- Teacher resolves feedback
- Teacher edits terms according to feedback
- Student exports glossary
- Teacher uploads course knowledge documents
- Backend creates KnowledgeDocument and KnowledgeChunk records
- Teacher searches knowledge chunks
- Teacher checks knowledge evidence during term review

## 2. Current Structure

Current basic structure:

LexiBridge-AI/
- backend/
  - app.py
  - requirements.txt
  - .venv/
- frontend/
  - index.html
- docs/
  - project-structure-plan.md

## 3. Current Problems

### 3.1 backend/app.py is too concentrated

The current app.py contains database models, file parsing, term extraction, feedback APIs, knowledge-base APIs, and Flask routes.

It can run now, but it will become hard to maintain when login, AI API, and cloud deployment are added.

### 3.2 frontend/index.html is too concentrated

The current index.html contains HTML, CSS, and JavaScript in one file.

It includes teacher-side logic, student-side logic, feedback logic, knowledge-base logic, export logic, and modal logic.

A small JavaScript syntax error may break the whole page.

### 3.3 Configuration is not separated

The project still has hard-coded configuration, such as API_BASE, database path, upload folder path, SECRET_KEY, and future AI API keys.

These should later be moved into config files or environment variables.

## 4. Target Structure

Future target structure:

LexiBridge-AI/
- README.md
- .gitignore
- .env.example
- backend/
  - app.py
  - config.py
  - models/
  - routes/
  - services/
  - utils/
- frontend/
  - index.html
  - css/
  - js/
- docs/
  - project-structure-plan.md
  - api.md
  - database.md
  - deployment.md
  - roadmap.md
- scripts/
  - init_db.py
  - backup_db.py
  - rebuild_knowledge_index.py

## 5. Backend Refactoring Order

1. Extract configuration into config.py
2. Extract utility functions
3. Extract database models
4. Extract routes with Flask Blueprint
5. Extract AI and knowledge-base services

## 6. Frontend Refactoring Order

1. Extract API_BASE into js/config.js
2. Extract CSS into css/main.css
3. Extract common API functions into js/api.js
4. Split JavaScript by module
5. Consider React or Vue only when the project becomes larger

## 7. Current Restrictions

At this stage, do not:

- Move app.py
- Move index.html
- Split the main JavaScript
- Change database structure
- Change API routes
- Delete existing files
- Introduce a frontend framework

## 8. Summary

The current project is stable as a v0.1 local MVP.

The engineering principle is:

- Document first
- Configure second
- Refactor low-risk parts first
- Modularize gradually
- Never break a working system just to make the structure look professional
