import os
import sqlite3
from flask import Flask, request, jsonify
from dotenv import load_dotenv

# Carrega as variáveis do arquivo .env
load_dotenv()

app = Flask(__name__)

# --- Configuração do SQLite ---
# Vamos salvar o banco em uma pasta 'data' para persistência
DB_DIR = "/app/data"
DATABASE_PATH = os.path.join(DB_DIR, "players.db")

API_SECRET_KEY = os.environ.get('API_SECRET_KEY')

def get_db_conn():
    """Estabelece uma conexão com o banco de dados SQLite."""
    # Garante que o diretório exista
    os.makedirs(DB_DIR, exist_ok=True)
    
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row  # Facilita o acesso aos dados por nome
    return conn

def init_db():
    """Cria a tabela de nicks se ela não existir."""
    print("Inicializando o banco de dados SQLite...")
    try:
        with get_db_conn() as conn:
            # SQL para criar a tabela
            conn.execute("""
            CREATE TABLE IF NOT EXISTS player_nicks (
                auth_id TEXT PRIMARY KEY,
                nick TEXT NOT NULL,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            """)
        conn.commit()
        print("Tabela 'player_nicks' verificada/criada com sucesso.")
    except Exception as e:
        print(f"Erro ao inicializar tabela: {e}")

# --- Middleware de Segurança (Idêntico) ---
@app.before_request
def check_api_key():
    auth_header = request.headers.get('Authorization')
    if not auth_header:
        return jsonify({"error": "Missing Authorization Header"}), 401
    
    try:
        token_type, token = auth_header.split(' ')
        if token_type.lower() != 'bearer' or token != API_SECRET_KEY:
            raise ValueError()
    except ValueError:
        return jsonify({"error": "Invalid API Key"}), 401
    
# --- Rotas da API ---

@app.route('/')
def health_check():
    return jsonify({"status": "API online com SQLite"}), 200

# Rota para CARREGAR o Nick (GET)
@app.route('/player/<string:auth_id>/nick', methods=['GET'])
def get_nick(auth_id):
    try:
        with get_db_conn() as conn:
            # Note o placeholder '?' para sqlite
            cur = conn.execute("SELECT nick FROM player_nicks WHERE auth_id = ?", (auth_id,))
            row = cur.fetchone()
                
        if row:
            return jsonify({"nick": row["nick"]}), 200
        else:
            return jsonify({"error": "Player not found"}), 404
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Rota para SALVAR o Nick (POST)
@app.route('/player/<string:auth_id>/nick', methods=['POST'])
def set_nick(auth_id):
    data = request.json
    new_nick = data.get('nick')

    if not new_nick:
        return jsonify({"error": "Missing 'nick' in JSON body"}), 400

    try:
        # SQL "UPSERT" mais simples para SQLite
        sql = """
        INSERT INTO player_nicks (auth_id, nick, updated_at)
        VALUES (?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(auth_id) 
        DO UPDATE SET nick = excluded.nick, updated_at = CURRENT_TIMESTAMP;
        """
        
        with get_db_conn() as conn:
            conn.execute(sql, (auth_id, new_nick))
            conn.commit()
            
        return jsonify({"message": "Nick updated successfully"}), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Inicializa o DB (cria a tabela) ANTES de rodar a app
if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000)
else:
    # Isso é chamado quando o Gunicorn roda a app
    init_db()