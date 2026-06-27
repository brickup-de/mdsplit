"""Split Markdown files into chapters at a given heading level.

Each chapter (or subchapter) is written to its own file,
which is named after the heading title.
These files are written to subdirectories representing the document's structure.

Optionally you can create:
- table of contents (toc.md) for each input file
- navigation footers (links to table of contents, previous page, next page)

Note:
- Code blocks (```) are detected (and headers inside ignored)
- The output is guaranteed to be identical with the input
  (except for the separation into multiple files of course)
    - This means: no touching of whitespace or changing - to * of your lists
      like some viusual Markdown editors tend to do
- Text before the first heading is written to a file with the same name as the Markdown file
- Chapters with the same heading name are written to the same file.
- Reading from stdin is supported
- Can easily handle large files,
  e.g. a 1 GB file is split into 30k files in 35 seconds on a 2015 Thinkpad (with an SSD)

Limitations:
- Only [ATX headings](https://spec.commonmark.org/0.31.2/#atx-headings)
  such as '# Heading 1' are supported.
  [Setext headings](https://spec.commonmark.org/0.31.2/#setext-headings)
  (underlined headings) are not recognised.
"""

from abc import ABC, abstractmethod
from collections import namedtuple
from dataclasses import dataclass
from pathlib import Path
import argparse
import io
import os
import re
import sys

FENCES = ["```", "~~~"]
MAX_HEADING_LEVEL = 6
DIR_SUFFIX = "_split"

Chapter = namedtuple("Chapter", "parent_headings, heading, text")


def normalize_anchor(text: str) -> str:
    """
    Convert heading text to GitHub-style anchor ID.
    - Lowercase
    - Replace spaces with -
    - Remove special chars (except - and _)
    - Strip leading/trailing non-alphanumeric
    """
    if not text:
        return ""
    anchor = text.lower()
    anchor = re.sub(r'[^\w\- ]', '', anchor)  # Remove special chars
    anchor = re.sub(r'[\s]+', '-', anchor)   # Replace whitespace with -
    anchor = anchor.strip('-_')               # Trim non-alphanumeric from ends
    return anchor


def is_same_file(file_part: str, current_file: Path) -> bool:
    """Check if file_part refers to the current file or is empty."""
    if not file_part or file_part == '':
        return True
    if file_part.startswith('./') or file_part.startswith('/'):
        return False
    if file_part.endswith('.md') or file_part.endswith('.markdown'):
        return False
    # If it's just a fragment (no file part), consider it same file
    return True


# Patterns for link processing
# Fixed regex pattern - need to escape the angle brackets properly
INLINE_LINK_PATTERN = re.compile(r'\[([^\]]+)\]\(\s*(?:<([^>]+)>|([^\s)]+))\s*(?:"([^"]*)")?\s*\)')
ANCHOR_ONLY_PATTERN = re.compile(r'^#.+$')
REF_DEFINITION_PATTERN = re.compile(r'^\s*\[([^\]]+)\]\s*:\s*(.+)$')
FOOTNOTE_REF_PATTERN = re.compile(r'\[\^([^\]]+)\]')
FOOTNOTE_DEF_PATTERN = re.compile(r'^\s*\[\^([^\]]+)\]\s*:\s*(.+)$')


