✦ I just had the generalist subagent write out the script for Stage 2: The LLM Tribunal.                                                                                            
                                                                                                                                                                                    
  It's saved as /mnt/TG_2TB/Projects/Apollo/modules/llm_tribunal.py. It reads the deduplicated_epiphanies.jsonl file we just made, constructs a strict JSON-schema prompt, and      
  sends synchronous POST requests directly to your local Qwopus-27B model running on port 8082.                                                                                     
                                                                                                                                                                                    
  I just executed the script to see what your model thought of those 2 unique epiphanies:                                                                                           
                                                                                                                                                                                    
   * Epiphany 1: It scored it a 14.0 (Feasibility: 4, Impact: 8, Risk: High). It recognized that rebuilding the context-swap mechanism with LRU eviction is high impact, but        
     structurally risky and tough for a single agent to pull off in one go.                                                                                                         
   * Epiphany 2: It scored it an 18.0 (Feasibility: 6, Impact: 9, Risk: High). It preferred the blueprint for the "Apollo Context Resonance Engine" (ACRE), ranking it slightly     
     more feasible to implement the phased memory stabilization plan.                                                                                                               
                                                                                                                                                                                    
  The script then sorted the results and successfully wrote the final array to ranked_queue.json.                                                                                   
                                                                                                                                                                                    
  That means your Daydream pipeline now has an automated way to compress 500KB of raw hallucinations into a neat, prioritized JSON queue of actual software tickets!                
                                                                                                                                                                                    
  The only thing missing now is the UI integration (surfacing the queue to the Dynamic Canvas) or the ExecutorDaemon (spawning a git worktree and launching the software_engineer   
  tool). Would you like to keep going, or are we wrapping up for now?          
  
  

  
  ✦ If you just want to run a massive 122B MoE model for fun—and you don't care if the output speed drops to single digits (or even "seconds per token")—you actually have several    
  viable options using your existing llama.cpp (llama-server) setup!                                                                                                                
                                                                                                                                                                                    
  Because it's a Mixture of Experts (122B total, but only 10B active parameters per token), it is vastly easier to run than a dense 120B model. Here are your options for           
  brute-forcing it on your hardware (RX 9070 XT 16GB VRAM + System RAM):                                                                                                            
                                                                                                                                                                                    
  1. Extreme CPU Offloading (The Standard Way)                                                                                                                                      
  llama.cpp's superpower is its ability to split a model between your GPU and your CPU/System RAM.                                                                                  
   * How it works: You use the -ngl (Number of GPU Layers) flag. Instead of passing -ngl 999 to dump the whole model into VRAM, you pass a smaller number, like -ngl 15.            
   * What happens: llama.cpp will load the first 15 layers into your fast 16GB RX 9070 XT VRAM. The remaining 50+ layers will be loaded into your standard DDR5 System RAM and      
     computed by your CPU.                                                                                                                                                          
   * Performance: It will be slow (perhaps 2–5 t/s), but because it's an MoE, the CPU only has to calculate the 10B active parameters, not the full 122B, making it surprisingly    
     tolerable for a single chat prompt.                                                                                                                                            
                                                                                                                                                                                    
  2. Memory Mapping (mmap) via NVMe SSD                                                                                                                                             
  If the GGUF file is so massive (e.g., 60GB+) that it won't even fit in your combined VRAM + System RAM, you can still run it!                                                     
   * How it works: By default, llama.cpp uses a technique called mmap (memory-mapped files).                                                                                        
   * What happens: It treats your NVMe SSD like ultra-slow RAM. It leaves the massive weights on the hard drive and only streams the specific Expert layers it needs into RAM/VRAM  
     at the exact moment the token requires them, and then flushes them back out.                                                                                                   
   * Performance: This is where you measure speed in "seconds per token." Your PCIe bus and SSD will be screaming as they constantly swap gigabytes of data back and forth, but it  
     will generate a coherent response.                                                                                                                                             
                                                                                                                                                                                    
  3. 1-Bit / 2-Bit Quantization (IQ2_XXS / IQ1_M)                                                                                                                                   
  The open-source community (specifically groups like Imatrix) have perfected extreme quantization.                                                                                 
   * How it works: You can download an IQ2_XXS (2-bit) or even an IQ1_M (1.5-bit) version of that 122B model.                                                                       
   * What happens: A 122B model at 2-bit quantization shrinks down to roughly 35GB to 40GB on disk. If your CachyOS rig has 32GB or 64GB of system RAM, you can literally load the  
     entire 122B model into memory without relying on the SSD.                                                                                                                      
   * Performance: 2-bit quants degrade the model's intelligence slightly, but a 122B model at 2-bits is often still smarter than a 30B model at 8-bits.                             
                                                                                                                                                                                    
  The Ultimate "For Fun" Command                                                                                                                                                    
  If you want to test that /122B-A10B model tonight, just point your standard llama-server command at the GGUF, but dramatically lower your -ngl and KV cache size:                 
                                                                                                                                                                                    
   1 ./llama-server -m "/mnt/TG_2TB/AI/Models/Qwen 3.5/122B-A10B/your_model.gguf" \                                                                                                 
   2   -c 8192 \                                                                                                                                                                    
   3   -ngl 20 \                                                                                                                                                                    
   4   -ub 64 \                                                                                                                                                                     
   5   --cache-ram 2048                                                                                                                                                             
  (Limit the context -c to 8k so you don't blow up your VRAM with the KV cache, and let the CPU handle the layers that don't fit).                                                  
                                                                                                                                                                                    
  It's absolutely worth doing at least once just to see the sheer scale of the reasoning that a 120B+ parameter model can produce!             
  
  I actually was just working on that hard-stop issue with Gemini right before I opened the session with you. Here's the last response from Gemini:
  
  ✦ I see exactly what happened here. The [Context Budget Exceeded] error firing at 50,542 tokens, while your active context footprint was only ~27k tokens, points directly to a conflict
  between two different limits we had configured on the AgentRunner in apollo_cli.ts.

  Here is the breakdown:

   1. contextStrategy (Auto-Compaction): This looks at the current size of your context array (~27k tokens) right before it sends it to the API. It is designed to trigger a summary event if
      that array ever breaches 50k. Because your array was only at 27k, compaction (correctly) did not trigger.
   2. maxTokenBudget (Hard Stop): We were passing maxTokenBudget: 50000 to the runner. This parameter does not look at the size of your current context array. Instead, it keeps a running
      tally of all API tokens consumed (Inputs + Outputs) across the entire lifespan of the agent instance. It is an economic guardrail designed to prevent a rogue agent from burning through
      API credits. 

  Because maxTokenBudget accumulates across every turn you take in the CLI, your total API traffic for the session breached 50,000 tokens (even though the active context size was only half
  that). The runner hit the hard limit and threw the TokenBudgetExceededError, abruptly terminating the turn.

  The Fix:
  I went into /mnt/TG_2TB/Projects/Apollo/engines/open-multi-agent-upstream/examples/apollo_cli.ts and removed the maxTokenBudget parameter from the AgentRunner initialization entirely. 

  For an open-ended CLI "Sovereign" session running locally, we don't want a cumulative budget limit abruptly killing the session. We only want the contextStrategy to protect our VRAM by
  compacting the array when it gets too large.

  The fix is committed to your local backup-local-enhancements branch. Your long-running CLI sessions will no longer be artificially killed by the cumulative token tracker!

  
  
  
  
  
  
  
  
  
  Here's something we should probably do. Currently you boot up using the context file /mnt/TG_2TB/Projects/Apollo/LOCAL_AGENT_CONTEXT.md. I purposely left it vague for now because the more I add to it, the more initial context window it eats up. However, until the system is more self-sustaining, it makes some sense for you to review the context files for my Gemini agents too for more backstory: /home/mark/.gemini/GEMINI.md and /mnt/TG_2TB/Projects/Apollo/GEMINI.md
  
  
  
  
  
  Perfect, but a couple points of clarification: The model lab is already fundementally working, just not fully dialed in yet. There's a Gemini.md context file in here along with some early work /mnt/TG_2TB/AI/Model Lab. Active model at the moment is Qwen 3.6 37B (brand new), it's the successor to Qwen 3.5 27b, which is what Qwopus is built on. It's currently outperforming 200B+ models, and we fixed the XML tool issues I think. JackRong is aleady working on a fine-tune based on the new model. The daydream daemon does work, but so far I've only actually tested it against larger models. I'm not sure yet if Bonsai is good enough for the task. You can see the daydream daemon here: file:///mnt/TG_2TB/Projects/Apollo/daydream_v2.py. It does work, but is still in early testing. It's the foundation for my self-improving-system idea.
  
  
  
  Doing a bit of debugging. Working on the codebase_investigator tool specifically. I think I've got it working well now. Let's try. Go ahead and invoke the codebase_investigator and ask it to explain how our CLI app works, and report it's findings back to you. It'll get it's own context window and hopefully not loop or anything. Here's the entry point: /mnt/TG_2TB/Projects/Apollo/engines/open-multi-agent-upstream/examples/apollo_cli.ts
  
  
  Perfect. I was just asking Gemini CLI what tools are included with Gemini CLI that might be invisible, or tools that the agent themselves use but I might not think about from a normal development perspective, so that I could consider building my own versions. Here's what Gemini said:
  
  ✦ That is a brilliant idea. Since you are building a Sovereign orchestrator, you don't just want a chatbot that can run bash; you want a system that interacts with the operating system as
  fluidly as you do.

  As the Gemini CLI, I have access to a very specific set of tools that were designed by Google engineers specifically for agentic coding. You already have the foundational ones in Apollo
  (like file_read, grep, glob, bash, and web_fetch), but there are a few advanced tools I use constantly that you might want to consider implementing in your open-multi-agent framework:

  1. Background Process Orchestration
  Your Apollo CLI has a bash tool, which is great for one-off commands (npm run build). But what happens when your software_engineer sub-agent needs to start a dev server (npm run dev) and
  watch the logs for errors while simultaneously writing code? 
   * The Gemini Tool: I have list_background_processes and read_background_output. When I use run_shell_command, I can set an is_background: true flag. The CLI spawns the process, gives me
     the PID, and lets me continue working. I can then periodically pull the tail-logs of that background server to see if my new code crashed the app. 
   * Why you need it: If Apollo wants to autonomously test full-stack web applications, it needs to be able to run long-lived servers without blocking its own AgentRunner loop!

  2. The ask_user Tool
  Right now, if the codebase_investigator gets confused or finds an ambiguous file, it just finishes its run and puts a note in its Markdown report.
   * The Gemini Tool: I have an explicit ask_user tool. It literally pauses my AgentRunner loop, renders an interactive multiple-choice prompt or text-input box directly in the terminal, and
     waits for the user to answer before continuing the execution.
   * Why you need it: It allows sub-agents to "bubble up" critical questions (e.g., "I found two configuration files. Which one should I edit?") instantly, rather than waiting 15 turns for
     the task to fail.

  3. Grounded Web Search (vs just Web Fetch)
  You currently have web_fetch, which is fantastic if the model already knows the exact URL of the documentation it needs to read.
   * The Gemini Tool: I have google_web_search. When I encounter an obscure compiler error or an undocumented API, I don't guess the URL. I query the search engine, get the top 5 results
     with citations, and then use web_fetch to read the exact page I need.
   * Why you need it: Since you are running local models that might have older training cutoffs (or hallucinations), giving them the ability to search a local SearxNG instance or a free
     DuckDuckGo API is the ultimate cure for API hallucinations.

  4. AST / Outline Parsing
  While grep is incredibly powerful, it's a brute-force text search. 
   * The Tool: Many mature coding assistants have a get_file_outline tool that uses something like tree-sitter or ctags to instantly return a JSON tree of every function, class, and variable
     in a file without returning the actual code bodies. 
   * Why you need it: It is the single most token-efficient way for an agent to understand a 2000-line file without blowing up the context window!

