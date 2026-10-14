import base64
import io
import json
import tempfile
import time
import unittest
from unittest.mock import patch

import numpy as np
from PIL import Image

from rubinot.planejamento import residual
from rubinot.assistencia import aprendizado
from rubinot.adapters.diario_assistencia import Diario
from rubinot.assistencia.utamo import Utamo
from rubinot.observacao.supplies import hotkeys, ler_numero
from rubinot.hunt.metricas import variacoes_estoque, consumo_itens


class AprendizadoIntegradoTest(unittest.TestCase):
    def dados(self):
        return [dict(origem_id=str(i), sessao=str(i), instante=i*100, contexto={'hunt':'QA'},
                     grupo='TwinII', faixa=5, previsto=10, observado=20) for i in range(6)]

    def test_residual_sessoes_futuras_e_contextos_isolados(self):
        rows = self.dados()
        m = residual.treinar(rows)
        self.assertTrue(m['promover'])
        self.assertEqual(m['treino_sessoes'], ['0','1','2'])
        self.assertEqual(m['teste_sessoes'], ['4','5'])
        self.assertEqual(residual.prever(m['perfis'], {**rows[0], 'contexto':{'hunt':'outra'}}), 10)
        self.assertFalse(residual.treinar(rows, m)['promover'])
        self.assertEqual(residual.treinar(rows*20)['amostras'], 6)
        self.assertEqual(residual.treinar([{**r,'qa':True} for r in rows])['amostras'],0)

    def test_residual_rejeita_piora_e_sessoes_sobrepostas(self):
        rows=self.dados(); rows[-1]['observado']=5
        self.assertFalse(residual.treinar(rows)['promover'])
        rows=self.dados()+[{**self.dados()[0], 'origem_id':'novo','instante':450}]
        self.assertEqual(residual.treinar(rows)['estado'],'sessoes_sobrepostas')
        rows=self.dados()+[{**self.dados()[0], 'origem_id':'nan','observado':float('nan')}]
        self.assertEqual(len(residual.validos(rows)),6)

    def observacoes(self):
        return [dict(id=str(i),sessao='s',contexto={'hunt':'QA'},tipo='observacao',t=i,
                     instante=i,combate=True,escudo=False,vida=.99,certificado=True,
                     dano=300,caido_s=i,pronta=True) for i in range(9)]

    def test_utamo_censura_intervencao_lacuna_e_duplicados(self):
        rows=self.observacoes()
        self.assertEqual(len(aprendizado.episodios(rows*2)),1)
        rows[4]['som_recente']=True
        self.assertEqual(aprendizado.episodios(rows),[])
        rows[8]['vida']=.5
        self.assertTrue(aprendizado.episodios(rows)[0]['perigo_futuro'])
        self.assertEqual(aprendizado.episodios([rows[0],rows[-1]]),[])
        rows[5]['certificado']=False
        self.assertEqual(aprendizado.episodios(rows),[])

    def test_diario_congela_retomada_e_preserva_linha_incompleta(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=Diario(tmp,'s',{'hunt':'QA'},8,100)
            d.guardar({'id':'a','tipo':'aviso'})
            d.guardar({'id':'a','tipo':'aviso'})
            with d.arquivo.open('a',encoding='utf8') as f: f.write('{"incompleta":')
            with patch('rubinot.adapters.diario_assistencia.treinar', side_effect=AssertionError('retreinou')):
                outro=Diario(tmp,'s',{'hunt':'QA'},8,200)
            outro.guardar({'id':'b','tipo':'aviso'})
            linhas=d.arquivo.read_text(encoding='utf8').splitlines()
            self.assertEqual(len(linhas),3)
            self.assertEqual(json.loads(linhas[-1])['id'],'b')
            self.assertEqual(outro.politica,d.politica)

    def test_emergencia_independe_de_prontidao_e_nao_usa_vida_antiga(self):
        u=Utamo();u.som=False;u.pasta='s';u.agora=100;u.vida=.5;u.vida_t=100
        u.escudo_on=False;u.escudo_t=100
        u.observacao=('s','QA',{},dict(id='q',t=100,instante=100,processado_em=time.time(),
                                     prontidao={'magic_shield':{'pronta':False}}),'')
        u._avalia()
        self.assertEqual(len(u.historico),1)
        u.agora=140;u._avalia()
        self.assertEqual(len(u.historico),1)

    def test_prontidao_negativa_cala_recast(self):
        u=Utamo();u.som=False;u.pasta='s';u.agora=100;u.escudo_on=False;u.escudo_t=100;u.caiu_desde=0
        u.eventos.append((100,'damage_taken',3000,'criatura'))
        u.observacao=('s','QA',{},dict(id='q',t=100,instante=100,processado_em=time.time(),
                                     prontidao={'magic_shield':{'pronta':False}}),'')
        u._avalia();self.assertEqual(u.historico,[])

    def test_ocr_estoque_rejeita_ambiguidade_e_preserva_identidade_pendente(self):
        rng=np.random.default_rng(33);sprite=rng.integers(0,150,(5,5,3),dtype=np.uint8)
        glyph=np.array([[1,0,1],[1,1,1],[0,0,1]],dtype=np.uint8)
        tela=Image.new('RGB',(60,30));tela.paste(Image.fromarray(sprite),(10,4))
        tela.paste(Image.fromarray(np.repeat((glyph*255)[:,:,None],3,2)),(10,12))
        b=io.BytesIO();Image.fromarray(sprite).save(b,format='PNG')
        refs={'digitos':{'4':[glyph.tolist()]},'itens':[dict(item='desconhecido',
              referencia_visual_confirmada=True,icone=base64.b64encode(b.getvalue()).decode(),contador_relativo=[0,8,3,3])]}
        rows=hotkeys(tela,refs,'QA',0,'q','s')
        self.assertEqual(rows[0]['valor'],4);self.assertFalse(rows[0]['identidade_confirmada'])
        tela.paste(Image.fromarray(sprite),(40,4))
        self.assertEqual(hotkeys(tela,refs,'QA',0,'q','s'),[])
        self.assertIsNone(ler_numero(Image.new('RGB',(10,10)),refs['digitos']))

    def test_estoque_nao_vira_consumo_e_refil_nao_vira_gasto(self):
        rows=[dict(t=t,char='QA',item='mana',serie='s',origem='estoque_hotkey',
                   unidade='unidades',valor=v,local=[10,20],prova=str(t),
                   preco_observado={'gold':488,'origem':'NPC'}) for t,v in [(0,10),(2,8),(4,20),(20,19)]]
        a,b,c=variacoes_estoque(rows)
        self.assertEqual(a['custo_estimado_gold'],976)
        self.assertIsNone(a['consumo_confirmado'])
        self.assertIsNone(b['quantidade_estimada']);self.assertIsNone(c['quantidade_estimada'])
        self.assertEqual(consumo_itens(rows),[])


if __name__=='__main__': unittest.main()
