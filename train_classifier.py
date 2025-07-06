# File: train_classifier.py 
# (Place this in your root project directory, at the same level as run.py)

from app.query_classifier_training import train_classifier
import logging

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("Starting classifier training...")
    train_classifier()
    print("Training completed!")