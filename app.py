import os
import sqlite3
from flask import Flask, request, jsonify
from dotenv import load_dotenv

# Carrega as variáveis do arquivo .env
load_dotenv()

app = Flask(__name__)

# --- Configuração do SQLite ---
DB_DIR = "/app/data"
DATABASE_PATH = os.path.join(DB_DIR, "players.db")
API_SECRET_KEY = os.environ.get('API_SECRET_KEY')

def get_db_conn():
    """Estabelece uma conexão com o banco de dados SQLite."""
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Cria as tabelas se elas não existirem."""
    print("Inicializando o banco de dados SQLite...")
    try:
        with get_db_conn() as conn:
            # Tabela 1: Nicks dos Jogadores
            conn.execute("""
            CREATE TABLE IF NOT EXISTS player_nicks (
                auth_id TEXT PRIMARY KEY,
                nick TEXT NOT NULL,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            """)
            
            # --- ATUALIZADO: Tabela 2: Mensagens Públicas do Chat ---
            # (auth_id e FOREIGN KEY removidos)
            conn.execute("""
            CREATE TABLE IF NOT EXISTS chat_messages (
                message_id INTEGER PRIMARY KEY AUTOINCREMENT,
                nick TEXT NOT NULL,
                message_text TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            """)
        conn.commit()
        print("Tabelas 'player_nicks' e 'chat_messages' verificadas/criadas.")
    except Exception as e:
        print(f"Erro ao inicializar tabelas: {e}")

# --- Middleware de Segurança ---
@app.before_request
def check_api_key():
    # Ignora a verificação de chave para a rota 'health_check'
    if request.path == '/':
        return

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

# --- Rotas de Player Nick (Sem mudanças) ---

@app.route('/player/<string:auth_id>/nick', methods=['GET'])
def get_nick(auth_id):
    try:
        with get_db_conn() as conn:
            cur = conn.execute("SELECT nick FROM player_nicks WHERE auth_id = ?", (auth_id,))
            row = cur.fetchone()
        if row:
            return jsonify({"nick": row["nick"]}), 200
        else:
            return jsonify({"error": "Player not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/player/<string:auth_id>/nick', methods=['POST'])
def set_nick(auth_id):
    data = request.json
    new_nick = data.get('nick')
    if not new_nick:
        return jsonify({"error": "Missing 'nick' in JSON body"}), 400
    try:
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

# --- ROTA ADICIONADA (Verificar Nick) ---
@app.route('/nicks/check', methods=['GET'])
def check_nick_exists():
    """Verifica se um nick já existe (case-insensitive)."""
    nick_to_check = request.args.get('name')
    if not nick_to_check:
        return jsonify({"error": "Missing 'name' query parameter"}), 400

    try:
        with get_db_conn() as conn:
            # COLLATE NOCASE faz a busca ser case-insensitive no SQLite
            cur = conn.execute(
                "SELECT 1 FROM player_nicks WHERE nick = ? COLLATE NOCASE LIMIT 1", 
                (nick_to_check,)
            )
            row = cur.fetchone()
            
            if row:
                # 200 OK, e o nick existe
                return jsonify({"exists": True}), 200
            else:
                # 200 OK, e o nick não existe
                return jsonify({"exists": False}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- ROTAS DE CHAT ATUALIZADAS ---

@app.route('/chat/messages', methods=['GET'])
def get_chat_messages():
    """Pega as últimas N mensagens públicas. O cliente chama isso."""
    try:
        # Pega as últimas 30 mensagens, da mais antiga para a mais nova
        sql = """
        SELECT nick, message_text, timestamp FROM chat_messages
        ORDER BY message_id DESC
        LIMIT 30;
        """
        with get_db_conn() as conn:
            cur = conn.execute(sql)
            rows = cur.fetchall()
            
        # Inverte a lista para que fiquem na ordem correta (antiga -> nova)
        messages = [dict(row) for row in reversed(rows)]
        return jsonify(messages), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- ATUALIZADO ---
@app.route('/chat/message', methods=['POST'])
def post_chat_message():
    """Salva uma nova mensagem pública. O servidor Unity chama isso."""
    data = request.json
    # auth_id = data.get('auth_id') # <-- REMOVIDO
    nick = data.get('nick')
    message_text = data.get('message_text')

    # Validação atualizada
    if not all([nick, message_text]):
        return jsonify({"error": "Missing nick or message_text"}), 400

    try:
        # SQL Atualizado
        sql = """
        INSERT INTO chat_messages (nick, message_text)
        VALUES (?, ?);
        """
        with get_db_conn() as conn:
            # Parâmetros atualizados
            conn.execute(sql, (nick, message_text))
            conn.commit()
        return jsonify({"message": "Message saved"}), 201
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- ROTAS DE ADMIN (Sem mudanças, já não usava auth_id) ---

@app.route('/admin/player/<string:auth_id>', methods=['DELETE'])
def admin_delete_nick(auth_id):
    """[Admin] Exclui um jogador (e seu nick) pelo auth_id."""
    
    try:
        with get_db_conn() as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM player_nicks WHERE auth_id = ?", (auth_id,))
            deleted_count = cur.rowcount
            conn.commit()
        
        if deleted_count > 0:
            return jsonify({
                "message": "Player deleted successfully", 
                "auth_id": auth_id,
                "deleted_count": deleted_count
            }), 200
        else:
            return jsonify({
                "error": "Player not found", 
                "auth_id": auth_id
            }), 404
            
    except Exception as e:
        return jsonify({"error": f"An error occurred: {e}"}), 500

@app.route('/admin/chat/delete_range', methods=['POST'])
def delete_chat_messages_range():
    """
    [Admin] Exclui mensagens de chat por um intervalo de IDs.
    Requer JSON: {"start_id": X, "end_id": Y}
    """
    data = request.json
    start_id = data.get('start_id')
    end_id = data.get('end_id')

    # --- Validação ---
    if start_id is None or end_id is None:
        return jsonify({"error": "Missing 'start_id' or 'end_id' in JSON body"}), 400
    
    try:
        start_id = int(start_id)
        end_id = int(end_id)
    except ValueError:
        return jsonify({"error": "'start_id' and 'end_id' must be integers"}), 400
    
    if start_id > end_id:
        return jsonify({"error": "'start_id' must be less than or equal to 'end_id'"}), 400
    
    # --- Execução ---
    try:
        sql = "DELETE FROM chat_messages WHERE message_id BETWEEN ? AND ?;"
        
        with get_db_conn() as conn:
            # Precisamos de um cursor para obter o 'rowcount' (linhas afetadas)
            cur = conn.cursor()
            cur.execute(sql, (start_id, end_id))
            deleted_count = cur.rowcount
            conn.commit()
        
        return jsonify({
            "message": f"Successfully deleted messages from ID {start_id} to {end_id}.",
            "deleted_count": deleted_count
        }), 200
            
    except Exception as e:
        return jsonify({"error": f"An error occurred: {e}"}), 500


# --- Inicialização ---

# Inicializa o DB (cria a tabela) ANTES de rodar a app
if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000)
else:
    # Isso é chamado quando o Gunicorn roda a app
    init_db()