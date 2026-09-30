# StudyWise

StudyWise is a personal study planner for organizing courses, lectures, labs, assignments, grades, and weekly study tasks.

## Features

- Track lecture and lab study progress.
- Keep assignments, quizzes, and projects with due dates.
- Generate a suggested weekly study plan from upcoming deadlines and unfinished lessons.
- Record coursework grades by subject.
- Use the included SpongeBob-themed background across the app.

## Run on Windows

1. Install Python if it is not already installed. Select **Add Python to PATH** during setup.
2. Open the project folder and double-click `Start StudyWise.vbs` for a quiet launch, or `run_windows.bat` to see startup messages.
3. The first launch installs the required packages. Then open `http://localhost:8501` in your browser if it does not open automatically.
4. Keep the launcher running while you use the site. To stop it, close the launcher window or stop the Streamlit process.

## Run from a terminal

Open Command Prompt in the project folder and run:

```bat
run_windows.bat
```

Alternatively, use Python directly:

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

## Your study data

The app stores study progress in a local SQLite database named `studywise.db`. This file is excluded from GitHub, so your personal study data stays on your computer and is not included in the repository.

The initial timetable is based on Group B.
