import os
import logging
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv

# Add parent directory to path for imports
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot.database import get_session, User, init_db

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__, template_folder='templates')

# Available curators for each sphere
CURATORS = {
    "business": [
        {"id": "coach", "name": "Коуч", "description": "Строгий бизнес-коуч"},
        {"id": "friend", "name": "Друг", "description": "Дружелюбный наставник"}
    ],
    "soul": [
        {"id": "empathy", "name": "Эмпат", "description": "Эмпатичный психолог"},
        {"id": "mindfulness", "name": "Осознанность", "description": "Мастер осознанности"}
    ],
    "body": [
        {"id": "strict", "name": "Строгий", "description": "Строгий тренер"},
        {"id": "relaxed", "name": "Расслабленный", "description": "Расслабленный подход"}
    ]
}


@app.route('/curator-choice')
def curator_choice():
    """Render the curator choice page."""
    user_id = request.args.get('user_id')
    logger.info(f"Curator choice page requested for user_id: {user_id}")
    
    if not user_id:
        logger.error("No user_id provided")
        return "Error: user_id is required", 400
    
    try:
        telegram_id = int(user_id)
    except ValueError:
        logger.error(f"Invalid user_id: {user_id}")
        return "Error: invalid user_id", 400
    
    # Get user data
    with get_session() as session:
        user = session.query(User).filter(User.telegram_id == telegram_id).first()
        
        if not user:
            logger.error(f"User not found: {telegram_id}")
            return "Error: user not found", 404
        
        user_data = {
            "telegram_id": user.telegram_id,
            "recommended_business": user.recommended_business,
            "recommended_soul": user.recommended_soul,
            "recommended_body": user.recommended_body,
            "selected_business": user.selected_business,
            "selected_soul": user.selected_soul,
            "selected_body": user.selected_body
        }
    
    logger.info(f"Rendering curator choice for user {telegram_id}")
    
    return render_template(
        'curator_choice.html',
        user=user_data,
        curators=CURATORS
    )


@app.route('/api/select-curator', methods=['POST'])
def select_curator():
    """API endpoint to select a curator for a sphere."""
    data = request.get_json()
    
    if not data:
        logger.error("No JSON data provided")
        return jsonify({"error": "No data provided"}), 400
    
    telegram_id = data.get('user_id')
    sphere = data.get('sphere')
    curator = data.get('curator')
    
    logger.info(f"Select curator request: user={telegram_id}, sphere={sphere}, curator={curator}")
    
    if not all([telegram_id, sphere, curator]):
        logger.error("Missing required fields")
        return jsonify({"error": "Missing required fields: user_id, sphere, curator"}), 400
    
    # Validate sphere
    if sphere not in CURATORS:
        logger.error(f"Invalid sphere: {sphere}")
        return jsonify({"error": f"Invalid sphere: {sphere}"}), 400
    
    # Validate curator
    valid_curators = [c["id"] for c in CURATORS[sphere]]
    if curator not in valid_curators:
        logger.error(f"Invalid curator {curator} for sphere {sphere}")
        return jsonify({"error": f"Invalid curator: {curator}"}), 400
    
    try:
        telegram_id = int(telegram_id)
    except ValueError:
        logger.error(f"Invalid user_id: {telegram_id}")
        return jsonify({"error": "Invalid user_id"}), 400
    
    # Update user's selected curator
    with get_session() as session:
        user = session.query(User).filter(User.telegram_id == telegram_id).first()
        
        if not user:
            logger.error(f"User not found: {telegram_id}")
            return jsonify({"error": "User not found"}), 404
        
        if sphere == "business":
            user.selected_business = curator
        elif sphere == "soul":
            user.selected_soul = curator
        elif sphere == "body":
            user.selected_body = curator
        
        logger.info(f"Updated {sphere} curator to {curator} for user {telegram_id}")
    
    return jsonify({"success": True, "message": f"Curator {curator} selected for {sphere}"})


@app.route('/health')
def health():
    """Health check endpoint."""
    return jsonify({"status": "ok"})


def run_webapp():
    """Run the Flask webapp."""
    init_db()
    
    host = os.getenv("EXPRESS_HOST", "127.0.0.1").replace("https://", "").replace("http://", "")
    port = int(os.getenv("EXPRESS_PORT", 5000))
    
    logger.info(f"Starting webapp on {host}:{port}")
    app.run(host=host, port=port, debug=True)


if __name__ == '__main__':
    run_webapp()


