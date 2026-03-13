#!/usr/bin/env python3
'''
SearXNG Web Search Tool

Implements web search via the SearXNG instance running on G14.

Trust Tier: 0 (Full Autonomy, read-only)
'''

import logging
from typing import Dict, List, Any
import aiohttp

from tools import Tool, ToolParameter, TrustTier


logger = logging.getLogger(__name__)


# SearXNG service URL (on G14 auxiliary node)
SEARXNG_URL = 'http://g14:8888'


async def search_web(
    query: str,
    num_results: int = 5
) -> Dict[str, Any]:
    '''
    Search the web using SearXNG

    Args:
        query: Search query string
        num_results: Number of results to return (default 5, max 10)

    Returns:
        Dictionary with search results
    '''
    # Clamp num_results
    num_results = max(1, min(num_results, 10))

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f'{SEARXNG_URL}/search',
                params={
                    'q': query,
                    'format': 'json',
                    'pageno': 1
                }
            ) as response:
                if response.status != 200:
                    logger.error(
                        f'SearXNG returned status {response.status}'
                    )
                    return {
                        'query': query,
                        'results': [],
                        'error': f'HTTP {response.status}'
                    }

                data = await response.json()

                # Extract results
                raw_results = data.get('results', [])
                results = []

                for item in raw_results[:num_results]:
                    results.append({
                        'title': item.get('title', ''),
                        'url': item.get('url', ''),
                        'content': item.get('content', ''),
                        'engine': item.get('engine', '')
                    })

                logger.info(
                    f'SearXNG search: "{query}" '
                    f'returned {len(results)} results'
                )

                return {
                    'query': query,
                    'num_results': len(results),
                    'results': results
                }

    except Exception as e:
        logger.error(f'SearXNG search failed: {e}', exc_info=True)
        return {
            'query': query,
            'results': [],
            'error': str(e)
        }


# Tool definition
searxng_tool = Tool(
    name='web_search',
    description=(
        'Search the web using SearXNG. '
        'Returns titles, URLs, and snippets from search results. '
        'Use this for current events, factual lookups, or research.'
    ),
    parameters=[
        ToolParameter(
            name='query',
            type='string',
            description='The search query',
            required=True
        ),
        ToolParameter(
            name='num_results',
            type='integer',
            description='Number of results to return (1-10)',
            required=False,
            default=5
        )
    ],
    trust_tier=TrustTier.TIER_0,  # Read-only, safe
    enabled=True
)
