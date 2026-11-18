"""安装出错时恢复受管文件，临时副本仅用于当前操作。"""
from contextlib import contextmanager
import json
from pathlib import Path
import shutil
import sys
import tempfile


@contextmanager
def rollback_on_failure(paths):
    scratch = Path(tempfile.mkdtemp(prefix='feipi-install-'))
    saved = {}
    keep_scratch = False
    try:
        for index, path in enumerate(dict.fromkeys(paths)):
            copy = scratch/str(index)
            if path.is_symlink():
                copy.symlink_to(path.readlink())
            elif path.is_dir():
                shutil.copytree(path, copy, symlinks=True)
            elif path.is_file():
                shutil.copy2(path, copy)
            saved[path] = copy
        try:
            yield
        except BaseException:
            print('安装中断，正在还原受管文件。', file=sys.stderr)
            try:
                for path, copy in reversed(saved.items()):
                    if path.is_symlink() or path.is_file():
                        path.unlink()
                    elif path.is_dir():
                        shutil.rmtree(path)
                    if copy.is_symlink():
                        path.parent.mkdir(parents=True, exist_ok=True)
                        path.symlink_to(copy.readlink())
                    elif copy.is_dir():
                        shutil.copytree(copy, path, symlinks=True)
                    elif copy.is_file():
                        path.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(copy, path)
            except Exception:
                keep_scratch = True
                print('自动还原未完成，临时副本保留在 '+str(scratch), file=sys.stderr)
                (scratch/'paths.json').write_text(json.dumps({str(path): copy.name for path, copy in saved.items()},
                                                            ensure_ascii=False, indent=2))
                raise
            raise
    finally:
        if not keep_scratch:
            shutil.rmtree(scratch)
