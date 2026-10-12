"""Gera/verifica snapshots do componente canônico, mantendo repos separados."""
import argparse
import hashlib
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--verificar', action='store_true')
    args = p.parse_args()
    origem = ROOT / 'hunt-analyzer/ui/shared/tracker.js'
    conteudo = origem.read_bytes()
    sha = hashlib.sha256(conteudo).hexdigest()
    destinos = [ROOT / nome / 'public/shared/tracker.js' for nome in ('loe-hunt-tracker-solo', 'loe-hunt-tracker')
                if (ROOT / nome).is_dir()]
    for destino in destinos:
        manifesto = destino.with_suffix('.manifest.json')
        if args.verificar:
            assert destino.read_bytes() == conteudo, f'Snapshot divergente: {destino}'
            assert json.loads(manifesto.read_text(encoding='utf8'))['sha256'] == sha
        else:
            destino.parent.mkdir(parents=True, exist_ok=True)
            destino.write_bytes(conteudo)
            manifesto.write_text(json.dumps({'fonte': 'hunt-analyzer/ui/shared/tracker.js', 'sha256': sha}, indent=2), encoding='utf8')
    print(f'Snapshots equivalentes: {len(destinos)}')


if __name__ == '__main__':
    main()
