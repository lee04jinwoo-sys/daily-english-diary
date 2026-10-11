from app.core.config import resolve_db_path


def test_legacy_diary_db_is_moved_to_essay_db(tmp_path):
    legacy = tmp_path / "diary.db"
    legacy.write_bytes(b"data")
    (tmp_path / "diary.db-wal").write_bytes(b"wal")
    path = resolve_db_path(tmp_path)
    assert path == tmp_path / "essay.db"
    assert path.read_bytes() == b"data"
    assert (tmp_path / "essay.db-wal").read_bytes() == b"wal"
    assert not legacy.exists()


def test_existing_essay_db_wins(tmp_path):
    (tmp_path / "essay.db").write_bytes(b"new")
    (tmp_path / "diary.db").write_bytes(b"old")
    assert resolve_db_path(tmp_path).read_bytes() == b"new"
    assert (tmp_path / "diary.db").exists()  # never touched or deleted


def test_fresh_install(tmp_path):
    assert resolve_db_path(tmp_path) == tmp_path / "essay.db"
