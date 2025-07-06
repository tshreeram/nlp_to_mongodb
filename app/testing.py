import json
import logging
from pymongo import MongoClient
from nl2query import NL2Query  # You'll need to install this package

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("NL2Query_Test")

# MongoDB connection settings - replace with your actual connection info
MONGODB_URI = "mongodb://localhost:27017/"
DATABASE_NAME = "testDB"

# Connect to MongoDB
client = MongoClient(MONGODB_URI)
db = client[DATABASE_NAME]

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

def test_nl2query(collection_name, natural_language_query):
    """
    Test nl2query with a specific collection and query
    """
    try:
        # Get collection schema
        schema = get_collection_schema(collection_name)
        
        # Initialize NL2Query
        nl2query_engine = NL2Query(db_type="mongodb")
        
        # Generate query
        logger.info(f"Testing query: '{natural_language_query}' on collection '{collection_name}'")
        query_config = nl2query_engine.generate(
            query=natural_language_query,
            schema=schema
        )
        
        # Log the generated query
        logger.info(f"Generated query configuration:\n{json.dumps(query_config, indent=2)}")
        
        # Execute the query to test results
        collection = db[collection_name]
        
        # This part may need adjustment based on nl2query's output format
        if 'aggregate' in query_config:
            results = list(collection.aggregate(query_config['aggregate']))
        else:
            results = list(collection.find(
                query_config.get('filter', {}),
                query_config.get('projection', None)
            ).limit(10))
        
        # Print summary of results
        logger.info(f"Query returned {len(results)} results")
        
        # Print a sample result (first 2 items)
        if results:
            sample = results[:2]
            logger.info(f"Sample results:\n{json.dumps(sample, indent=2, default=str)}")
        
        return {
            "query_config": query_config,
            "result_count": len(results),
            "sample_results": results[:2] if results else []
        }
        
    except Exception as e:
        logger.error(f"Error testing nl2query: {str(e)}")
        return {"error": str(e)}

def run_test_suite():
    """
    Run a suite of test queries to evaluate nl2query performance
    """
    # List of collections to test
    collections = db.list_collection_names()
    
    if not collections:
        logger.error("No collections found in database")
        return
    
    # Select a collection for testing
    test_collection = collections[0]
    logger.info(f"Using collection: {test_collection}")
    
    # Test queries - add your own examples based on your data
    test_queries = [
        "Show me all records",
        "Count how many documents are in the collection",
        "Find documents where the status is active",
        "What's the average value of the price field?",
        "Group documents by category and count them"
    ]
    
    # Run each test query
    results = {}
    for query in test_queries:
        results[query] = test_nl2query(test_collection, query)
    
    # Save results to a file
    with open("nl2query_test_results.json", "w") as f:
        json.dump(results, f, indent=2, default=str)
    
    logger.info("Test results saved to nl2query_test_results.json")

if __name__ == "__main__":
    # Run the test suite
    run_test_suite()
    
    # Or test a specific query
    # result = test_nl2query("your_collection", "your specific query here")
    # print(json.dumps(result, indent=2, default=str))