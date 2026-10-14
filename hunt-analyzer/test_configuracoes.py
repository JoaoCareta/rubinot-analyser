"""Contrato de evidência, isolamento e reconhecimento com a imagem real da roda."""
import pathlib
import tempfile
import unittest
from unittest.mock import patch
from PIL import Image, ImageDraw
import configuracoes as c


class ConfiguracoesTest(unittest.TestCase):
    def test_cura_icones_corretos_e_independentes_da_posicao(self):
        img=Image.open('tests/fixtures/leitores/cura-autocura.png').convert('RGB')
        textos=c.linhas(img)
        _,slots=c.cura_da_imagem(img,textos)
        self.assertEqual([(s['id'],s['vida_percent']) for s in slots[:3]],
                         [('mass_healing',75),('ultimate_healing',70),('restoration',60)])
        primeiro=img.crop((255,100,287,132));terceiro=img.crop((255,188,287,220))
        img.paste(terceiro,(255,100));img.paste(primeiro,(255,188))
        _,slots=c.cura_da_imagem(img,textos)
        self.assertEqual([s['id'] for s in slots[:3]],['restoration','ultimate_healing','mass_healing'])
        ImageDraw.Draw(img).rectangle((255,100,286,131),fill=(255,0,255))
        self.assertIsNone(c.cura_da_imagem(img,textos)[1][0]['id'])

    def test_rtc_sd_nao_exige_limiar_de_criaturas(self):
        slots=[{'tipo':'magia','slot':i+1,'estado':'vazio_confirmado'} for i in range(5)]
        slots += [{'tipo':'runa','slot':1,'id':'avalanche_rune','prioridade':2,'creatures':1},
                  {'tipo':'runa','slot':2,'id':'sudden_death_rune','prioridade':1,'creatures':None}]
        with patch.object(c,'rtc_da_imagem',return_value=({},slots)):
            s=c.observar('rtc',Image.new('RGB',(300,200)),'QA','teste',textos=[])['snapshot']
        self.assertTrue(s['completo'])
        import json
        alias=next(self.raiz.rglob('rtc_atual.json'))
        legado={**s,'completo':False}
        alias.write_text(json.dumps(legado),encoding='utf8')
        prova=alias.with_name(s['id']+'_rtc.json')
        prova.write_text(json.dumps(legado),encoding='utf8')
        with patch.object(c,'rtc_da_imagem',return_value=({},slots)):
            relida=c.observar('rtc',Image.new('RGB',(300,200)),'QA','teste',textos=[],capturado_em=s['instante'])['snapshot']
        self.assertTrue(relida['completo'])
        self.assertNotEqual(relida['id'],s['id'])
        self.assertFalse(json.loads(prova.read_text(encoding='utf8'))['completo'])
        self.assertEqual(c.consultar('QA')['rtc']['id'],relida['id'])
        slots[5]['creatures']=None
        with patch.object(c,'rtc_da_imagem',return_value=({},slots)):
            s=c.observar('rtc',Image.new('RGB',(300,200)),'QA','teste',textos=[])['snapshot']
        self.assertFalse(s['completo'])

    def test_vessels_isolado_de_botoes_da_roda(self):
        painel=Image.open(pathlib.Path(__file__).parent/'tests/fixtures/leitores/vessels-cura.png').convert('RGB')
        img=Image.new('RGB',(painel.width+340,painel.height),'black')
        img.paste(painel,(340,0))
        ImageDraw.Draw(img).rectangle((10,24,12,42),fill=(160,160,160))
        campos,_=c.campos_das_linhas('roda',c.linhas(img))
        self.assertEqual(campos['vessels.Damage and Healing'],'+3')
        self.assertEqual(campos['vessels.Heal Friend'],'+7.5%')
        self.assertNotIn('gemas.TR',campos)

    def test_bonus_visivel_nao_inventa_gema(self):
        linhas=[{'texto':'Vessels','x':100,'y':10},{'texto':'Strong Ice Wa...','x':60,'y':30},{'texto':'+12%','x':220,'y':30},
            {'texto':'Revelation Perks','x':100,'y':100},{'texto':'Blessing ofthe Gr... Stage 1','x':60,'y':120}]
        campos,_=c.campos_das_linhas('roda',linhas)
        self.assertEqual(campos['vessels.Strong Ice Wave'],'+12%')
        self.assertEqual(campos['revelation.Blessing of the Grove'],'Stage 1')
        self.assertFalse(any(k.startswith('gemas.') for k in campos))
        campos,_=c.campos_das_linhas('roda',[{**l,'texto':l['texto'].replace('Strong Ice','Strong ?ce').replace('Stage 1','Stage ?')} for l in linhas])
        self.assertNotIn('vessels.Strong Ice Wave',campos)
        self.assertNotIn('revelation.Blessing of the Grove',campos)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.raiz = pathlib.Path(self.tmp.name)
        self.patch = patch.object(c, 'RAIZ', self.raiz)
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self.tmp.cleanup()

    def test_confirmacao_versionada_e_total_visual(self):
        img=Image.new('RGB',(300,200),'black')
        c.observar('rtc',img,'QA','observacao',[{'texto':'Preset: ice','y':2}])
        c.pontos_total('QA',987)
        payload={'regras_versao':c._json(c.AQUI/'ui'/'roda_catalogo.json')['versao'],'modelo_versao':'temporal-1','contexto':{'char':'QA','total':987,'preset':'ice'},
                 'rtc':{'linhas':[]},'cura':{'linhas':[]},'roda':{'pontos':{}}}
        s=c.guardar_sugestao('QA',payload);c.confirmar('QA',s['id'])
        self.assertTrue(c.consultar('QA')['confirmacao']['valida'])
        self.assertNotIn('confirmacao',c.consultar('QA','s0',True))
        c.observar('rtc',img,'QA','observacao',[{'texto':'Preset: novo','y':2}])
        self.assertFalse(c.consultar('QA')['confirmacao']['valida'])
        with self.assertRaises(ValueError):c.confirmar('QA',s['id'])
        c.observar('roda',img,'QA','observacao',[{'texto':'Available Promotion Points','x':10,'y':20},{'texto':'3 / 990','x':10,'y':35}])
        self.assertEqual(c.pontos_total('QA')['valor'],990)
        self.assertEqual(c.pontos_total('QA')['origem'],'visual')
        with self.assertRaises(ValueError):c.guardar_sugestao('QA',payload)

    def test_reconhece_sem_calibrar_e_estabiliza(self):
        pasta=pathlib.Path('tests/fixtures/leitores')
        for tipo,arquivo in [('rtc','01-rtc-configurado.png'),('cura','cura.png'),('roda','roda-referencia.png')]:
            img=Image.open(pasta/arquivo).convert('RGB');leitor=c.Leitor(estabilizar=True)
            char='QA '+tipo
            leitor.processar_imagem(img,char)
            self.assertNotIn(tipo,c.consultar(char))
            leitor.processar_imagem(img,char)
            self.assertIn(tipo,c.consultar(char))
            n=len(list(self.raiz.rglob(f'*_{tipo}.json')))
            leitor.processar_imagem(img,char)
            self.assertEqual(n,len(list(self.raiz.rglob(f'*_{tipo}.json'))))
        s=c.consultar('QA cura')['cura']
        self.assertEqual(s['preset'],'ice')
        self.assertEqual([s['slots'][i]['vida_percent'] for i in range(2)],[90,75])
        self.assertEqual(s['slots'][0]['id'],'mass_healing')
        self.assertEqual(s['slots'][1]['id'],'ultimate_healing')
        self.assertFalse(s['aplicado_confirmado'])

    def test_eventos_sem_cast_nao_inventam_frequencia(self):
        import observacao_execucao as o
        cura=o.evento({'kind':'heal_other','value':500,'target':'Aliado','t':2},'quadro1','QA')
        r=o.avaliar({'id':'s'},[cura],[[0,10]],{})
        self.assertEqual(r['frequencia_observada'],{})
        cast=o.evento({'kind':'cast','words':'exura vita','t':3},'quadro2','QA')
        self.assertEqual(cast['magia_id'],'ultimate_healing')
        r=o.avaliar({'id':'s'},[cast,cast],[[0,10]],{})
        self.assertIsNone(r['falhas_por_ausencia'])
        self.assertEqual(r['frequencia_observada']['ultimate_healing'],6)
        self.assertFalse(o.revisar_latencia([cast])['aceita'])
        dados=[dict(cast,id=str(i),t=i+1,elegivel_em=i) for i in range(30)]
        revisao=o.revisar_latencia(dados)
        self.assertTrue(revisao['aceita'])
        self.assertEqual(revisao['modelo']['latencia_s'],1)
        self.assertEqual(revisao['modelo']['validacao'],10)

    def test_recursos_reais_sem_converter_bp_em_hp(self):
        import observacao_execucao as o
        img=Image.open('tests/fixtures/leitores/cura.png')
        r=o.recursos(img)
        self.assertEqual(r['vida']['atual'],5855)
        self.assertEqual(r['mana']['maxima'],32610)
        self.assertNotIn('vida',o.recursos(Image.new('RGB',(1920,1080),'black')))

    def test_parcial_isolada_e_prova(self):
        img = Image.new('RGB', (200, 100), 'black')
        a = c.observar('rtc', img, 'Personagem A', 'session_1', [{'texto': 'Preset: um', 'y': 2}])['snapshot']
        self.assertFalse(a['aplicado_confirmado'])
        self.assertIsNotNone(c.prova(a['prova']))
        self.assertIsNone(c.prova('../calibracao_print.png'))
        self.assertIn('rtc', c.consultar('Personagem A', 'session_1', True))
        self.assertNotIn('rtc', c.consultar('Personagem A', 'session_2', True))
        self.assertNotIn('rtc', c.consultar('Personagem B', 'session_1', True))
        b = c.observar('rtc', img, 'Personagem A', 'session_1', [{'texto': 'Preset: dois', 'y': 2}])['snapshot']
        self.assertNotEqual(a['id'], b['id'])
        self.assertEqual(b['preset'], 'dois')

    def test_qualidade_nao_apaga_e_nao_mistura_presets(self):
        img = Image.new('RGB', (200, 100), 'black')
        boas = [{'texto': 'Preset: um', 'y': 2}, {'texto': 'Available Promotion Points', 'y': 20, 'x': 10}, {'texto': '12 / 987', 'y': 35, 'x': 10}]
        c.observar('roda', img, 'A', 'session_1', boas)
        parcial = c.observar('roda', img, 'A', 'session_1', [{'texto': 'Preset: um', 'y': 2}, {'texto': '? / ?', 'y': 35}])['snapshot']
        self.assertEqual(parcial['campos']['pontos.total']['valor'], 987)
        nova = c.observar('roda', img, 'A', 'session_1', [{'texto': 'Preset: dois', 'y': 2}])['snapshot']
        self.assertNotIn('pontos.total', nova['campos'])
        self.assertFalse(nova['aplicado_confirmado'])

    def test_referencia_real_e_janela_movida(self):
        p = pathlib.Path('tests/fixtures/leitores/roda-referencia.png')
        if not p.exists():
            self.skipTest('Imagem de referência local indisponível')
        img = Image.open(p).convert('RGB')
        linhas = c.linhas(img)
        campos, _ = c.campos_das_linhas('roda', linhas)
        self.assertEqual(campos['pontos.total'], 987)
        self.assertEqual(campos['pontos.livres'], 12)
        self.assertEqual(campos['pontos.investidos'], 975)
        self.assertEqual(campos['conviction.Aug. Mass Healing'], 'I')
        self.assertEqual(campos['preset'], 'pt-dammage')
        snap = c.calibrar('roda', {'left': 5, 'top': 18, 'width': 999, 'height': 644}, p, 'A')['snapshot']
        self.assertEqual(snap['campos']['pontos.total']['valor'], 987)
        moved = Image.new('RGB', (1200, 800), 'black')
        moved.paste(img.crop((5,18,1004,662)), (100,80))
        arquivo = self.raiz/'f_000001.png';moved.save(arquivo)
        c.Leitor().processar(arquivo, 'A', 'session_2')
        lido = c.consultar('A', 'session_2', True)
        self.assertEqual(lido['roda']['campos']['pontos.total']['valor'], 987)
        self.assertFalse(lido['roda']['aplicado_confirmado'])

    def test_rtc_real_slots_campos_e_popup(self):
        pasta = pathlib.Path('tests/fixtures/leitores')
        p = pasta/'01-rtc-configurado.png'
        img = Image.open(p).crop((540,272,1381,738)).convert('RGB')
        leitura = c.observar('rtc',img,'A','s1')['snapshot']
        self.assertEqual(leitura['preset'],'ice')
        slots = leitura['slots']
        self.assertEqual(len(slots),7)
        self.assertEqual([s['id'] for s in slots[:4]],['eternal_winter','ice_burst','strong_ice_wave','forked_glacier'])
        self.assertEqual([s['creatures'] for s in slots[:4]],[7,4,3,1])
        self.assertEqual([s['prioridade'] for s in slots[:4]],[1,1,1,2])
        self.assertEqual([s['mana_percent'] for s in slots[:5]],[5]*5)
        self.assertEqual(slots[4]['estado'],'vazio_confirmado')
        self.assertEqual(slots[5]['creatures'],1)
        self.assertEqual(slots[5]['id'],'avalanche_rune')
        self.assertEqual(slots[6]['id'],'sudden_death_rune')
        self.assertIsNone(slots[6]['creatures'])
        self.assertFalse(leitura['aplicado_confirmado'])
        self.assertTrue(leitura['campos']['rtc.virar_para_alvo']['valor'])
        self.assertFalse(leitura['campos']['rtc.combo_em_ordem_de_prioridade']['valor'])
        popup = Image.open(pasta/'02-rtc-seletor.png').crop((540,272,1381,738))
        self.assertEqual(c.observar('rtc',popup,'A','s1')['snapshot']['slots'],[])
        # Trocar um ícone por vazio não pode manter a magia anterior no slot.
        mudada = img.copy();mudada.paste(img.crop((255,286,287,318)),(255,126))
        nova = c.observar('rtc',mudada,'A','s1')['snapshot']
        self.assertIsNone(nova['slots'][0]['id'])
        self.assertEqual(nova['slots'][0]['estado'],'vazio_confirmado')
        # Oclusão de um ícone deixa o campo desconhecido, sem falso vazio.
        mudada.paste((0,0,0),(255,166,287,198))
        nova = c.observar('rtc',mudada,'A','s1')['snapshot']
        self.assertIsNone(nova['slots'][1]['id'])
        self.assertEqual(nova['slots'][1]['estado'],'icone_nao_identificado')

    def test_rtc_calibracao_movimento_escala_e_deduplicacao(self):
        p = pathlib.Path('tests/fixtures/leitores/01-rtc-configurado.png')
        c.calibrar('rtc',{'left':540,'top':272,'width':841,'height':466},p,'A')
        img = Image.open(p).crop((540,272,1381,738)).resize((1682,932),Image.Resampling.NEAREST)
        moved = Image.new('RGB',(1850,1100),'black');moved.paste(img,(80,60))
        arquivo=self.raiz/'f_000002.png';moved.save(arquivo)
        leitor=c.Leitor();leitor.processar(arquivo,'A','s2')
        leitura=c.consultar('A','s2',True)['rtc']
        self.assertEqual(leitura['preset'],'ice')
        self.assertEqual(leitura['slots'][0]['id'],'eternal_winter')
        self.assertEqual(leitura['slots'][0]['creatures'],7)
        antes=len(list(self.raiz.rglob('*_rtc.json')))
        leitor.processar(arquivo,'A','s2')
        self.assertEqual(len(list(self.raiz.rglob('*_rtc.json'))),antes)
        # Cabeçalho sozinho, sem colunas, não cria uma configuração.
        parcial=Image.new('RGB',(841,466),'black');original=Image.open(p).crop((540,272,1381,738))
        parcial.paste(original.crop((590,36,670,56)),(590,36))
        self.assertEqual(c.rtc_da_imagem(parcial,c.linhas(parcial))[1],[])

    def test_roda_selecao_zero_nao_e_total(self):
        pasta=pathlib.Path('tests/fixtures/leitores')
        for nome,atual,limite in [('03-roda-ressonancia.png',50,50),('04-roda-magic-skill.png',75,75),('05-roda-mass-healing.png',100,100),('06-roda-mana-leech.png',0,150),('07-roda-healing-link.png',200,200)]:
            img=Image.open(pasta/nome).crop((460,182,1460,825))
            s=c.observar('roda',img,'A','s3')['snapshot']
            campos=s['campos']
            self.assertEqual(campos['selection.pontos']['valor'],atual)
            self.assertEqual(campos['selection.limite']['valor'],limite)
            self.assertIn('selection.nome',campos)
            self.assertFalse(campos['selection.efeito_ativo_confirmado']['valor'])
            self.assertEqual(campos['pontos.total']['valor'],987)
            self.assertEqual(s['preset'],'test-heal-link')
            self.assertFalse(s['aplicado_confirmado'])

    def test_casas_da_roda_por_numero_e_acumulacao(self):
        import leitura_jogo
        pasta=pathlib.Path('tests/fixtures/leitores')
        esperados={'03-roda-ressonancia.png':('QTL0',50),'04-roda-magic-skill.png':('QTL1',75),'05-roda-mass-healing.png':('QTL4',100),'06-roda-mana-leech.png':('QTL7',0),'07-roda-healing-link.png':('QTL8',200)}
        for nome,(fatia,n) in esperados.items():
            im=Image.open(pasta/nome).crop((460,182,1460,825));s=c.observar('roda',im,'QA','s')['snapshot']
            self.assertEqual(s['campos']['fatias.'+fatia]['valor'],n)
        self.assertEqual(s['casas_lidas'],5)
        self.assertFalse(s['completo'])
        self.assertEqual(s['campos']['fatias.QTL7']['valor'],0)
        # Oclusão da borda não permite inferir pontos pela fatia verde.
        im.paste((0,0,0),(237,70,767,597));txt=c.linhas(im);campos,_=c.campos_das_linhas('roda',txt)
        self.assertEqual(leitura_jogo.selecao_roda(im,c._json(c.AQUI/'ui'/'roda_catalogo.json'),txt,campos),{})

    def test_codigo_visual_e_paridade_do_grafo(self):
        import leitura_jogo,zlib,base64,json
        cat=c._json(c.AQUI/'ui'/'roda_catalogo.json')
        for voc,lista in cat['vocacoes'].items():
            for caminho in lista['caminhos_minimos']:
                self.assertTrue(leitura_jogo.validar_roda(cat,voc,caminho['pontos'],caminho['custo']))
                raw=bytearray([255]*48)
                for f in lista['fatias']:raw[f['indice']]=caminho['pontos'].get(f['id'],0)
                enc=zlib.compressobj(wbits=-15);b=enc.compress(raw)+enc.flush()
                codigo=('D0' if voc=='ED' else 'S0')+base64.urlsafe_b64encode(b).decode().rstrip('=')
                lido=leitura_jogo.codigo_visivel([{'texto':codigo}],cat,987)
                self.assertEqual(sum(v for k,v in lido.items() if k.startswith('fatias.')),caminho['custo'])
        self.assertEqual(leitura_jogo.codigo_visivel([{'texto':'D0????'}],cat,987),{})
        raiz=next(f for f in cat['vocacoes']['ED']['fatias'] if f['raiz'])
        filha=next(f for f in cat['vocacoes']['ED']['fatias'] if not f['raiz'] and raiz['id'] in f['conexoes'])
        self.assertFalse(leitura_jogo.validar_roda(cat,'ED',{raiz['id']:raiz['limite']-1,filha['id']:1},987))

    def test_vocacao_do_destinatario_explicita(self):
        import leitura_jogo
        slots=[{'tipo':'party','id':'heal_friend','destino_indice':1,'vocacao_destino':None}]
        campos={'heal_friend.destinos_texto':'Argano'}
        self.assertIsNone(leitura_jogo.destinatarios(slots,campos,[])[0]['vocacao_destino'])
        s=leitura_jogo.destinatarios(slots,campos,[{'nome':'Argano','vocacao':'EK'}])
        self.assertIsNone(s[0]['vocacao_destino']) # a lista não é a ordem das regras
        regras={'origem':'usuario','provas':['print'],'slots':{'heal_friend':{'1':'EK'}}}
        s=leitura_jogo.destinatarios(slots,campos,[{'nome':'Argano','vocacao':'EK'}],regras)
        self.assertEqual(s[0]['vocacao_destino'],'EK')

    def test_concordancia_cura_e_roda_nao_so_completude(self):
        sugestao={'rtc':{'linhas':[]},'cura':{'linhas':[{'id':'ultimate_healing','vida_percent':90}]},'roda':{'pontos':{'QTL0':50},'gemas':[]}}
        observado={'cura':{'completo':True,'slots':[{'tipo':'autocura','id':'ultimate_healing','vida_percent':75}]},'roda':{'completo':True,'campos':{'fatias.QTL0':{'valor':49}}}}
        r=c.concordancia(sugestao,observado)
        self.assertEqual(r['estado'],'divergente');self.assertEqual(len(r['diferencas']),2)

    def test_contexto_cast_explicito_e_gap(self):
        import contexto_execucao as ctx
        self.assertAlmostEqual(ctx.tempo_quadro('f_074459_250.png'),27899.25)
        quadros=[{'t':0,'vida':{'atual':500,'maxima':1000}},{'t':4,'vida':{'atual':600,'maxima':1000}},{'t':30,'vida':{'atual':700,'maxima':1000}}]
        r=ctx.construir('QA','s',[],quadros,[],[],{})
        self.assertEqual(len(r['cura']['janelas']),1);self.assertEqual(r['cura']['potencia_hp'],{})
        self.assertIsNone(r['cobertura'])

    def test_elegibilidade_nao_aprende_em_estado_parcial(self):
        import contexto_execucao as ctx
        cast={'t':3,'kind':'cast','qualidade':'identificada','magia_id':'atk'}
        linha={'id':'atk','cd':2,'grupo':2,'mana':20,'mana_percent':5,'creatures':2}
        s={'contexto':{'char':'QA'},'rtc':{'linhas':[linha]},'cura':{'linhas':[]}}
        recurso={'t':1,'mana':{'atual':100,'percentual':50},'criaturas':3}
        prev=[dict(cast,t=0)]
        self.assertEqual(ctx.elegibilidade(cast,s,prev,recurso,{'estado':'parcial'})['elegibilidade'],'inconclusiva')
        r=ctx.elegibilidade(cast,s,prev,recurso,{'estado':'confere'})
        self.assertEqual(r['elegivel_em'],2)
        recurso['criaturas']=1
        self.assertEqual(ctx.elegibilidade(cast,s,prev,recurso,{'estado':'confere'})['elegibilidade'],'condicao_ausente')

    def test_frequencia_union_de_intervalos_e_dedupe_entre_fontes(self):
        import observacao_execucao as o
        evento={'kind':'cast','words':'exura vita','ts':'10:00:01','t':1,'body':'You cast exura vita.'}
        a=o.evento(evento,'session_1/c_1.png','QA');b=o.evento(evento,'session_1/c_2.png','QA')
        self.assertEqual(a['id'],b['id'])
        r=o.avaliar({'id':'s'},[a,b],[[0,4],[2,6]],{})
        self.assertEqual(r['segundos_validos'],6);self.assertEqual(r['frequencia_observada']['ultimate_healing'],10)

    def test_escrita_invalida_preserva_ultimo_registro(self):
        p=self.raiz/'modelo.json';c._grava(p,{'valor':7})
        with self.assertRaises(ValueError):c._grava(p,{'valor':float('nan')})
        self.assertEqual(c._json(p),{'valor':7})

    def test_magnitude_normalizada_e_validacao_separada(self):
        import contexto_execucao as ctx
        magias=[{'id':'vita','tipo':'cura'}];eventos=[];quadros=[]
        for i in range(12):
            t=i*5;quadros.append({'t':t,'vida':{'atual':200,'maxima':2000}})
            eventos.extend([{'t':t,'kind':'cast','qualidade':'identificada','magia_id':'vita','base_multiplicador':1.2,'fixo_hp':20},
                            {'t':t+.5,'kind':'heal_self','alvo':'QA','value':1220}])
        modelo=ctx.construir('QA','s',eventos,quadros,[],magias)
        self.assertEqual(modelo['cura']['potencia_hp']['vita'],1000)
        self.assertEqual(modelo['cura']['qualidade']['vita']['validacao'],4)
        for e in eventos:e.pop('base_multiplicador',None)
        self.assertEqual(ctx.construir('QA','s',eventos,quadros,[],magias)['cura']['potencia_hp'],{})

    def test_vocacao_so_de_informacao_explicita(self):
        import contexto_execucao as ctx,events_build as ev
        kind,d=ev.classify('You see Argano (Level 900). He is an elite knight.')
        self.assertEqual(kind,'player_info')
        casts=[{'kind':'cast','qualidade':'identificada','magia_id':'heal_friend','alvo':'Argano','t':1}]
        r=ctx.construir('QA','s',casts,[],[],[])
        self.assertEqual(r['cura']['aliados'],[])
        r=ctx.construir('QA','s',[*casts,{'kind':kind,'t':2,**d}],[],[],[])
        self.assertEqual(r['cura']['aliados'][0]['vocacao'],'EK')

    def test_observador_cruza_dois_consoles_sem_duplicar(self):
        import observacao_execucao as o,events_build as ev
        sessao=self.raiz/'session_20261012_000000';sessao.mkdir()
        for nome in ('c_000001_000.png','s_000001_000.png','c_000002_000.png','s_000002_000.png'):(sessao/nome).touch()
        def mensagens(p,*_):
            return [('00:00:01','QA [100]: exura vita')] if p.name.startswith('s_') else [('00:00:01','You heal yourself for 100 hitpoints.')]
        import aprendizado_hunt as ah
        registro_original=ah.Registro
        with patch.object(ev,'frame_messages',side_effect=mensagens), patch.object(ah,'Registro',side_effect=lambda raiz:registro_original(self.raiz/'registro_qa')):
            obs=o.Observador();obs.processar(sessao,'QA');obs.processar(sessao,'QA')
        casts=[e for e in obs.eventos if e['kind']=='cast']
        self.assertEqual(len(casts),1);self.assertEqual(casts[0]['magia_id'],'ultimate_healing')
        self.assertEqual(obs.intervalos,[[1,2]])
        self.assertEqual(len(obs.eventos),2)

    def test_normaliza_blessing_apenas_com_vida_recente(self):
        import observacao_execucao as o
        linha={'id':'ultimate_healing','multiplicador_base':1.2,'blessing':.1}
        obs={'concordancia':{'estado':'confere'},'sugestao':{'contexto':{'char':'QA'},'cura':{'linhas':[linha]},'roda':{'efeitos':{'fixo_hp':20}}}}
        e={'magia_id':'ultimate_healing','t':10,'alvo':'QA'}
        o.normalizar_cast(e,obs,{'t':9.5,'vida':{'percentual':20}})
        self.assertAlmostEqual(e['base_multiplicador'],1.44)
        outro={'magia_id':'ultimate_healing','t':10,'alvo':'QA'}
        o.normalizar_cast(outro,obs,{'t':5,'vida':{'percentual':20}})
        self.assertNotIn('base_multiplicador',outro)

    def test_sio_com_aspas_duplas_do_cliente(self):
        import observacao_execucao as o
        e=o.evento({'kind':'speech','actor':'QA','text':"exura sio ''Argano''",'t':1},'s/s_1.png','QA')
        self.assertEqual(e['magia_id'],'heal_friend');self.assertEqual(e['alvo'],'Argano')

    def test_especies_e_console_parcial_nao_calibram_cobertura(self):
        import contexto_execucao as ctx
        magias=[{'id':'fork','tipo':'ofensiva','cd':6,'grupo':2},{'id':'cura','tipo':'cura'}]
        eventos=[]
        for i in range(15):
            t=i*4
            eventos.extend([{'id':f'f{i}','kind':'cast','t':t,'magia_id':'fork','qualidade':'identificada'},
                {'id':f'c{i}','kind':'cast','t':t,'magia_id':'cura','qualidade':'identificada'},
                *[{'id':f'd{i}.{j}','kind':'damage_dealt','t':t,'ts':str(t),'alvo':'rage squid','value':100+j} for j in range(3)]])
        self.assertIsNone(ctx.construir('QA','s',eventos,[],[],magias)['cobertura'])
        r=ctx.calibrar_ataque('QA','s',eventos,magias,{})
        self.assertEqual(r['magias']['fork']['com_dano_associado'],15)
        self.assertEqual(r['magias']['fork']['linhas_dano_associadas'],45)
        self.assertFalse(r['cobertura_completa'])

    def test_intervalo_efetivo_holdout_e_sem_misturar_configuracoes(self):
        import contexto_execucao as ctx,datetime
        magias=[{'id':'fork','tipo':'ofensiva','cd':6,'grupo':2}]
        eventos=[{'id':str(i),'kind':'cast','t':100+i*4,'magia_id':'fork','qualidade':'identificada'} for i in range(45)]
        r=ctx.calibrar_ataque('QA','s',eventos,magias,{})
        self.assertEqual(r['intervalos_efetivos']['fork']['segundos'],4)
        self.assertEqual(r['intervalos_efetivos']['fork']['validacao'],10)
        self.assertEqual(r['intervalos_efetivos']['fork']['erro_depois'],0)
        # Uma duplicata de fala no mesmo segundo não é um segundo lançamento.
        duplicada=[*eventos,dict(eventos[0],id='outro')]
        self.assertEqual(ctx.calibrar_ataque('QA','s',duplicada,magias,{})['magias']['fork']['lancamentos'],45)
        insuficiente=ctx.calibrar_ataque('QA','s',eventos[:29],magias,{})
        self.assertEqual(insuficiente['intervalos_efetivos'],{})
        recente={'instante':datetime.datetime(2026,10,12,0,4,0).timestamp()}
        self.assertLess(ctx.calibrar_ataque('QA','s',eventos,magias,recente)['magias']['fork']['lancamentos'],15)
        ruim=[*eventos[:-10],*[dict(e,t=eventos[-11]['t']+(j+1)*6) for j,e in enumerate(eventos[-10:])]]
        self.assertEqual(ctx.calibrar_ataque('QA','s',ruim,magias,{})['intervalos_efetivos'],{})


    def test_cura_calibracao_com_margem_e_barra_variavel(self):
        original = Image.open('tests/fixtures/leitores/cura.png').convert('RGB')
        painel = original.crop((540,272,1381,738))
        # A aba pressionada e sua barra variam; o conteúdo comprova Cura.
        painel.paste((70,70,70), (12,27,407,63))
        tela = Image.new('RGB', (1100,700), 'black')
        tela.paste(painel, (100,100))
        arquivo = self.raiz/'cura_margem.png'
        tela.save(arquivo)
        r = c.calibrar('cura', {'left':80,'top':70,'width':881,'height':506}, arquivo, 'QA')['snapshot']
        self.assertEqual(r['slots'][0]['id'], 'mass_healing')
        self.assertEqual(r['slots'][0]['vida_percent'], 90)
        c.Leitor().processar_imagem(tela, 'Outro', 's')
        self.assertIn('cura', c.consultar('Outro', 's', True))
        self.assertNotIn('rtc', c.consultar('Outro', 's', True))
        movida = Image.new('RGB', (1200,800), 'black')
        movida.paste(tela.crop((80,70,961,576)), (150,140))
        movida.save(arquivo)
        c.Leitor().processar(arquivo, 'QA', 's2')
        self.assertEqual(c.consultar('QA', 's2', True)['cura']['slots'][0]['vida_percent'], 90)

    def test_cura_aba_inativa_e_indicativos_fora_do_painel_rejeitados(self):
        rtc = Image.open('tests/fixtures/leitores/01-rtc-configurado.png').convert('RGB')
        self.assertEqual(c.cura_da_imagem(rtc, c.linhas(rtc))[1], [])
        arquivo = self.raiz/'rtc.png'
        rtc.save(arquivo)
        with self.assertRaises(ValueError):
            c.calibrar('cura', {'left':540,'top':272,'width':841,'height':466}, arquivo, 'QA')
        self.assertNotIn('cura', c.consultar('QA'))
        from rubinot.observacao.configuracao import ancora_cura
        self.assertIsNone(ancora_cura([
            {'texto':'Cura','x':203,'y':41},
            {'texto':'Cura por magia','x':278,'y':200},
            {'texto':'Treino de mana','x':665,'y':200}]))


    def test_guardar_automatico_e_troca_de_abas_na_hunt(self):
        pasta = pathlib.Path('tests/fixtures/leitores')
        leitor = c.Leitor()
        for tipo, nome in [('rtc','01-rtc-configurado.png'), ('cura','cura.png'), ('roda','roda-referencia.png')]:
            p = pasta/nome
            s = c.calibrar('auto', {}, p, 'QA')['snapshot']
            self.assertEqual(s['tipo'], tipo)
            self.assertTrue(s['slots'] if tipo != 'roda' else s['campos']['pontos.total'])
            f = self.raiz/f'q_{tipo}.png'
            Image.open(p).save(f)
            leitor.processar(f, 'QA', 'hunt_teste')
            self.assertEqual(c.ESTADO_LEITOR['janelas'], [tipo])
            observado = c.consultar('QA','hunt_teste',True)
            self.assertIn(tipo, observado)
            if tipo == 'cura':
                # O título RTCaster continua visível, mas sua aba está inativa.
                self.assertEqual(observado['rtc']['preset'], 'ice')
                self.assertTrue(all(s.get('atual') for s in observado['rtc']['slots']))
        preto = self.raiz/'preto.png'
        Image.new('RGB',(1000,700),'black').save(preto)
        with self.assertRaises(ValueError):c.calibrar('auto', {}, preto, 'QA')

    def test_monitor_usa_quadro_atual_sem_esperar_proximo_f(self):
        from rubinot.bootstrap.monitor import Monitor
        for nome in ['f_140001.png','q_140001.png','q_140003.png','c_140004.png']:
            (self.raiz/nome).touch()
        self.assertEqual(Monitor._quadros(self.raiz)[-1].name, 'q_140003.png')
        self.assertEqual(Monitor._quadros(None), [])
        m = Monitor(lambda: None, lambda: False, lambda: {})
        self.assertFalse(m.leitor.estabilizar)


if __name__ == '__main__':
    unittest.main()
