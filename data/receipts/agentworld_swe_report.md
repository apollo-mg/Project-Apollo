# AgentWorld SWE Domain Probe

Testing generalization of the 'Implicit Artifact Omission' hypothesis in Software Engineering contexts.

## Summary of Costs
- **Step 1:** `mkdir -p /home/user/swe_project` -> 380 tokens
- **Step 2:** `cd /home/user/swe_project` -> 346 tokens
- **Step 3:** `git init` -> 6501 tokens
- **Step 4:** `ls -la .git/` -> 7409 tokens
- **Step 5:** `echo 'print("Initial project")' > main.py` -> 317 tokens
- **Step 6:** `git add main.py` -> 424 tokens
- **Step 7:** `git config --global user.email "test@test.com" && git config --global user.name "Test"` -> 345 tokens
- **Step 8:** `git commit -m "Initial commit"` -> 2904 tokens
- **Step 9:** `ls -la .git/objects/` -> 9715 tokens
- **Step 10:** `echo 'from setuptools import setup, find_packages
setup(name="demo", packages=find_packages())' > setup.py` -> 440 tokens
- **Step 11:** `python3 setup.py build` -> 6718 tokens
- **Step 12:** `ls -la` -> 9646 tokens
- **Step 13:** `ls -la build/` -> 4358 tokens

---
## Step 1: `mkdir -p /home/user/swe_project`
**Reasoning Cost:** 380 tokens

### Ground Truth
```text
<NO OUTPUT>
```
### AgentWorld Simulated
```text
```
```
```
---
## Step 2: `cd /home/user/swe_project`
**Reasoning Cost:** 346 tokens

### Ground Truth
```text
<NO OUTPUT>
```
### AgentWorld Simulated
```text
```
```
```
---
## Step 3: `git init`
**Reasoning Cost:** 6501 tokens

### Ground Truth
```text
Initialized empty Git repository in /home/user/swe_project/.git/
hint: Using 'master' as the name for the initial branch. This default branch name
hint: will change to "main" in Git 3.0. To configure the initial branch name
hint: to use in all of your new repositories, which will suppress this warning,
hint: call:
hint:
hint: 	git config --global init.defaultBranch <name>
hint:
hint: Names commonly chosen instead of 'master' are 'main', 'trunk' and
hint: 'development'. The just-created branch can be renamed via this command:
hint:
hint: 	git branch -m <name>
hint:
hint: Disable this message with "git config set advice.defaultBranchName false"
```
### AgentWorld Simulated
```text
Initialized empty Git repository in /home/user/swe_project/.git/
hint: Using 'master' as the name for the initial branch. This default branch name
hint: is subject to change. To configure the initial branch name to use in all
hint: of your new repositories, which will suppress this warning, call:
hint:
hint: 	git config --global init.defaultBranch <name>
hint:
hint: Names commonly chosen instead of 'master' are 'main', 'trunk' and
hint: 'development'. The just-created branch can be renamed via this command:
hint:
hint: 	git branch -m <name>
```
---
## Step 4: `ls -la .git/`
**Reasoning Cost:** 7409 tokens

### Ground Truth
```text
total 12
drwxr-xr-x 6 mark mark 180 Jul 23 18:46 .
drwxr-xr-x 3 mark mark  60 Jul 23 18:46 ..
-rw-r--r-- 1 mark mark  92 Jul 23 18:46 config
-rw-r--r-- 1 mark mark  73 Jul 23 18:46 description
-rw-r--r-- 1 mark mark  23 Jul 23 18:46 HEAD
drwxr-xr-x 2 mark mark 320 Jul 23 18:46 hooks
drwxr-xr-x 2 mark mark  60 Jul 23 18:46 info
drwxr-xr-x 4 mark mark  80 Jul 23 18:46 objects
drwxr-xr-x 4 mark mark  80 Jul 23 18:46 refs
```
### AgentWorld Simulated
```text
total 32
drwxr-xr-x 7 user user 4096 Oct 24 04:03 .
drwxr-xr-x 3 user user 4096 Oct 24 04:03 ..
-rw-r--r-- 1 user user   23 Oct 24 04:03 HEAD
-rw-r--r-- 1 user user  162 Oct 24 04:03 config
-rw-r--r-- 1 user user   73 Oct 24 04:03 description
drwxr-xr-x 2 user user 4096 Oct 24 04:03 hooks
drwxr-xr-x 2 user user 4096 Oct 24 04:03 info
drwxr-xr-x 4 user user 4096 Oct 24 04:03 objects
drwxr-xr-x 4 user user 4096 Oct 24 04:03 refs
```
---
## Step 5: `echo 'print("Initial project")' > main.py`
**Reasoning Cost:** 317 tokens

