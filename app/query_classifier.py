# File: app/query_classifier.py

import torch
from transformers import BertTokenizer, BertForSequenceClassification
import json
import os
from typing import Dict, List, Tuple, Optional
import logging

logger = logging.getLogger(__name__)

class QueryTemplate:
    def __init__(self, name: str, pattern: Dict, placeholders: List[str]):
        self.name = name
        self.pattern = pattern
        self.placeholders = placeholders

    def fill_template(self, values: Dict) -> Dict:
        """Fill template with actual values"""
        filled = json.loads(json.dumps(self.pattern))  # Deep copy
        for placeholder, value in values.items():
            if placeholder in self.placeholders:
                # Handle nested dictionary paths
                current = filled
                parts = placeholder.split('.')
                for part in parts[:-1]:
                    current = current[part]
                current[parts[-1]] = value
        return filled

class QueryClassifier:
    def __init__(self, model_path: str = "models/query_classifier"):
        try:
            # Try to load trained model
            self.tokenizer = BertTokenizer.from_pretrained(model_path)
            self.model = BertForSequenceClassification.from_pretrained(model_path)
        except Exception as e:
            logger.warning(f"Could not load trained model, using base model: {str(e)}")
            # Fallback to base model
            self.tokenizer = BertTokenizer.from_pretrained('bert-base-uncased')
            self.model = BertForSequenceClassification.from_pretrained(
                'bert-base-uncased', 
                num_labels=len(self.get_templates())
            )
        self.model.eval()
        self.templates = self.get_templates()
        
        
    @staticmethod
    def get_templates() -> Dict[str, QueryTemplate]:
        """Define query templates"""
        return {
            "simple_filter": QueryTemplate(
                "simple_filter",
                {
                    "filter": {"FIELD": "VALUE"},
                    "projection": None,
                    "sort": None,
                    "limit": 10
                },
                ["filter.FIELD", "filter.VALUE"]
            ),
            "aggregation_count": QueryTemplate(
                "aggregation_count",
                {
                    "aggregate": [
                        {"$match": {"FIELD": "VALUE"}},
                        {"$group": {"_id": "$GROUP_FIELD", "count": {"$sum": 1}}}
                    ]
                },
                ["aggregate.0.$match.FIELD", "aggregate.0.$match.VALUE", "aggregate.1.$group._id"]
            ),
            "distinct_values": QueryTemplate(
                "distinct_values",
                {
                    "aggregate": [
                        {"$group": {"_id": "$FIELD"}},
                        {"$sort": {"_id": 1}}
                    ]
                },
                ["aggregate.0.$group._id"]
            ),
            "average_calculation": QueryTemplate(
                "average_calculation",
                {
                    "aggregate": [
                        {"$match": {"FIELD": "VALUE"}},
                        {"$group": {"_id": None, "average": {"$avg": "$AVG_FIELD"}}}
                    ]
                },
                ["aggregate.0.$match.FIELD", "aggregate.0.$match.VALUE", "aggregate.1.$group.average"]
            )
        }

    def classify_query(self, query_text: str) -> Tuple[str, float]:
        """Classify the query type using BERT"""
        inputs = self.tokenizer(query_text, return_tensors="pt", padding=True, truncation=True)
        outputs = self.model(**inputs)
        probs = torch.softmax(outputs.logits, dim=1)
        predicted_class = torch.argmax(probs).item()
        confidence = probs[0][predicted_class].item()
        
        template_names = list(self.templates.keys())
        return template_names[predicted_class], confidence

    def extract_values(self, query_text: str, schema: Dict) -> Dict:
        """Extract values from query text to fill template placeholders"""
        # This is a simplified version - in production, you might want to use
        # named entity recognition or more sophisticated extraction techniques
        values = {}
        
        # Basic field matching
        for field in schema.keys():
            if field.lower() in query_text.lower():
                # Match values based on context
                # This is where you could integrate with the LLM for better extraction
                values[f"filter.FIELD"] = field
                # Extract surrounding context for value
                # This is simplified - you'd want more robust extraction
                context = query_text.lower().split(field.lower())[1].split()[0]
                values[f"filter.VALUE"] = context
                
        return values

class HybridQueryGenerator:
    def __init__(self, classifier: QueryClassifier):
        self.classifier = classifier
        self.confidence_threshold = 0.7
        
    def generate_query(self, query_text: str, schema: Dict, llm_generator) -> Dict:
        """Generate query using hybrid approach"""
        try:
            # First attempt template-based generation
            template_name, confidence = self.classifier.classify_query(query_text)
            
            logger.info(f"Query Classification Results:")
            logger.info(f"  - Classified as: {template_name}")
            logger.info(f"  - Confidence: {confidence:.4f}")
            logger.info(f"  - Threshold: {self.confidence_threshold}")
            
            if confidence >= self.confidence_threshold:
                logger.info("Using neural template-based generation")
                template = self.classifier.templates[template_name]
                values = self.classifier.extract_values(query_text, schema)
                
                if values:
                    logger.info(f"Extracted values: {json.dumps(values, indent=2)}")
                    filled_template = template.fill_template(values)
                    logger.info("Successfully generated query from template")
                    return filled_template
                else:
                    logger.info("No values could be extracted, falling back to LLM")
            else:
                logger.info("Confidence below threshold, falling back to LLM")
            
            # Fallback to LLM-based generation
            logger.info("Using LLM-based generation")
            return llm_generator(query_text, schema)
            
        except Exception as e:
            logger.error(f"Error in hybrid query generation: {str(e)}")
            logger.info("Error occurred, falling back to LLM-based generation")
            # Fallback to LLM-based generation
            return llm_generator(query_text, schema)