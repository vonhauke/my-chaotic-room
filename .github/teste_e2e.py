"""Teste de ponta a ponta do my chaotic room (automação do GitHub e uso local).

Abre a janela real (pywebview) com um banco vazio numa pasta temporária e usa o app
como uma pessoa: cadastra (com o autocompletar do tipo, foto e observações), valida o
tipo obrigatório, busca, ordena, edita com duplo clique, seleciona vários (Ctrl e
Shift), exclui com confirmação (e backup), limpa a seleção clicando no vazio e usa
o "Buscar no Google".

uso: python .github/teste_e2e.py
Sai com código 1 se algo falhar.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import traceback
from datetime import datetime

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from PIL import Image  # noqa: E402

TMP = tempfile.mkdtemp(prefix="chaotic-teste-")
import app as app_mod  # noqa: E402

# banco, fotos e backups do teste ficam numa pasta temporária (nunca no cadastro real)
app_mod.PASTA_BASE = TMP
app_mod.DB_PATH = os.path.join(TMP, "instrumentos.db")
app_mod.BACKUP_DIR = os.path.join(TMP, "backups")
app_mod.FOTOS_DIR = os.path.join(TMP, "fotos")
abertos = []
app_mod.webbrowser.open = lambda url: abertos.append(url)   # "Buscar no Google" sem abrir o navegador

import argila  # noqa: E402
import webview  # noqa: E402

CAPTURAS = os.environ.get("ARGILA_CAPTURAS")
falhas = []


def verificar(cond, mensagem):
    print(("ok   " if cond else "FALHA ") + mensagem, flush=True)
    if not cond:
        falhas.append(mensagem)


def roteiro(janela, app):
    js = janela.evaluate_js

    def esperar(condicao, limite=20, nome=""):
        fim = time.time() + limite
        while time.time() < fim:
            try:
                if js(condicao):
                    return True
            except Exception:
                pass
            time.sleep(0.15)
        verificar(False, f"tempo esgotado esperando: {nome or condicao}")
        return False

    def capturar(nome):
        if CAPTURAS and sys.platform.startswith("linux"):
            time.sleep(0.6)
            subprocess.run(["import", "-window", "root", os.path.join(CAPTURAS, nome + ".png")])

    def clicar(seletor, **teclas):
        opcoes = json.dumps(dict({"bubbles": True}, **teclas))
        js(f"document.querySelector({json.dumps(seletor)}).dispatchEvent(new MouseEvent('click', {opcoes}))")

    def texto(id_):
        return js(f"document.getElementById({json.dumps(id_)}).textContent")

    def visivel(id_):
        return js(f"!document.getElementById({json.dumps(id_)}).classList.contains('oculto')")

    def digitar(id_, valor):
        js(f"(() => {{ const c = document.getElementById({json.dumps(id_)}); c.value = {json.dumps(valor)};"
           "c.dispatchEvent(new Event('input', {bubbles: true})); c.dispatchEvent(new Event('change', {bubbles: true})); })()")

    def linhas():
        return json.loads(js("JSON.stringify(Cadastro._s.linhas.map(l => [l.tipo, l.marca, l.modelo]))"))

    try:
        esperar("document.documentElement.classList.contains('pronto')", 90, "interface pronta")
        verificar(visivel("vazio"), "cadastro vazio mostra o convite para começar")
        capturar("01-vazio")

        # 1) novo: tipo obrigatório, autocompletar, foto e observações
        clicar("#btn-novo")
        esperar("!document.getElementById('modal-form').classList.contains('oculto')", 5, "formulário")
        clicar("#form-salvar")
        verificar(esperar("!document.getElementById('erro-tipo').classList.contains('oculto')", 5, "erro do tipo"),
                  "salvar sem tipo mostra 'Informe o tipo do item'")
        js("document.getElementById('f-tipo').focus()")
        digitar("f-tipo", "gui")
        verificar(esperar("document.getElementById('sugestoes').classList.contains('aberto') && "
                          "document.querySelector('#sugestoes .menu-item').dataset.v === 'Guitarra'", 5, "sugestão"),
                  "autocompletar sugere 'Guitarra' ao digitar 'gui'")
        capturar("02-autocompletar")
        js("document.getElementById('f-tipo').dispatchEvent(new KeyboardEvent('keydown', {key: 'ArrowDown', bubbles: true}));"
           "document.getElementById('f-tipo').dispatchEvent(new KeyboardEvent('keydown', {key: 'Enter', bubbles: true}))")
        verificar(js("document.getElementById('f-tipo').value") == "Guitarra", "seta + Enter escolhe a sugestão")
        foto = os.path.join(TMP, "minha-guitarra.png")
        Image.new("RGB", (800, 600), (190, 80, 50)).save(foto)
        digitar("f-marca", "Fender")
        digitar("f-modelo", "Stratocaster")
        digitar("f-serie", "MX19087654")
        digitar("f-foto", foto)
        verificar(esperar("!!document.querySelector('#f-previa img')", 10, "prévia"), "prévia da foto aparece no formulário")
        digitar("f-obs", "Comprada em 2019. Captadores trocados.")
        capturar("03-formulario")
        clicar("#form-salvar")
        verificar(esperar("Cadastro._s.linhas.length === 1 && document.getElementById('modal-form').classList.contains('oculto')",
                          10, "salvou"), "instrumento cadastrado aparece na lista")
        verificar(esperar("document.getElementById('d-nome').textContent === 'Fender Stratocaster'", 10, "detalhe"),
                  "o novo item fica selecionado, com os detalhes no painel")
        verificar(esperar("!!document.getElementById('foto-img').getAttribute('src')", 10, "foto"), "foto aparece no painel")
        verificar(len(os.listdir(app_mod.FOTOS_DIR)) == 1, "a foto é copiada para a pasta fotos/ do app")
        verificar(texto("d-data") == datetime.now().strftime("%d/%m/%Y"), "data de inclusão em DD/MM/AAAA")
        verificar(texto("d-obs").startswith("Comprada"), "observações aparecem nos detalhes")
        capturar("04-detalhe")

        # 2) mais itens
        for tipo, marca, modelo in [("Pedal", "Boss", "DS-1"), ("Microfone", "Shure", "SM58"), ("Cabo", "", "P10 3 m")]:
            app.salvar({"tipo": tipo, "marca": marca, "modelo": modelo})
        js("Cadastro.carregar()")
        esperar("Cadastro._s.linhas.length === 4", 10, "4 itens")
        verificar([l[0] for l in linhas()] == ["Cabo", "Guitarra", "Microfone", "Pedal"], "lista em ordem alfabética do tipo")

        # 3) busca e ordenação
        digitar("busca", "shu")
        verificar(esperar("Cadastro._s.linhas.length === 1", 5, "busca"), "busca filtra por marca ('shu' → Shure)")
        digitar("busca", "")
        esperar("Cadastro._s.linhas.length === 4", 5, "limpar busca")
        clicar('#tabela th[data-col="marca"]')
        esperar("Cadastro._s.coluna === 'marca'", 5, "ordenar")
        verificar(esperar("Cadastro._s.linhas.length === 4 && Cadastro._s.linhas[1].marca === 'Boss'", 5, "ordem marca"),
                  "clicar no cabeçalho ordena pela coluna")
        clicar('#tabela th[data-col="marca"]')
        verificar(esperar("Cadastro._s.crescente === false && Cadastro._s.linhas[0].marca === 'Shure'", 5, "desc"),
                  "clicar de novo inverte a ordem")

        # 4) editar com duplo clique
        id_pedal = js("Cadastro._s.linhas.find(l => l.tipo === 'Pedal').id")
        js(f"document.querySelector('#linhas tr[data-id=\"{id_pedal}\"]').dispatchEvent(new MouseEvent('dblclick', {{bubbles: true}}))")
        esperar("!document.getElementById('modal-form').classList.contains('oculto') && "
                "document.getElementById('f-modelo').value === 'DS-1'", 5, "editar")
        digitar("f-modelo", "DS-1 Distortion")
        clicar("#form-salvar")
        verificar(esperar("document.getElementById('d-nome').textContent === 'Boss DS-1 Distortion'", 10, "editado"),
                  "duplo clique edita e o painel mostra a alteração")

        # 5) seleção múltipla
        ids = json.loads(js("JSON.stringify(Cadastro._s.linhas.map(l => l.id))"))
        clicar(f'#linhas tr[data-id="{ids[0]}"]')
        clicar(f'#linhas tr[data-id="{ids[2]}"]', ctrlKey=True)
        verificar(esperar("Cadastro._s.selecao.size === 2 && document.getElementById('btn-editar').disabled", 5, "ctrl"),
                  "Ctrl+clique soma à seleção; Editar fica desativado com vários")
        verificar(visivel("detalhe-varios") and texto("varios-titulo") == "2 itens selecionados", "painel mostra '2 itens selecionados'")
        clicar(f'#linhas tr[data-id="{ids[0]}"]')
        clicar(f'#linhas tr[data-id="{ids[3]}"]', shiftKey=True)
        verificar(esperar("Cadastro._s.selecao.size === 4", 5, "shift"), "Shift+clique seleciona o intervalo (1º ao 4º)")
        capturar("05-varios")

        # 6) clique no vazio limpa a seleção
        js("document.getElementById('rolagem').dispatchEvent(new MouseEvent('click', {bubbles: true}))")
        verificar(esperar("Cadastro._s.selecao.size === 0 && !document.getElementById('detalhe-vazio').classList.contains('oculto')",
                          5, "limpar"), "clicar numa área vazia limpa a seleção")

        # 7) excluir com confirmação (e backup antes)
        backups_antes = len([b for b in os.listdir(app_mod.BACKUP_DIR) if "antes_exclusao" in b]) if os.path.isdir(app_mod.BACKUP_DIR) else 0
        clicar(f'#linhas tr[data-id="{ids[0]}"]')
        clicar(f'#linhas tr[data-id="{ids[1]}"]', ctrlKey=True)
        clicar("#btn-excluir")
        verificar(esperar("!document.getElementById('modal-excluir').classList.contains('oculto') && "
                          "document.querySelectorAll('#excluir-lista li').length === 2", 5, "confirmação"),
                  "excluir pede confirmação listando os itens")
        capturar("06-excluir")
        clicar("#excluir-nao")
        verificar(esperar("Cadastro._s.linhas.length === 4", 5, "cancelar"), "Cancelar não exclui nada")
        clicar("#btn-excluir")
        esperar("!document.getElementById('modal-excluir').classList.contains('oculto')", 5, "confirmação 2")
        clicar("#excluir-sim")
        verificar(esperar("Cadastro._s.linhas.length === 2", 10, "excluiu"), "confirmar exclui os itens selecionados")
        backups_depois = len([b for b in os.listdir(app_mod.BACKUP_DIR) if "antes_exclusao" in b])
        verificar(backups_depois == backups_antes + 1, "um backup é feito antes de excluir")

        # 8) Buscar no Google (só marca e modelo)
        clicar("#btn-novo")
        esperar("!document.getElementById('modal-form').classList.contains('oculto')", 5, "form google")
        digitar("f-marca", "Roland")
        digitar("f-modelo", "Juno-106")
        clicar("#btn-google")
        esperar("true", 1)
        time.sleep(0.5)
        verificar(abertos and abertos[-1].endswith("q=Roland+Juno-106"), f"'Buscar no Google' pesquisa marca e modelo ({abertos})")
        clicar("#form-cancelar")

        erros_js = js("JSON.stringify(window.__erros)")
        verificar(erros_js in ("[]", None), f"sem erros de JavaScript ({erros_js})")
    except Exception:
        traceback.print_exc()
        falhas.append("exceção no roteiro")
    finally:
        janela.destroy()


def main():
    app = app_mod.App()
    janela = argila.criar_janela("my chaotic room (teste)", app, 1080, 700, 880, 520)
    app._janela = janela
    webview.start(roteiro, (janela, app), http_server=True, private_mode=True)
    shutil.rmtree(TMP, ignore_errors=True)
    if falhas:
        print(f"\n{len(falhas)} falha(s):\n- " + "\n- ".join(falhas))
        sys.exit(1)
    print("\nTudo certo: o my chaotic room funcionou de ponta a ponta.")


if __name__ == "__main__":
    main()
