from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_original_hologram_and_real_state_contract():
    html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
    script = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
    assert 'id="copilotAvatar"' in html
    assert "holo-network" in html
    assert "/api/copilot/runtime-state" in script
    assert "payload.state" in script
    for state in ("listening", "thinking", "planning", "offline"):
        assert state in (ROOT / "web" / "styles.css").read_text(encoding="utf-8")


def test_voice_fallback_permission_denial_and_no_background_recording():
    html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
    script = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
    assert "Audio is never stored" in html
    assert 'event.error === "not-allowed"' in script
    assert "Voice recognition is unavailable" in script
    assert "continuous = false" in script
    assert "Requesting microphone permission" in script
    assert 'id="startCopilotQuickListening"' in html
    assert 'id="copilotQuickAutoSpeak"' in html
    assert 'id="copilotQuickAutoSend"' in html
    assert 'id="muteCopilotQuickVoice"' in html
    assert 'copilotRecognitionTarget = "quick"' in script
    assert "speakCopilotText(response.content" in script
    assert "Audio stays in this browser and is never stored" in html


def test_reduced_motion_mobile_layout_and_connected_health_controls():
    css = (ROOT / "web" / "styles.css").read_text(encoding="utf-8")
    html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
    script = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
    assert "prefers-reduced-motion:reduce" in css
    assert "@media(max-width:700px)" in css
    for control in (
        "runFullHealthCheck",
        "runSolidConnectionGate",
        "exportHealthReport",
        "stopCopilotGeneration",
        "retryCopilotMessage",
    ):
        assert f'id="{control}"' in html
        assert f'$("#{control}")' in script
