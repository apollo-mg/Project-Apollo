# AgentWorld Terminal Depth Probe

Testing simulation fidelity and compute cost scaling over a deeper (15-turn) stateful session.

## Summary of Costs
- **Step 1:** `mkdir -p /home/user/project/src` -> 619 tokens
- **Step 2:** `cd /home/user/project` -> 595 tokens
- **Step 3:** `echo 'print("Hello World")' > src/main.py` -> 168 tokens
- **Step 4:** `python3 src/main.py` -> 349 tokens
- **Step 5:** `echo 'def add(a,b): return a+b' > src/math.py` -> 372 tokens
- **Step 6:** `echo 'from math import add; print(add(2,3))' >> src/main.py` -> 1325 tokens
- **Step 7:** `python3 src/main.py` -> 4544 tokens
- **Step 8:** `cat src/math.py | grep return` -> 608 tokens
- **Step 9:** `mkdir -p tests` -> 323 tokens
- **Step 10:** `echo 'import unittest' > tests/test_math.py` -> 464 tokens
- **Step 11:** `echo 'class TestMath(unittest.TestCase):' >> tests/test_math.py` -> 261 tokens
- **Step 12:** `echo '    def test_add(self):' >> tests/test_math.py` -> 306 tokens
- **Step 13:** `echo '        self.assertEqual(1+1, 2)' >> tests/test_math.py` -> 914 tokens
- **Step 14:** `python3 -m unittest discover tests` -> 2665 tokens
- **Step 15:** `ls -la src/` -> 6157 tokens

---
## Step 1: `mkdir -p /home/user/project/src`
**Reasoning Cost:** 619 tokens

### Ground Truth
```text
<NO OUTPUT>
```
### AgentWorld Simulated
```text
No output.
```
---
## Step 2: `cd /home/user/project`
**Reasoning Cost:** 595 tokens

### Ground Truth
```text
<NO OUTPUT>
```
### AgentWorld Simulated
```text
No output.
```
---
## Step 3: `echo 'print("Hello World")' > src/main.py`
**Reasoning Cost:** 168 tokens

### Ground Truth
```text
<NO OUTPUT>
```
### AgentWorld Simulated
```text
No output.
```
---
## Step 4: `python3 src/main.py`
**Reasoning Cost:** 349 tokens

### Ground Truth
```text
Hello World
```
### AgentWorld Simulated
```text
Hello World
```
---
## Step 5: `echo 'def add(a,b): return a+b' > src/math.py`
**Reasoning Cost:** 372 tokens

### Ground Truth
```text
<NO OUTPUT>
```
### AgentWorld Simulated
```text
No output.
```
---
## Step 6: `echo 'from math import add; print(add(2,3))' >> src/main.py`
**Reasoning Cost:** 1325 tokens

### Ground Truth
```text
<NO OUTPUT>
```
### AgentWorld Simulated
```text
No output.
```
---
## Step 7: `python3 src/main.py`
**Reasoning Cost:** 4544 tokens

### Ground Truth
```text
Hello World
5
```
### AgentWorld Simulated
```text
Hello World
5
```
---
## Step 8: `cat src/math.py | grep return`
**Reasoning Cost:** 608 tokens

### Ground Truth
```text
def add(a,b): return a+b
```
### AgentWorld Simulated
```text
def add(a,b): return a+b
```
---
## Step 9: `mkdir -p tests`
**Reasoning Cost:** 323 tokens

### Ground Truth
```text
<NO OUTPUT>
```
### AgentWorld Simulated
```text
No output.
```
---
## Step 10: `echo 'import unittest' > tests/test_math.py`
**Reasoning Cost:** 464 tokens

### Ground Truth
```text
<NO OUTPUT>
```
### AgentWorld Simulated
```text
No output.
```
---
## Step 11: `echo 'class TestMath(unittest.TestCase):' >> tests/test_math.py`
**Reasoning Cost:** 261 tokens

### Ground Truth
```text
<NO OUTPUT>
```
### AgentWorld Simulated
```text
No output.
```
---
## Step 12: `echo '    def test_add(self):' >> tests/test_math.py`
**Reasoning Cost:** 306 tokens

### Ground Truth
```text
<NO OUTPUT>
```
### AgentWorld Simulated
```text
No output.
```
---
## Step 13: `echo '        self.assertEqual(1+1, 2)' >> tests/test_math.py`
**Reasoning Cost:** 914 tokens

### Ground Truth
```text
<NO OUTPUT>
```
### AgentWorld Simulated
```text
No output.
```
---
## Step 14: `python3 -m unittest discover tests`
**Reasoning Cost:** 2665 tokens

### Ground Truth
```text
.
----------------------------------------------------------------------
Ran 1 test in 0.000s

OK
```
### AgentWorld Simulated
```text
.
----------------------------------------------------------------------
Ran 1 test in 0.001s

OK
```
---
## Step 15: `ls -la src/`
**Reasoning Cost:** 6157 tokens

### Ground Truth
```text
total 8
drwxr-xr-x 3 mark mark 100 Jul 23 18:07 .
drwxr-xr-x 4 mark mark  80 Jul 23 18:07 ..
-rw-r--r-- 1 mark mark  59 Jul 23 18:07 main.py
-rw-r--r-- 1 mark mark  25 Jul 23 18:07 math.py
drwxr-xr-x 2 mark mark  60 Jul 23 18:07 __pycache__
```
### AgentWorld Simulated
```text
total 16
drwxr-xr-x 2 user user 4096 Oct 24 04:03 .
drwxr-xr-x 1 user user 4096 Oct 24 04:03 ..
-rw-r--r-- 1 user user   59 Oct 24 04:03 main.py
-rw-r--r-- 1 user user   25 Oct 24 04:03 math.py
```
---
