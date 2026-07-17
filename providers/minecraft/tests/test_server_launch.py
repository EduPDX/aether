"""Tests for launch detection and console parsing."""

import sys
from pathlib import Path

from aether_provider_minecraft.server.console import MinecraftConsoleCodec
from aether_provider_minecraft.server.launch import build_launch_spec
from aether_sdk import LaunchContext


def ctx(root: Path, **data) -> LaunchContext:
    return LaunchContext(root_dir=root, provider_data=data)


def test_custom_command_wins(tmp_path):
    (tmp_path / "server.jar").write_bytes(b"x")
    spec = build_launch_spec(ctx(tmp_path, command=["echo", "hi"]))
    assert spec is not None
    assert spec.command == ["echo", "hi"]
    assert spec.stop_command == "stop"


def test_run_script_detected(tmp_path):
    script = tmp_path / ("run.bat" if sys.platform == "win32" else "run.sh")
    script.write_text("java @user_jvm_args.txt @libraries/... nogui")
    spec = build_launch_spec(ctx(tmp_path))
    assert spec is not None
    assert "nogui" in spec.command
    assert str(script) in " ".join(spec.command)


def test_server_jar_detected_with_memory(tmp_path):
    (tmp_path / "server.jar").write_bytes(b"x")
    spec = build_launch_spec(ctx(tmp_path, memory_mb=4096, java="java17"))
    assert spec is not None
    assert spec.command[0] == "java17"
    assert "-Xmx4096M" in spec.command
    assert "server.jar" in spec.command


def test_forge_universal_jar_detected(tmp_path):
    (tmp_path / "forge-1.20.1-47.2.0-universal.jar").write_bytes(b"x")
    spec = build_launch_spec(ctx(tmp_path))
    assert spec is not None
    assert "forge-1.20.1-47.2.0-universal.jar" in spec.command


def test_nothing_found(tmp_path):
    assert build_launch_spec(ctx(tmp_path)) is None


def test_console_codec_parses_levels_and_ready():
    codec = MinecraftConsoleCodec()

    line = codec.parse('[12:34:56] [Server thread/INFO]: Done (12.345s)! For help, type "help"')
    assert line.level == "INFO"
    assert line.ready is True
    assert line.message.startswith("Done")

    warn = codec.parse("[12:34:56] [Worker-Main-2/WARN]: Mods loaded in dev mode")
    assert warn.level == "WARN"
    assert warn.ready is False

    unknown = codec.parse("some raw text without format")
    assert unknown.level == ""
    assert unknown.message == "some raw text without format"
