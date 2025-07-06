from pathlib import Path
import json
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import tempfile
from datetime import datetime
import os

class DataManager:
    def __init__(self):
        self.cache_dir = Path("logs/cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
    def cache_results(self, query_results, query_id=None):
        # Ensure data is in a list of dictionaries format
        if isinstance(query_results, dict):
            formatted_results = [query_results]
        elif isinstance(query_results, list) and (not query_results or not isinstance(query_results[0], dict)):
            formatted_results = [{"value": item} for item in query_results]
        else:
            formatted_results = query_results
            
        query_id = query_id or datetime.now().strftime('%Y%m%d_%H%M%S')
        cache_file = self.cache_dir / f'query_{query_id}.json'
        
        with open(cache_file, 'w') as f:
            json.dump(formatted_results, f)
        return cache_file

    def format_table_preview(self, data):
        """
        Format query results into a clean HTML table with proper styling.
        Handles nested data and limits preview size for large datasets.
        """
        # Ensure data is compatible with pandas
        if isinstance(data, dict):
            df = pd.DataFrame([data])
        elif isinstance(data, list) and (not data or not isinstance(data[0], dict)):
            df = pd.DataFrame({"value": data})
        else:
            # Handle nested data like aggregation results
            if len(data) == 1 and 'employees' in data[0]:
                df = pd.DataFrame(data[0]['employees'])
            else:
                df = pd.DataFrame(data)
        
        # Flatten nested dictionaries for better display
        flattened_df = self._flatten_nested_columns(df)
            
        # Limit preview size for large datasets
        if len(flattened_df) > 10:
            preview = pd.concat([
                flattened_df.head(5),
                pd.DataFrame([{col: '...' for col in flattened_df.columns}]),
                flattened_df.tail(5)
            ])
        else:
            preview = flattened_df
            
        # Generate HTML with enhanced styling for readability
        html_table = preview.to_html(
            classes='table table-striped table-bordered table-hover', 
            index=False,
            escape=False,
            render_links=True,
            border=0
        )
        
        # Add responsive wrapper for better mobile display
        styled_table = f"""
        <div class="table-responsive">
            {html_table}
        </div>
        """
        
        return styled_table
    
    def _flatten_nested_columns(self, df):
        """Flatten nested dictionary columns for better display in tables"""
        # Make a copy to avoid modifying the original dataframe
        flat_df = df.copy()
        
        # Find dictionary columns that need flattening
        dict_columns = [col for col in flat_df.columns if isinstance(flat_df[col].iloc[0], dict) if len(flat_df) > 0]
        
        # Flatten each dictionary column
        for col in dict_columns:
            # Extract the dictionaries into a temporary dataframe
            nested_df = pd.json_normalize(flat_df[col])
            
            # Rename columns to show the hierarchy
            nested_df = nested_df.rename(columns={key: f"{col}.{key}" for key in nested_df.columns})
            
            # Drop the dictionary column and join with the flattened columns
            flat_df = flat_df.drop(columns=[col]).join(nested_df)
        
        return flat_df