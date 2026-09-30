# AutoWebFix

AutoWebFix is an AI-powered automated web application analysis and repair system. It combines headless web crawling with autonomous LLM agents to detect, analyze, and propose/apply fixes for broken features, UI issues, and broken links across web applications.

---

## 🚧 Project Status

> **Under Active Development**  
> *Current Phase:* Core Setup & Crawler Agent Architecture

---

## 🏗️ Architecture & Pipeline

The system operates through a sequence of specialized autonomous agents:

┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Crawler Agent  │ ──> │ Analysis Agent  │ ──> │   Fixing Agent  │ ──> │ Validation Agent│
│ (Playwright Core│     │ (LLM Diagnostic)│     │(Patch Generator)│     │ (Regression Test│
└─────────────────┘     └─────────────────┘     └─────────────────┘     └─────────────────┘

1. **Crawling Agent:** Traverses target web applications using Playwright to map routes, record interactions, capture DOM snapshots, and monitor console errors.
2. **Analysis Agent:** Evaluates captured logs, stack traces, and UI snapshots to pinpoint root causes.
3. **Fixing Agent:** Proposes code patches or config updates to resolve identified bugs.
4. **Validation Agent:** Re-runs automated interaction tests against the fix to confirm the bug is resolved without introducing regressions.

---

## 🛠️ Tech Stack

* **Language:** Python 3.10+
* **Browser Automation:** Playwright
* **AI & Intelligence:** LLMs / OpenAI API
* **Testing:** PyTest
* **Version Control:** Git & GitHub

---

## 📂 Project Structure

AutoWebFix/
├── agents/
│   ├── crawler/        # Playwright crawler logic & site navigation
│   ├── analysis/       # Diagnostic prompts & log analyzers
│   ├── fixer/          # Code patch generation logic
│   └── validation/     # Automated testing and verification
├── docs/               # Architecture diagrams and API documentation
├── tests/              # Unit & integration test suites
├── .gitignore          # Excluded environments and local cache files
├── README.md           # Project documentation
└── requirements.txt    # Python dependencies
