import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image
import painel_stream as ps
from rubinot.observacao import geometria_paineis as geo, paineis, itens_painel
from rubinot.adapters import paineis as diario
from rubinot.hunt.metricas import tempo_sessao

FIXTURES = Path(__file__).resolve().parents[1]/'fixtures'/'leitores'


def quadro(nome='xp-adaptativo', pos=(30,40), tamanho=(600,700)):
    im = Image.new('RGB',tamanho,(45,45,45))
    with Image.open(FIXTURES/(nome+'.png')) as painel:
        im.paste(painel,pos)
    return im


class PaineisAdaptativosTest(unittest.TestCase):
    def test_xp_segue_posicao_sem_calibracao_e_nao_inclui_scrollbar(self):
        for pos in [(30,40),(380,215)]:
            im = quadro(pos=pos)
            valores = ps.ler_xp(im,Path('.'))
            self.assertEqual(valores['RawXPGain'],18844571)
            self.assertEqual(valores['XP/h'],112914432)
            self.assertEqual(geo.detectar(im)['regioes']['xp']['box'][0],pos[0]+4)

    def test_largura_e_medida_na_moldura(self):
        with Image.open(FIXTURES/'xp-adaptativo.png') as ref:
            largo = Image.new('RGB',(ref.width+72,ref.height),(60,60,60))
            largo.paste(ref.crop((0,0,161,ref.height)),(0,0))
            largo.paste(ref.crop((161,0,ref.width,ref.height)),(233,0))
        im = Image.new('RGB',(600,700),(45,45,45)); im.paste(largo,(40,50))
        r = geo.detectar(im)['regioes']['xp']
        self.assertGreater(r['box'][2]-r['box'][0],210)
        self.assertEqual(ps.ler_xp(im,Path('.'))['RawXPGain'],18844571)

    def test_escala_dupla_normaliza_sem_mudar_numero(self):
        im=quadro().resize((1200,1400),Image.Resampling.NEAREST)
        self.assertEqual(ps.ler_xp(im,Path('.'))['RawXPGain'],18844571)
        self.assertEqual(geo.detectar(im)['regioes']['xp']['escala'],2)

    def test_oculto_e_ambiguo_nao_reusam_coordenada(self):
        im=quadro(); self.assertIn('xp',geo.detectar(im)['regioes'])
        outro=Image.new('RGB',im.size,(45,45,45))
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);(p/'calibracao.json').write_text(json.dumps({'regioes':{'xp':{'left':34,'top':55,'width':157,'height':230}}}))
            self.assertEqual(ps.ler_xp(outro,p),{})
        duplo=quadro()
        with Image.open(FIXTURES/'xp-adaptativo.png') as painel: duplo.paste(painel,(300,40))
        self.assertIn('xp',geo.detectar(duplo)['ambiguos'])
        self.assertEqual(ps.ler_xp(duplo,Path('.')),{})

    def test_tempo_apenas_party_inclusive_zero_reset_e_ausente(self):
        im=quadro('party-cabecalho')
        self.assertEqual(ps.ler_tempo_sessao(im,Path('.')),3840)
        self.assertIsNone(ps.ler_tempo_sessao(quadro(),Path('.')))
        self.assertEqual(ps.tempo_sessao(['Session: 00:00h']),0)
        self.assertEqual(ps.tempo_sessao(['Session: 27:04h']),97440)
        for texto in ['Session: 01:60h','Session: ?1:04h','Session: 1:04?']:
            self.assertIsNone(ps.tempo_sessao([texto]))

    def test_estimativas_nao_invalidam_economia(self):
        with patch.object(ps,'recortar_painel',return_value=Image.new('RGB',(100,100))), patch.object(ps,'ler',return_value=({'Loot':100,'Supplies':70,'Balance':30,'RawXPGain':999},[])), patch.object(ps,'ler_xp',return_value={}):
            v,_=ps.ler_quadro(Image.new('RGB',(100,100)),Path('.'),(0,0,90,90),90)
        self.assertEqual(v,{'Loot':100,'Supplies':70,'Balance':30})

    def test_input_elementos_percentuais_e_total_no_quadro_real(self):
        r=ps.ler_input(quadro('input-adaptativo'),Path('.'))
        self.assertEqual(r['total'],1254505)
        self.assertEqual(r['max_dps'],5316)
        self.assertEqual([x['tipo'] for x in r['tipos']],['morte','terra','fisico','gelo','fogo'])
        self.assertEqual(sum(x['valor'] for x in r['tipos']),1254505)
        self.assertEqual(r['tipos'][0]['percentual'],44.9)
        self.assertEqual(r['modo'],'desconhecido')

    def test_input_digito_desconhecido_nao_vira_sufixo_valido(self):
        rows=[{'texto':'Damage Types','box':[0,0,100,10]}, {'texto':'? 1?562 (44.9%)','box':[0,20,100,30]}]
        with patch.object(ps,'linhas_detalhadas',return_value=rows):
            self.assertEqual(ps.distribuicao_input(Image.new('RGB',(150,150)))['tipos'],[])

    def test_numero_abreviado_e_lista_parcial(self):
        r=paineis.campos('hunt',['Damage: 11,373k','Session: 01:06h'])
        self.assertEqual(r['Damage']['valor'],11373000)
        self.assertEqual(r['Damage']['resolucao'],1000)
        self.assertNotIn('Session',r)
        membros=paineis.membros_party(['Player One','? 10','? 20','? 30','Player Two','? -10','? 40'])
        self.assertTrue(membros[0]['completo']);self.assertFalse(membros[1]['completo'])
        self.assertIsNone(membros[1]['cura']['valor'])

    def test_itens_sao_estimativas_e_nao_consumo_exato(self):
        im=quadro('supply-adaptativo')
        r=itens_painel.ler(ps.recortar_painel(im,Path('.'),'supply'))
        self.assertTrue(r['itens'])
        self.assertTrue(all(i['estimativa'] for i in r['itens']))
        self.assertIn(164,[i['quantidade'] for i in r['itens']])

    def test_diario_conserva_revisoes_e_pendentes_anteriores(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp); (p/'paineis').mkdir();diario.gravar(p/'paineis'/'pendentes.json',{'f_antigo.png':{'t':0}})
            for i,pos in enumerate([(30,40),(300,200)]):
                im=quadro(pos=pos);nome=f'f_00000{i}_000.png';im.save(p/nome)
                diario.registrar(im,p,nome,i)
            linhas=[json.loads(s) for s in (p/'paineis'/'observacoes.jsonl').read_text(encoding='utf8').splitlines()]
            self.assertNotEqual(linhas[0]['layout']['revisao'],linhas[1]['layout']['revisao'])
            self.assertEqual(len(list((p/'paineis'/'provas').glob('*.png'))),2)
            self.assertIn('f_antigo.png',diario.ler_json(p/'paineis'/'pendentes.json'))
            self.assertIsNone(diario.resumo(p)['tempo_sessao_s'])

    def test_falha_de_leitura_mantem_quadro_pendente(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)
            with patch.object(paineis,'ler',side_effect=RuntimeError('leitor indisponÃ­vel')):
                with self.assertRaises(RuntimeError):diario.registrar(quadro(),p,'f_000001_000.png',1)
            self.assertIn('f_000001_000.png',diario.ler_json(p/'paineis'/'pendentes.json'))

    def test_retencao_nao_apaga_quadros_pendentes(self):
        import ao_vivo
        with tempfile.TemporaryDirectory() as tmp:
            raiz=Path(tmp);p=raiz/'session_20261013_010000';p.mkdir();(p/'paineis').mkdir()
            im=p/'f_010000_000.png';quadro().save(im)
            diario.gravar(p/'paineis'/'pendentes.json',{im.name:{'t':3600}})
            self.assertEqual(ao_vivo.limpa_quadros(raiz=raiz),(0,0))
            self.assertTrue(im.exists())

    def test_party_cortado_nao_vira_total_de_tres_membros(self):
        import ks
        import layout
        textos=['Session: 01:04h','Loot: 100','Supplies: 70','Balance: 30',
                'Player One','10','100','50','Player Two','10','100','50',
                'Player Three','10','100','50','Player Four','0']
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'f_010000_000.png';quadro().save(p)
            with patch.object(ps,'recortar_painel',return_value=Image.new('RGB',(160,200))), patch.object(ks.Leitor,'linhas',return_value=[(t,0,10) for t in textos]), patch.object(ps,'linhas',return_value=textos), patch.object(ps,'ler_quadro',return_value=({},[])), patch.object(ps,'ler_xp',return_value={}):
                self.assertIsNone(ks.Leitor().party(p,layout.LEGADO,'Player One'))

    def test_paridade_do_tempo_sessao(self):
        casos=[{},None,*[{'tempo_sessao_s':v,'tempo_sessao_origem':fonte} for v in [None,0,60,60.0,60.5,97440,-1,True,'60',9007199254740992] for fonte in ['Party Hunt','Hunt Analyser',None]]]
        js="const t=require('./ui/taxas.js');let s='';process.stdin.on('data',c=>s+=c);process.stdin.on('end',()=>console.log(JSON.stringify(JSON.parse(s).map(t.tempoSessao))));"
        r=subprocess.run(['node','-e',js],input=json.dumps(casos),capture_output=True,text=True,timeout=10,check=True)
        self.assertEqual(json.loads(r.stdout),[tempo_sessao(c) for c in casos])


if __name__=='__main__':unittest.main()
