#!/usr/bin/env python3
"""NO AI GYM terminal entry point. Python 3.10+, Tree-sitter language pack."""
import argparse
import json
import os
import re
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
# The installed link may be invoked through an older system Python. Re-enter
# the managed interpreter before importing third-party modules.
VENV_PYTHON = ROOT / '.gym-venv' / 'bin' / 'python'
if VENV_PYTHON.is_file() and Path(sys.prefix).resolve() != (ROOT/'.gym-venv').resolve():
    os.execv(str(VENV_PYTHON),[str(VENV_PYTHON),str(Path(__file__).resolve())]+sys.argv[1:])
from code_skeleton import EXTENSIONS, LANGUAGES
OWNER = 'no-ai-gym-cli-v1'
SKIP = {'.git', '.build', 'build', 'dist', 'node_modules', 'vendor', 'Pods', 'DerivedData', '__pycache__', '.venv', 'venv'}
SECRET = {'.env', 'credentials.json', 'secrets.json', 'id_rsa', 'id_ed25519'}


def excluded(path):
    if re.search(r'(^|[^a-z])(agents|queue|setup|readme)(?=[^a-z]|$)',path.name.casefold()):
        return True
    return any(p.startswith('.') or p in SKIP for p in path.parts) or path.name in SECRET or path.suffix.lower() in {'.pem', '.key', '.p12', '.pfx', '.keystore'}


def selectable(path, relative):
    if path.is_symlink() or not path.is_file() or excluded(relative) or path.suffix.lower() not in EXTENSIONS:
        return False
    try:
        with path.open('rb') as stream:
            data = stream.read(2_000_001)
        if len(data)>2_000_000: return False
        data.decode('utf-8')
        return b'\0' not in data
    except (UnicodeError, OSError):
        return False


def collect(target):
    if target.is_file():
        return [target] if selectable(target, Path(target.name)) else []
    files = []
    for base, dirs, names in os.walk(str(target), followlinks=False):
        dirs[:] = sorted(d for d in dirs if not excluded(Path(d)) and not (Path(base)/d).is_symlink())
        for name in sorted(names):
            p = Path(base)/name
            if selectable(p, p.relative_to(target)):
                files.append(p)
            if len(files) > 200:
                raise ValueError('대상 파일이 200개를 넘습니다. 더 작은 폴더를 지정하세요.')
    return files


def select_target(value, cwd):
    if value is not None:
        p = Path(value).expanduser()
        p = p if p.is_absolute() else cwd/p
        if p.is_symlink():
            raise ValueError('심볼릭 링크 대신 실제 파일·폴더 경로를 지정하세요.')
        p = p.resolve()
        if excluded(Path(p.name)):
            raise ValueError('숨김·빌드·의존성·비밀 설정 경로는 제외합니다: '+str(p))
        if not p.exists() or not (p.is_file() or p.is_dir()):
            raise ValueError('파일·폴더가 없습니다: '+str(p))
        return p
    candidates = sorted((p for p in cwd.iterdir() if selectable(p, Path(p.name))), key=lambda p:p.name)
    if not candidates:
        raise ValueError('현재 폴더에 대상 파일이 없습니다. 경로 또는 . 을 지정하세요.')
    if len(candidates) == 1:
        return candidates[0].resolve()
    for i, p in enumerate(candidates, 1):
        print('{}: {}'.format(i,p.name))
    if not sys.stdin.isatty():
        raise ValueError('파일이 여러 개입니다. 파일명을 지정하세요.')
    value = input('추가할 파일 번호 (취소: Enter): ').strip()
    if not value.isdigit() or not 1 <= int(value) <= len(candidates):
        raise ValueError('대상 선택을 취소했습니다.')
    return candidates[int(value)-1].resolve()


def read_config(home):
    path = home/'.config/no-ai-gym/config.json'
    if not path.is_file() or path.is_symlink():
        raise ValueError('먼저 개인 gym에서 bash scripts/install.sh 를 실행하세요.')
    data=json.loads(path.read_text(encoding='utf-8'))
    if data.get('owner') != OWNER:
        raise ValueError('Gym 설정이 올바르지 않습니다.')
    return data


def validate_gym(gym):
    if (gym/'workouts').is_symlink() or not (gym/'workouts').is_dir():
        raise ValueError('Gym workouts 폴더가 없습니다.')


