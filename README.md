# RescueComm

RescueComm is a lightweight, local two-sided emergency communication demo for a college environment.

## Folder Structure

```text
rescuecomm/
├── main.py
├── requirements.txt
├── README.md
├── data/
│   └── rescuecomm.db          # created automatically on first run
└── static/
    ├── citizen.html
    ├── dashboard.html
    ├── css/
    │   └── styles.css
    └── js/
        ├── citizen.js
        └── dashboard.js
```

## Run Locally

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn main:app --reload
```

Open:

- Citizen Portal: <http://127.0.0.1:8000/citizen>
- Authority ICCC: <http://127.0.0.1:8000/dashboard>
- API docs: <http://127.0.0.1:8000/docs>
