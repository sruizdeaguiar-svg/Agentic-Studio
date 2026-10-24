"""Build-time checks for native payload execute modes, links and OS load commands."""
import os
from pathlib import Path
import struct

REQUIRED=('Contents/MacOS/Agentic Studio','Contents/Resources/python/bin/python3','Contents/Resources/codex/codex')

def minimum_os(path):
    with path.open('rb') as stream:
        header=stream.read(32)
        if header[:4]!=b'\xcf\xfa\xed\xfe':return None
        commands=struct.unpack_from('<I',header,16)[0]
        if commands>4096:raise ValueError('Invalid Mach-O command count')
        version=None
        for _ in range(commands):
            prefix=stream.read(8)
            if len(prefix)!=8:raise ValueError('Truncated Mach-O command')
            kind,size=struct.unpack('<II',prefix)
            if not 8<=size<=16_000_000:raise ValueError('Invalid Mach-O command size')
            body=stream.read(size-8)
            if len(body)!=size-8:raise ValueError('Truncated Mach-O command')
            if kind==0x32:version=struct.unpack_from('<I',body,4)[0]
            elif kind==0x24:version=struct.unpack_from('<I',body,0)[0]
        return (version>>16,(version>>8)&255,version&255) if version is not None else None

def verify_payload(app,target=(12,0,0)):
    app=Path(app).resolve()
    for relative in REQUIRED:
        path=app/relative
        if not path.is_file() or not os.access(path,os.X_OK):raise ValueError('Missing executable permission: '+relative)
    versions=[]
    for path in app.rglob('*'):
        if path.is_symlink() and not path.resolve().is_relative_to(app):raise ValueError('Payload link escapes the application: '+str(path.relative_to(app)))
        if path.is_file() and not path.is_symlink():
            version=minimum_os(path)
            if version is not None:
                if version>target:raise ValueError('Binary requires newer macOS: '+str(path.relative_to(app))+' '+str(version))
                versions.append(version)
    return {'executable_permissions':True,'symlinks_inside_app':True,'mach_o_files_checked':len(versions),'highest_minimum_macos':'.'.join(map(str,max(versions))) if versions else None}
