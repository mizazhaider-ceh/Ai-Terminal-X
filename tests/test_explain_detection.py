import importlib.util
import os

REPO_DIR = os.path.join(os.path.dirname(__file__), "..")


def load_main_module():
    # the script filename has hyphens, so load it by path
    path = os.path.join(REPO_DIR, "ai-terminal-x.py")
    spec = importlib.util.spec_from_file_location("ai_terminal_x", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


mod = load_main_module()
detect_explain_request = mod.detect_explain_request


def test_explain_prefix_detected():
    triggered, topic, prefix = detect_explain_request("explain grep")
    assert triggered is True
    assert topic == "grep"
    assert prefix == "explain "


def test_case_insensitive_prefix():
    triggered, topic, _ = detect_explain_request("What is ssh")
    assert triggered is True
    assert topic == "ssh"


def test_prefix_with_no_topic():
    triggered, topic, prefix = detect_explain_request("explain ")
    assert triggered is True
    assert topic is None
    assert prefix == "explain "


def test_normal_request_not_detected():
    assert detect_explain_request("list all files") == (False, None, None)


def test_tell_me_about_prefix():
    triggered, topic, _ = detect_explain_request("tell me about tmux")
    assert triggered is True
    assert topic == "tmux"