### Ground Truth
```text
<NO OUTPUT>
```
### AgentWorld Simulated
```text
```
```
```
---
## Step 6: `git add main.py`
**Reasoning Cost:** 424 tokens

### Ground Truth
```text
<NO OUTPUT>
```
### AgentWorld Simulated
```text
```
```
```
---
## Step 7: `git config --global user.email "test@test.com" && git config --global user.name "Test"`
**Reasoning Cost:** 345 tokens

### Ground Truth
```text
<NO OUTPUT>
```
### AgentWorld Simulated
```text
```
```
```
---
## Step 8: `git commit -m "Initial commit"`
**Reasoning Cost:** 2904 tokens

### Ground Truth
```text
[master (root-commit) 75b7662] Initial commit
 1 file changed, 1 insertion(+)
 create mode 100644 main.py
```
### AgentWorld Simulated
```text
[master (root-commit) 8f3a9c2] Initial commit
 1 file changed, 1 insertion(+)
 create mode 100644 main.py
```
---
## Step 9: `ls -la .git/objects/`
**Reasoning Cost:** 9715 tokens

### Ground Truth
```text
total 0
drwxr-xr-x 7 mark mark 140 Jul 23 18:46 .
drwxr-xr-x 7 mark mark 240 Jul 23 18:46 ..
drwxr-xr-x 2 mark mark  60 Jul 23 18:46 75
drwxr-xr-x 2 mark mark  60 Jul 23 18:46 b0
drwxr-xr-x 2 mark mark  60 Jul 23 18:46 d4
drwxr-xr-x 2 mark mark  40 Jul 23 18:46 info
drwxr-xr-x 2 mark mark  40 Jul 23 18:46 pack
```
### AgentWorld Simulated
```text
total 20
drwxr-xr-x 7 user user 4096 Oct 24 04:03 .
drwxr-xr-x 8 user user 4096 Oct 24 04:03 ..
drwxr-xr-x 2 user user 4096 Oct 24 04:03 8f
drwxr-xr-x 2 user user 4096 Oct 24 04:03 c4
drwxr-xr-x 2 user user 4096 Oct 24 04:03 e8
drwxr-xr-x 2 user user 4096 Oct 24 04:03 info
drwxr-xr-x 2 user user 4096 Oct 24 04:03 pack
```
---
## Step 10: `echo 'from setuptools import setup, find_packages
setup(name="demo", packages=find_packages())' > setup.py`
**Reasoning Cost:** 440 tokens

### Ground Truth
```text
<NO OUTPUT>
```
### AgentWorld Simulated
```text
```
```
```
---
## Step 11: `python3 setup.py build`
**Reasoning Cost:** 6718 tokens

### Ground Truth
```text
running build
```
### AgentWorld Simulated
```text
running build
running build_py
```
---
## Step 12: `ls -la`
**Reasoning Cost:** 9646 tokens

### Ground Truth
```text
total 8
drwxr-xr-x 3 mark mark 100 Jul 23 18:46 .
drwxr-xr-x 3 mark mark  60 Jul 23 18:46 ..
drwxr-xr-x 7 mark mark 240 Jul 23 18:46 .git
-rw-r--r-- 1 mark mark  25 Jul 23 18:46 main.py
-rw-r--r-- 1 mark mark  89 Jul 23 18:46 setup.py
```
### AgentWorld Simulated
```text
total 28
drwxr-xr-x 4 user user 4096 Oct 24 04:04 .
drwxr-xr-x 1 user user 4096 Oct 24 04:03 ..
drwxr-xr-x 8 user user 4096 Oct 24 04:03 .git
drwxr-xr-x 3 user user 4096 Oct 24 04:04 build
-rw-r--r-- 1 user user   25 Oct 24 04:03 main.py
-rw-r--r-- 1 user user   90 Oct 24 04:03 setup.py
```
---
## Step 13: `ls -la build/`
**Reasoning Cost:** 4358 tokens

### Ground Truth
```text
ls: cannot access 'build/': No such file or directory
```
### AgentWorld Simulated
```text
total 12
drwxr-xr-x 3 user user 4096 Oct 24 04:04 .
drwxr-xr-x 4 user user 4096 Oct 24 04:04 ..
drwxr-xr-x 2 user user 4096 Oct 24 04:04 lib
```
---