class Splitter(ABC):
    def __init__(self, encoding, level, toc, navigation, adapt_crossrefs, force, verbose):
        self.encoding = encoding
        self.level = level
        self.toc = toc
        self.navigation = navigation
        self.adapt_crossrefs = adapt_crossrefs
        self.force = force
        self.verbose = verbose
        self.stats = Stats()

    @abstractmethod
    def process(self):
        pass

    @abstractmethod
    def print_stats(self):
        pass

    def process_stream(self, in_stream, fallback_out_file_name, out_path):
        if self.adapt_crossrefs:
            return self._process_stream_with_adaptation(in_stream, fallback_out_file_name, out_path)
        else:
            # Original processing - unchanged for backwards compatibility
            return self._process_stream_original(in_stream, fallback_out_file_name, out_path)
    
    def _process_stream_original(self, in_stream, fallback_out_file_name, out_path):
        """Original process_stream implementation without cross-reference adaptation."""
        if self.verbose:
            print(f"Create output folder '{out_path}'")

        toc = "# Table of Contents\n"
        self.stats.in_files += 1
        chapters = split_by_heading(in_stream, self.level)
        nav_chapter_path2title = {}

        for chapter in chapters:
            self.stats.chapters += 1
            chapter_dir = out_path
            for parent in chapter.parent_headings:
                chapter_dir = chapter_dir / get_valid_filename(parent)
            chapter_dir.mkdir(parents=True, exist_ok=True)

            chapter_filename = (
                fallback_out_file_name
                if chapter.heading is None
                else get_valid_filename(chapter.heading.heading_title) + ".md"
            )
            chapter_path = chapter_dir / chapter_filename

            if self.verbose:
                print(f"Write {len(chapter.text)} lines to '{chapter_path}'")
            if not chapter_path.exists():
                # the first time a chapter file is written
                # (can happen multiple times for duplicate headings)
                self.stats.new_out_files += 1
                title = (
                    Splitter.remove_md_suffix(fallback_out_file_name)
                    if chapter.heading is None
                    else chapter.heading.heading_title
                )
                if self.navigation:
                    nav_chapter_path2title[chapter_path.relative_to(out_path)] = title
                if self.toc:
                    indent = len(chapter.parent_headings) * "  "
                    toc += f"\n{indent}- [{title}](<./{chapter_path.relative_to(out_path)}>)"
            with open(chapter_path, mode="a", encoding=self.encoding) as file:
                for line in chapter.text:
                    file.write(line)

        if self.navigation:
            nav_chapter_paths = list(nav_chapter_path2title)
            for i, chapter_path in enumerate(nav_chapter_paths):
                with open(out_path / chapter_path, mode="a", encoding=self.encoding) as file:
                    nav = []
                    if self.toc:
                        nav.append(f"[🡅](./toc.md)")
                    if i > 0:
                        prev_path = nav_chapter_paths[i - 1]
                        nav.append(f"[🡄 {nav_chapter_path2title[prev_path]}](./{prev_path})")
                    if i < len(nav_chapter_path2title) - 1:
                        next_path = nav_chapter_paths[i + 1]
                        nav.append(f"[{nav_chapter_path2title[next_path]} 🡆](./{next_path})")
                    file.write("\n\n---\n\n")
                    file.write(" ·•⦁•· ".join(nav))

        if self.toc:
            self.stats.new_out_files += 1
            with open(out_path / "toc.md", mode="w", encoding=self.encoding) as file:
                if self.verbose:
                    print(f"Write table of contents to {out_path / 'toc.md'}")
                file.write(toc)

    @staticmethod
    def remove_md_suffix(filename):
        if filename.endswith(".md"):
            return filename[:-3]
        return filename

    def _collect_metadata(self, in_stream, fallback_out_file_name, out_path):
        """
        Pass 1: Collect all headings for anchor mapping.
        Returns heading_map: {normalized_heading: (relative_path, anchor_id)}
        """
        heading_map = {}
        
        # First, we need to split the content to know where headings go
        # But we can't consume the stream, so we'll read it into memory
        content = in_stream.read()
        if isinstance(content, bytes):
            content = content.decode(self.encoding or 'utf-8')
        
        # Split by lines and process
        lines = content.splitlines(keepends=True)
        
        # We'll simulate the splitting process to build heading map
        chapters = split_by_heading(lines, self.level)
        
        for chapter in chapters:
            if chapter.heading:
                normalized = normalize_anchor(chapter.heading.heading_title)
                # Calculate the chapter path
                chapter_dir = out_path
                for parent in chapter.parent_headings:
                    chapter_dir = chapter_dir / get_valid_filename(parent)
                
                chapter_filename = get_valid_filename(chapter.heading.heading_title) + ".md"
                chapter_path = chapter_dir / chapter_filename
                relative_path = chapter_path.relative_to(out_path)
                
                # First occurrence wins for duplicates
                if normalized not in heading_map:
                    heading_map[normalized] = (relative_path, normalized)
        
        # Rewind the stream by creating a new StringIO with the content
        # We need to return both the heading_map and the content for re-processing
        return heading_map, content

    def _transform_line(self, line, heading_map, current_file):
        """
        Transform a single line, adapting anchor links using the heading_map.
        """
        # Skip transformation if within code fence
        if line.startswith(tuple(FENCES)):
            return line
            
        # Process inline links
        def transform_inline_link(match):
            text = match.group(1)
            # Group 2 is from angle brackets <url>, Group 3 is from normal (url)
            url = match.group(2) or match.group(3)
            title = match.group(4) or ''
            
            if not url or '#' not in url:
                # No anchor, external or file-only link
                return match.group(0)
            
            # Split URL into file and anchor parts
            if url.startswith('#'):
                # Anchor-only link
                anchor = url[1:]
                file_part = None
            else:
                # Could be file.md#anchor or #anchor or /path#anchor
                parts = url.split('#', 1)
                file_part = parts[0]
                anchor = parts[1]
            
            # Normalize anchor for lookup
            normalized_anchor = normalize_anchor(anchor)
            
            # Check if this is an internal anchor link (no file part or same file)
            if file_part is None or file_part == '' or is_same_file(file_part, current_file):
                # This is an internal anchor link
                if normalized_anchor in heading_map:
                    target_file, target_anchor = heading_map[normalized_anchor]
                    # Calculate relative path from current_file to target_file
                    # current_file is an absolute path, target_file is relative to out_path
                    current_path = Path(current_file)
                    out_path = current_path.parent  # Get the output directory
                    target_path = out_path / target_file
                    
                    # Check if the target is the same file as the current file
                    if current_path.name == target_path.name and current_path.parent == target_path.parent:
                        # Same file - only use the anchor
                        new_url = f"#{target_anchor}"
                    else:
                        # Different file - calculate relative path
                        if current_path.parent == target_path.parent:
                            relative_path = target_path.name
                        else:
                            # Calculate relative path from current file's directory to target
                            relative_path = target_path.relative_to(current_path.parent)
                        
                        new_url = f"./{relative_path}#{target_anchor}"
                    
                    if title:
                        return f"[{text}]({new_url} \"{title}\")"
                    return f"[{text}]({new_url})"
            
            # External link or can't resolve - return original
            return match.group(0)
        
        # Apply transformation to the line
        new_line = INLINE_LINK_PATTERN.sub(transform_inline_link, line)
        return new_line

    def _process_stream_with_adaptation(self, in_stream, fallback_out_file_name, out_path):
        """
        Process stream with cross-reference adaptation using two-pass approach.
        """
        if self.verbose:
            print(f"Create output folder '{out_path}'")

        # Pass 1: Collect metadata (headings)
        heading_map, content = self._collect_metadata(in_stream, fallback_out_file_name, out_path)
        
        if self.verbose:
            print(f"Collected {len(heading_map)} heading anchors")

        # Create a new stream from the content
        content_stream = io.StringIO(content)
        
        toc = "# Table of Contents\n"
        self.stats.in_files += 1
        chapters = split_by_heading(content_stream, self.level)
        nav_chapter_path2title = {}

        for chapter in chapters:
            self.stats.chapters += 1
            chapter_dir = out_path
            for parent in chapter.parent_headings:
                chapter_dir = chapter_dir / get_valid_filename(parent)
            chapter_dir.mkdir(parents=True, exist_ok=True)

            chapter_filename = (
                fallback_out_file_name
                if chapter.heading is None
                else get_valid_filename(chapter.heading.heading_title) + ".md"
            )
            chapter_path = chapter_dir / chapter_filename

            if self.verbose:
                print(f"Write {len(chapter.text)} lines to '{chapter_path}'")
            if not chapter_path.exists():
                # the first time a chapter file is written
                # (can happen multiple times for duplicate headings)
                self.stats.new_out_files += 1
                title = (
                    Splitter.remove_md_suffix(fallback_out_file_name)
                    if chapter.heading is None
                    else chapter.heading.heading_title
                )
                if self.navigation:
                    nav_chapter_path2title[chapter_path.relative_to(out_path)] = title
                if self.toc:
                    indent = len(chapter.parent_headings) * "  "
                    toc += f"\n{indent}- [{title}](<./{chapter_path.relative_to(out_path)}>)"
            
            # Write chapter content with transformations
            within_fence = False
            with open(chapter_path, mode="a", encoding=self.encoding) as file:
                for line in chapter.text:
                    # Track fence state
                    if line.startswith(tuple(FENCES)):
                        within_fence = not within_fence
                    
                    if within_fence:
                        # Write line unchanged - NO transformations
                        file.write(line)
                    else:
                        # Transform the line
                        transformed_line = self._transform_line(line, heading_map, chapter_path)
                        file.write(transformed_line)

        if self.navigation:
            nav_chapter_paths = list(nav_chapter_path2title)
            for i, chapter_path in enumerate(nav_chapter_paths):
                with open(out_path / chapter_path, mode="a", encoding=self.encoding) as file:
                    nav = []
                    if self.toc:
                        nav.append(f"[🡅](./toc.md)")
                    if i > 0:
                        prev_path = nav_chapter_paths[i - 1]
                        nav.append(f"[🡄 {nav_chapter_path2title[prev_path]}](./{prev_path})")
                    if i < len(nav_chapter_path2title) - 1:
                        next_path = nav_chapter_paths[i + 1]
                        nav.append(f"[{nav_chapter_path2title[next_path]} 🡆](./{next_path})")
                    file.write("\n\n---\n\n")
                    file.write(" ·•⦁•· ".join(nav))

        if self.toc:
            self.stats.new_out_files += 1
            with open(out_path / "toc.md", mode="w", encoding=self.encoding) as file:
                if self.verbose:
                    print(f"Write table of contents to {out_path / 'toc.md'}")
                file.write(toc)


