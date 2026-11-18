"""Tree-sitter body selection. Source is data, never executed."""
from pathlib import Path

EXTENSIONS = {
    '.swift':'swift', '.js':'javascript', '.mjs':'javascript', '.cjs':'javascript',
    '.jsx':'javascript', '.ts':'typescript', '.mts':'typescript', '.cts':'typescript',
    '.tsx':'tsx', '.py':'python', '.go':'go', '.java':'java', '.kt':'kotlin',
    '.kts':'kotlin', '.c':'c', '.h':'c', '.cc':'cpp', '.cpp':'cpp', '.cxx':'cpp',
    '.hpp':'cpp', '.hh':'cpp', '.hxx':'cpp', '.cs':'csharp', '.rs':'rust',
    '.dart':'dart', '.rb':'ruby',
}
LANGUAGES = set(EXTENSIONS.values())
FUNCTIONS = {
    'javascript': {'function_declaration','function_expression','generator_function_declaration',
                   'generator_function','arrow_function','method_definition'},
    'typescript': {'function_declaration','function_expression','generator_function_declaration',
                   'generator_function','arrow_function','method_definition'},
    'tsx': {'function_declaration','function_expression','generator_function_declaration',
            'generator_function','arrow_function','method_definition'},
    'python': {'function_definition','lambda'},
    'go': {'function_declaration','method_declaration','func_literal'},
    'java': {'method_declaration','constructor_declaration','lambda_expression'},
    'c': {'function_definition'},
    'cpp': {'function_definition','lambda_expression'},
    'csharp': {'method_declaration','constructor_declaration','destructor_declaration',
               'local_function_statement','accessor_declaration','lambda_expression','anonymous_method_expression'},
    'rust': {'function_item','closure_expression'},
    'ruby': {'method','singleton_method','block','do_block'},
}
STUB = {
    'swift': 'fatalError("GYM TODO")', 'kotlin': 'TODO("GYM TODO")',
    'javascript': 'throw new Error("GYM TODO");',
    'typescript': 'throw new Error("GYM TODO");', 'tsx': 'throw new Error("GYM TODO");',
    'python': 'raise NotImplementedError("GYM TODO")', 'go': 'panic("GYM TODO")',
    'java': 'throw new UnsupportedOperationException("GYM TODO");',
    'c': '/* GYM TODO */ for (;;) {}', 'cpp': 'throw "GYM TODO";',
    'csharp': 'throw new System.NotImplementedException("GYM TODO");',
    'rust': 'todo!("GYM TODO")', 'dart': 'throw UnimplementedError("GYM TODO");',
    'ruby': 'raise NotImplementedError, "GYM TODO"',
}
BRACED = {'block','statement_block','compound_statement','constructor_body'}


def language_for(path, override=None):
    if Path(path).suffix.lower() not in EXTENSIONS:
        raise ValueError('지원하는 코드 확장자가 아닙니다: '+str(path))
    if override and override not in LANGUAGES:
        raise ValueError('지원하지 않는 언어: '+override)
    return override or ('cpp' if Path(path).suffix=='.C' else EXTENSIONS[Path(path).suffix.lower()])


def parser_for(language):
    try:
        from tree_sitter_language_pack import get_parser
        return get_parser(language)
    except (ImportError, LookupError) as error:
        raise ValueError('파서 설치가 필요합니다. gym 레포에서 bash scripts/install.sh 실행: '+str(error))


def walk(root):
    stack=[root]
    while stack:
        node=stack.pop()
        yield node
        stack.extend(reversed(node.named_children))


def child(node, *types):
    return next((n for n in node.named_children if n.type in types),None)


def body_for(node, language):
    # These grammars expose body nodes directly, including anonymous functions.
    if language=='swift':
        if node.type in {'function_body','lambda_literal','computed_getter','computed_setter','computed_modify','computed_property'}:
            return child(node,'statements')
        return None
    if language=='kotlin':
        if node.type in {'function_body','lambda_literal','secondary_constructor'}:
            statements=child(node,'statements')
            if statements is not None: return statements
            # Expression-bodied functions: retain the '=' token.
            if any(c.type=='=' for c in node.children):
                return next((c for c in reversed(node.named_children) if not c.is_extra),None)
        return None
    if language=='dart':
        if node.type in {'function_body','function_expression_body'}:
            block=child(node,'block')
            if block is not None: return block
            arrow=next((c for c in node.children if c.type=='=>'),None)
            if arrow is not None:
                return next((c for c in node.named_children if c.start_byte>=arrow.end_byte and not c.is_extra),None)
        return None
    if node.type not in FUNCTIONS.get(language,set()): return None
    body=node.child_by_field_name('body')
    if body is None and language=='csharp': body=child(node,'block')
    if body is not None and body.type=='arrow_expression_clause':
        return next((c for c in body.named_children if not c.is_extra),None)
    return body


