"""Install checkout-backed skill links without replacing existing installations."""
import argparse
import os
from pathlib import Path
import sys

NAMES = ('grok-subagent', 'cursor-subagent-3rd')
ROOT = Path(__file__).resolve().parents[1]


def main(action, argv=None):
    parser = argparse.ArgumentParser(description=f'{action.title()} Cursor agent skills (symlinks).')
    parser.add_argument('--skills-dir', type=Path,
                        default=Path(os.environ.get('CODEX_HOME', str(Path.home()/'.codex')))/'skills')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args(argv)
    target = args.skills_dir.expanduser().resolve()
    links = [(target/name, ROOT/'skills'/name) for name in NAMES]
    try:
        for link, source in links:
            if link == source or source in link.parents or link in source.parents:
                raise ValueError('Install destination must be outside the source skill folders.')
            if link.exists() or link.is_symlink():
                if not link.is_symlink() or link.resolve() != source.resolve():
                    raise ValueError(f'Refusing to {action}: existing path is not owned by this checkout: {link}')
        changed = []
        if action == 'install' and not args.dry_run:
            target.mkdir(parents=True, exist_ok=True)
        try:
            for link, source in links:
                if action == 'install':
                    if link.is_symlink():
                        print(f'Already installed: {link}')
                    elif args.dry_run:
                        print(f'Would link: {link} -> {source}')
                    else:
                        link.symlink_to(source, target_is_directory=True)
                        changed.append(link)
                        print(f'Installed: {link}')
                elif link.is_symlink():
                    if args.dry_run:
                        print(f'Would unlink: {link}')
                    else:
                        link.unlink()
                        print(f'Uninstalled: {link}')
                else:
                    print(f'Already absent: {link}')
        except OSError:
            if action == 'install':
                for link in changed:
                    if link.is_symlink() and link.resolve() == (ROOT/'skills'/link.name).resolve():
                        link.unlink()
            raise
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0
