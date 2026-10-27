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


def test_get_current_process_memory():
    from fct.resource_manager import get_current_process_memory, get_process_peak_memory

    mem = get_current_process_memory()
    assert isinstance(mem, int)
    assert mem > 0

    peak = get_process_peak_memory()
    assert isinstance(peak, int)
    assert peak >= mem


def test_memory_tracker_captures_allocation():
    from fct.resource_manager import MemoryTracker

    with MemoryTracker(sample_interval_seconds=0.002) as tracker:
        # Allocate ~10 MB temporary buffer
        buf = bytearray(10 * 1024 * 1024)
        for i in range(0, len(buf), 4096):
            buf[i] = 1
        assert len(buf) == 10 * 1024 * 1024
        del buf

    assert tracker.peak_process_bytes > 0
    assert tracker.peak_python_bytes >= 10 * 1024 * 1024
    assert tracker.elapsed_seconds >= 0.0