class StdinSplitter(Splitter):
    """Split content from stdin"""

    def __init__(self, encoding, level, toc, navigation, adapt_crossrefs, out_path, force, verbose):
        super().__init__(encoding, level, toc, navigation, adapt_crossrefs, force, verbose)
        self.out_path = Path(DIR_SUFFIX) if out_path is None else Path(out_path)
        if self.out_path.exists():
            if self.force:
                print(f"Warning: writing output to existing directory '{self.out_path}'")
            else:
                raise MdSplitError(f"Output directory '{self.out_path}' already exists. Exiting..")

    def process(self):
        self.process_stream(sys.stdin, "stdin.md", self.out_path)

    def print_stats(self):
        print("Splittig result (from stdin):")
        print(f"- {self.stats.chapters} extracted chapter(s)")
        print(f"- {self.stats.new_out_files} new output file(s) ({self.out_path})")


class PathBasedSplitter(Splitter):
    """Split a specific file or all .md files found in a directory (recursively)"""

    def __init__(self, in_path, encoding, level, toc, navigation, adapt_crossrefs, out_path, force, verbose):
        super().__init__(encoding, level, toc, navigation, adapt_crossrefs, force, verbose)
        self.in_path = Path(in_path)
        if not self.in_path.exists():
            raise MdSplitError(f"Input file/directory '{self.in_path}' does not exist. Exiting..")
        elif self.in_path.is_file():
            self.out_path = Path(self.in_path.stem) if out_path is None else Path(out_path)
        else:
            self.out_path = (
                Path(self.in_path.stem + DIR_SUFFIX) if out_path is None else Path(out_path)
            )
        if self.out_path.exists():
            if force:
                print(f"Warning: writing output to existing directory '{self.out_path}'")
            else:
                raise MdSplitError(f"Output directory '{self.out_path}' already exists. Exiting..")

    def process(self):
        if self.in_path.is_file():
            self.process_file(self.in_path, self.out_path)
        else:
            self.process_directory(self.in_path, Path(self.out_path))

    def process_directory(self, in_dir_path, out_path):
        for dir_path, dirs, files in os.walk(in_dir_path):
            for file_name in files:
                if not Path(file_name).suffix == ".md":
                    continue
                file_path = Path(dir_path) / file_name
                new_out_path = (
                    out_path / os.path.relpath(dir_path, in_dir_path) / Path(file_name).stem
                )
                self.process_file(file_path, new_out_path)

    def process_file(self, in_file_path, out_path):
        if self.verbose:
            print(f"Process file '{in_file_path}' to '{out_path}'")
        with open(in_file_path, encoding=self.encoding) as stream:
            self.process_stream(stream, in_file_path.name, out_path)

    def print_stats(self):
        print("Splittig result:")
        print(f"- {self.stats.in_files} input file(s) ({self.in_path})")
        print(f"- {self.stats.chapters} extracted chapter(s)")
        print(f"- {self.stats.new_out_files} new output file(s) ({self.out_path})")


