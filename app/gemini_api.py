import google.generativeai as genai
from config import Config
from pymongo import MongoClient
import json
from bson import ObjectId
import logging
import os
import re
import ast
from datetime import datetime
from flask import current_app as app
from app.query_classifier import QueryClassifier, HybridQueryGenerator

# Initialize the classifier and hybrid generator
query_classifier = QueryClassifier()
hybrid_generator = HybridQueryGenerator(query_classifier)

# Set up logging for AI debugging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("AI_Query_Generator")


# MongoDB Connection
client = MongoClient(Config.MONGODB_URI)
db = client[Config.DATABASE_NAME]

def get_available_collections():
    """
    Dynamically retrieves the list of collections in the database
    """
    return db.list_collection_names()


def get_collection_context(collection_name):
    """
    Generate a contextual prompt about the collection schema
    """
    schema = get_collection_schema(collection_name)
    return f"""
    Context for {collection_name} collection:
    Available Fields: {', '.join(schema.keys())}
    Field Types: {json.dumps(schema)}

    When user asks about this collection, you can:
    1. Translate natural language to MongoDB queries
    2. Provide insights based on the collection's structure
    3. Help user explore data intelligently
    """

def get_collection_schema(collection_name):
    """
    Retrieves schema/keys of a specific MongoDB collection
    """
    collection = db[collection_name]
    # Take a sample document to understand the structure
    sample_doc = collection.find_one()
    
    if sample_doc:
        # Extract keys and their types
        schema = {key: type(value).__name__ for key, value in sample_doc.items()}
        return schema
    return {}


def analyze_query_pattern(query_text):
    """
    Analyzes the natural language query to identify the query pattern
    and extract relevant components.
    """
    # Common query pattern indicators
    patterns = {
        'distinct_values': {
            'indicators': ['what are', 'list', 'show', 'different', 'unique', 'distinct', 'all'],
            'operations': ['$group', '$distinct']
        },
        'counting': {
            'indicators': ['how many', 'count', 'total number', 'number of'],
            'operations': ['$count', '$sum']
        },
        'aggregation': {
            'indicators': ['average', 'mean', 'highest', 'lowest', 'maximum', 'minimum', 'sum'],
            'operations': ['$avg', '$max', '$min', '$sum']
        },
        'filtering': {
            'indicators': ['where', 'with', 'has', 'in', 'for', 'by'],
            'operations': ['$match', '$filter']
        }
    }
    
    # Analyze query for patterns
    identified_patterns = []
    for pattern_type, pattern_info in patterns.items():
        if any(indicator in query_text.lower() for indicator in pattern_info['indicators']):
            identified_patterns.append({
                'type': pattern_type,
                'operations': pattern_info['operations']
            })
    
    return identified_patterns

def analyze_schema_capabilities(collection_schema):
    """
    Analyzes the collection schema to understand available fields
    and their potential operations.
    """
    field_capabilities = {}
    
    for field, field_type in collection_schema.items():
        if field == '_id':
            continue
            
        capabilities = {
            'type': field_type,
            'operations': []
        }
        
        # Determine possible operations based on field type
        if field_type in ['int', 'float', 'number']:
            capabilities['operations'].extend(['$sum', '$avg', '$min', '$max', '$group'])
            
        elif field_type in ['str', 'string']:
            capabilities['operations'].extend(['$group', '$match', '$regex'])
            
        elif field_type == 'dict':
            capabilities['operations'].extend(['$unwind', '$match'])
            
        elif field_type == 'list':
            capabilities['operations'].extend(['$unwind', '$size'])
            
        field_capabilities[field] = capabilities
    
    return field_capabilities

