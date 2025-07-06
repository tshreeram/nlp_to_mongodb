from flask import Blueprint, render_template, flash, redirect, url_for, request, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from flask import current_app as app
from app import db
import pandas as pd
from pathlib import Path
from datetime import datetime
from app.models import User, Message
from app.forms import LoginForm, RegistrationForm, ChatForm
from app.gemini_api import generate_response,get_available_collections, get_collection_context, get_collection_schema, execute_mongodb_query, generate_mongodb_query, log_query, parse_ai_response
from config import Config
import json
import shutil
from app.data_manager import DataManager


bp = Blueprint('main', __name__)

@bp.route('/')
@bp.route('/index')
@login_required
def index():
    form = ChatForm()
    
    # messages = Message.query.filter_by(user_id=current_user.id).order_by(Message.timestamp.asc()).all()
    
    messages = []
           
    return render_template('index.html', title='Home', form=form, messages=messages)

@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        Message.query.filter_by(user_id=current_user.id).delete()
        return redirect(url_for('main.index'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user is None or not user.check_password(form.password.data):
            flash('Invalid username or password')
            return redirect(url_for('main.login'))
        login_user(user)
        return redirect(url_for('main.index'))
    return render_template('login.html', title='Sign In', form=form)

@bp.route('/logout')
def logout():
    if current_user.is_authenticated:
        # Delete all messages associated with the user
        Message.query.filter_by(user_id=current_user.id).delete()
        db.session.commit()
        
        # Clean up cache directory
        cache_dir = Path("logs/cache")
        if cache_dir.exists():
            shutil.rmtree(cache_dir)
            cache_dir.mkdir(parents=True, exist_ok=True)
    
    logout_user()
    return redirect(url_for('main.index'))

@bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(username=form.username.data, email=form.email.data)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash('Congratulations, you are now a registered user!')
        return redirect(url_for('main.login'))
    return render_template('register.html', title='Register', form=form)


@bp.route('/chat', methods=['POST'])
@login_required
def chat():
    form = ChatForm()
    
    # For AJAX requests, handle form data manually
    if request.is_json:
        data = request.get_json()
        form.message.data = data.get('message', '')
        selected_collection = data.get('selected_collection', '')
    else:
        selected_collection = request.form.get('selected_collection', '')
    
    # Check form validation 
    if form.validate() or request.is_json:
        # Get message from form or request data
        user_message_content = form.message.data if form.message.data else request.form.get('message', '')
        
        if not user_message_content:
            return jsonify({'error': 'No message provided'}), 400
            
        # Save user message
        user_message = Message(content=user_message_content, author=current_user)
        db.session.add(user_message)
        
        try:
            # Initialize response string
            full_response = ""
            
            # If a collection is selected, attempt to query the database
            if selected_collection:
                # Get schema and generate query configuration
                schema = get_collection_schema(selected_collection)
                query_config = generate_mongodb_query(user_message_content, schema)
                
                # Execute query if configuration is not empty
                if query_config and (query_config.get('filter') or query_config.get('aggregate')):
                    query_results = execute_mongodb_query(selected_collection, query_config)
                    
                    # Format query configuration as nicely formatted JSON
                    query_config_formatted = json.dumps(query_config, indent=4)
                    
                    if query_results:
                        dm = DataManager()
                        cache_file = dm.cache_results(query_results)
                        table_preview = dm.format_table_preview(query_results)
                        
                        # Build the response with proper formatting and spacing
                        full_response = f"""
                        <div class="query-result-container">
                            <div class="query-details mb-4">
                                <h5>Query Details:</h5>
                                <pre class="query-code"><code>{query_config_formatted}</code></pre>
                            </div>
                            
                            <div class="table-responsive">
                                <h5>Results Preview:</h5>
                                {table_preview}
                            </div>
                            
                            <div class="view-full-data mt-3">
                                <a href="{url_for('main.view_full_data', filename=Path(cache_file).name)}" 
                                   class="btn btn-primary" target="_blank">View Full Data</a>
                            </div>
                        </div>
                        """
                    else:
                        full_response = f"""
                        <div class="query-result-container">
                            <div class="query-details mb-4">
                                <h5>Query Details:</h5>
                                <pre class="query-code"><code>{query_config_formatted}</code></pre>
                            </div>
                            
                            <div class="alert alert-info">
                                No results found for this query.
                            </div>
                        </div>
                        """
                    
                    # Log query details
                    log_query(
                        username=current_user.username,
                        nlp_query=user_message_content,
                        mongodb_query=query_config
                    )
                else:
                    full_response = """
                    <div class="alert alert-warning">
                        I couldn't generate a valid database query from your request. 
                        Please try rephrasing or provide more specific details.
                    </div>
                    """
            else:
                # For non-collection queries, get the direct response
                full_response = generate_response(user_message_content)
            
            # Save bot message
            bot_message = Message(content=full_response, author=current_user, is_bot=True)
            db.session.add(bot_message)
            db.session.commit()

            return jsonify({
                'user_message': user_message.content,
                'bot_message': full_response
            })
            
        except Exception as e:
            app.logger.error(f"Error in chat route: {str(e)}")
            error_response = f"""
            <div class="alert alert-danger">
                <strong>Error:</strong> {str(e)}
            </div>
            """
            
            # Save error message
            bot_message = Message(content=error_response, author=current_user, is_bot=True)
            db.session.add(bot_message)
            db.session.commit()
            
            return jsonify({
                'user_message': user_message.content,
                'bot_message': error_response
            })
    
    return jsonify({'error': 'Invalid form submission'}), 400


@bp.route('/collections')
@login_required
def list_collections():
    """
    Dynamically return list of available MongoDB collections
    """
    collections = get_available_collections()
    return jsonify(collections)

@bp.route('/collection_schema/<collection_name>')
@login_required
def get_schema(collection_name):
    """
    Return schema for a selected collection
    """
    schema = get_collection_schema(collection_name)
    return jsonify(schema)


@bp.route('/full_data/<filename>/data')
@login_required
def get_visualization_data(filename):
    """Return the cached data as JSON for visualization"""
    cache_file = Path("logs/cache") / filename
    try:
        with open(cache_file) as f:
            data = json.load(f)
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@bp.route('/full_data/<filename>')
@login_required
def view_full_data(filename):
    cache_file = Path("logs/cache") / filename
    try:
        with open(cache_file) as f:
            data = json.load(f)
        
        # Ensure data is a list of dictionaries
        if isinstance(data, list) and all(isinstance(item, dict) for item in data):
            df = pd.DataFrame(data)
            return render_template('full_data.html', 
                                 table=df.to_html(classes='table table-striped', index=False),
                                 columns=df.columns.tolist())  # Pass columns for sorting
        else:
            flash("Invalid data format in cache file.")
            return redirect(url_for('main.index'))
    except Exception as e:
        flash(f"Error loading data: {str(e)}")
        return redirect(url_for('main.index'))