def split_by_heading(text, max_level):
    """
    Generator that returns a list of chapters from text.
    Each chapter's text includes the heading line.
    """
    curr_parent_headings = [None] * MAX_HEADING_LEVEL
    curr_heading_line = None
    curr_lines = []
    within_fence = False
    for next_line in text:
        next_line = Line(next_line)

        if next_line.is_fence():
            within_fence = not within_fence

        is_chapter_finished = (
            not within_fence and next_line.is_heading() and next_line.heading_level <= max_level
        )
        if is_chapter_finished:
            if len(curr_lines) > 0:
                parents = __get_parents(curr_parent_headings, curr_heading_line)
                yield Chapter(parents, curr_heading_line, curr_lines)

                if curr_heading_line is not None:
                    curr_level = curr_heading_line.heading_level
                    curr_parent_headings[curr_level - 1] = curr_heading_line.heading_title
                    for level in range(curr_level, MAX_HEADING_LEVEL):
                        curr_parent_headings[level] = None

            curr_heading_line = next_line
            curr_lines = []

        curr_lines.append(next_line.full_line)
    parents = __get_parents(curr_parent_headings, curr_heading_line)
    yield Chapter(parents, curr_heading_line, curr_lines)


def __get_parents(parent_headings, heading_line):
    if heading_line is None:
        return []
    max_level = heading_line.heading_level
    trunc = list(parent_headings)[: (max_level - 1)]
    return [h for h in trunc if h is not None]


