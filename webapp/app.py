import os
import logging
from flask import Flask, render_template, request, jsonify, send_from_directory
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
        {"id": "plan", "name": "Развернутый", "description": "аналитик для создания личных принципов работы с деньгами через документирование ошибок, понимание циклов и долгосрочное стратегическое планирование.", "available": True},
        {"id": "vibe", "name": "Краткий", "description": "фокусировщик на измеримых целях и немедленном действии для всех форматов работы: от найма до бизнеса через приоритизацию и быстрые итерации.", "available": True},
        {"id": "sandberg", "name": "Шерил Сэндберг", "description": "эксперт по корпоративной карьере, переговорам о зарплате и нетворкингу для тех, кто работает в офисе и хочет расти вертикально.", "available": False},
        {"id": "chehov", "name": "Антон Павлович Чехов", "description": "наставник для творческих людей по монетизации таланта через множественные каналы: от журналов до театров, от прагматизма к искусству.", "available": False},
        {"id": "belford", "name": "Джордан Белфорт", "description": "мастер продаж и убеждения для тех, кому нужны деньги здесь и сейчас через бизнес.", "available": False}
    ],
    "soul": [
        {"id": "plan", "name": "Развернутый", "description": "Наставник по глубинной психологии и работе с бессознательным", "available": True},
        {"id": "vibe", "name": "Краткий", "description": "Наставник по стоической философии и практическим инструментам", "available": True},
        {"id": "markaryan", "name": "Арсен Маркарян", "description": "практический психолог для распознавания манипуляций, ролей в треугольнике Карпмана и понимания игр во всех отношениях.", "available": False},
        {"id": "osho", "name": "Ошо", "description": "провокационный учитель медитации и наблюдения для тех, кто хочет отстраниться от отождествления с мыслями и эмоциями.", "available": False},
        {"id": "avrelii", "name": "Марк Аврелий", "description": "прагматичный стоик с краткими максимами для различения контролируемого от неконтролируемого и принятия реальности без драмы.", "available": False}
    ],
    "body": [
        {"id": "plan", "name": "Развернутый", "description": "биохакинг, наука, холистический подход", "available": True},
        {"id": "vibe", "name": "Краткий", "description": "прямые команды, старая школа", "available": True},
        {"id": "arnold", "name": "Арнольд Шварценеггер", "description": "силовые тренировки, бодибилдинг, масса", "available": False},
        {"id": "brus", "name": "Брюс Ли", "description": "скорость, функциональность, боевые искусства, философия движения", "available": False},
        {"id": "krishna", "name": "Кришнамачарья", "description": "йога, растяжка, мобильность, связь дыхания и тела", "available": False}
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


@app.route('/assets/<path:filepath>')
def serve_assets(filepath):
    """Serve static assets from the assets directory."""
    assets_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'assets')
    return send_from_directory(assets_dir, filepath)


def run_webapp():
    """Run the Flask webapp."""
    init_db()
    
    host = os.getenv("EXPRESS_HOST", "127.0.0.1").replace("https://", "").replace("http://", "")
    port = int(os.getenv("EXPRESS_PORT", 5000))
    
    logger.info(f"Starting webapp on {host}:{port}")
    app.run(host=host, port=port, debug=True)


if __name__ == '__main__':
    run_webapp()


