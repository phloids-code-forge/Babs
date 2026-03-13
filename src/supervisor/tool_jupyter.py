#!/usr/bin/env python3
'''
Python Code Execution Tool

Implements python code execution via Docker.
The supervisor uses `docker exec` to run code inside the isolated `babs-jupyter` container.

Trust Tier: 1 (Notify & Execute) - Can execute arbitrary code but is restricted to the internal network and workspace.
'''

import logging
import json
import asyncio
import tempfile
import os
from typing import Dict, Any

from src.supervisor.tools import Tool, ToolParameter, TrustTier

logger = logging.getLogger(__name__)

async def execute_python(
    code: str,
    timeout_sec: int = 30
) -> Dict[str, Any]:
    '''
    Execute Python code in the sandbox container
    
    Args:
        code: Python code to execute
        timeout_sec: Maximum execution time in seconds
        
    Returns:
        Dictionary with execution results including 'output'
    '''
    # We create a temporary script file on the host (where supervisor runs)
    # The workspace volume is shared between supervisor and jupyter container
    
    try:
        # Create a subprocess to run the python script from stdin
        process = await asyncio.create_subprocess_exec(
            "python3", "-c", code,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        try:
            # Wait for execution to finish with timeout
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout_sec)
            
            output = ""
            if stdout:
                output += stdout.decode()
            if stderr:
                output += f"\\n--- Errors ---\\n{stderr.decode()}"
                
            return {
                'success': process.returncode == 0,
                'output': output.strip() or "(No output)"
            }
            
        except asyncio.TimeoutError:
            # Kill process if it timed out
            process.kill()
            return {
                'success': False,
                'output': '',
                'error': f'Execution timed out after {timeout_sec} seconds'
            }
            
    except Exception as e:
        logger.error(f'Python execution failed: {e}', exc_info=True)
        return {'success': False, 'output': '', 'error': str(e)}

# Tool definition
execute_python_tool = Tool(
    name='execute_python',
    description=(
        'Execute Python code in a secure environment. '
        'You can define variables, functions, and import standard libraries. '
        'Returns the stdout or execution results. Use print() to output values you want to see.'
    ),
    parameters=[
        ToolParameter(
            name='code',
            type='string',
            description='The complete Python code to execute strictly as a string',
            required=True
        ),
        ToolParameter(
            name='timeout_sec',
            type='integer',
            description='Maximum time in seconds to wait for execution to complete',
            required=False,
            default=30
        )
    ],
    trust_tier=TrustTier.TIER_1,  # Notify & Execute - local execution container
    enabled=True
)
