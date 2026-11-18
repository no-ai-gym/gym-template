"""Optional local regression checks: .gym-venv/bin/python scripts/check_parsers.py"""
import tempfile
import unittest
from pathlib import Path
from code_skeleton import candidates, replace_body, language_for, replace_bodies, outermost_targets
from pipeline import publish

SAMPLES = {
    'swift': 'func value(_ x: Int) -> Int { return x + 1 }\n',
    'javascript': 'function value(x) { return x + 1; }\n',
    'typescript': 'function value(x: number): number { return x + 1; }\n',
    'tsx': 'function Value() { return <div>hello</div>; }\n',
    'python': 'def value(x):\n    return x + 1\n',
    'go': 'package sample\nfunc value(x int) int { return x + 1 }\n',
    'java': 'class Sample { int value(int x) { return x + 1; } }\n',
    'kotlin': 'fun value(x: Int): Int { return x + 1 }\n',
    'c': 'int value(int x) { return x + 1; }\n',
    'cpp': 'int value(int x) { return x + 1; }\n',
    'csharp': 'class Sample { int Value(int x) { return x + 1; } }\n',
    'rust': 'fn value(x: i32) -> i32 { x + 1 }\n',
    'dart': 'int value(int x) { return x + 1; }\n',
    'ruby': 'def value(x)\n  x + 1\nend\n',
}
EXTRA = [
    ('swift','let f = { (x: Int) -> Int in x + 1 }\n'),
    ('swift','struct S { static var live: Client { Client { x in x + 1 } send: { y in y + 2 } } }\n'),
    ('javascript','const f = x => x + 1;\n'),
    ('javascript','const f = x => <div>{x}</div>;\n'),
    ('typescript','const f = (x: number): number => x + 1;\n'),
    ('python','f = lambda x: x + 1\n'),
    ('go','package sample\nvar f = func(x int) int { return x + 1 }\n'),
    ('java','class S { Runnable r = () -> work(); }\n'),
    ('kotlin','fun value(x: Int) = x + 1\n'),
    ('kotlin','val f = { x: Int -> x + 1 }\n'),
    ('cpp','auto f = [](int x) { return x + 1; };\n'),
    ('csharp','class S { int Value(int x) => x + 1; }\n'),
    ('rust','fn main() { let f = |x: i32| x + 1; }\n'),
    ('dart','int value(int x) => x + 1;\n'),
    ('ruby','f = ->(x) { x + 1 }\n'),
    ('javascript','function f() { const s = "} 한글 {"; return s; }\r\n'),
    ('python','def f():\n    """braces { } 한글"""\n    return 1\n'),
]

class ParserChecks(unittest.TestCase):
    def check_source(self,language,text):
        source=text.encode('utf-8')
        targets=candidates(source,language)
        self.assertTrue(targets,language+' candidates missing')
        for target in targets:
            output=replace_body(source,language,target)
            self.assertNotEqual(output,source)
            self.assertEqual(output[:target['start']],source[:target['start']])
            replacement_end=target['start']+len(target['replacement'].encode('utf-8'))
            self.assertEqual(output[replacement_end:],source[target['end']:])
            self.assertIn(b'GYM TODO',output)

    def test_all_languages(self):
        for lang,text in SAMPLES.items():
            with self.subTest(language=lang): self.check_source(lang,text)

    def test_expression_nested_unicode_and_crlf(self):
        for lang,text in EXTRA:
            with self.subTest(language=lang,source=text): self.check_source(lang,text)

    def test_all_sibling_bodies_and_swift_format(self):
        source=b'enum Codec {\n    static func encode() -> Int { return 41 }\n    static func decode() -> Int { return 42 }\n}\n'
        targets=candidates(source,'swift')
        self.assertEqual(len(outermost_targets(targets)),2)
        output=replace_bodies(source,'swift',targets)
        self.assertEqual(output.count(b'GYM TODO'),2)
        self.assertNotIn(b'return 41',output)
        self.assertNotIn(b'return 42',output)
        self.assertIn(b'fatalError("GYM TODO")\n    }',output)

    def test_all_languages_replace_siblings(self):
        for lang,text in SAMPLES.items():
            # Two copies provide independent top-level/class/function bodies.
            if lang=='go': text=text+'func second() int { return 123456 }\n'
            else: text=text+text
            with self.subTest(language=lang):
                source=text.encode()
                targets=candidates(source,lang)
                self.assertGreaterEqual(len(outermost_targets(targets)),2)
                output=replace_bodies(source,lang,targets)
                self.assertGreaterEqual(output.count(b'GYM TODO'),2)

    def test_invalid_source_rejected(self):
        with self.assertRaises(ValueError): candidates(b'def f(:', 'python')

    def test_non_code_rejected(self):
        for name in ['config.json','notes.md','settings.yaml','photo.png']:
            with self.subTest(name=name), self.assertRaises(ValueError): language_for(name)

    def test_java_filename_original_and_duplicate_preserved(self):
        with tempfile.TemporaryDirectory() as name:
            gym=Path(name)
            (gym/'workouts').mkdir()
            source=gym/'Sample.java'
            original=SAMPLES['java'].encode()
            source.write_bytes(original)
            target=candidates(original,'java')[0]
            code=replace_body(original,'java',target)
            folder=publish(gym,source,original,code,target,'java')
            self.assertEqual({p.name for p in folder.iterdir()}, {'Sample.java','Original.java.txt'})
            self.assertEqual((folder/'Original.java.txt').read_bytes(),original)
            self.assertEqual(source.read_bytes(),original)
            (folder/'Sample.java').write_bytes(b'learner implementation')
            self.assertEqual(publish(gym,source,original,code,target,'java'),folder)
            self.assertEqual((folder/'Sample.java').read_bytes(),b'learner implementation')

if __name__=='__main__': unittest.main(verbosity=2)
