#!/usr/bin/env python3
'''
Babs Tool Framework

MCP-compatible tool system with Trust Tier enforcement.

Trust Tiers (from babs-design-philosophy-v1_5.md Section 2):
- Tier 0: Full Autonomy (read-only, no approval needed)
- Tier 1: Notify and Execute (acts immediately, logs after)
- Tier 2: Propose and Wait (requires explicit approval)
- Tier 3: Confirm Twice (high-stakes gate, no timeout)
'''

import logging
from enum import IntEnum
from typing import Any, Callable, Dict, List, Optional
from pydantic import BaseModel, Field


logger = logging.getLogger(__name__)


class TrustTier(IntEnum):
    '''Trust tier levels for tool execution'''
    TIER_0 = 0  # Full autonomy, no approval
    TIER_1 = 1  # Notify and execute
    TIER_2 = 2  # Propose and wait (30min timeout)
    TIER_3 = 3  # Confirm twice (no timeout)


class ToolParameter(BaseModel):
    '''Tool parameter definition'''
    name: str
    type: str  # 'string', 'integer', 'boolean', 'object', 'array'
    description: str
    required: bool = True
    default: Optional[Any] = None


class Tool(BaseModel):
    '''Tool definition compatible with MCP and OpenAI function calling'''
    name: str
    description: str
    parameters: List[ToolParameter]
    trust_tier: TrustTier
    enabled: bool = True

    def to_openai_schema(self) -> Dict[str, Any]:
        '''Convert to OpenAI function calling schema'''
        properties = {}
        required = []

        for param in self.parameters:
            properties[param.name] = {
                'type': param.type,
                'description': param.description
            }
            if param.default is not None:
                properties[param.name]['default'] = param.default
            if param.required:
                required.append(param.name)

        return {
            'type': 'function',
            'function': {
                'name': self.name,
                'description': self.description,
                'parameters': {
                    'type': 'object',
                    'properties': properties,
                    'required': required
                }
            }
        }


class ToolResult(BaseModel):
    '''Result of tool execution'''
    tool_name: str
    success: bool
    result: Any
    error: Optional[str] = None
    trust_tier: TrustTier
    approved: bool = False  # For Tier 2/3, was this approved?
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ToolRegistry:
    '''Registry of available tools with execution handlers'''

    def __init__(self):
        self.tools: Dict[str, Tool] = {}
        self.handlers: Dict[str, Callable] = {}

    def register(
        self,
        tool: Tool,
        handler: Callable
    ):
        '''Register a tool with its execution handler'''
        self.tools[tool.name] = tool
        self.handlers[tool.name] = handler
        logger.info(
            f'Registered tool: {tool.name} '
            f'(Tier {tool.trust_tier.value})'
        )

    def get_tool(self, name: str) -> Optional[Tool]:
        '''Get tool definition by name'''
        return self.tools.get(name)

    def get_enabled_tools(self) -> List[Tool]:
        '''Get all enabled tools'''
        return [t for t in self.tools.values() if t.enabled]

    def get_tools_for_vllm(self) -> List[Dict[str, Any]]:
        '''Get OpenAI-compatible tool schemas for vLLM'''
        return [
            tool.to_openai_schema()
            for tool in self.get_enabled_tools()
        ]

    async def execute(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        approved: bool = False
    ) -> ToolResult:
        '''
        Execute a tool with Trust Tier enforcement

        Args:
            tool_name: Name of the tool to execute
            arguments: Tool arguments
            approved: For Tier 2/3, has this been approved by phloid?

        Returns:
            ToolResult with execution outcome
        '''
        tool = self.get_tool(tool_name)
        if not tool:
            return ToolResult(
                tool_name=tool_name,
                success=False,
                result=None,
                error=f'Tool not found: {tool_name}',
                trust_tier=TrustTier.TIER_0
            )

        if not tool.enabled:
            return ToolResult(
                tool_name=tool_name,
                success=False,
                result=None,
                error=f'Tool is disabled: {tool_name}',
                trust_tier=tool.trust_tier
            )

        # Trust Tier enforcement
        if tool.trust_tier >= TrustTier.TIER_2 and not approved:
            # Tier 2/3 requires approval
            logger.warning(
                f'Tool {tool_name} (Tier {tool.trust_tier.value}) '
                f'requires approval but was not approved'
            )
            return ToolResult(
                tool_name=tool_name,
                success=False,
                result=None,
                error='Approval required for this tool',
                trust_tier=tool.trust_tier,
                approved=False
            )

        # Execute the tool
        handler = self.handlers.get(tool_name)
        if not handler:
            return ToolResult(
                tool_name=tool_name,
                success=False,
                result=None,
                error=f'No handler registered for tool: {tool_name}',
                trust_tier=tool.trust_tier
            )

        try:
            logger.info(
                f'Executing tool: {tool_name} '
                f'(Tier {tool.trust_tier.value})'
            )
            result = await handler(**arguments)

            return ToolResult(
                tool_name=tool_name,
                success=True,
                result=result,
                trust_tier=tool.trust_tier,
                approved=approved
            )

        except Exception as e:
            logger.error(
                f'Tool execution failed: {tool_name}',
                exc_info=True
            )
            return ToolResult(
                tool_name=tool_name,
                success=False,
                result=None,
                error=str(e),
                trust_tier=tool.trust_tier,
                approved=approved
            )
