Operations_2

/Apollo/generate_ard_catalog.py: 
    
    What: It automatically generates a Google ARD style macro-architecture manifes (ai_catalog.json) using Vercel EVE style micro-architecture, where an agent's capabilities are defined strictly by it's physical directory structure of tools/ and skills/.
    
    How: 
    1. Directory Traversal: It accepts a path to an Eve-style agent directory.
    2. Tools Parsing: It recurses through the  tools/  directory, grabbing  .ts  and  .py  files. It extracts the filename as the capability and uses regex to try and find the
        description: "..."  string to generate natural-language  representativeQueries .
    3. Skills Parsing: It walks through the  skills/  directory grabbing  .md  files. It pulls the filenames and parses the  # Headings  to build semantic intent queries.
    4. ARD Compilation: It compiles everything into a single  ai-catalog.json  output file located in the root of that agent's directory, formatted strictly to the ARD specification we
        just reviewed.
