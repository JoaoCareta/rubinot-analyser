(() => {
  const lista = document.querySelector('#referenciasResumo');
  if (!lista) return;
  const elemento = (tag, texto) => { const e = document.createElement(tag); e.textContent = texto; return e; };
  const data = instante => instante ? new Date(instante * 1000).toLocaleString('pt-BR') : 'data não registrada';
  async function atualizar() {
    try {
      const status = await fetch('/api/status').then(r => { if (!r.ok) throw Error(); return r.json(); });
      const char = status.fonte?.tipo === 'twitch' ? status.fonte.char : status.char;
      document.querySelector('#referenciasPersonagem').textContent = char ? 'Personagem: ' + char : 'Abra o jogo ou escolha um personagem na fonte para consultar suas referências.';
      lista.replaceChildren();
      if (!char) return;
      const registros = await fetch('/api/configuracoes?' + new URLSearchParams({char})).then(r => { if (!r.ok) throw Error(); return r.json(); });
      for (const [tipo, nome] of [['rtc','RTC'],['cura','Cura'],['roda','Roda de habilidades']]) {
        const card = elemento('article', ''); card.className = 'referencia-resumo';
        card.append(elemento('strong', nome));
        const referencia = registros.calibracoes?.[tipo], leitura = registros[tipo];
        card.append(elemento('p', referencia ? 'Referência guardada: ' + data(referencia.instante) : 'Sem referência manual guardada.'));
        card.append(elemento('p', leitura ? 'Última leitura: ' + data(leitura.instante) : 'Nenhuma leitura coletada.'));
        const link = elemento('a', 'Conferir ' + nome); link.href = '/configuracoes?' + new URLSearchParams({char, tipo});
        card.append(link); lista.append(card);
      }
    } catch {
      lista.textContent = 'Não foi possível consultar as referências. Tentando novamente…';
    }
  }
  atualizar(); setInterval(atualizar, 5000);
})();
