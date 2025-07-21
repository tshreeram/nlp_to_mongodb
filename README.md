# Natural Language to MongoDB (NL2Mongo)

Convert natural language queries into executable MongoDB queries using LLMs — enhanced with schema awareness, visualization, feedback learning, caching, and basic access control.

---

## Overview

This project bridges the gap between natural language inputs and MongoDB querying by leveraging a language model (Gemini API) and fine-tuning via feedback learning. It mimics the concept of "Natural Language to SQL" (NL2SQL), but adapted specifically for MongoDB collections.

At its core, the system:
- Accepts natural language inputs from users
- Uses LLMs to generate **read-only** MongoDB queries with schema context
- Stores query results in a cache format for ready visualization
- Displays results and charts using an interactive frontend
- Incorporates a feedback loop where a BERT-based model learns from successful logs and improves query generation over time
- Enforces security through user registration, login, and session management

---

## Architecture

```
User Input (NL)
     ↓
Frontend (HTML/JS/Bootstrap)
     ↓
Flask API (Python Backend)
     ↓
User Session Validation
     ↓
LLM (Gemini API) + Schema Injection
     ↓
MongoDB Read Query Generation
     ↓
Execution + Caching + Logging
     ↓
Visualization Tools + Feedback Loop
```

---

## Tech Stack

| Layer        | Technology                                           |
|--------------|------------------------------------------------------|
| Frontend     | HTML, CSS, Bootstrap, jQuery, AJAX, Chart.js         |
| Backend      | Python, Flask                                        |
| LLM          | Gemini API or any other free api works I guess       |
| DB           | MongoDB                                              |
| Caching      | In-memory (optional: Redis or file-based)            |
| Learning     | BERT (Transformers - feedback loop retraining)       |
| Storage      | JSON log files                                       |
| Auth         | Flask Sessions, Secure Login/Register                |

---

## Features

- Natural Language to MongoDB: Understands user intent and translates to schema-aware, read-only MongoDB queries
- Read-Only Safety: Only allows queries like `find()`, `aggregate()` for secure data access
- Self-Improving: Feedback loop with BERT model retraining on successful queries from logs
- Result Caching: Query results are cached for quick access and visual rendering
- Visualization Ready: Frontend supports rendering results with charts and tables
- Secure UI: Basic user authentication (register/login/session) built-in

---

## Getting Started

### Prerequisites

- Python 3.8+
- MongoDB instance (local or cloud)
- Gemini API key (or any other LLM provider)
- Node.js (optional, for full frontend dependency resolution)

### Disclaimer

**Note:** The trained BERT-based classifier model used in the feedback loop is **not included in this repository** due to size and licensing restrictions.

If you wish to use the feedback learning system, you have two options:

1. **Train the model yourself** using the `train_classifier.py` script (logs will be used as training data).
2. **Disable or remove the classifier logic** in the codebase (e.g., `query_classifier.py`, `query_classifier_training.py`) if you only want LLM-based query generation.

Make sure to have a sufficient number of successful query logs in `logs/query_logs.json` before initiating training.

### Installation

```bash
git clone https://github.com/yourusername/NL2Mongo.git
cd NL2Mongo
pip install -r requirements.txt
```

### Set Environment Variables

```bash
export GEMINI_API_KEY=your_api_key_here
export SECRET_KEY=your_flask_secret_key
```

### Run the App

```bash
python run.py
```

Then open in your browser: [http://localhost:5000](http://localhost:5000)


## Project Structure

```
NL2Mongo/
.
│   app.db
│   config.py
│   requirements.txt
│   run.py
│   train_classifier.py
│   validate_logs.py
│
├───app
│   │   data_manager.py
│   │   forms.py
│   │   gemini_api.py
│   │   models.py
│   │   mongo_utils.py
│   │   query_classifier.py
│   │   query_classifier_training.py
│   │   routes.py
│   │   testing.py
│   │   __init__.py
│   │
│   ├───static
│   │   └───css
│   │           styles.css
│   │
│   ├───templates
│   │       base.html
│   │       full_data.html
│   │       index.html
│   │       login.html
│   │       register.html
│   │       select_collection.html
│   │
│   └───__pycache__
│
├───instance
│       app.db
│
├───logs
│   │   query_logs.json
│   │
│   └───cache
│
├───models
│   └───query_classifier
│           config.json
│           special_tokens_map.json
│           tokenizer_config.json
│           vocab.txt
```

---

## Feedback Loop: Learning from Success

All successful MongoDB queries (that execute without error) are logged along with user input and result metadata. Periodically, a BERT-based model is retrained on this data to improve intent detection and semantic parsing.

This feedback system helps bridge the gap between what users *mean* and how MongoDB *expects* queries — without fine-tuning the base LLM.

---

## Visualization Layer

Each query result is:
- Stored temporarily in cache (file or in-memory)
- Rendered dynamically using Chart.js and tabular views
- Visual types (bar, pie, line, etc.) are selectable per result set

This allows data exploration without needing external BI tools.

---

## Example

**Input:**

"List all products that were added in the last 7 days and have stock greater than 50"

**Generated Query:**

```javascript
db.products.find({
  addedAt: { $gte: new Date(Date.now() - 7*24*60*60*1000) },
  stock: { $gt: 50 }
})
```

---

## Security & Access Control

- Users must register/login before accessing query generation
- Sessions are maintained securely with Flask session middleware
- Only read operations (`find`, `aggregate`) are allowed to prevent write/delete access to the database
- Input sanitation and query validation included before execution

---

## Future Improvements

- Replace BERT with lightweight fine-tuned transformer for semantic parsing
- Role-based access control (RBAC) for multiple user tiers
- Docker containerization and deployment pipeline
- UI enhancement for query history and saved dashboards

---

## License

MIT License. See `LICENSE` file for details.

---

## Contributing

Pull requests are welcome. For major changes, please open an issue first to discuss what you'd like to change.

---

## Acknowledgments

- Google Gemini API
- HuggingFace Transformers (for BERT)
- Flask and MongoDB Communities
- Chart.js for frontend visualization
