"""my chaotic room - cadastro de instrumentos musicais e equipamentos.

Interface: HTML/CSS em ui/ (design system "Argila", em ui/ds/), mostrada numa janela
nativa pelo pywebview (Edge WebView2 no Windows, WebKit no Mac). Este arquivo cuida
do banco SQLite, das fotos e dos backups, e expõe tudo para a interface (classe App).
"""

import base64
import glob
import io
import os
import shutil
import sqlite3
import sys
import threading
import uuid
import webbrowser
from datetime import datetime
from urllib.parse import quote_plus

from PIL import Image, ImageOps

TITULO = "my chaotic room"
TAMANHO_FOTO_DETALHE = (640, 420)       # a foto vai para a interface já reduzida
TAMANHO_FOTO_PREVIA = (360, 240)

# Recursos (interface, ícones) ficam junto do código; no .exe do PyInstaller, na pasta temporária.
PASTA_RECURSOS = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
# Dados do usuário (banco, fotos, backups): no .exe/.app ficam em %APPDATA% (ou na pasta do
# usuário no Mac), porque a pasta temporária some a cada vez que o app fecha. Rodando pelo
# código-fonte, ficam ao lado do app.py.
if getattr(sys, "frozen", False):
    PASTA_BASE = os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), "my chaotic room")
    os.makedirs(PASTA_BASE, exist_ok=True)
else:
    PASTA_BASE = PASTA_RECURSOS
DB_PATH = os.path.join(PASTA_BASE, "instrumentos.db")
BACKUP_DIR = os.path.join(PASTA_BASE, "backups")
FOTOS_DIR = os.path.join(PASTA_BASE, "fotos")
MAX_BACKUPS = 20

TIPOS = [
    "Amplificador", "Baixo", "Banjo", "Bateria", "Cabo", "Caixa de Som",
    "Cavaquinho", "Cello", "Controlador MIDI", "Drum Machine", "Flauta",
    "Guitarra", "Mesa de Som", "Microfone", "Monitor", "Pedal", "Percussão",
    "Saxofone", "Sintetizador", "Teclado/Piano", "Trompete", "Ukulele",
    "Viola", "Violão", "Violino", "Outro",
]

COLUNAS = ["tipo", "marca", "modelo", "numero_serie", "data_inclusao"]
EXTENSOES_FOTO = ("*.jpg", "*.jpeg", "*.png", "*.gif", "*.bmp", "*.webp", "*.tif", "*.tiff", "*.heic", "*.heif", "*.ico")


def fazer_backup(motivo="auto"):
    """Copia o banco atual para a pasta backups/ antes de operações sensíveis ou ao abrir o app."""
    if not os.path.isfile(DB_PATH):
        return
    os.makedirs(BACKUP_DIR, exist_ok=True)
    carimbo = datetime.now().strftime("%Y%m%d_%H%M%S")
    destino = os.path.join(BACKUP_DIR, f"instrumentos_{carimbo}_{motivo}.db")
    shutil.copy2(DB_PATH, destino)
    _limpar_backups_antigos()


def _limpar_backups_antigos():
    arquivos = sorted(glob.glob(os.path.join(BACKUP_DIR, "instrumentos_*.db")))
    excesso = len(arquivos) - MAX_BACKUPS
    for antigo in arquivos[:max(excesso, 0)]:
        os.remove(antigo)


def formatar_data(data_iso):
    """Converte a data guardada no banco (AAAA-MM-DD, pra ordenar certo) para exibição em DD/MM/AAAA."""
    if not data_iso:
        return None
    try:
        return datetime.strptime(data_iso, "%Y-%m-%d").strftime("%d/%m/%Y")
    except ValueError:
        return data_iso


def copiar_foto_para_pasta(caminho_original):
    """Garante que a foto do instrumento tenha uma cópia própria dentro de fotos/,
    em vez de só apontar pro arquivo original em outro lugar do computador."""
    if not caminho_original:
        return caminho_original
    if not os.path.isabs(caminho_original):
        return caminho_original  # já é um nome gerenciado (ou inválido) — mantém como está
    if not os.path.isfile(caminho_original):
        return caminho_original  # caminho absoluto que não existe — mantém como está
    os.makedirs(FOTOS_DIR, exist_ok=True)
    extensao = os.path.splitext(caminho_original)[1]
    novo_nome = f"{uuid.uuid4().hex}{extensao}"
    shutil.copy2(caminho_original, os.path.join(FOTOS_DIR, novo_nome))
    return novo_nome


