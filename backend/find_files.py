"""Find a folder's input files by extension, ignoring case.

glob matches names case-sensitively on macOS and Linux whatever the filesystem does, so
'*.csv' skips REPORT.CSV. The converters use this for their inputs instead of globbing.
"""

import os


def find_files(folder, *extensions: str) -> list[str]:
    """Sorted paths of the files in folder whose extension is one of extensions, ignoring case.

    Extensions include the dot, e.g. find_files(input_folder, '.jpg', '.jpeg'). Like glob,
    hidden files (macOS '._photo.jpg' leftovers) are skipped and a missing folder gives [].
    """
    if not os.path.isdir(folder):
        return []
    wanted = tuple(ext.lower() for ext in extensions)
    paths = (
        os.path.join(folder, name)
        for name in os.listdir(folder)
        if not name.startswith('.') and name.lower().endswith(wanted)
    )
    return sorted(p for p in paths if os.path.isfile(p))
