"""Entrada única do executável distribuído, com módulos compilados."""
import json
import os
import pathlib
import sys


def main():
    os.chdir(pathlib.Path(__file__).resolve().parent)
    if "--autoteste" in sys.argv:
        import app
        import ao_vivo
        import capture
        import lap_watch
        import ks
        import runtime
        import av
        import truststore
        from streamlink import Streamlink
        from streamlink.plugins.twitch import Twitch
        stream_session = Streamlink()
        assert Twitch(stream_session, 'https://www.twitch.tv/9dude') is not None
        stream_session.http.close()
        assert av.Codec('h264', 'r') is not None
        assert app.ao_vivo is not None, getattr(app, "ERRO_AO_VIVO", "motor indisponível")
        assert ao_vivo.taxas([]) is not None
        assert app.BOTAO_X.size > 0 and app.GLYPHS
        assert all((app.AQUI / p).is_file() for p in
                   ("ui/index.html", "ui/hunt.html", "ui/taxas.js", "pin_template.png"))
        assert runtime.comando("capture", "teste")[-1] == "teste"
        assert pathlib.Path(runtime.comando("capture", "teste")[0]).is_file()
        resultado = {"ok": True, "compilado": runtime.COMPILADO,
                     "comando": runtime.comando("capture", "teste")}
        if "--resultado" in sys.argv:
            pathlib.Path(sys.argv[sys.argv.index("--resultado") + 1]).write_text(
                json.dumps(resultado, ensure_ascii=False), encoding="utf-8")
        else:
            print(json.dumps(resultado, ensure_ascii=False))
        return
    if len(sys.argv) >= 3 and sys.argv[1] == "--processo":
        processo = sys.argv[2]
        sys.argv = [sys.argv[0], *sys.argv[3:]]
        if processo == "app":
            import app
            app.main()
        elif processo == "capture":
            import capture
            capture.main()
        elif processo == "lap_watch":
            import lap_watch
            lap_watch.main()
        elif processo == "ks":
            import ks
            ks.main()
        else:
            raise ValueError(f"Processo desconhecido: {processo}")
    else:
        import controle
        controle.main()


if __name__ == "__main__":
    main()