def setup(args, home):
    gym=args.gym.expanduser().resolve()
    validate_gym(gym)
    cfg=home/'.config/no-ai-gym/config.json'; link=home/'.local/bin/gym'
    if cfg.exists():
        old=read_config(home)
        if old['gym_root'] != str(gym) and not args.replace:
            raise ValueError('다른 gym이 연결되어 있습니다. --replace로 변경하세요.')
    if link.exists() or link.is_symlink():
        if not link.is_symlink() or link.resolve() != Path(__file__).resolve():
            raise ValueError('기존 gym 명령어를 덮어쓰지 않습니다: '+str(link))
    cfg.parent.mkdir(parents=True,exist_ok=True); link.parent.mkdir(parents=True,exist_ok=True)
    Path(__file__).chmod(0o755)
    if not link.is_symlink():
        link.symlink_to(Path(__file__).resolve())
    cfg.write_text(json.dumps({'owner':OWNER,'gym_root':str(gym),'tool':None},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('Gym CLI 설치 완료: {}'.format(gym))
    print('다른 프로젝트에서: gym add 파일명 / gym add 폴더 / gym add .')
    if str(link.parent) not in os.environ.get('PATH','').split(os.pathsep):
        print('현재 터미널에서 한 번 실행: export PATH="$HOME/.local/bin:$PATH"')
        print('다음 터미널에도 적용하려면 같은 줄을 ~/.zshrc 또는 ~/.bashrc에 추가하세요.')


def main(argv=None):
    parser=argparse.ArgumentParser(description='NO AI GYM terminal CLI')
    parser.add_argument('--home',type=Path,default=Path.home(),help=argparse.SUPPRESS)
    sub=parser.add_subparsers(dest='command')
    install=sub.add_parser('setup'); install.add_argument('--tool',choices=['codex','claude'],help=argparse.SUPPRESS); install.add_argument('--gym',type=Path,default=ROOT); install.add_argument('--replace',action='store_true')
    sub.add_parser('status'); sub.add_parser('uninstall')
    add=sub.add_parser('add'); add.add_argument('target',nargs='?'); add.add_argument('--tool',choices=['codex','claude'],help=argparse.SUPPRESS); add.add_argument('--dry-run',action='store_true')
    add.add_argument('--part',help='비울 본문 번호, 예: T2')
    add.add_argument('--list',action='store_true',help='본문 후보만 표시')
    add.add_argument('--language',choices=sorted(LANGUAGES),help='.h 등 언어가 모호한 파일 지정')
    args=parser.parse_args(argv); home=args.home.expanduser().resolve()
    if args.command=='setup':
        setup(args,home); return 0
    if args.command is None:
        parser.print_help(); return 0
    config=read_config(home); gym=Path(config['gym_root'])
    if args.command=='uninstall':
        link=home/'.local/bin/gym'
        if not link.is_symlink() or link.resolve()!=Path(__file__).resolve():
            raise ValueError('다른 gym 명령어는 제거하지 않습니다.')
        link.unlink(); (home/'.config/no-ai-gym/config.json').unlink()
        print('CLI 제거 완료. 과제와 기존 채팅 스킬은 보존했습니다.'); return 0
    if args.command=='status':
        print(json.dumps(config,ensure_ascii=False,indent=2)); return 0
    validate_gym(gym)
    cwd=Path.cwd().resolve(); target=select_target(args.target,cwd); files=collect(target)
    if not files:
        raise ValueError('지원하는 코드 파일이 없습니다. 설정·문서·바이너리는 받지 않습니다.')
    print('대상: {} ({}개 파일) · 본문 선택 · AI 사용 없음'.format(target,len(files)),flush=True)
    if args.dry_run:
        print(json.dumps({'pipeline':['parse code','select one body','save exercise and original'], 'source_files':[str(p) for p in files]},ensure_ascii=False,indent=2)); return 0
    from pipeline import run
    if len(files)>1 and (args.part or args.language):
        raise ValueError('--part와 --language는 파일 하나를 지정할 때 사용하세요.')
    return run(gym,files,args.part,args.language,args.list)



if __name__=='__main__':
    try:
        sys.exit(main())
    except (ValueError,OSError,KeyError,subprocess.SubprocessError) as error:
        print('Gym: '+str(error),file=sys.stderr); sys.exit(1)
    except (KeyboardInterrupt,EOFError):
        print('\n취소했습니다.',file=sys.stderr); sys.exit(130)
