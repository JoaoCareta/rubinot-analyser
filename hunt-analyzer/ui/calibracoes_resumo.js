(() => {
  const lista = document.querySelector('#referenciasResumo');
  if (!lista) return;
  const elemento = (tag, texto) => { const e = document.createElement(tag); e.textContent = texto; return e; };
  const data = instante => instante ? new Date(instante * 1000).toLocaleString('pt-BR') : 'data não registrada';
  const aviso = elemento('p', ''); aviso.hidden = true; aviso.setAttribute('role', 'status'); lista.after(aviso);
  const cards = new Map();
  let consultando = false, personagem;
  const texto = (e, valor) => { if (e.textContent !== valor) e.textContent = valor; };
  async function atualizar() {
    if (consultando) return;
    consultando = true;
    try {
      const status = await fetch('/api/status').then(r => { if (!r.ok) throw Error(); return r.json(); });
      const char = status.fonte?.tipo === 'twitch' ? status.fonte.char : status.char;
      const registros = char ? await fetch('/api/configuracoes?' + new URLSearchParams({char})).then(r => { if (!r.ok) throw Error(); return r.json(); }) : null;
      // Só publica uma resposta completa. Esvaziar antes do await encolhia
      // também o card da fonte, que compartilha a mesma linha da grade.
      texto(document.querySelector('#referenciasPersonagem'), char ? 'Personagem: ' + char : 'Abra o jogo ou escolha um personagem na fonte para consultar suas referências.');
      aviso.hidden = true;
      if (personagem !== char || !cards.size) { lista.replaceChildren(); cards.clear(); personagem = char; }
      if (!char) return;
      for (const [tipo, nome] of [['rtc','RTC'],['cura','Cura'],['roda','Roda de habilidades']]) {
        if (!cards.has(tipo)) {
          const card = elemento('article', ''); card.className = 'referencia-resumo';
          const referencia = elemento('p', ''), leitura = elemento('p', ''), uso = elemento('p', '');
          const link = elemento('a', 'Conferir ' + nome); link.href = '/configuracoes?' + new URLSearchParams({char, tipo});
          card.append(elemento('strong', nome), referencia, leitura);
          if (tipo === 'rtc') card.append(uso);
          card.append(link); lista.append(card); cards.set(tipo, {referencia, leitura, uso});
        }
        const card = cards.get(tipo);
        const referencia = registros.calibracoes?.[tipo], leitura = registros[tipo];
        texto(card.referencia, referencia ? 'Referência guardada: ' + data(referencia.instante) : 'Sem referência manual guardada.');
        texto(card.leitura, leitura ? 'Última leitura: ' + data(leitura.visto_por_ultimo_em||leitura.instante) : 'Nenhuma leitura coletada.');
        if(tipo==='rtc')texto(card.uso,registros.uso_componentes?.rtc?.uso_confirmado?'Uso confirmado na calibração.':'Uso desta leitura ainda não confirmado.');
      }
    } catch {
      texto(aviso, 'Não foi possível atualizar as referências. Tentando novamente…'); aviso.hidden = false;
    } finally { consultando = false; }
  }
  atualizar(); setInterval(atualizar, 5000);
})();
