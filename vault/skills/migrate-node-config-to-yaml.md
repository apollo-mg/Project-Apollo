---
name: migrate-node-config-to-yaml
description: Migrate Node.js configuration files from JSON to YAML. Use when you need to add comments, multi-line strings, or improve human-readability for complex agent profile configurations.
---

# Migrating Node.js Configs to YAML

YAML is preferred over JSON for complex configuration files (like agent profiles) because it supports comments, true multi-line strings, and is less sensitive to minor syntax errors like trailing commas.

## Migration Procedure

Follow these steps to transition a configuration file from `.json` to `.yaml`.

### 1. Install Dependencies
Install a YAML parser into your project directory.

```bash
npm install yaml
# OR
npm install js-yaml
```

### 2. Automatic Data Conversion
Use a one-off Node.js command to convert the existing JSON data to YAML format to ensure no data is lost.

```bash
node -e "const fs = require('fs'); const yaml = require('yaml'); const json = JSON.parse(fs.readFileSync('config.json', 'utf8')); fs.writeFileSync('config.yaml', yaml.stringify(json));"
```

### 3. Update Source Code
Refactor your configuration loader to use the new parser and file path.

**Before (JSON):**
```typescript
import * as fs from 'fs'
const config = JSON.parse(fs.readFileSync('config.json', 'utf-8'))
```

**After (YAML):**
```typescript
import * as fs from 'fs'
import YAML from 'yaml'
const config = YAML.parse(fs.readFileSync('config.yaml', 'utf-8'))
```

### 4. Cleanup
Remove the old JSON file and update any `.gitignore` or documentation references.

```bash
rm config.json
```

## Benefits for Agents

- **Comments**: Use `#` to document sampling parameters (e.g. `# temp 0 for deterministic coding`).
- **Multi-line Blocks**: Use the `|` operator for system prompts to avoid `\n` character clutter.
- **Robustness**: White-space based syntax prevents CLI crashes caused by missing commas or brackets.

## Pitfalls & Verification

- **NPM Pruning**: In some environments, running `npm install <package>` may prune existing peer dependencies. Verify your `node_modules` and run a full `npm install` if imports fail after migration.
- **Type Safety**: Ensure your TypeScript interfaces accurately reflect the YAML structure, which is identical to the original JSON.
- **Pathing**: Double-check all instances where the config path is hardcoded (e.g. absolute paths vs relative paths in dev/prod).
