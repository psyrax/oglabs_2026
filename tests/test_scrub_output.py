import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from scrub_output import scrub_text, load_env_secrets, scrub_dir


def test_redacts_aws_key():
    out, findings = scrub_text("clave AKIAIOSFODNN7EXAMPLE aqui")
    assert "AKIAIOSFODNN7EXAMPLE" not in out
    assert "[REDACTED:AWS_KEY]" in out
    assert findings


def test_redacts_openai_key():
    out, _ = scrub_text("token sk-proj-abc123DEF456ghi789JKL012mno fin")
    assert "sk-proj-" not in out
    assert "[REDACTED:API_KEY]" in out


def test_redacts_prompt_id():
    out, _ = scrub_text("usa pmpt_69b90b4671ac8190 ahora")
    assert "pmpt_69b90b4671ac8190" not in out
    assert "[REDACTED:PROMPT_ID]" in out


def test_redacts_env_secret_value():
    out, _ = scrub_text("mi clave es supersecreto123", secrets=["supersecreto123"])
    assert "supersecreto123" not in out
    assert "[REDACTED:SECRET]" in out


def test_redacts_private_ip_when_enabled():
    out, _ = scrub_text("server at 192.168.50.113 ok", ip_path_on=True)
    assert "192.168.50.113" not in out
    assert "[IP omitida]" in out


def test_path_kept_by_default():
    # IP/path scrubbing is off by default (blog uses them intentionally).
    out, findings = scrub_text("vive en /mnt/user/appdata/oglabs hoy")
    assert "/mnt/user/appdata/oglabs" in out
    assert findings == []


def test_redacts_path_when_enabled():
    out, _ = scrub_text("vive en /mnt/user/appdata/oglabs/.env hoy", ip_path_on=True)
    assert "/mnt/user" not in out
    assert "[ruta omitida]" in out


def test_redacts_email_when_enabled():
    out, _ = scrub_text("escribe a juan@example.com hoy", email_on=True)
    assert "juan@example.com" not in out
    assert "[email omitido]" in out


def test_redacts_env_assignment():
    out, _ = scrub_text("config API_KEY=abcdef123456 en el html")
    assert "abcdef123456" not in out
    assert "API_KEY=[REDACTED]" in out


def test_keeps_normal_text():
    out, findings = scrub_text("Un post normal sobre homelab y agentes.")
    assert out == "Un post normal sobre homelab y agentes."
    assert findings == []


def test_load_env_secrets(tmp_path):
    env = tmp_path / ".env"
    env.write_text(
        "S3_BUCKET=mybucket\n"
        "OPENAI_API_KEY=sk-supersecret\n"
        "AWS_DEFAULT_REGION=us-east-1\n"
        "# COMMENTED_KEY=ignored\n"
        "OLLAMA_HOST=http://h:11434\n"
    )
    secrets = load_env_secrets(env)
    assert "sk-supersecret" in secrets       # *_API_KEY -> secret
    assert "mybucket" not in secrets          # S3_BUCKET not a secret name
    assert "us-east-1" not in secrets         # region not a secret
    assert "http://h:11434" not in secrets    # host not a secret
    assert "ignored" not in secrets           # commented line skipped


def test_scrub_dir_rewrites_html(tmp_path):
    out = tmp_path / "output"
    out.mkdir()
    f = out / "index.html"
    f.write_text("clave AKIAIOSFODNN7EXAMPLE en el build")
    report = scrub_dir(out, secrets=[])
    txt = f.read_text()
    assert "AKIAIOSFODNN7EXAMPLE" not in txt
    assert "[REDACTED:AWS_KEY]" in txt
    assert report  # at least one file with findings
