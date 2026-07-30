import pytest

from copilot.datasource.tushare_client import TushareTokenMissing, create_tushare_pro


class FakeTushareModule:
    def __init__(self):
        self.received_token = None

    def pro_api(self, token):
        self.received_token = token
        return {"client": "ok"}


def test_create_tushare_pro_requires_token():
    with pytest.raises(TushareTokenMissing) as exc:
        create_tushare_pro(None, tushare_module=FakeTushareModule())

    assert "TUSHARE_TOKEN" in str(exc.value)
    assert "None" not in str(exc.value)


def test_create_tushare_pro_passes_token_without_logging_it(capsys):
    fake = FakeTushareModule()

    client = create_tushare_pro("secret-token", tushare_module=fake)

    assert client == {"client": "ok"}
    assert fake.received_token == "secret-token"
    captured = capsys.readouterr()
    assert "secret-token" not in captured.out
    assert "secret-token" not in captured.err
