import os
import tempfile
from pathlib import Path
import pytest
import sys

# Add the parent directory to sys.path so we can import mdsplit
sys.path.insert(0, str(Path(__file__).parent.parent))

from mdsplit import PathBasedSplitter, normalize_anchor


def test_normalize_anchor_basic():
    """Test basic anchor normalization"""
    assert normalize_anchor("Heading One") == "heading-one"
    assert normalize_anchor("What's New?") == "whats-new"
    assert normalize_anchor("Special Chars: @#$%") == "special-chars"
    assert normalize_anchor("  Trim Spaces  ") == "trim-spaces"
    assert normalize_anchor("") == ""


def test_normalize_anchor_case_insensitive():
    """Test that normalization is case insensitive"""
    assert normalize_anchor("Heading One") == normalize_anchor("heading one")
    assert normalize_anchor("HEADING ONE") == "heading-one"


def test_crossrefs_disabled_by_default():
    """Test that cross-reference adaptation is disabled by default"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        splitter = PathBasedSplitter(
            in_path="tests/test_crossrefs_anchor.md",
            encoding=None,
            level=1,
            toc=False,
            navigation=False,
            adapt_crossrefs=False,  # Default should be False
            out_path=tmp_dir,
            force=True,
            verbose=False
        )
        splitter.process()
        
        # Check that links are NOT transformed when disabled
        heading_one_path = Path(tmp_dir) / "Heading-One.md"
        content = heading_one_path.read_text()
        
        assert "[Link to heading two](#heading-two)" in content
        assert "[External link](http://example.com)" in content
        # Should NOT contain adapted links
        assert "./Heading-Two.md" not in content


def test_crossrefs_enabled():
    """Test that cross-reference adaptation works when enabled"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        splitter = PathBasedSplitter(
            in_path="tests/test_crossrefs_anchor.md",
            encoding=None,
            level=1,
            toc=False,
            navigation=False,
            adapt_crossrefs=True,
            out_path=tmp_dir,
            force=True,
            verbose=False
        )
        splitter.process()
        
        # Check that links ARE transformed when enabled
        heading_one_path = Path(tmp_dir) / "Heading-One.md"
        content = heading_one_path.read_text()
        
        # Internal links should be adapted
        assert "[Link to heading two](./Heading-Two.md#heading-two)" in content
        assert "[Link to heading three](./Heading-Three.md#heading-three)" in content
        
        # External links should remain unchanged
        assert "[External link](http://example.com)" in content
        
        # Check links in other files
        heading_three_path = Path(tmp_dir) / "Heading-Three.md"
        content_three = heading_three_path.read_text()
        assert "[Another link](./Heading-Two.md#heading-two)" in content_three
        
        # Links with titles should be preserved
        assert '"First heading"' in content_three


def test_crossrefs_code_block_protection():
    """Test that links inside code blocks are not transformed"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        splitter = PathBasedSplitter(
            in_path="tests/test_crossrefs_codeblock.md",
            encoding=None,
            level=1,
            toc=False,
            navigation=False,
            adapt_crossrefs=True,
            out_path=tmp_dir,
            force=True,
            verbose=False
        )
        splitter.process()
        
        code_block_path = Path(tmp_dir) / "Code-Block-Test.md"
        content = code_block_path.read_text()
        
        # Regular link should be transformed
        assert "[link to other](./Other-Section.md#other-section)" in content
        
        # Code block is in the Other-Section.md file
        other_section_path = Path(tmp_dir) / "Other-Section.md"
        other_content = other_section_path.read_text()
        
        # Code block content should be unchanged
        assert "[link that should not be transformed](#code-block-test)" in other_content
        # The code block should NOT contain the adapted link
        assert "Code-Block-Test.md" not in other_content  # Should not be adapted in code block


def test_crossrefs_self_references():
    """Test links that reference the same file"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        splitter = PathBasedSplitter(
            in_path="tests/test_crossrefs_anchor.md",
            encoding=None,
            level=1,
            toc=False,
            navigation=False,
            adapt_crossrefs=True,
            out_path=tmp_dir,
            force=True,
            verbose=False
        )
        splitter.process()
        
        heading_two_path = Path(tmp_dir) / "Heading-Two.md"
        content = heading_two_path.read_text()
        
        # Self-references should work
        assert "[Back to heading one](./Heading-One.md#heading-one)" in content


def test_crossrefs_backwards_compatibility():
    """Test that existing tests still pass with crossref disabled"""
    # This is more of an integration test - we'll run it with the existing test infrastructure
    with tempfile.TemporaryDirectory() as tmp_dir:
        splitter = PathBasedSplitter(
            in_path="tests/test_resources/simple.md",
            encoding=None,
            level=1,
            toc=False,
            navigation=False,
            adapt_crossrefs=False,  # Disabled
            out_path=tmp_dir,
            force=True,
            verbose=False
        )
        splitter.process()
        
        # Just verify it doesn't crash and creates expected files
        # Note: get_valid_filename() converts spaces to dashes
        heading1_path = Path(tmp_dir) / "Heading-1.md"
        heading2_path = Path(tmp_dir) / "Heading-2.md"
        
        assert heading1_path.exists()
        assert heading2_path.exists()
        
        # Also verify content matches expected files exactly
        with open(heading1_path, 'r') as f:
            actual_content = f.read()
        with open("tests/test_expected/by_h1/simple/Heading-1.md", "r") as f:
            expected_content = f.read()
        assert actual_content == expected_content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])