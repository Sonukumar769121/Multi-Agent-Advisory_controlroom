# Agricultural Advisory Control Room

[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/downloads/release/python-3110/)
[![Framework](https://img.shields.io/badge/framework-Microsoft%20Agent%20Framework-green.svg)](https://github.com/microsoft/agent-framework)
[![Tests](https://img.shields.io/badge/tests-15%20passed-brightgreen.svg)](tests/)

An autonomous multi-agent agricultural advisory decision-support system utilizing the **Blackboard (Hearsay-II) Architectural Pattern**, built with **Microsoft Agent Framework** in **Python 3.11**.

Given a farmer's crop, location, and phenological growth stage, the system coordinates specialized decoupled agents to synthesize **ONE plain-language advisory strictly under 120 words** containing:
1. **Agronomic Field Action** (e.g., sow, wait, irrigate, hold irrigation based on real 7-day rainfall forecasts).
2. **Market Timing** (sell vs. hold based on real APMC mandi modal prices vs. the official Minimum Support Price [MSP] floor).
3. **Government Welfare Scheme** (verified scheme name, exact benefits, and eligibility criteria retrieved from ChromaDB vector collections).

---

## 🏗️ Architecture & Specialized Agents

The system decouples all communication through an SQLite-backed thread-safe **Advisory Board**. Agents never communicate directly with each other.

| Agent | Responsibility | Data Source |
| :--- | :--- | :--- |
| **Intake Agent** | Validates farmer profile, normalizes crop aliases, and resolves coordinates. | Open-Meteo Geocoding API |
| **Weather Agent** | Extracts 7-day rainfall, max/min temperature, wind speed, and humidity. | Open-Meteo Forecast API |
| **Crop Agent** | Weather-aware agronomic action derivation based on ICAR/KVK guidance. | ChromaDB (`crop_guidance`) |
| **Market Agent** | Evaluates daily mandi modal prices and calculates 7-day trend vs MSP floor. | Data.gov.in Agmarknet API |
| **Scheme Agent** | Retrieves matching welfare policies with grounded eligibility citations. | ChromaDB (`schemes`) |
| **Advisor Coordinator** | Synthesizes final plain-language advisory ($\le 120$ words) in English, Hindi, or Punjabi. | Advisory Board Synthesis |

---

## 🚀 Quick Start

### 1. Installation
```bash
git clone https://github.com/Sonukumar769121/Multi-Agent-Advisory_controlroom.git
cd Multi-Agent-Advisory_controlroom
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Run CLI Demonstration
```bash
python run_demo.py --crop "Wheat" --location "Karnal, Haryana" --stage "vegetative" --language "en"
```

### 3. Launch Interactive Web Dashboard
```bash
streamlit run app.py
```
Open [http://localhost:8501](http://localhost:8501) in your browser.

### 4. Run Automated Test Suite
```bash
pytest tests/ -v
```

---

## 📄 Submission Dossier
* [RK2E2332A16_Project2_Agentic_AI.pdf](RK2E2332A16_Project2_Agentic_AI.pdf): Full 38-page comprehensive architectural specification and viva preparation dossier.