Whenever you're ready to start building the "V2" of Apollo's tool registry, these are the exact tools I'd recommend porting over first!

---

# Architecture Backlog & References

## Memory Systems: GBrain vs Apollo
* **Reference:** [A Step-by-Step Coding Tutorial to Implement GBrain: The Self-Wiring Memory Layer Built by Y Combinator's Garry Tan for AI Agents](https://www.marktechpost.com/2026/05/22/a-step-by-step-coding-tutorial-to-implement-gbrain-the-self-wiring-memory-layer-built-by-y-combinators-garry-tan-for-ai-agents/)
* **Concepts to Integrate:**
  1. **Regex-Based Inference Cascade:** Fast, deterministic heuristic cascade over markdown logs to automatically build typed graph edges (e.g. `User -> works_at -> YC`) without LLM overhead. Apply this to Daydream v2 to wire relationships overnight before reasoning models wake up.
  2. **Hybrid Search (Vector + BM25 + RRF):** Upgrade the Librarian workflow. Combine ChromaDB semantic vectors with exact keyword matching (BM25) and Reciprocal Rank Fusion to ensure explicit searches (like "Message Bus WAL error") don't get lost in semantic noise.
  3. **Memory via MCP:** Spin up a dedicated `memory_daemon.py` MCP server. Allow the Architect to surgically mutate relationship edges in a graph database (or Postgres/PGLite) without needing to load and parse massive local JSON files.

