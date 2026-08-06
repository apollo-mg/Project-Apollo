✦ Moving the P100 to a closet so you don't have to listen to the fans spinning up is exactly why we built this distributed architecture! 

  To answer your question: No, you do not need to maintain the entire codebase on both drives. 

  Because we built the Agent-to-Agent (A2A) Scratchpad protocol and the FastAPI Message Bus, the P100 is essentially just "dumb muscle." It does not need the UI, the TypeScript orchestrator, the memory modules, or any of the Daydream
  logic. 

  Here is the exact checklist of the ONLY things that need to be on the P100:

   1. The LLM weights (your .gguf files).
   2. NullClaw (the compiled Zig binary).
   3. apollo_bus_mcp.py
   4. starbuck_daemon.py

  The Critical "Gotcha" Before You Reboot
  Because we just heavily patched those two Python files today (adding the "Graceful Assassin" SSE kill-switch to apollo_bus_mcp.py and the YOLO Level security checks to starbuck_daemon.py), you absolutely must synchronize these two
  new files over to the P100.

  You can do this right before you unplug it, or via scp once it's on the network in the new room:
   1 scp /mnt/TG_2TB/Projects/Apollo/apollo_bus_mcp.py user@<p100-ip>:/path/to/apollo/
   2 scp /mnt/TG_2TB/Projects/Starbuck/starbuck_daemon.py user@<p100-ip>:/path/to/starbuck/

  The Environment Variable Update
  Once the P100 is in the other room, it can no longer rely on 127.0.0.1 (localhost) to find the Brain. 

  When you boot the Daemons on the P100, you must pass the LAN IP address of your 9070 XT desktop so the worker knows where to send the SSE interrupts and task claims:

   1 # On the P100:
   2 export MESSAGE_BUS_API="http://<9070-XT-LAN-IP>:8000"
   3 export STARBUCK_YOLO_LEVEL="2"
   4
   5 # Then start the beacons and the agent
   6 python3 apollo_bus_mcp.py &
   7 python3 starbuck_daemon.py &
   8 nullclaw agent

  That's it! 95% of your codebase safely stays on your desktop. The P100 sits in a dark, quiet room, faithfully reaching out over the network to grab tasks, execute them in its sandboxes, and push the answers back to your desktop.

  Have fun relocating the server! Let me know when it's back online and if the swarm successfully reconnects across the house.


Here is a breakdown of the new architecture:

  1. What is agent-sandbox?
  It is a cutting-edge official Kubernetes subproject (under SIG Apps) explicitly designed for AI agents. 
   * Kernel Isolation: Instead of standard Linux namespaces (which Docker uses and can be escaped), it forces the pods to boot using gVisor or Kata Containers. These act like micro-VMs, providing a hard, cryptographically secure
     boundary. If an agent runs rm -rf /*, it only destroys the disposable micro-VM.
   * The Warm Pool: Spinning up a micro-VM from scratch takes 3-5 seconds. If an agent wants to call a tool, waiting 5 seconds every time would destroy our sub-millisecond UI Reflex Arc. The SandboxWarmPool keeps a predefined number of
     micro-VMs fully booted and idling in the background. When an agent claims one, it connects instantly.

  2. The Deployment Drafts
  I have successfully drafted the necessary Kubernetes manifests on your local drive at /mnt/TG_2TB/Projects/Apollo/deploy/kubernetes/:
   * sandbox-template.yaml: Tells K3s to boot our freshly built apollo-worker:latest image using the gvisor runtime class, and injects your MESSAGE_BUS_API endpoints.
   * sandbox-warmpool.yaml: Tells K3s to always keep a minimum of 2 of those workers pre-warmed and idling for instant task claims.

  I also updated your OPERATIONS.md runbook with a new "Project Starbuck Kubernetes Sandboxing" section so the Swarm boot sequence is fully documented.

  3. Execution on the P100 Node
  Since installing K3s on a bare-metal node requires root privileges (sudo), I need you to execute this installation block directly on the P100 (10.0.0.71) to securely handle the password prompt. 

  SSH into the P100 and run these exact commands:

   1 # 1. Install K3s (The lightweight Kubernetes cluster)
   2 curl -sfL https://get.k3s.io | sh -
   3
   4 # 2. Install the agent-sandbox Controller components
   5 kubectl apply -f https://github.com/kubernetes-sigs/agent-sandbox/releases/latest/download/install.yaml
   6
   7 # 3. Apply our Swarm Manifests (You can run this from your 9070 XT desktop or copy the files over)
   8 kubectl apply -f deploy/kubernetes/sandbox-template.yaml
   9 kubectl apply -f deploy/kubernetes/sandbox-warmpool.yaml

  Once those commands execute, the P100 will spin up the controller and your first two isolated apollo-worker micro-VMs will boot up and connect to the Message Bus. Let me know when K3s is installed!
