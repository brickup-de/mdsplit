import os
from pathlib import Path


def list_files(in_path):
    collected = set()
    for dir_path, dirs, files in os.walk(in_path):
        for file_name in files:
            collected.add(str(Path(dir_path, file_name).relative_to(in_path)))
    return collected


def assert_same_file_list(actual_dir, expected_dir):
    assert list_files(actual_dir) == list_files(expected_dir)


def assert_same_file_contents(tmp_dir, expected_dir, encoding=None):
    for dir_path, dirs, files in os.walk(expected_dir):
        for file_name in files:
            expected_file = Path(dir_path, file_name)
            expected = expected_file.read_text(encoding=encoding)

            actual_file = tmp_dir / expected_file.relative_to(expected_dir)
            actual = actual_file.read_text(encoding=encoding)
            assert actual == expected, (
                f"Content mismatch in {expected_file}\n"
                f"Expected:\n{expected}\n"
                f"Actual:\n{actual}"
            )


def test_links_anchors(tmp_path, script_runner):
    """Test that inline anchor links are adapted when adapt_crossrefs is enabled.
    
    This test verifies the existing functionality where inline anchor links
    [text](#anchor) are adapted to work across split files.
    """
    ret = script_runner.run(
        [
            "mdsplit.py",
            "tests/test_resources_links/anchors.md",
            "--output",
            str(tmp_path),
            "--adapt-crossrefs",
            "--force",
        ]
    )
    assert ret.success
    assert_same_file_list(tmp_path, "tests/test_expected/links_anchors")
    assert_same_file_contents(tmp_path, "tests/test_expected/links_anchors")


def test_links_disabled(tmp_path, script_runner):
    """Test multi-file scenario without adapt_crossrefs.
    
    Without --adapt-crossrefs, cross-file links, reference-style links, and footnotes
    remain unchanged in their respective files.
    """
    ret = script_runner.run(
        [
            "mdsplit.py",
            "tests/test_resources_links/crossrefs/",
            "--output",
            str(tmp_path),
            "--force",
        ]
    )
    assert ret.success
    assert_same_file_list(tmp_path, "tests/test_expected/links_disabled")
    assert_same_file_contents(tmp_path, "tests/test_expected/links_disabled")


def test_links_crossrefs(tmp_path, script_runner):
    """Test multi-file scenario with cross-file links, same-named footnotes, and linkrefs."""
    ret = script_runner.run(
        [
            "mdsplit.py",
            "tests/test_resources_links/crossrefs/",
            "--output",
            str(tmp_path),
            "--adapt-crossrefs",
            "--force",
        ]
    )
    assert ret.success
    assert_same_file_list(tmp_path, "tests/test_expected/links_crossrefs")
    assert_same_file_contents(tmp_path, "tests/test_expected/links_crossrefs")


def test_links_footnotes(tmp_path, script_runner):
    """Test footnotes with adapt_crossrefs enabled."""
    ret = script_runner.run(
        [
            "mdsplit.py",
            "tests/test_resources_links/footnotes.md",
            "--output",
            str(tmp_path),
            "--adapt-crossrefs",
            "--force",
        ]
    )
    assert ret.success
    assert_same_file_list(tmp_path, "tests/test_expected/links_footnotes")
    assert_same_file_contents(tmp_path, "tests/test_expected/links_footnotes")


def test_links_linkrefs(tmp_path, script_runner):
    """Test reference-style links with adapt_crossrefs enabled."""
    ret = script_runner.run(
        [
            "mdsplit.py",
            "tests/test_resources_links/linkrefs.md",
            "--output",
            str(tmp_path),
            "--adapt-crossrefs",
            "--force",
        ]
    )
    assert ret.success
    assert_same_file_list(tmp_path, "tests/test_expected/links_linkrefs")
    assert_same_file_contents(tmp_path, "tests/test_expected/links_linkrefs")
