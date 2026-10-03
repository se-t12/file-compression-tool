from fct.resource_manager import cleanup_temp


def test_cleanup_removes_existing_files(tmp_path):
    f1 = tmp_path / "a.tmp"
    f2 = tmp_path / "b.tmp"
    f1.write_text("x")
    f2.write_text("y")

    cleanup_temp([f1, f2])

    assert not f1.exists()
    assert not f2.exists()


def test_cleanup_ignores_missing_files(tmp_path):
    missing = tmp_path / "does_not_exist.tmp"
    # Should not raise.
    cleanup_temp([missing])
