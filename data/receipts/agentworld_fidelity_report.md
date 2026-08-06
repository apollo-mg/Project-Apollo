# AgentWorld Terminal Fidelity Probe

Comparing ground truth bash execution vs AgentWorld-35B-A3B simulation.

## Command 0: `mkdir -p /home/user/project`
**AgentWorld Reasoning Cost:** ~290 tokens

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
## Command 1: `cd /home/user/project && echo 'print("Simulation Test")' > test.py`
**AgentWorld Reasoning Cost:** ~230 tokens

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
## Command 2: `cd /home/user/project && ls -la`
**AgentWorld Reasoning Cost:** ~4686 tokens

### Ground Truth
```text
total 4
drwxr-xr-x 2 mark mark 60 Jul 23 17:45 .
drwxr-xr-x 3 mark mark 60 Jul 23 17:45 ..
-rw-r--r-- 1 mark mark 25 Jul 23 17:45 test.py
```
### AgentWorld Simulated
```text
total 12
drwxr-xr-x 2 user user 4096 Oct 24 04:03 .
drwxr-xr-x 1 user user 4096 Oct 24 04:03 ..
-rw-r--r-- 1 user user   25 Oct 24 04:03 test.py
```
---
## Command 3: `cd /home/user/project && python3 test.py`
**AgentWorld Reasoning Cost:** ~327 tokens

### Ground Truth
```text
Simulation Test
```
### AgentWorld Simulated
```text
Simulation Test
```
---
## Command 4: `cd /home/user/project && cat missing_file.txt`
**AgentWorld Reasoning Cost:** ~324 tokens

### Ground Truth
```text
cat: missing_file.txt: No such file or directory
```
### AgentWorld Simulated
```text
cat: missing_file.txt: No such file or directory
```
---
## Command 5: `cd /home/user/project && grep 'Test' test.py | wc -l`
**AgentWorld Reasoning Cost:** ~460 tokens

### Ground Truth
```text
1
```
### AgentWorld Simulated
```text
1
```
---
