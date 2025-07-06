import torch
from torch.utils.data import Dataset, DataLoader
from transformers import BertTokenizer, BertForSequenceClassification, AdamW
from sklearn.model_selection import train_test_split
import json
import logging
import pandas as pd
from typing import Dict, List, Tuple
import numpy as np
from tqdm import tqdm
from pathlib import Path
import matplotlib.pyplot as plt

logger = logging.getLogger(__name__)

# Expanded Templates with additional query types
QUERY_TEMPLATES = {
    "simple_filter": {
        "pattern": {
            "filter": {"FIELD": "VALUE"},
            "projection": None,
            "sort": None,
            "limit": 10
        },
        "placeholders": ["filter.FIELD", "filter.VALUE"],
        "examples": [
            "show me all documents where name is John",
            "find records with status active",
            "get entries where price is greater than 100"
        ]
    },
    "aggregation_count": {
        "pattern": {
            "aggregate": [
                {"$match": {"FIELD": "VALUE"}},
                {"$group": {"_id": "$GROUP_FIELD", "count": {"$sum": 1}}}
            ]
        },
        "placeholders": ["aggregate.0.$match.FIELD", "aggregate.0.$match.VALUE", "aggregate.1.$group._id"],
        "examples": [
            "count number of orders by status",
            "how many users are there per country",
            "get total sales grouped by product category"
        ]
    },
    "distinct_values": {
        "pattern": {
            "aggregate": [
                {"$group": {"_id": "$FIELD"}},
                {"$sort": {"_id": 1}}
            ]
        },
        "placeholders": ["aggregate.0.$group._id"],
        "examples": [
            "what are the unique categories",
            "show me all different status values",
            "list distinct product types"
        ]
    },
    "average_calculation": {
        "pattern": {
            "aggregate": [
                {"$match": {"FIELD": "VALUE"}},
                {"$group": {"_id": None, "average": {"$avg": "$AVG_FIELD"}}}
            ]
        },
        "placeholders": ["aggregate.0.$match.FIELD", "aggregate.0.$match.VALUE", "aggregate.1.$group.average"],
        "examples": [
            "calculate average price for category electronics",
            "what is the mean age of users in New York",
            "get average order value by customer type"
        ]
    },
    "complex_filter": {
        "pattern": {
            "filter": {
                "$and": [
                    {"FIELD1": "VALUE1"},
                    {"FIELD2": "VALUE2"}
                ]
            },
            "sort": {"SORT_FIELD": "SORT_ORDER"},
            "limit": 10
        },
        "placeholders": ["filter.$and.0.FIELD1", "filter.$and.0.VALUE1", "filter.$and.1.FIELD2", "filter.$and.1.VALUE2", "sort.SORT_FIELD"],
        "examples": [
            "find orders with status pending and price greater than 100 sorted by date",
            "show active users in California with age above 25 ordered by name",
            "get products in electronics category with stock less than 10 sorted by price"
        ]
    },
    "time_series_aggregation": {
        "pattern": {
            "aggregate": [
                {
                    "$match": {
                        "timestamp": {
                            "$gte": "START_DATE",
                            "$lte": "END_DATE"
                        }
                    }
                },
                {
                    "$group": {
                        "_id": {
                            "$dateToString": {
                                "format": "%Y-%m-%d",
                                "date": "$timestamp"
                            }
                        },
                        "value": {"$SUM_OR_AVG": "$METRIC_FIELD"}
                    }
                },
                {"$sort": {"_id": 1}}
            ]
        },
        "placeholders": ["aggregate.0.$match.timestamp.$gte", "aggregate.0.$match.timestamp.$lte", "aggregate.1.$group.value", "aggregate.1.$group._id"],
        "examples": [
            "show daily sales totals for the last month",
            "calculate average temperature readings per day between January and March",
            "get sum of transactions by date for Q1 2024"
        ]
    },
    # New templates added below
    "top_n_query": {
        "pattern": {
            "filter": {"FIELD": "VALUE"},
            "sort": {"SORT_FIELD": -1},
            "limit": "N"
        },
        "placeholders": ["filter.FIELD", "filter.VALUE", "sort.SORT_FIELD", "limit"],
        "examples": [
            "show me top 5 products by sales",
            "list the 10 most expensive items in inventory",
            "find the 3 highest rated restaurants in New York"
        ]
    },
    "full_text_search": {
        "pattern": {
            "filter": {
                "$text": {
                    "$search": "SEARCH_TERM"
                }
            },
            "sort": {
                "score": {
                    "$meta": "textScore"
                }
            }
        },
        "placeholders": ["filter.$text.$search"],
        "examples": [
            "search for documents containing machine learning",
            "find articles mentioning climate change",
            "look for posts about artificial intelligence"
        ]
    },
    "nested_field_query": {
        "pattern": {
            "filter": {
                "PARENT_FIELD.NESTED_FIELD": "VALUE"
            }
        },
        "placeholders": ["filter.PARENT_FIELD.NESTED_FIELD", "filter.PARENT_FIELD.NESTED_FIELD.VALUE"],
        "examples": [
            "find orders where shipping.address.country is USA",
            "get users with profile.settings.notifications enabled",
            "show products where specs.dimensions.height is greater than 10"
        ]
    },
    "range_query": {
        "pattern": {
            "filter": {
                "FIELD": {
                    "$gte": "MIN_VALUE",
                    "$lte": "MAX_VALUE"
                }
            }
        },
        "placeholders": ["filter.FIELD", "filter.FIELD.$gte", "filter.FIELD.$lte"],
        "examples": [
            "find products with price between 50 and 100",
            "show orders with quantity from 5 to 20",
            "get users with age range 25 to 40"
        ]
    },
    "array_contains": {
        "pattern": {
            "filter": {
                "ARRAY_FIELD": {
                    "$in": ["VALUE"]
                }
            }
        },
        "placeholders": ["filter.ARRAY_FIELD", "filter.ARRAY_FIELD.$in.0"],
        "examples": [
            "find products with tags including organic",
            "show users with interests containing gaming",
            "get posts with categories including science"
        ]
    },
    "exists_query": {
        "pattern": {
            "filter": {
                "FIELD": {
                    "$exists": True
                }
            }
        },
        "placeholders": ["filter.FIELD", "filter.FIELD.$exists"],
        "examples": [
            "show users who have profile pictures",
            "find products that have reviews",
            "get documents with rating field present"
        ]
    },
    "min_max_aggregation": {
        "pattern": {
            "aggregate": [
                {"$match": {"FIELD": "VALUE"}},
                {"$group": {
                    "_id": "$GROUP_BY",
                    "min_value": {"$min": "$MIN_FIELD"},
                    "max_value": {"$max": "$MAX_FIELD"}
                }}
            ]
        },
        "placeholders": ["aggregate.0.$match.FIELD", "aggregate.0.$match.VALUE", "aggregate.1.$group._id", "aggregate.1.$group.min_value", "aggregate.1.$group.max_value"],
        "examples": [
            "find minimum and maximum prices by product category",
            "get lowest and highest temperatures by month",
            "calculate minimum and maximum order values by customer"
        ]
    }
}

