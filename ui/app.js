/* my chaotic room - logica da interface.
   O Python (app.py) expoe a API em window.pywebview.api; aqui ficam a lista,
   a selecao, o painel de detalhes, o formulario e a confirmacao de exclusao. */

const $ = (id) => document.getElementById(id);

window.__erros = [];
window.addEventListener("error", (e) => window.__erros.push(String(e.message)));
window.addEventListener("unhandledrejection", (e) => window.__erros.push(String(e.reason)));

const Cadastro = (() => {
  const s = {
    linhas: [],
    total: 0,
    termo: "",
    coluna: "tipo",
    crescente: true,
    selecao: new Set(),   // ids selecionados
    ancora: null,         // ultimo clicado (para Shift+clique)
    tipos: [],
    editandoId: null,     // null = novo
    detalheId: null,
  };
  let api = null;
  let buscaTimer = null;
  const plural = (n, um, varios) => `${n} ${n === 1 ? um : varios}`;

  /* ---------- lista ---------- */
  async function carregar() {
    const r = await api.listar(s.termo, s.coluna, s.crescente);
    s.linhas = r.linhas;
    s.total = r.total;
    const visiveis = new Set(s.linhas.map((l) => l.id));
    s.selecao = new Set([...s.selecao].filter((id) => visiveis.has(id)));
    desenhar();
    atualizarDetalhes();
  }

  function desenhar() {
    $("subtitulo").textContent = `${plural(s.total, "instrumento cadastrado", "instrumentos cadastrados")}`;
    $("rodape").textContent = `${s.linhas.length} de ${plural(s.total, "instrumento", "instrumentos")}`;
    document.querySelectorAll("#tabela th[data-col]").forEach((th) => {
      const ativa = th.dataset.col === s.coluna;
      th.classList.toggle("ativa", ativa);
      th.innerHTML = th.textContent.replace(/[▲▼]/g, "").trim() + (ativa ? `<span class="seta">${s.crescente ? "▲" : "▼"}</span>` : "");
    });
    $("linhas").innerHTML = s.linhas.map((l) => `
      <tr data-id="${l.id}" class="${s.selecao.has(l.id) ? "selecionada" : ""}">
        <td class="tipo" title="${DS.escapar(l.tipo)}">${DS.escapar(l.tipo)}</td>
        <td title="${DS.escapar(l.marca)}">${DS.escapar(l.marca)}</td>
        <td title="${DS.escapar(l.modelo)}">${DS.escapar(l.modelo)}</td>
        <td class="mono" title="${DS.escapar(l.numero_serie)}">${DS.escapar(l.numero_serie)}</td>
        <td class="data">${DS.escapar(l.data_inclusao)}</td>
      </tr>`).join("");
    const vazio = s.linhas.length === 0;
    $("vazio").classList.toggle("oculto", !vazio);
    if (vazio) {
      const buscando = s.total > 0;
      $("vazio-titulo").textContent = buscando ? "Nada encontrado" : "Nenhum instrumento cadastrado";
      $("vazio-texto").textContent = buscando
        ? `Nenhum tipo, marca ou modelo contém “${s.termo}”.`
        : "Comece pela sua guitarra, um pedal ou aquele cabo que sempre some.";
      $("vazio-novo").classList.toggle("oculto", buscando);
    }
  }

  function pintarSelecao() {
    document.querySelectorAll("#linhas tr").forEach((tr) => tr.classList.toggle("selecionada", s.selecao.has(Number(tr.dataset.id))));
    atualizarDetalhes();
  }

  function clicarLinha(e, id) {
    const ordem = s.linhas.map((l) => l.id);
    if (e.shiftKey && s.ancora !== null && ordem.includes(s.ancora)) {
      const [a, b] = [ordem.indexOf(s.ancora), ordem.indexOf(id)].sort((x, y) => x - y);
      if (!(e.ctrlKey || e.metaKey)) s.selecao.clear();
      ordem.slice(a, b + 1).forEach((x) => s.selecao.add(x));
    } else if (e.ctrlKey || e.metaKey) {
      s.selecao.has(id) ? s.selecao.delete(id) : s.selecao.add(id);
      s.ancora = id;
    } else {
      s.selecao = new Set([id]);
      s.ancora = id;
    }
    pintarSelecao();
  }

  function moverSelecao(passo, estender) {
    if (!s.linhas.length) return;
    const ordem = s.linhas.map((l) => l.id);
    const atual = s.ancora !== null && ordem.includes(s.ancora) ? ordem.indexOf(s.ancora) : -1;
    const novo = Math.min(Math.max(atual + passo, 0), ordem.length - 1);
    if (estender) s.selecao.add(ordem[novo]); else s.selecao = new Set([ordem[novo]]);
    s.ancora = ordem[novo];
    pintarSelecao();
    document.querySelector(`#linhas tr[data-id="${ordem[novo]}"]`)?.scrollIntoView({ block: "nearest" });
  }

  function ordenarPor(coluna) {
    if (coluna === s.coluna) s.crescente = !s.crescente;
    else { s.coluna = coluna; s.crescente = true; }
    carregar();
  }

  /* ---------- detalhes ---------- */
  async function atualizarDetalhes() {
    const ids = [...s.selecao];
    $("btn-editar").disabled = ids.length !== 1;
    $("btn-excluir").disabled = ids.length === 0;
    $("detalhe-vazio").classList.toggle("oculto", ids.length !== 0);
    $("detalhe-varios").classList.toggle("oculto", ids.length < 2);
    $("varios-titulo").textContent = plural(ids.length, "item selecionado", "itens selecionados");
    if (ids.length !== 1) {
      $("detalhe-um").classList.add("oculto");
      s.detalheId = null;
      return;
    }
    const id = ids[0];
    if (s.detalheId === id && !$("detalhe-um").classList.contains("oculto")) return;
    s.detalheId = id;
    const d = await api.detalhes(id);
    if (!d || s.detalheId !== id) return;
    $("d-tipo").textContent = d.tipo;
    $("d-nome").textContent = d.nome;
    $("d-marca").textContent = d.marca || "—";
    $("d-modelo").textContent = d.modelo || "—";
    $("d-serie").textContent = d.numero_serie || "—";
    $("d-data").textContent = d.data_inclusao;
    $("d-obs").textContent = d.observacoes;
    $("d-obs-bloco").classList.toggle("oculto", !d.observacoes);
    const img = $("foto-img");
    if (d.foto) { img.src = d.foto; img.classList.remove("oculto"); } else { img.removeAttribute("src"); img.classList.add("oculto"); }
    $("foto-vazia").classList.toggle("oculto", !!d.foto);
    $("foto").disabled = !d.tem_foto;
    $("detalhe-um").classList.remove("oculto");
    $("detalhe-um").classList.remove("entra"); void $("detalhe-um").offsetWidth; $("detalhe-um").classList.add("entra");
  }

  /* ---------- formulario ---------- */
  async function abrirForm(id = null) {
    s.editandoId = id;
    $("form-titulo").textContent = id ? "Editar instrumento" : "Novo instrumento";
    const d = id ? await api.detalhes(id) : null;
    $("f-tipo").value = d ? d.tipo : "";
    $("f-marca").value = d ? d.marca : "";
    $("f-modelo").value = d ? d.modelo : "";
    $("f-serie").value = d ? d.numero_serie : "";
    $("f-foto").value = d ? d.foto_path : "";
    $("f-obs").value = d ? d.observacoes : "";
    mostrarPrevia(d ? d.foto : null);
    erroTipo(false);
    fecharSugestoes();
    $("modal-form").classList.remove("oculto");
    $("f-tipo").focus();
  }
  const fecharForm = () => { $("modal-form").classList.add("oculto"); fecharSugestoes(); };
  const formAberto = () => !$("modal-form").classList.contains("oculto");

  function mostrarPrevia(dataUri) {
    $("f-previa").innerHTML = dataUri ? `<img src="${dataUri}" alt="">` : icone("image", 20);
    $("btn-tirar-foto").classList.toggle("oculto", !$("f-foto").value.trim());
  }

  function erroTipo(sim) {
    $("f-tipo").classList.toggle("invalida", sim);
    $("erro-tipo").classList.toggle("oculto", !sim);
  }

  async function salvar(e) {
    e && e.preventDefault();
    fecharSugestoes();
    const r = await api.salvar({
      tipo: $("f-tipo").value, marca: $("f-marca").value, modelo: $("f-modelo").value,
      numero_serie: $("f-serie").value, foto_path: $("f-foto").value, observacoes: $("f-obs").value,
    }, s.editandoId);
    if (r.erro) { erroTipo(true); $("f-tipo").focus(); return; }
    fecharForm();
    s.selecao = new Set([r.id]);
    s.ancora = r.id;
    s.detalheId = null;
    await carregar();
    document.querySelector(`#linhas tr[data-id="${r.id}"]`)?.scrollIntoView({ block: "nearest" });
    DS.toast(s.editandoId ? "Alterações salvas" : "Instrumento cadastrado");
  }

  /* autocompletar do tipo: primeiro os que comecam com o texto, depois os que contem */
  let sugestaoAtiva = -1;
  function filtrarTipos(texto) {
    texto = texto.trim().toLowerCase();
    if (!texto) return s.tipos;
    const comeca = s.tipos.filter((t) => t.toLowerCase().startsWith(texto));
    return comeca.length ? comeca : s.tipos.filter((t) => t.toLowerCase().includes(texto));
  }
  function abrirSugestoes() {
    const texto = $("f-tipo").value;
    const lista = filtrarTipos(texto);
    const exato = lista.length === 1 && lista[0].toLowerCase() === texto.trim().toLowerCase();
    if (!lista.length || exato) return fecharSugestoes();
    const marca = (t) => {
      const i = t.toLowerCase().indexOf(texto.trim().toLowerCase());
      return texto.trim() && i >= 0
        ? DS.escapar(t.slice(0, i)) + "<b>" + DS.escapar(t.slice(i, i + texto.trim().length)) + "</b>" + DS.escapar(t.slice(i + texto.trim().length))
        : DS.escapar(t);
    };
    $("sugestoes").innerHTML = lista.map((t, i) => `<button type="button" class="menu-item" role="option" data-v="${DS.escapar(t)}" data-i="${i}">${marca(t)}</button>`).join("");
    $("sugestoes").classList.add("aberto");
    sugestaoAtiva = -1;
  }
  function fecharSugestoes() { $("sugestoes").classList.remove("aberto"); sugestaoAtiva = -1; }
  function escolherSugestao(valor) { $("f-tipo").value = valor; erroTipo(false); fecharSugestoes(); $("f-marca").focus(); }
  function moverSugestao(passo) {
    const itens = [...$("sugestoes").querySelectorAll(".menu-item")];
    if (!itens.length) return;
    sugestaoAtiva = (sugestaoAtiva + passo + itens.length) % itens.length;
    itens.forEach((el, i) => el.classList.toggle("ativa", i === sugestaoAtiva));
    itens[sugestaoAtiva].scrollIntoView({ block: "nearest" });
  }

  /* ---------- excluir ---------- */
  async function pedirExclusao() {
    const ids = [...s.selecao];
    if (!ids.length) return;
    const rotulos = await api.rotulos(ids);
    if (ids.length === 1) {
      $("excluir-pergunta").textContent = `Excluir “${rotulos[0]}” do cadastro?`;
      $("excluir-lista").classList.add("oculto");
    } else {
      $("excluir-pergunta").textContent = `Excluir ${ids.length} itens do cadastro?`;
      $("excluir-lista").innerHTML = rotulos.map((r) => `<li>${DS.escapar(r)}</li>`).join("");
      $("excluir-lista").classList.remove("oculto");
    }
    $("modal-excluir").classList.remove("oculto");
    $("excluir-nao").focus();
  }
  const fecharExcluir = () => $("modal-excluir").classList.add("oculto");
  async function confirmarExclusao() {
    const ids = [...s.selecao];
    fecharExcluir();
    const n = await api.excluir(ids);
    s.selecao.clear();
    s.detalheId = null;
    await carregar();
    DS.toast(n === 1 ? "Item excluído" : `${n} itens excluídos`);
  }

  /* ---------- inicio ---------- */
  async function iniciar() {
    desenharIcones();
    api = await DS.api();
    const ini = await api.estado_inicial();
    s.tipos = ini.tipos;
    if (ini.mac) document.querySelector(".dica-teclas").innerHTML = "<kbd>⌘</kbd> ou <kbd>Shift</kbd> + clique para selecionar vários";
    await carregar();

    $("busca").addEventListener("input", () => {
      clearTimeout(buscaTimer);
      buscaTimer = setTimeout(() => { s.termo = $("busca").value; carregar(); }, 120);
    });
    document.querySelectorAll("#tabela th[data-col]").forEach((th) => (th.onclick = () => ordenarPor(th.dataset.col)));
    $("linhas").addEventListener("click", (e) => { const tr = e.target.closest("tr"); if (tr) clicarLinha(e, Number(tr.dataset.id)); });
    $("linhas").addEventListener("dblclick", (e) => { const tr = e.target.closest("tr"); if (tr) abrirForm(Number(tr.dataset.id)); });
    $("linhas").addEventListener("mousedown", (e) => { if (e.shiftKey) e.preventDefault(); });   // sem selecionar texto
    // clique numa area vazia da lista limpa a selecao
    $("rolagem").addEventListener("click", (e) => {
      if (!e.target.closest("tr") && !e.target.closest("button") && s.selecao.size) { s.selecao.clear(); pintarSelecao(); }
    });

    $("btn-novo").onclick = $("vazio-novo").onclick = () => abrirForm(null);
    $("btn-editar").onclick = () => { if (s.selecao.size === 1) abrirForm([...s.selecao][0]); };
    $("btn-excluir").onclick = pedirExclusao;
    $("foto").onclick = async () => { if (s.detalheId) { const erro = await api.abrir_foto(s.detalheId); if (erro) DS.toast(erro); } };

    $("form").addEventListener("submit", salvar);
    $("form-fechar").onclick = $("form-cancelar").onclick = fecharForm;
    $("modal-form").addEventListener("mousedown", (e) => { if (e.target === $("modal-form")) fecharForm(); });
    $("btn-google").onclick = async () => { const erro = await api.buscar_no_google($("f-marca").value, $("f-modelo").value); if (erro) DS.toast(erro); };
    $("btn-escolher").onclick = async () => { const r = await api.escolher_foto(); if (r) { $("f-foto").value = r.caminho; mostrarPrevia(r.previa); } };
    $("btn-tirar-foto").onclick = () => { $("f-foto").value = ""; mostrarPrevia(null); };
    $("f-foto").addEventListener("change", async () => mostrarPrevia(await api.previa_foto($("f-foto").value)));
    $("f-tipo").addEventListener("input", () => { erroTipo(false); abrirSugestoes(); });
    $("f-tipo").addEventListener("focus", abrirSugestoes);
    $("f-tipo").addEventListener("blur", () => setTimeout(fecharSugestoes, 150));
    $("f-tipo").addEventListener("keydown", (e) => {
      const aberto = $("sugestoes").classList.contains("aberto");
      if (e.key === "ArrowDown") { if (!aberto) abrirSugestoes(); moverSugestao(1); e.preventDefault(); }
      else if (e.key === "ArrowUp" && aberto) { moverSugestao(-1); e.preventDefault(); }
      else if (e.key === "Enter" && aberto && sugestaoAtiva >= 0) {
        escolherSugestao($("sugestoes").querySelectorAll(".menu-item")[sugestaoAtiva].dataset.v); e.preventDefault();
      } else if (e.key === "Escape" && aberto) { fecharSugestoes(); e.stopPropagation(); e.preventDefault(); }
    });
    $("sugestoes").addEventListener("mousedown", (e) => { const b = e.target.closest(".menu-item"); if (b) { e.preventDefault(); escolherSugestao(b.dataset.v); } });

    $("excluir-nao").onclick = fecharExcluir;
    $("excluir-sim").onclick = confirmarExclusao;
    $("modal-excluir").addEventListener("mousedown", (e) => { if (e.target === $("modal-excluir")) fecharExcluir(); });

    document.addEventListener("keydown", (e) => {
      const excluindo = !$("modal-excluir").classList.contains("oculto");
      if (e.key === "Escape") {
        if (excluindo) fecharExcluir(); else if (formAberto()) fecharForm(); else if (s.selecao.size) { s.selecao.clear(); pintarSelecao(); }
        return;
      }
      if (formAberto() || excluindo) return;
      const digitando = ["INPUT", "TEXTAREA"].includes(document.activeElement?.tagName);
      if (digitando) return;
      if (e.key === "ArrowDown") { moverSelecao(1, e.shiftKey); e.preventDefault(); }
      else if (e.key === "ArrowUp") { moverSelecao(-1, e.shiftKey); e.preventDefault(); }
      else if (e.key === "Enter" && s.selecao.size === 1) { abrirForm([...s.selecao][0]); e.preventDefault(); }
      else if (e.key === "Delete" && s.selecao.size) { pedirExclusao(); e.preventDefault(); }
      else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "a") { s.linhas.forEach((l) => s.selecao.add(l.id)); pintarSelecao(); e.preventDefault(); }
    });

    document.documentElement.classList.add("pronto");
  }

  document.addEventListener("DOMContentLoaded", iniciar);
  return { _s: s, carregar };
})();
