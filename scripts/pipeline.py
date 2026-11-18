"""Local code recall practice. No AI calls or generated specifications."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile

def load_index(gym):
    path=gym/'.gym-index.json'
    if path.is_symlink(): raise ValueError('Gym 인덱스 링크는 수정하지 않습니다.')
    if not path.exists(): return {}
    data=json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data,dict): raise ValueError('Gym 인덱스 형식 오류')
    return data


def atomic_write(path, text):
    fd,name=tempfile.mkstemp(prefix='.gym-write-',dir=str(path.parent))
    temp=Path(name)
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as stream: stream.write(text)
        temp.replace(path)
    finally:
        if temp.exists(): temp.unlink()


def destination(gym, source):
    stem=re.sub(r'([a-z0-9])([A-Z])',r'\1-\2',source.stem).lower().replace('_','-')
    slug=re.sub(r'[^\w-]+','-',stem).strip('-') or 'exercise'
    folder=gym/'workouts'/slug
    number=2
    while folder.exists() or folder.is_symlink():
        folder=gym/'workouts'/(slug+'-'+str(number))
        number+=1
    return folder


def publish(gym, source, original, code, target, language):
    lock=gym/'.gym-publish.lock'
    fd=os.open(str(lock),os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    folder=None; temp=None
    try:
        index=load_index(gym)
        key='local-body-v2:'+str(source)+':'+hashlib.sha256(original).hexdigest()+':'+language+':'+target['id']
        record=index.get(key)
        if record:
            name=record.get('folder','')
            if not name or Path(name).name!=name or name in ('.','..'):
                raise ValueError('과제 인덱스 경로 오류')
            previous=gym/'workouts'/name
            if previous.is_symlink(): raise ValueError('과제 폴더 링크는 사용하지 않습니다.')
            if previous.is_dir(): return previous
        folder=destination(gym,source)
        temp=Path(tempfile.mkdtemp(prefix='.gym-task-',dir=str(gym/'workouts')))
        implementation=source.name
        (temp/('Original'+source.suffix+'.txt')).write_bytes(original)
        (temp/implementation).write_bytes(code)
        index=load_index(gym)
        index[key]={'folder':folder.name,'implementation':implementation,'source':str(source),'target':target['id']}
        temp.rename(folder); temp=None
        try:
            atomic_write(gym/'.gym-index.json',json.dumps(index,ensure_ascii=False,indent=2)+'\n')
        except Exception:
            shutil.rmtree(str(folder)); raise
        return folder
    finally:
        if temp is not None and temp.exists(): shutil.rmtree(str(temp))
        os.close(fd); lock.unlink()


def choose(targets, selected=None):
    selected=selected.upper()
    if selected.isdigit(): selected='T'+selected
    item=next((item for item in targets if item['id']==selected),None)
    if item is None: raise ValueError('목록에 없는 본문 번호입니다.')
    return item


def run(gym, files, part=None, language=None, list_only=False):
    from code_skeleton import language_for, candidates, replace_body, replace_bodies, outermost_targets
    failed=False
    for source in files:
        source=source.resolve()
        try:
            lang=language_for(source,language)
            original=source.read_bytes()
            if len(original)>2_000_000: raise ValueError('2 MB 이하의 코드 파일을 지정하세요.')
            print('▶ {} · {}'.format(source.name,lang),flush=True)
            targets=candidates(original,lang)
            if not targets:
                print('건너뜀: 지원되는 구현 본문이 없습니다.'); continue
            if list_only:
                for item in targets:
                    print('{} · {}행 · {}'.format(item['id'],item['line'],item['label']))
                continue
            if part is None:
                selected=outermost_targets(targets)
                code=replace_bodies(original,lang,selected)
                target={'id':'ALL-v1','line':selected[0]['line']}
                print('  구현 본문 {}개 비움'.format(len(selected)))
            else:
                target=choose(targets,part)
                print('  본문: {} · {}행 · {}'.format(target['id'],target['line'],target['label']))
                code=replace_body(original,lang,target)
            folder=publish(gym,source,original,code,target,lang)
            print('✓ 구현 파일: '+str(folder/source.name))
            print('  원본 비교: '+str(folder/('Original'+source.suffix+'.txt')))
        except (ValueError,OSError,KeyError) as error:
            failed=True; print('추가 실패 [{}]: {}'.format(source.name,error),file=sys.stderr)
        except (KeyboardInterrupt,EOFError):
            print('취소했습니다.',file=sys.stderr); return 130
    return 1 if failed else 0