class QueryDataset(Dataset):
    def __init__(self, texts: List[str], labels: List[int], tokenizer: BertTokenizer, max_length: int = 128):
        self.texts = texts
        self.labels = labels
        self.tokenizer = tokenizer
        self.max_length = max_length

    def __len__(self):
        return len(self.texts)

    def __getitem__(self, idx):
        text = str(self.texts[idx])
        label = self.labels[idx]

        encoding = self.tokenizer(
            text,
            truncation=True,
            padding='max_length',
            max_length=self.max_length,
            return_tensors='pt'
        )

        return {
            'input_ids': encoding['input_ids'].flatten(),
            'attention_mask': encoding['attention_mask'].flatten(),
            'labels': torch.tensor(label, dtype=torch.long)
        }

class QueryClassifierTrainer:
    def __init__(self, model_save_path: str = "models/query_classifier"):
        self.model_save_path = Path(model_save_path)
        self.model_save_path.parent.mkdir(parents=True, exist_ok=True)
        self.tokenizer = BertTokenizer.from_pretrained('bert-base-uncased')
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.template_to_idx = {name: idx for idx, name in enumerate(QUERY_TEMPLATES.keys())}
        self.idx_to_template = {idx: name for name, idx in self.template_to_idx.items()}
        # Initialize history for learning curve
        self.training_history = {
            'train_accuracy': [],
            'val_accuracy': [],
            'epochs': []
        }
    
    def generate_synthetic_data(self) -> Tuple[List[str], List[int]]:
        """Generate additional synthetic training examples"""
        synthetic_texts = []
        synthetic_labels = []
        
        field_examples = {
            'user': ['name', 'age', 'email', 'country', 'status', 'registration_date', 'login_count', 'subscription_type'],
            'product': ['category', 'price', 'stock', 'rating', 'brand', 'color', 'size', 'weight', 'material'],
            'order': ['date', 'total', 'status', 'quantity', 'customer_id', 'shipping_method', 'payment_type', 'discount'],
            'metric': ['value', 'timestamp', 'type', 'source', 'unit', 'accuracy', 'device_id', 'location'],
            'document': ['title', 'author', 'published_date', 'content', 'tags', 'views', 'comments', 'likes']
        }
        
        for template_name, template_info in QUERY_TEMPLATES.items():
            base_examples = template_info['examples']
            
            # Generate variations
            for base in base_examples:
                for entity, fields in field_examples.items():
                    for field in fields:
                        # Replace generic terms with specific fields
                        new_example = base.replace('FIELD', field)\
                                        .replace('category', field)\
                                        .replace('status', field)\
                                        .replace('price', field)
                        synthetic_texts.append(new_example)
                        synthetic_labels.append(self.template_to_idx[template_name])
                        
        return synthetic_texts, synthetic_labels

    def prepare_data(self, query_logs_path: str) -> Tuple[List[str], List[int]]:
        """Process query logs and prepare training data"""
        texts = []
        labels = []
        
        # Load real query logs
        if Path(query_logs_path).exists():
            with open(query_logs_path, 'r') as f:
                logs = [json.loads(line) for line in f]
            
            for log in logs:
                nlp_query = log['nlp_query']
                mongodb_query = log['mongodb_query']
                template_type = self._identify_template_type(mongodb_query)
                if template_type:
                    texts.append(nlp_query)
                    labels.append(self.template_to_idx[template_type])
        
        # Add template examples
        for template_name, template_info in QUERY_TEMPLATES.items():
            texts.extend(template_info['examples'])
            labels.extend([self.template_to_idx[template_name]] * len(template_info['examples']))
        
        # Add synthetic data
        synthetic_texts, synthetic_labels = self.generate_synthetic_data()
        texts.extend(synthetic_texts)
        labels.extend(synthetic_labels)
        
        logger.info(f"Prepared {len(texts)} training examples")
        return texts, labels

    def _identify_template_type(self, query: Dict) -> str:
        """Match a query to a template type"""
        try:
            # Handle None or invalid queries
            if not query or not isinstance(query, dict):
                logger.warning(f"Invalid query format: {query}")
                return None

            # Aggregate pipeline queries
            if 'aggregate' in query and isinstance(query['aggregate'], list):
                pipeline = query['aggregate']
                
                for stage in pipeline:
                    if not isinstance(stage, dict):
                        continue
                        
                    # Time series check
                    if '$group' in stage and isinstance(stage['$group'], dict):
                        group_stage = stage['$group']
                        if '_id' in group_stage and isinstance(group_stage['_id'], dict):
                            if '$dateToString' in group_stage['_id']:
                                return 'time_series_aggregation'
                    
                    # Min/max aggregation check
                    if '$group' in stage and isinstance(stage['$group'], dict):
                        group_stage = stage['$group']
                        if '$min' in str(group_stage) and '$max' in str(group_stage):
                            return 'min_max_aggregation'
                    
                    # Count/sum check
                    if '$group' in stage and any('$sum' in v for v in stage['$group'].values() if isinstance(v, dict)):
                        return 'aggregation_count'
                    
                    # Average check    
                    if '$group' in stage and any('$avg' in v for v in stage['$group'].values() if isinstance(v, dict)):
                        return 'average_calculation'
                
                # Distinct values check
                if len(pipeline) >= 2:
                    if '$group' in pipeline[0] and '$sort' in pipeline[1]:
                        return 'distinct_values'

            # Filter queries
            elif 'filter' in query and isinstance(query['filter'], dict):
                filter_query = query['filter']
                
                # Full text search
                if '$text' in filter_query:
                    return 'full_text_search'
                
                # Exists query
                if any('$exists' in v if isinstance(v, dict) else False for v in filter_query.values()):
                    return 'exists_query'
                
                # Array contains
                if any('$in' in v if isinstance(v, dict) else False for v in filter_query.values()):
                    return 'array_contains'
                
                # Range query
                if any(isinstance(v, dict) and '$gte' in v and '$lte' in v for v in filter_query.values()):
                    return 'range_query'
                
                # Nested field query
                if any('.' in k for k in filter_query.keys()):
                    return 'nested_field_query'
                
                # Complex filter with AND
                if '$and' in filter_query:
                    return 'complex_filter'
                
                # Top N query - check for sort and limit
                if 'sort' in query and 'limit' in query:
                    return 'top_n_query'
                
                # Default to simple filter
                return 'simple_filter'

            logger.warning(f"No matching template found for query: {query}")
            return None
            
        except Exception as e:
            logger.warning(f"Error identifying template type: {str(e)}")
            return None
    
    def train(self, query_logs_path: str, epochs: int = 5, batch_size: int = 16, learning_rate: float = 2e-5):
        """Train the BERT classifier"""
        
        try:
            # Verify query logs exist
            if not Path(query_logs_path).exists():
                raise FileNotFoundError(f"Query logs file not found: {query_logs_path}")
                
            # Prepare data
            logger.info("Preparing training data...")
            texts, labels = self.prepare_data(query_logs_path)
            
            if len(texts) < batch_size:
                logger.warning(f"Very few training examples ({len(texts)}). Consider reducing batch_size.")
                batch_size = max(1, len(texts) // 2)
            
            logger.info(f"Starting training with {len(texts)} examples, batch size {batch_size}")
            
            # Prepare data
            texts, labels = self.prepare_data(query_logs_path)
            X_train, X_val, y_train, y_val = train_test_split(texts, labels, test_size=0.2, random_state=42)

            # Create datasets
            train_dataset = QueryDataset(X_train, y_train, self.tokenizer)
            val_dataset = QueryDataset(X_val, y_val, self.tokenizer)

            train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
            val_loader = DataLoader(val_dataset, batch_size=batch_size)

            # Initialize model
            model = BertForSequenceClassification.from_pretrained(
                'bert-base-uncased',
                num_labels=len(self.template_to_idx)
            ).to(self.device)

            optimizer = AdamW(model.parameters(), lr=learning_rate)

            # Reset training history
            self.training_history = {
                'train_accuracy': [],
                'val_accuracy': [],
                'epochs': []
            }

            # Training loop
            best_accuracy = 0
            for epoch in range(epochs):
                model.train()
                total_loss = 0
                correct_train = 0
                total_train = 0
                
                progress_bar = tqdm(train_loader, desc=f'Epoch {epoch + 1}/{epochs}')
                
                for batch in progress_bar:
                    optimizer.zero_grad()
                    
                    input_ids = batch['input_ids'].to(self.device)
                    attention_mask = batch['attention_mask'].to(self.device)
                    labels = batch['labels'].to(self.device)

                    outputs = model(
                        input_ids=input_ids,
                        attention_mask=attention_mask,
                        labels=labels
                    )

                    loss = outputs.loss
                    total_loss += loss.item()
                    
                    # Calculate training accuracy
                    predictions = torch.argmax(outputs.logits, dim=1)
                    correct_train += (predictions == labels).sum().item()
                    total_train += labels.size(0)
                    
                    loss.backward()
                    optimizer.step()

                    progress_bar.set_postfix({'loss': total_loss / (progress_bar.n + 1)})

                # Calculate training accuracy for the epoch
                train_accuracy = correct_train / total_train
                
                # Validation
                model.eval()
                val_accuracy = self._validate(model, val_loader)
                
                # Store metrics for learning curve
                self.training_history['train_accuracy'].append(train_accuracy)
                self.training_history['val_accuracy'].append(val_accuracy)
                self.training_history['epochs'].append(epoch + 1)
                
                logger.info(f"Epoch {epoch + 1}/{epochs}, Train Accuracy: {train_accuracy:.4f}, Validation Accuracy: {val_accuracy:.4f}")

                # Save best model
                if val_accuracy > best_accuracy:
                    best_accuracy = val_accuracy
                    model.save_pretrained(self.model_save_path)
                    self.tokenizer.save_pretrained(self.model_save_path)

            logger.info(f"Training completed. Best validation accuracy: {best_accuracy:.4f}")
            
            # Generate and save learning curve
            self._plot_learning_curve()
            
            return best_accuracy
            
            
        except Exception as e:
            logger.error(f"Training error: {str(e)}")
            raise

    def _validate(self, model: BertForSequenceClassification, val_loader: DataLoader) -> float:
        """Validate the model"""
        correct = 0
        total = 0
        
        with torch.no_grad():
            for batch in val_loader:
                input_ids = batch['input_ids'].to(self.device)
                attention_mask = batch['attention_mask'].to(self.device)
                labels = batch['labels'].to(self.device)

                outputs = model(input_ids=input_ids, attention_mask=attention_mask)
                predictions = torch.argmax(outputs.logits, dim=1)
                
                correct += (predictions == labels).sum().item()
                total += labels.size(0)

        return correct / total
    
    def _plot_learning_curve(self):
        """Generate and save learning curve plot"""
        plt.figure(figsize=(10, 6))
        plt.plot(self.training_history['epochs'], self.training_history['train_accuracy'], 'b-', label='Training Accuracy')
        plt.plot(self.training_history['epochs'], self.training_history['val_accuracy'], 'r-', label='Validation Accuracy')
        plt.title('Learning Curve: Model Accuracy over Training Epochs')
        plt.xlabel('Epochs')
        plt.ylabel('Accuracy')
        plt.legend()
        plt.grid(True)
        plt.tight_layout()
        
        # Save the figure
        plot_dir = Path("logs")
        plot_dir.mkdir(exist_ok=True)
        plt.savefig(plot_dir / "learning_curve.png")
        logger.info(f"Learning curve saved to logs/learning_curve.png")
        plt.close()

def train_classifier():
    """Main training function"""
    trainer = QueryClassifierTrainer()
    accuracy = trainer.train("logs/query_logs.json")
    logger.info(f"Training completed with final accuracy: {accuracy}")

if __name__ == "__main__":
    train_classifier()