def resolver_foto(nome_ou_caminho):
    """Transforma o valor salvo no banco no caminho real do arquivo no disco."""
    if not nome_ou_caminho:
        return None
    if os.path.isabs(nome_ou_caminho):
        return nome_ou_caminho  # fotos cadastradas antes dessa mudança
    return os.path.join(FOTOS_DIR, nome_ou_caminho)


def foto_como_data_uri(caminho, tamanho):
    """Miniatura da foto (para o <img> da interface), ou None se não der para abrir."""
    if not caminho or not os.path.isfile(caminho):
        return None
    try:
        with Image.open(caminho) as img:
            img = ImageOps.exif_transpose(img)
            img.thumbnail(tamanho)
            if img.mode not in ("RGB", "L"):
                fundo = Image.new("RGB", img.size, (255, 255, 255))
                fundo.paste(img.convert("RGBA"), mask=img.convert("RGBA").split()[3])
                img = fundo
            saida = io.BytesIO()
            img.convert("RGB").save(saida, "JPEG", quality=88)
        return "data:image/jpeg;base64," + base64.b64encode(saida.getvalue()).decode("ascii")
    except Exception:
        return None


def conectar():
    fazer_backup(motivo="abertura")
    con = sqlite3.connect(DB_PATH, check_same_thread=False)
    con.execute("""
        CREATE TABLE IF NOT EXISTS instrumentos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tipo TEXT NOT NULL,
            marca TEXT,
            modelo TEXT,
            numero_serie TEXT,
            foto_path TEXT,
            observacoes TEXT
        )
    """)
    colunas_existentes = {linha[1] for linha in con.execute("PRAGMA table_info(instrumentos)")}
    if "data_inclusao" not in colunas_existentes:
        con.execute("ALTER TABLE instrumentos ADD COLUMN data_inclusao TEXT")
    con.commit()
    return con


def rotulo_de(dados):
    return dados["tipo"] + (f" - {dados['marca']}" if dados.get("marca") else "")


