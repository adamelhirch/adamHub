from app.services import proxy_pool


def _pool(tmp_path, proxies: list[str], cooldown_seconds: int = 600) -> proxy_pool.ProxyPool:
    file_path = tmp_path / "proxies.txt"
    file_path.write_text("\n".join(proxies) + "\n", encoding="utf-8")
    return proxy_pool.load_proxies(file_path=str(file_path), cooldown_seconds=cooldown_seconds)


def _urls(proxies: list[str]) -> list[str]:
    return [f"http://{p}" for p in proxies]


def test_parse_proxies_ignores_comments_and_blank_lines():
    raw = (
        "# residential proxies\n"
        "\n"
        "user1:pass1@proxy-a.example:8000\n"
        "   # indented comment\n"
        "   \n"
        "user2:pass2@proxy-b.example:8001\n"
    )
    assert proxy_pool.parse_proxies(raw) == _urls(["user1:pass1@proxy-a.example:8000", "user2:pass2@proxy-b.example:8001"])


def test_parse_proxies_normalizes_scheme():
    raw = (
        "user1:pass1@proxy-a.example:8000\n"
        "http://user2:pass2@proxy-b.example:8001\n"
        "https://user3:pass3@proxy-c.example:8002\n"
        "socks5://user4:pass4@proxy-d.example:8003\n"
    )
    assert proxy_pool.parse_proxies(raw) == [
        "http://user1:pass1@proxy-a.example:8000",
        "http://user2:pass2@proxy-b.example:8001",
        "https://user3:pass3@proxy-c.example:8002",
        "socks5://user4:pass4@proxy-d.example:8003",
    ]


def test_load_proxies_missing_file_gives_empty_pool(tmp_path):
    pool = proxy_pool.load_proxies(file_path=str(tmp_path / "nope.txt"))
    assert len(pool) == 0
    assert pool.acquire("s1") is None


def test_load_proxies_empty_file_gives_empty_pool(tmp_path):
    file_path = tmp_path / "empty.txt"
    file_path.write_text("# nothing\n\n", encoding="utf-8")
    pool = proxy_pool.load_proxies(file_path=str(file_path))
    assert len(pool) == 0
    assert pool.acquire("s1") is None


def test_empty_pool_release_is_noop(tmp_path):
    pool = proxy_pool.load_proxies(file_path=str(tmp_path / "nope.txt"))
    pool.release("http://user:pass@host:8000", ok=False)
    assert pool.acquire("s1") is None


def test_acquire_is_sticky_per_scope(tmp_path):
    pool = _pool(tmp_path, ["user:a@a.example:8000", "user:b@b.example:8000", "user:c@c.example:8000"])
    first = pool.acquire("search=lait,farine")
    second = pool.acquire("search=lait,farine")
    assert first is not None
    assert second == first
    pool.release(first, ok=True)
    assert pool.acquire("search=lait,farine") == first


def test_new_scope_round_robins(tmp_path):
    pool = _pool(tmp_path, ["a@a.example:8000", "b@b.example:8000", "c@c.example:8000"])
    first = pool.acquire("s1")
    second = pool.acquire("s2")
    third = pool.acquire("s3")
    fourth = pool.acquire("s4")
    assert {first, second, third} == set(_urls(["a@a.example:8000", "b@b.example:8000", "c@c.example:8000"]))
    assert fourth == first


def test_blocked_proxy_rotates_to_next(tmp_path):
    pool = _pool(tmp_path, ["a@a.example:8000", "b@b.example:8000", "c@c.example:8000"], cooldown_seconds=600)
    first = pool.acquire("s1")
    pool.release(first, ok=False)
    next_proxy = pool.acquire("s1")
    assert next_proxy is not None
    assert next_proxy != first
    assert pool.acquire("s2") != first


def test_blocked_proxy_stays_in_cooldown(tmp_path):
    pool = _pool(tmp_path, ["a@a.example:8000", "b@b.example:8000"], cooldown_seconds=600)
    blocked = pool.acquire("s1")
    pool.release(blocked, ok=False)
    for scope in ("s2", "s3", "s4"):
        assert pool.acquire(scope) != blocked


def test_cooldown_proxy_comes_back_after_expiry(tmp_path):
    pool = _pool(tmp_path, ["a@a.example:8000", "b@b.example:8000"], cooldown_seconds=0)
    blocked = pool.acquire("s1")
    pool.release(blocked, ok=False)
    other = pool.acquire("s2")
    assert other != blocked
    pool.release(other, ok=False)
    assert pool.acquire("s3") == blocked


def test_load_proxies_reads_cooldown_from_env(tmp_path, monkeypatch):
    file_path = tmp_path / "proxies.txt"
    file_path.write_text("a@a.example:8000\n", encoding="utf-8")
    monkeypatch.setenv("ADAMHUB_PROXY_COOLDOWN_SECONDS", "5")
    pool = proxy_pool.load_proxies(file_path=str(file_path))
    assert pool.cooldown_seconds == 5


def test_load_proxies_defaults_cooldown(tmp_path, monkeypatch):
    file_path = tmp_path / "proxies.txt"
    file_path.write_text("a@a.example:8000\n", encoding="utf-8")
    monkeypatch.delenv("ADAMHUB_PROXY_COOLDOWN_SECONDS", raising=False)
    pool = proxy_pool.load_proxies(file_path=str(file_path))
    assert pool.cooldown_seconds == 600


def test_load_proxies_uses_env_file_path(monkeypatch, tmp_path):
    file_path = tmp_path / "proxies.txt"
    file_path.write_text("a@a.example:8000\nb@b.example:8000\n", encoding="utf-8")
    monkeypatch.setenv("ADAMHUB_PROXIES_FILE", str(file_path))
    pool = proxy_pool.load_proxies()
    assert len(pool) == 2


def test_module_level_acquire_release(monkeypatch, tmp_path):
    pool = _pool(tmp_path, ["a@a.example:8000"])
    monkeypatch.setattr(proxy_pool, "_pool", pool)
    acquired = proxy_pool.acquire("s1")
    assert acquired == "http://a@a.example:8000"
    proxy_pool.release(acquired, ok=True)
    assert proxy_pool.acquire("s1") == acquired