class Line:
    """
    Detect code blocks and ATX headings.

    Headings are detected according to commonmark, e.g.:
    - only 6 valid levels
    - up to three spaces before the first # is ok
    - empty heading is valid
    - closing hashes are stripped
    - whitespace around title are stripped
    """

    def __init__(self, line):
        self.full_line = line
        self._detect_heading(line)

    def _detect_heading(self, line):
        self.heading_level = 0
        self.heading_title = None
        result = re.search("^[ ]{0,3}(#+)(.*)", line)
        if result is not None and (len(result[1]) <= MAX_HEADING_LEVEL):
            title = result[2]
            if len(title) > 0 and not (title.startswith(" ") or title.startswith("\t")):
                # if there is a title it must start with space or tab
                return
            self.heading_level = len(result[1])

            # strip whitespace and closing hashes
            title = title.strip().rstrip("#").rstrip()
            self.heading_title = title

    def is_fence(self):
        for fence in FENCES:
            if self.full_line.startswith(fence):
                return True
        return False

    def is_heading(self):
        return self.heading_level > 0


class MdSplitError(Exception):
    """MdSplit must stop but has an explanation string to be shown to the user"""


@dataclass
class Stats:
    in_files: int = 0
    new_out_files: int = 0
    chapters: int = 0


def get_valid_filename(name):
    """
    Adapted from https://github.com/django/django/blob/main/django/utils/text.py
    """
    s = str(name).strip().replace(" ", "-")
    s = re.sub(r"(?u)[^-\w.]", "", s)
    if s in {"", ".", ".."}:
        raise ValueError(f"Could not derive file name from '{name}'")
    return s


def main():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter, description=__doc__
    )
    # not using argparse.FileType because I don't want an open file handle yet
    parser.add_argument(
        "input",
        nargs="?",
        help="path to input file/folder (omit or set to '-' to read from stdin)",
        default="-",
    )
    parser.add_argument(
        "-e",
        "--encoding",
        type=str,
        help="force a specific encoding, default: python's default platform encoding",
        default=None,
    )
    parser.add_argument(
        "-l",
        "--max-level",
        type=int,
        choices=range(1, MAX_HEADING_LEVEL + 1),
        help="maximum heading level to split, default: %(default)s",
        default=1,
    )
    parser.add_argument(
        "-t",
        "--table-of-contents",
        action="store_true",
        help="generate a table of contents (one 'toc.md' per input file)",
    )
    parser.add_argument(
        "-n",
        "--navigation",
        action="store_true",
        help="add a navigation footer on each page (links to toc, previous page, next page)",
    )
    parser.add_argument(
        "-a",
        "--adapt-crossrefs",
        action="store_true",
        help="adapt internal links to work across split files",
    )
    parser.add_argument(
        "-o", "--output", default=None, help="path to output folder (must not exist)"
    )
    parser.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="write into output folder even if it already exists",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    try:
        splitter_args = {
            "encoding": args.encoding,
            "level": args.max_level,
            "toc": args.table_of_contents,
            "navigation": args.navigation,
            "adapt_crossrefs": args.adapt_crossrefs,
            "out_path": args.output,
            "force": args.force,
            "verbose": args.verbose,
        }
        splitter = (
            StdinSplitter(**splitter_args)
            if args.input == "-"
            else PathBasedSplitter(args.input, **splitter_args)
        )
        splitter.process()
        splitter.print_stats()
    except MdSplitError as e:
        print(e)
        sys.exit(1)


if __name__ == "__main__":
    main()