def generate_mongodb_query(natural_language_query, collection_schema):
    """
    Hybrid query generation system that combines neural classification and LLM generation
    while maintaining all original features
    """
    try:
        # Step 1: Analyze the query pattern (maintaining original functionality)
        query_patterns = analyze_query_pattern(natural_language_query)
        
        # Step 2: Analyze schema capabilities (maintaining original functionality)
        field_capabilities = analyze_schema_capabilities(collection_schema)
        
        # Step 3: Define the LLM generator function that preserves all original context
        def llm_generator(query, schema):
            # Preserve the original detailed prompt structure
            prompt = f"""
            As a MongoDB query expert, generate a query configuration based on the following analysis:

            Query Analysis:
            - Identified Patterns: {json.dumps([p['type'] for p in query_patterns])}
            - Supported Operations: {json.dumps([op for p in query_patterns for op in p['operations']])}

            Schema Analysis:
            {json.dumps(field_capabilities, indent=2)}

            Natural Language Query: "{query}"

            Generate a query configuration that:
            1. Uses the appropriate operations based on identified patterns
            2. Considers the field capabilities from the schema
            3. Returns results in a meaningful order
            4. Includes proper aggregation stages when needed

            Return ONLY a JSON object with these possible keys:
            - filter: for basic filtering
            - projection: for field selection
            - sort: for sorting results
            - limit: for result limitation
            - aggregate: for aggregation pipeline (as array)
            """

            # Generate and validate query as in original
            genai.configure(api_key=Config.GEMINI_API_KEY)
            model = genai.GenerativeModel('gemini-1.5-pro')
            
            logger.info(f"Generating query with enriched prompt:\n{prompt}")
            response = model.generate_content(prompt)
            logger.info(f"Raw AI Response:\n{response.text}")
            
            return parse_ai_response(response.text)
        
        # Step 4: Use hybrid generator with full context
        query_config = hybrid_generator.generate_query(
            natural_language_query,
            collection_schema,
            llm_generator
        )
        
        if not query_config:
            logger.error("Failed to generate valid query configuration")
            return {}

        # Step 5: Post-process and optimize query (maintaining original functionality)
        result = optimize_query_config(query_config, query_patterns, field_capabilities)
        
        logger.info(f"Final hybrid query configuration:\n{json.dumps(result, indent=2)}")
        return result
        
    except Exception as e:
        logger.error(f"Query generation error: {str(e)}")
        return {}

def optimize_query_config(query_config, patterns, capabilities):
    """
    Post-process and optimize the generated query configuration.
    """
    result = {
        "filter": {},
        "projection": None,
        "sort": None,
        "limit": None,
        "aggregate": None
    }
    
    try:
        # Convert standalone operations to aggregate pipeline when appropriate
        if any(p['type'] in ['distinct_values', 'counting', 'aggregation'] for p in patterns):
            pipeline = []
            
            # Handle filtering first if present
            if query_config.get('filter'):
                pipeline.append({'$match': query_config['filter']})
            
            # Add group/aggregate operations
            if query_config.get('aggregate'):
                if isinstance(query_config['aggregate'], list):
                    pipeline.extend(query_config['aggregate'])
                else:
                    pipeline.append(query_config['aggregate'])
                    
            # Ensure proper sorting
            if not any('$sort' in stage for stage in pipeline):
                if any('$group' in stage for stage in pipeline):
                    pipeline.append({'$sort': {'_id': 1}})
                    
            result['aggregate'] = pipeline
            
        else:
            # For simple queries, maintain original structure
            result.update({k: v for k, v in query_config.items() if v is not None})
            
        return result
        
    except Exception as e:
        logger.error(f"Error optimizing query config: {str(e)}")
        return result

def execute_mongodb_query(collection_name, query_config, default_limit=10):
    """
    Execute MongoDB queries based on query configuration
    """
    try:
        collection = db[collection_name]
        
        # Handle aggregation pipeline
        if query_config.get('aggregate'):
            if not isinstance(query_config['aggregate'], list):
                # Convert to list if it's not already
                pipeline = [query_config['aggregate']] if query_config['aggregate'] else []
            else:
                pipeline = query_config['aggregate']
            results = list(collection.aggregate(pipeline))
            return _serialize_results(results)
        
        # Handle regular queries
        filter_query = query_config.get('filter', {})
        projection = query_config.get('projection')
        sort = query_config.get('sort')
        limit = query_config.get('limit', default_limit)
        
        # Build the query
        if projection:
            cursor = collection.find(filter_query, projection)
        else:
            cursor = collection.find(filter_query)
        
        # Apply sort if specified
        if sort:
            # Convert sort dictionary to list of tuples if necessary
            if isinstance(sort, dict):
                sort_list = [(k, v) for k, v in sort.items()]
                cursor = cursor.sort(sort_list)
            else:
                cursor = cursor.sort(sort)
            
        # Apply limit
        if limit:
            cursor = cursor.limit(limit)
        
        # Execute and serialize results
        results = list(cursor)
        return _serialize_results(results)
        
    except Exception as e:
        logger.error(f"Error executing MongoDB query: {str(e)}")
        return {"error": str(e)}
    
