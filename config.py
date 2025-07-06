import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'you-will-never-guess'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///app.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    GEMINI_API_KEY = 'AIzaSyCReXivEGHrKs3CiPwRfNuAvc8C9505fqY'
   
    MONGODB_URI = "mongodb://localhost:27017/"
    DATABASE_NAME = "testDB"



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
│   │   learning_curve.png
│   │   query_logs.json
│   │
│   └───cache
├───models
│   └───query_classifier
│           config.json
│           model.safetensors
│           special_tokens_map.json
│           tokenizer_config.json
│           vocab.txt
│
└───__pycache__
