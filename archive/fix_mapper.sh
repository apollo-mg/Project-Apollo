sshpass -p 'apollo' ssh -o StrictHostKeyChecking=no gemini@10.0.0.118 "sshpass -p 'apollo' ssh -o StrictHostKeyChecking=no mark@10.0.0.5 'cat > /home/mark/gemini/workspace/hardware_mapper/core/cpu.py <<\"INNER_EOF\"
import os

def get_cpu_model():
    try:
        with open(\"/proc/cpuinfo\", \"r\") as f:
            for line in f:
                if \"model name\" in line:
                    return line.split(\":\")[1].strip()
    except Exception:
        return \"Unknown CPU\"
    return \"Unknown CPU\"
INNER_EOF'"

sshpass -p 'apollo' ssh -o StrictHostKeyChecking=no gemini@10.0.0.118 "sshpass -p 'apollo' ssh -o StrictHostKeyChecking=no mark@10.0.0.5 'cat > /home/mark/gemini/workspace/hardware_mapper/core/gpu.py <<\"INNER_EOF\"
import subprocess

def get_gpu_model():
    try:
        result = subprocess.run([\"rocm-smi\"], capture_output=True, text=True)
        for line in result.stdout.split(\"\\n\"):
            if \"GPU\" in line and \"Model\" in line:
                return line.split(\":\")[1].strip()
    except Exception:
        return \"Unknown GPU\"
    return \"Unknown GPU\"
INNER_EOF'"

sshpass -p 'apollo' ssh -o StrictHostKeyChecking=no gemini@10.0.0.118 "sshpass -p 'apollo' ssh -o StrictHostKeyChecking=no mark@10.0.0.5 'cd /home/mark/gemini/workspace/hardware_mapper && /media/mark/AI_Fast/venv_apollo/bin/python3 main.py'"
