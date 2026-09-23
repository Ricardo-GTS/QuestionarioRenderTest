from io import StringIO

from django.core.management import call_command

from apps.questions import services


def test_warm_ollama_loads_model(monkeypatch):
    calls = []
    monkeypatch.setattr(services, "get_embedding", lambda text: calls.append(text) or [0.0])
    out = StringIO()
    call_command("warm_ollama", stdout=out)
    assert len(calls) == 1
    assert "modelo carregado" in out.getvalue()


def test_warm_ollama_never_fails_startup(monkeypatch):
    def down(text):
        raise services.EmbeddingServiceError("ollama fora")

    monkeypatch.setattr(services, "get_embedding", down)
    err = StringIO()
    call_command("warm_ollama", attempts=2, wait=0, stderr=err)  # nao levanta excecao
    assert "nao respondeu" in err.getvalue()
