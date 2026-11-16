"""CodePilot-X v0.4: 20-task independent evaluation (Python 3.9).
Run from project root: python3 scripts/evaluate_v04.py --attempts 2
Generated code executes locally. Use only trusted test repositories.
"""
import argparse
import json
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from codepilot.agent import run_agent

# id, module, initial source, task instruction, withheld assertions
TASKS = [
('casefold','auth','def login(u,p):\n    return u == "admin" and p == "secret"\n','Make usernames case-insensitive but passwords case-sensitive.',['assert login("ADMIN","secret")','assert not login("admin","SECRET")']),
('division','math_utils','def divide(a,b):\n    return a/b\n','Return None on division by zero, preserving other results.',['assert divide(4,0) is None','assert divide(9,2)==4.5']),
('stable_unique','collections_utils','def unique(xs):\n    return list(set(xs))\n','Remove duplicates preserving first occurrence order for hashable items.',['assert unique([3,1,3,2])==[3,1,2]','assert unique([])==[]']),
('palindrome','text_utils','def palindrome(s):\n    return s == s[::-1]\n','Ignore punctuation, whitespace and case when checking palindromes.',['assert palindrome("A man, a plan, a canal: Panama!")','assert not palindrome("hello")']),
('clamp','clamp_utils','def clamp(x,lo,hi):\n    return min(x,hi)\n','Clamp x to the inclusive [lo,hi] range and reject lo > hi with ValueError.',['assert clamp(-1,0,5)==0','assert clamp(9,0,5)==5','assert clamp(3,0,5)==3','try:\n clamp(2,5,1)\n assert False\nexcept ValueError: pass']),
('average','stats','def average(xs):\n    return sum(xs)/len(xs)\n','Return None for an empty list; otherwise compute arithmetic mean.',['assert average([]) is None','assert average([1,2,3])==2']),
('slugify','text_utils','def slugify(s):\n    return s.lower().replace(" ","-")\n','Strip outer whitespace, collapse repeated whitespace into one hyphen, and lowercase.',['assert slugify("  Hello   World  ")=="hello-world"','assert slugify("A\\tB")=="a-b"']),
('binary_search','search','def binary_search(xs,target):\n    return xs.index(target)\n','Implement binary search on sorted ascending list; return -1 if missing.',['assert binary_search([1,3,5],3)==1','assert binary_search([1,3,5],4)==-1','assert binary_search([],1)==-1']),
('flatten','collections_utils','def flatten(rows):\n    return rows\n','Flatten one level of a list of lists, preserving order.',['assert flatten([[1,2],[],[3]])==[1,2,3]','assert flatten([])==[]']),
('factorial','math_utils','def factorial(n):\n    return n * factorial(n-1)\n','Return factorial for nonnegative integers including 0; reject negatives with ValueError.',['assert factorial(0)==1','assert factorial(5)==120','try:\n factorial(-1)\n assert False\nexcept ValueError: pass']),
('word_count','text_utils','def word_count(s):\n    return len(s.split(" "))\n','Count whitespace-separated words, including tabs/newlines; empty text has zero words.',['assert word_count("  a  b\\tc ")==3','assert word_count("  ")==0']),
('rotate','collections_utils','def rotate(xs,k):\n    return xs[k:]+xs[:k]\n','Rotate list right by k positions; support negative k and empty lists.',['assert rotate([1,2,3],1)==[3,1,2]','assert rotate([1,2,3],-1)==[2,3,1]','assert rotate([],10)==[]']),
('merge_dicts','collections_utils','def merge(a,b):\n    return a\n','Merge two dictionaries without mutating inputs; b overrides duplicate keys.',['a={"x":1};b={"x":2,"y":3};assert merge(a,b)=={"x":2,"y":3};assert a=={"x":1}']),
('parse_bool','parse_utils','def parse_bool(s):\n    return bool(s)\n','Parse case-insensitive true/false, yes/no, 1/0 with surrounding whitespace; invalid values raise ValueError.',['assert parse_bool(" YES ") is True','assert parse_bool("false") is False','try:\n parse_bool("maybe")\n assert False\nexcept ValueError: pass']),
('normalize_email','text_utils','def normalize_email(s):\n    return s\n','Strip surrounding whitespace and lowercase the domain only, preserving local-part case.',['assert normalize_email(" User.Name@EXAMPLE.COM ")=="User.Name@example.com"']),
('chunk','collections_utils','def chunk(xs,n):\n    return [xs]\n','Split a list into consecutive chunks of size n; n <= 0 raises ValueError.',['assert chunk([1,2,3,4,5],2)==[[1,2],[3,4],[5]]','assert chunk([],2)==[]','try:\n chunk([1],0)\n assert False\nexcept ValueError: pass']),
('is_prime','math_utils','def is_prime(n):\n    return n%2 != 0\n','Correctly determine whether an integer is prime, including 0, 1, 2 and squares.',['assert not is_prime(0)','assert not is_prime(1)','assert is_prime(2)','assert is_prime(97)','assert not is_prime(49)']),
('safe_get','collections_utils','def safe_get(xs,i):\n    return xs[i]\n','Return None when index is out of range, while supporting valid negative indices.',['assert safe_get([1,2],5) is None','assert safe_get([1,2],-1)==2','assert safe_get([],0) is None']),
('titlecase','text_utils','def titlecase(s):\n    return s.upper()\n','Capitalize the first letter of each whitespace-separated word and lowercase remaining letters, preserving single spaces between words.',['assert titlecase("hELLO wORLD")=="Hello World"','assert titlecase("a b")=="A B"']),
('running_total','math_utils','def running_total(xs):\n    return [sum(xs)]\n','Return cumulative sums in input order; empty list returns empty list.',['assert running_total([1,2,-1])==[1,3,2]','assert running_total([])==[]']),
]

