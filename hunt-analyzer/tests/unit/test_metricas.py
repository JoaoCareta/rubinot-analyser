import unittest
from rubinot.hunt.metricas import taxas, especies


class MetricasTest(unittest.TestCase):
    def test_lacuna_e_zero_tem_denominadores_distintos(self):
        t = taxas([{'dur': 120, 'xp_raw': 1000, 'profit': 0},
                   {'dur': 120, 'xp_raw': None, 'profit': None}])
        self.assertEqual(t['raw_h'], 30000)
        self.assertEqual(t['voltas_raw'], 1)
        self.assertEqual(t['media']['profit'], 0)
        self.assertIsNone(t['taxa']['sup_pt_h'])

    def test_mediana_superior_limites_e_parcial(self):
        vs = [{'dur': 359, 'xp_raw_15min': n} for n in [10, 20, 30, 40]]
        vs += [{'dur': 360, 'xp_raw_15min': 999}, {'dur': 20, 'parcial': True, 'xp_raw_15min': 999}]
        t = taxas(vs)
        self.assertEqual(t['raw_h'], 120)
        self.assertEqual((t['voltas'], t['refil'], t['parciais']), (4, 1, 1))

    def test_supplies_separados_e_especies_legadas(self):
        t = taxas([{'dur': 120, 'sup_pt': 200, 'sup_eu': 10}])
        self.assertEqual((t['taxa']['sup_pt_h'], t['taxa']['sup_eu_h']), (6000, 300))
        self.assertEqual(especies([{'loots': {'Livro': 2}}, {'loots': {'Livro': 3}}]), {'Livro': 5})
        self.assertEqual(especies([{'especies': {'Livro': 1}}, {'loots': {'Outro': 9}}]), {'Livro': 1})
