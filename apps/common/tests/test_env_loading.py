from config.settings import base


def test_load_dotenv_loads_missing_values_without_overriding_environment(
    monkeypatch,
    tmp_path,
):
    environment_file = tmp_path / ".env"
    environment_file.write_text(
        "DOTENV_ONLY=loaded\nDOTENV_EXISTING=from-file\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("DOTENV_ONLY", raising=False)
    monkeypatch.setenv("DOTENV_EXISTING", "from-environment")

    base.load_dotenv(environment_file, override=False)

    assert base.os.environ["DOTENV_ONLY"] == "loaded"
    assert base.os.environ["DOTENV_EXISTING"] == "from-environment"
