"""Descriptor-relative project IO: never follow mutable project symlinks."""
import os
import stat
import uuid
from contextlib import contextmanager
from pathlib import Path

LIMIT = 2_000_000

@contextmanager
def parent(root, name, create=False):
    if not isinstance(name, str) or not name or '\x00' in name:
        raise ValueError('Ruta relativa no válida.')
    path = Path(name)
    if path.is_absolute() or '..' in path.parts or not path.parts:
        raise ValueError('La ruta sale del proyecto.')
    fd = None
    try:
        fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        for part in path.parts[:-1]:
            if create:
                try: os.mkdir(part, mode=0o700, dir_fd=fd)
                except FileExistsError: pass
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd); fd = child
        yield fd, path.parts[-1]
    except OSError as error:
        raise ValueError('Ruta insegura o no disponible en el proyecto.') from error
    finally:
        if fd is not None: os.close(fd)

def read_at(fd, name, missing=False):
    try:
        handle = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
    except FileNotFoundError:
        if missing: return None
        raise ValueError('Archivo inexistente.') from None
    try:
        info = os.fstat(handle)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > LIMIT:
            raise ValueError('Solo archivos regulares de hasta 2 MB sin enlaces múltiples.')
        with os.fdopen(handle, 'rb', closefd=False) as stream:
            data = stream.read(LIMIT + 1)
        if len(data) > LIMIT: raise ValueError('El archivo supera 2 MB.')
        return data
    finally: os.close(handle)

def read(root, name, missing=False):
    try:
        with parent(root, name) as (fd, leaf): return read_at(fd, leaf, missing)
    except ValueError as error:
        # Missing parents are absent proposal targets; do not create directories on read.
        if missing and isinstance(error.__cause__, FileNotFoundError): return None
        raise

def write(root, name, data, backup):
    if len(data) > LIMIT: raise ValueError('El contenido supera 2 MB.')
    with parent(root, name, create=True) as (fd, leaf):
        before = read_at(fd, leaf, missing=True)
        if before is not None: backup(before)
        temp = '.studio-write-' + uuid.uuid4().hex
        try:
            handle = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=fd)
            with os.fdopen(handle, 'wb') as stream:
                stream.write(data); stream.flush(); os.fsync(stream.fileno())
            # Replacement affects the directory entry, never a late symlink's target.
            os.replace(temp, leaf, src_dir_fd=fd, dst_dir_fd=fd)
        finally:
            try: os.unlink(temp, dir_fd=fd)
            except FileNotFoundError: pass