def expression_stub(language):
    if language in {'javascript','typescript','tsx'}:
        return '(() => { throw new Error("GYM TODO"); })()'
    if language=='python': return '(_ for _ in ()).throw(NotImplementedError("GYM TODO"))'
    if language=='java': return '{ throw new UnsupportedOperationException("GYM TODO"); }'
    if language=='csharp': return 'throw new System.NotImplementedException("GYM TODO")'
    if language=='dart': return 'throw UnimplementedError("GYM TODO")'
    return STUB[language]


def candidates(source, language):
    source.decode('utf-8')
    parser=parser_for(language)
    tree=parser.parse(source)
    if tree.root_node.has_error:
        raise ValueError('원본 문법을 파서가 해석하지 못했습니다. 파일은 수정하지 않습니다.')
    result=[]; seen=set()
    for node in walk(tree.root_node):
        body=body_for(node,language)
        if body is None or body.start_byte==body.end_byte: continue
        start,end=body.start_byte,body.end_byte
        block=body.type in BRACED
        if block:
            left=next((c for c in body.children if c.type=='{'),None)
            right=next((c for c in reversed(body.children) if c.type=='}'),None)
            if left is None or right is None: continue
            start,end=left.end_byte,right.start_byte
        # Swift/Kotlin expose statements separately from braces. Replace the
        # full interior, preserving closure parameters and their delimiter.
        if language in {'swift','kotlin'} and body.type=='statements':
            left=next((c for c in node.children if c.type=='{'),None)
            right=next((c for c in reversed(node.children) if c.type=='}'),None)
            if left is not None and right is not None:
                delimiter=left
                if node.type=='lambda_literal':
                    marker='in' if language=='swift' else '->'
                    delimiter=next((c for c in node.children if c.type==marker),left)
                start,end=delimiter.end_byte,right.start_byte
                block=True
        if (start,end) in seen: continue
        seen.add((start,end))
        line_start=source.rfind(b'\n',0,start)+1
        prefix=source[line_start:start]
        indent=prefix[:len(prefix)-len(prefix.lstrip(b' \t'))].decode('utf-8')
        newline='\r\n' if b'\r\n' in source else '\n'
        statement=block or body.type in {'block','statements','body_statement','block_body'}
        stub=STUB[language] if statement else expression_stub(language)
        replacement=(newline+indent+'    '+stub+newline+indent) if block else stub
        # Include the preceding line when a body-only node starts at column zero.
        header_start=source.rfind(b'\n',0,node.start_byte)+1
        if node.type in {'function_body','function_expression_body'}:
            header_start=source.rfind(b'\n',0,max(0,node.start_byte-1))+1
        header=source[header_start:start].decode('utf-8').strip()
        label=' '.join(header.split())[-180:] or node.type
        result.append({'start':start,'end':end,'replacement':replacement,
                       'line':source[:start].count(b'\n')+1,'label':label,'kind':node.type})
    for number,item in enumerate(result,1): item['id']='T'+str(number)
    return result


def replace_body(source, language, target):
    start,end=target['start'],target['end']
    output=source[:start]+target['replacement'].encode('utf-8')+source[end:]
    if parser_for(language).parse(output).root_node.has_error:
        raise ValueError('이 본문의 안전한 변환을 지원하지 않습니다. 다른 후보를 선택하세요. 저장하지 않았습니다.')
    return output


def outermost_targets(targets):
    """Use all disjoint outer bodies; nested bodies disappear with their parent."""
    selected=[]
    for target in sorted(targets,key=lambda t:(t['start'],-t['end'])):
        if selected and target['start']<selected[-1]['end']:
            if target['end']<=selected[-1]['end']: continue
            raise ValueError('구현 본문 범위가 겹칩니다. 저장하지 않았습니다.')
        selected.append(target)
    return selected


def replace_bodies(source, language, targets):
    selected=outermost_targets(targets)
    output=source
    for target in reversed(selected):
        output=output[:target['start']]+target['replacement'].encode('utf-8')+output[target['end']:]
    if parser_for(language).parse(output).root_node.has_error:
        raise ValueError('본문 변환 후 문법 오류가 생겨 저장하지 않았습니다.')
    return output