class App:
    """Banco, fotos e backups. Os métodos sem _ são chamados pela interface
    (window.pywebview.api.<metodo>); os resultados voltam para o JavaScript."""

    def __init__(self):
        self._janela = None
        self._trava = threading.RLock()   # o pywebview chama os métodos de threads diferentes
        self._con = conectar()

    # ----- leitura -----
    def _buscar_dados(self, id_):
        with self._trava:
            cur = self._con.execute("SELECT * FROM instrumentos WHERE id = ?", (id_,))
            colunas = [d[0] for d in cur.description]
            linha = cur.fetchone()
        return dict(zip(colunas, linha)) if linha else None

    def estado_inicial(self):
        return {"tipos": TIPOS, "mac": sys.platform == "darwin"}

    def listar(self, termo="", coluna="tipo", crescente=True):
        """Linhas da tabela (com a busca e a ordenação) e o total do cadastro."""
        coluna = coluna if coluna in COLUNAS else "tipo"
        direcao = "ASC" if crescente else "DESC"
        termo = (termo or "").strip().lower()
        with self._trava:
            cur = self._con.cursor()
            total = cur.execute("SELECT COUNT(*) FROM instrumentos").fetchone()[0]
            sql = "SELECT id, tipo, marca, modelo, numero_serie, data_inclusao FROM instrumentos"
            if termo:
                padrao = f"%{termo}%"
                cur.execute(f"""{sql} WHERE lower(tipo) LIKE ? OR lower(marca) LIKE ? OR lower(modelo) LIKE ?
                                ORDER BY {coluna} {direcao}""", (padrao, padrao, padrao))
            else:
                cur.execute(f"{sql} ORDER BY {coluna} {direcao}")
            linhas = cur.fetchall()
        return {
            "total": total,
            "linhas": [{"id": id_, "tipo": tipo or "", "marca": marca or "", "modelo": modelo or "",
                        "numero_serie": serie or "", "data_inclusao": formatar_data(data) or "—"}
                       for id_, tipo, marca, modelo, serie, data in linhas],
        }

    def detalhes(self, id_):
        dados = self._buscar_dados(id_)
        if not dados:
            return None
        caminho_foto = resolver_foto(dados.get("foto_path"))
        nome = " ".join(p for p in [dados.get("marca"), dados.get("modelo")] if p) or dados.get("tipo", "")
        return {
            "id": dados["id"], "tipo": dados.get("tipo") or "", "nome": nome,
            "marca": dados.get("marca") or "", "modelo": dados.get("modelo") or "",
            "numero_serie": dados.get("numero_serie") or "",
            "data_inclusao": formatar_data(dados.get("data_inclusao")) or "—",
            "observacoes": dados.get("observacoes") or "",
            "foto_path": dados.get("foto_path") or "",
            "foto": foto_como_data_uri(caminho_foto, TAMANHO_FOTO_DETALHE),
            "tem_foto": bool(caminho_foto and os.path.isfile(caminho_foto)),
        }

    def rotulos(self, ids):
        """Nomes dos itens (para a pergunta de confirmação antes de excluir)."""
        return [rotulo_de(d) for d in (self._buscar_dados(i) for i in ids) if d]

    # ----- escrita -----
    def salvar(self, dados, id_=None):
        """Cria (id_ vazio) ou altera um instrumento. Devolve {"erro": ...} ou {"id": ...}."""
        tipo = (dados.get("tipo") or "").strip()
        if not tipo:
            return {"erro": "Informe o tipo do item.", "campo": "tipo"}
        registro = {
            "tipo": tipo,
            "marca": (dados.get("marca") or "").strip(),
            "modelo": (dados.get("modelo") or "").strip(),
            "numero_serie": (dados.get("numero_serie") or "").strip(),
            "foto_path": copiar_foto_para_pasta((dados.get("foto_path") or "").strip()),
            "observacoes": (dados.get("observacoes") or "").strip(),
        }
        with self._trava:
            if id_:
                self._con.execute(
                    """UPDATE instrumentos SET tipo=?, marca=?, modelo=?, numero_serie=?,
                       foto_path=?, observacoes=? WHERE id=?""",
                    (registro["tipo"], registro["marca"], registro["modelo"], registro["numero_serie"],
                     registro["foto_path"], registro["observacoes"], id_),
                )
                novo_id = id_
            else:
                cur = self._con.execute(
                    """INSERT INTO instrumentos
                       (tipo, marca, modelo, numero_serie, foto_path, observacoes, data_inclusao)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (registro["tipo"], registro["marca"], registro["modelo"], registro["numero_serie"],
                     registro["foto_path"], registro["observacoes"], datetime.now().strftime("%Y-%m-%d")),
                )
                novo_id = cur.lastrowid
            self._con.commit()
        return {"id": novo_id}

    def excluir(self, ids):
        ids = [int(i) for i in ids or []]
        if not ids:
            return 0
        with self._trava:
            fazer_backup(motivo="antes_exclusao")
            self._con.executemany("DELETE FROM instrumentos WHERE id = ?", [(i,) for i in ids])
            self._con.commit()
        return len(ids)

    # ----- fotos e atalhos -----
    def escolher_foto(self):
        if self._janela is None:
            return None
        import argila

        escolha = self._janela.create_file_dialog(
            argila.TIPO_ABRIR, file_types=(f"Imagens ({';'.join(EXTENSOES_FOTO)})", "Todos os arquivos (*.*)"))
        if not escolha:
            return None
        caminho = escolha[0] if isinstance(escolha, (list, tuple)) else escolha
        return {"caminho": caminho, "previa": foto_como_data_uri(caminho, TAMANHO_FOTO_PREVIA)}

    def previa_foto(self, valor):
        """Miniatura do que está no campo Foto (caminho completo ou nome de uma foto já salva)."""
        return foto_como_data_uri(resolver_foto((valor or "").strip()), TAMANHO_FOTO_PREVIA)

    def abrir_foto(self, id_):
        dados = self._buscar_dados(id_)
        caminho = resolver_foto(dados.get("foto_path")) if dados else None
        if caminho and os.path.isfile(caminho):
            import argila

            try:
                argila.abrir_no_sistema(caminho)
            except Exception as e:
                return str(e)[:200]
        return None

    def buscar_no_google(self, marca, modelo):
        termo = " ".join(p for p in [(marca or "").strip(), (modelo or "").strip()] if p)
        if not termo:
            return "Informe ao menos a marca ou o modelo para buscar."
        webbrowser.open(f"https://www.google.com/search?q={quote_plus(termo)}")
        return None


def _identificar_processo_windows():
    """No Windows, dissocia o app do ícone genérico do Python na barra de tarefas."""
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("instrumentosmusicais.app")
    except Exception:
        pass


def main():
    import argila

    _identificar_processo_windows()
    app = App()
    janela = argila.criar_janela(TITULO, app, 1080, 700, 880, 520)
    app._janela = janela
    argila.iniciar(icone=os.path.join("assets_icone", "icone_app_instrumentos", "icone_1024.png"), titulo=TITULO)


if __name__ == "__main__":
    main()
