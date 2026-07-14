from debugrelay.services.monitoring import normalize_error_text


def test_normalization_removes_unstable_values() -> None:
    first = normalize_error_text(
        "Request 12345 failed at 2026-07-14T03:00:00Z "
        "for 550e8400-e29b-41d4-a716-446655440000 from 0x7ffdeadbeef"
    )
    second = normalize_error_text(
        "Request 98765 failed at 2026-07-14T04:30:00Z "
        "for 550e8400-e29b-41d4-a716-446655440001 from 0x8ffdeadbeef"
    )
    assert first == second
    assert first == "Request <number> failed at <timestamp> for <uuid> from <hex>"


def test_stack_normalization_ignores_line_numbers_and_temporary_paths() -> None:
    first = normalize_error_text(
        'File "/tmp/build-12345/src/orders.py", line 42, in submit',
        stack_frame=True,
    )
    second = normalize_error_text(
        'File "/tmp/build-98765/src/orders.py", line 3142, in submit',
        stack_frame=True,
    )
    assert first == second
    assert first == 'File "/tmp/<path>", line <line>, in submit'