def check(source, module, assertions):
    with tempfile.TemporaryDirectory() as d:
        root=Path(d)
        (root/(module+'.py')).write_text(source,encoding='utf-8')
        test='from {} import *\n'.format(module)+'\n'.join(assertions)+'\n'
        (root/'verify.py').write_text(test,encoding='utf-8')
        try:
            p=subprocess.run([sys.executable,'-I',str(root/'verify.py')],cwd=str(root),capture_output=True,text=True,timeout=8)
            # -I excludes cwd and script path from sys.path on some Python builds: use explicit PYTHONPATH-free run instead.
            if p.returncode and 'ModuleNotFoundError' in p.stderr:
                p=subprocess.run([sys.executable,str(root/'verify.py')],cwd=str(root),capture_output=True,text=True,timeout=8)
            return p.returncode==0,(p.stderr+p.stdout)[-1500:]
        except subprocess.TimeoutExpired:
            return False,'Timeout'

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--attempts',type=int,default=2)
    parser.add_argument('--output',default='benchmark-v04.json')
    parser.add_argument('--limit',type=int,default=20)
    args=parser.parse_args()
    if not 1<=args.attempts<=5 or not 1<=args.limit<=20: parser.error('attempts must be 1-5; limit 1-20')
    results=[]
    for task_id,module,source,instruction,checks in TASKS[:args.limit]:
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            (root/(module+'.py')).write_text(source,encoding='utf-8')
            (root/'tests').mkdir()
            (root/'tests'/'test_smoke.py').write_text('import unittest\nclass Smoke(unittest.TestCase):\n def test_smoke(self): self.assertTrue(True)\n',encoding='utf-8')
            started=time.monotonic()
            rec={'id':task_id,'task':instruction}
            try:
                response=run_agent(str(root),instruction,attempts=args.attempts)
                rec['existing_tests_passed']=bool(response['success'])
                rec['attempts']=len(response['history'])
                edited=response.get('files',{}).get(module+'.py')
                rec['hidden_tests_passed'],rec['error']=check(edited,module,checks) if edited is not None else (False,'No edited target file')
            except Exception as e:
                rec.update(existing_tests_passed=False,hidden_tests_passed=False,attempts=0,error=str(e)[:500])
            rec['elapsed_seconds']=round(time.monotonic()-started,3)
            results.append(rec)
            print('{}: hidden={} attempts={} time={}s'.format(task_id,rec['hidden_tests_passed'],rec['attempts'],rec['elapsed_seconds']),flush=True)
    report={'benchmark':'CodePilot-X v0.4 synthetic pilot','model_provider':'Configured via environment','task_count':len(results),'existing_test_pass_rate':sum(x['existing_tests_passed'] for x in results)/len(results),'hidden_test_task_success_rate':sum(x['hidden_tests_passed'] for x in results)/len(results),'mean_attempts':statistics.mean(x['attempts'] for x in results),'mean_seconds':statistics.mean(x['elapsed_seconds'] for x in results),'results':results,'limitations':['Synthetic single-file tasks, not SWE-bench','Tests run generated code locally; no security sandbox','Smoke tests are trivial; feedback loop not meaningfully challenged','One run per task; no statistical uncertainty or ablation comparisons']}
    Path(args.output).write_text(json.dumps(report,indent=2),encoding='utf-8')
    print('Saved {} | hidden success {:.1%}'.format(args.output,report['hidden_test_task_success_rate']))
if __name__=='__main__': main()