def _serialize_results(results):
    """
    Helper function to serialize MongoDB results
    """
    def serialize_value(v):
        if isinstance(v, ObjectId):
            return str(v)
        if isinstance(v, dict):
            return {k: serialize_value(v) for k, v in v.items()}
        if isinstance(v, list):
            return [serialize_value(x) for x in v]
        return v
    
    return [
        {k: serialize_value(v) for k, v in doc.items()}
        for doc in results
    ]
    
def generate_response(prompt, selected_collection=None):
    """
    Enhanced response generation with optional collection context.
    Now returns only essential information without additional narrative.
    """
    genai.configure(api_key=Config.GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-1.5-pro')
    
    if selected_collection:
        # If we're querying a collection, we don't need additional narrative
        # The query results will speak for themselves
        return ""  # Return empty string since we'll append query details and results
    else:
        # For non-collection queries, just return the direct response
        try:
            response = model.generate_content(prompt)
            return response.text
        except Exception as e:
            logger.error(f"Error generating response: {str(e)}")
            return "Error generating response."

def parse_ai_response(ai_response):
    """
    Parse and clean AI response, ensuring it's valid JSON.
    Returns a dictionary of the parsed response or None if parsing fails.
    """
    try:
        # Remove code block markers if present
        cleaned_response = ai_response
        if "```" in cleaned_response:
            # Extract content between code block markers
            pattern = r"```(?:json|JSON)?\n?(.*?)```"
            match = re.search(pattern, cleaned_response, re.DOTALL)
            if match:
                cleaned_response = match.group(1)
        
        # Strip whitespace and normalize line endings
        cleaned_response = cleaned_response.strip()
        
        # Log the cleaned response for debugging
        logger.info(f"Cleaned AI Response: {repr(cleaned_response)}")
        
        # Attempt to parse as JSON
        return json.loads(cleaned_response)
    
    except json.JSONDecodeError as e:
        logger.error(f"JSON parsing error: {str(e)}")
        logger.error(f"Failed to parse response: {repr(cleaned_response)}")
        try:
            # Fallback to literal_eval for Python dict-like responses
            return ast.literal_eval(cleaned_response)
        except (SyntaxError, ValueError) as e:
            logger.error(f"Literal eval failed: {str(e)}")
            return None
    except Exception as e:
        logger.error(f"Unexpected error parsing response: {str(e)}")
        return None

#helper functions
def log_query(username, nlp_query, mongodb_query):
    """
    Enhanced logging function that captures more details about the query execution
    """
    try:
        # Determine query type based on mongodb_query structure
        query_type = "unknown"
        if mongodb_query.get('aggregate'):
            if any('$group' in stage for stage in mongodb_query['aggregate']):
                query_type = "grouping"
            elif any('$count' in stage for stage in mongodb_query['aggregate']):
                query_type = "counting"
            else:
                query_type = "aggregation"
        elif mongodb_query.get('filter'):
            query_type = "filtering"

        log_data = {
            "username": username,
            "timestamp": datetime.utcnow().isoformat(),
            "nlp_query": nlp_query,
            "mongodb_query": mongodb_query,
            "query_type": query_type
        }

        log_dir = "logs"
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, "query_logs.json")

        with open(log_file, "a") as f:
            f.write(json.dumps(log_data) + "\n")
            
        # Also log to application logger for monitoring
        logger.info(f"Query logged - Type: {query_type}, User: {username}")
            
    except Exception as e:
        logger.error(f"Error logging query: {str(e)}")