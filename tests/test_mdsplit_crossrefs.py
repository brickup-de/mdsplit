import os
from pathlib import Path


def list_files(in_path):
    collected = set()
    for dir_path, dirs, files in os.walk(in_path):
        for file_name in files:
            collected.add(str(Path(dir_path, file_name).relative_to(in_path)))
    print(in_path, collected)
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
            print("----")
            print(actual)
            print("----")
            assert actual == expected, f"error while comparing {expected_file}"


def test_crossrefs_disabled(tmp_path, script_runner):
    """Test that cross-reference adaptation is disabled by default"""
    ret = script_runner.run(
        [
            "mdsplit.py",
            "tests/test_resources_crossrefs/crossrefs.md",
            "--output",
            str(tmp_path),
            "--force",
        ]
    )
    assert ret.success
    assert_same_file_list(tmp_path, "tests/test_expected/crossrefs_disabled")
    assert_same_file_contents(tmp_path, "tests/test_expected/crossrefs_disabled")


def test_crossrefs_enabled(tmp_path, script_runner):
    """Test that cross-reference adaptation works when enabled"""
    ret = script_runner.run(
        [
            "mdsplit.py",
            "tests/test_resources_crossrefs/crossrefs.md",
            "--output",
            str(tmp_path),
            "--adapt-crossrefs",
            "--force",
        ]
    )
    assert ret.success
    assert_same_file_list(tmp_path, "tests/test_expected/crossrefs_enabled")
    assert_same_file_contents(tmp_path, "tests/test_expected/crossrefs_enabled")


def test_crossrefs_with_navigation(tmp_path, script_runner):
    """Test that cross-reference adaptation works with navigation enabled"""
    ret = script_runner.run(
        [
            "mdsplit.py",
            "tests/test_resources_crossrefs/crossrefs.md",
            "--output",
            str(tmp_path),
            "--adapt-crossrefs",
            "--navigation",
            "--force",
        ]
    )
    assert ret.success
    # Check that files are created and contain navigation
    assert (Path(tmp_path) / "Introduction.md").exists()
    assert (Path(tmp_path) / "Advanced-Topics.md").exists()
    
    # Check that cross-references are adapted
    intro_content = (Path(tmp_path) / "Introduction.md").read_text()
    assert "[Learn more](./Advanced-Topics.md#advanced-topics)" in intro_content
    
    # Check that navigation links are present
    assert "🡅" in intro_content or "🡄" in intro_content or "🡆" in intro_content


def test_crossrefs_with_toc(tmp_path, script_runner):
    """Test that cross-reference adaptation works with table of contents"""
    ret = script_runner.run(
        [
            "mdsplit.py",
            "tests/test_resources_crossrefs/crossrefs.md",
            "--output",
            str(tmp_path),
            "--adapt-crossrefs",
            "--table-of-contents",
            "--force",
        ]
    )
    assert ret.success
    # Check that toc.md is created
    assert (Path(tmp_path) / "toc.md").exists()
    
    # Check that cross-references are adapted
    intro_content = (Path(tmp_path) / "Introduction.md").read_text()
    assert "[Learn more](./Advanced-Topics.md#advanced-topics)" in intro_content


def test_crossrefs_all_options(tmp_path, script_runner):
    """Test that cross-reference adaptation works with all options enabled"""
    ret = script_runner.run(
        [
            "mdsplit.py",
            "tests/test_resources_crossrefs/crossrefs.md",
            "--output",
            str(tmp_path),
            "--adapt-crossrefs",
            "--table-of-contents",
            "--navigation",
            "--force",
        ]
    )
    assert ret.success
    # Check that all expected files are created
    assert (Path(tmp_path) / "toc.md").exists()
    assert (Path(tmp_path) / "Introduction.md").exists()
    assert (Path(tmp_path) / "Advanced-Topics.md").exists()
    
    # Check that cross-references are adapted
    intro_content = (Path(tmp_path) / "Introduction.md").read_text()
    assert "[Learn more](./Advanced-Topics.md#advanced-topics)" in intro_content
    
    # Check that navigation and toc links are present
    assert "🡅" in intro_content or "🡄" in intro_content or "🡆" in intro_content