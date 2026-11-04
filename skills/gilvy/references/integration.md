# Installation and execution

The skill directory contains instructions and a small example, not the Python renderer. Copying it alone cannot install Gilvy, FFmpeg, a model or an MCP server.

Prefer the connected Gilvy MCP tools. Discover their actual names/signatures. For shell operation use the installed `gilvy` executable or its absolute virtualenv path; never assume the current directory is the repository. Input and output paths should be absolute. Assets/fonts resolve relative to their spec, while relative output paths may depend on cwd.

Core installation uses Python >=3.11 and FFmpeg/ffprobe. From an acquired repository, create a virtualenv and install the package into that environment. Optional extras are `download` (yt-dlp) and `cutout` (rembg/onnxruntime). Install extras with the same interpreter used by MCP. Cutout may download a model on first use; successful package import is not proof that the model is ready. Network-dependent TTS/downloads remain unverified until exercised.

For OpenCode use its current MCP configuration instructions. A local server command is an argument array `["/absolute/venv/bin/gilvy", "mcp"]`; no shell activation is required. `opencode mcp add gilvy --global -- /absolute/venv/bin/gilvy mcp` registers it. Check connection status; preserve unrelated configuration.

Run `gilvy doctor --json` or MCP `doctor` for read-only prerequisite discovery. It reports optional packages and model file presence separately from runtime readiness; inference remains unverified until separately exercised. On older installations without doctor, verify interpreter, FFmpeg/ffprobe, optional packages and bundled resources explicitly. Report unavailable/unverified capabilities rather than trying unsupported commands repeatedly.

Use fresh output directories for previews/analysis that require them. Keep approved source and artifact versions. Job states belong to the running process unless its documented contract says otherwise; a process restart is not an automatic resume. Never claim a queued render has completed.
