#!/bin/bash
# Sandboxed code execution entrypoint
# Reads Python code from stdin and executes it in a restricted environment
set -e

# Resource limits
ulimit -t 30        # CPU time limit (seconds)
ulimit -f 10240     # File size limit (10MB)

# Execute the Python code from stdin
python3 -c "$(cat /dev/stdin)"
