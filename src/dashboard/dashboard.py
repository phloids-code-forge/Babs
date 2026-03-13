#!/usr/bin/env python3
'''
Babs Dashboard Backend

FastAPI server providing:
- Chat interface (NATS pub/sub to Supervisor)
- Service health monitoring
- System status
- Approval queue (future)
'''

import asyncio
import json
import logging
import os
from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import uuid4

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
import nats
from nats.aio.client import Client as NATSClient


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Configuration
NATS_URL = os.getenv('NATS_URL', 'nats://localhost:4222')
USER_ID = os.getenv('USER_ID', 'phloid')


# Pydantic models
class ChatMessage(BaseModel):
    '''Chat message from user'''
    content: str
    thread_id: Optional[str] = None


class ServiceStatus(BaseModel):
    '''Service health status'''
    name: str
    status: str  # 'running', 'stopped', 'unknown'
    uptime: Optional[str] = None
    details: Optional[str] = None


# FastAPI app
app = FastAPI(title='Babs Dashboard')


# Global NATS connection
nc: Optional[NATSClient] = None


@app.on_event('startup')
async def startup_event():
    '''Connect to NATS on startup'''
    global nc
    logger.info(f'Connecting to NATS at {NATS_URL}')
    nc = await nats.connect(NATS_URL)
    logger.info('Dashboard connected to NATS')


@app.on_event('shutdown')
async def shutdown_event():
    '''Disconnect from NATS on shutdown'''
    global nc
    if nc:
        await nc.drain()
        logger.info('Dashboard disconnected from NATS')


@app.get('/')
async def root():
    '''Serve dashboard UI'''
    return FileResponse('static/index.html')


@app.get('/api/health')
async def health():
    '''Health check endpoint'''
    return {
        'status': 'healthy',
        'nats_connected': nc is not None and nc.is_connected,
        'timestamp': datetime.utcnow().isoformat()
    }


@app.get('/api/services')
async def get_services() -> List[ServiceStatus]:
    '''Get status of all Babs services'''
    # TODO: Query actual service health via docker API or health endpoints
    # For now, return mock data
    services = [
        ServiceStatus(
            name='vLLM (Nemotron 3 Nano)',
            status='running',
            details='Port 8000, 65+ tok/s'
        ),
        ServiceStatus(
            name='Supervisor',
            status='running',
            details='Connected to NATS, vLLM, Qdrant, G14'
        ),
        ServiceStatus(
            name='NATS',
            status='running',
            details='JetStream enabled'
        ),
        ServiceStatus(
            name='Qdrant',
            status='running',
            details='Procedural Memory: 5 entries'
        ),
        ServiceStatus(
            name='SearXNG (G14)',
            status='running',
            details='Web search enabled'
        ),
        ServiceStatus(
            name='Embedding (G14)',
            status='running',
            details='nomic-embed-text-v1.5, 768-dim'
        )
    ]
    return services


@app.post('/api/chat')
async def send_message(message: ChatMessage) -> Dict[str, Any]:
    '''
    Send a message to Babs via NATS

    Returns the response from the Supervisor
    '''
    if not nc or not nc.is_connected:
        raise HTTPException(status_code=503, detail='NATS not connected')

    # Generate thread ID if not provided
    thread_id = message.thread_id or str(uuid4())

    # Build message for Supervisor
    supervisor_message = {
        'content': message.content,
        'thread_id': thread_id,
        'user_id': USER_ID
    }

    try:
        logger.info(f'Sending message to Supervisor: {message.content[:50]}...')

        # Send request to Supervisor via NATS
        response = await nc.request(
            'supervisor.request',
            json.dumps(supervisor_message).encode(),
            timeout=60
        )

        # Parse response
        response_data = json.loads(response.data.decode())

        logger.info(f'Received response from Supervisor')

        return {
            'success': True,
            'thread_id': response_data.get('thread_id'),
            'content': response_data.get('content'),
            'model': response_data.get('model'),
            'metadata': response_data.get('metadata', {})
        }

    except asyncio.TimeoutError:
        logger.error('Supervisor request timed out')
        raise HTTPException(status_code=504, detail='Request timed out')
    except Exception as e:
        logger.error(f'Error sending message: {e}', exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.websocket('/ws/chat')
async def websocket_chat(websocket: WebSocket):
    '''
    WebSocket endpoint for real-time chat

    Future: Streaming responses, live updates
    '''
    await websocket.accept()
    logger.info('WebSocket connection established')

    try:
        while True:
            # Receive message from client
            data = await websocket.receive_text()
            message_data = json.loads(data)

            # Send to Supervisor
            message = ChatMessage(**message_data)
            response = await send_message(message)

            # Send response back to client
            await websocket.send_json(response)

    except WebSocketDisconnect:
        logger.info('WebSocket connection closed')
    except Exception as e:
        logger.error(f'WebSocket error: {e}', exc_info=True)
        await websocket.close()


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(
        'dashboard:app',
        host='0.0.0.0',
        port=3000,
        reload=True
    )
