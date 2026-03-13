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

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
import nats
from nats.aio.client import Client as NATSClient

# Model registry and OpenRouter integration
import sys
sys.path.insert(0, '/home/dave/babs')
from src.supervisor.model_registry import ModelRegistry
from src.supervisor.openrouter import OpenRouterClient, CostTracker


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


class ModelSelectRequest(BaseModel):
    '''Request to switch active model'''
    model_id: str


class ModelDownloadRequest(BaseModel):
    '''Request to download a model'''
    model_id: str
    quantization: Optional[str] = None
    bandwidth_limit_mbps: int = 50


# FastAPI app
app = FastAPI(title='Babs Dashboard')

# Mount static files directory
app.mount("/static", StaticFiles(directory="static"), name="static")

# Global NATS connection
nc: Optional[NATSClient] = None

# Global model registry and cost tracker
model_registry: Optional[ModelRegistry] = None
cost_tracker: Optional[CostTracker] = None
active_model_id: str = "local/nemotron3-nano"  # Default to Nano


@app.on_event('startup')
async def startup_event():
    '''Connect to NATS and initialize model registry on startup'''
    global nc, model_registry, cost_tracker

    # Connect to NATS
    logger.info(f'Connecting to NATS at {NATS_URL}')
    nc = await nats.connect(NATS_URL)
    logger.info('Dashboard connected to NATS')

    # Initialize model registry
    logger.info('Initializing model registry')
    models_dir = os.getenv('MODELS_DIR', '~/babs-data/models')
    cache_file = os.getenv('CACHE_FILE', '~/babs/config/model_registry.json')
    model_registry = ModelRegistry(models_dir=models_dir, cache_file=cache_file)

    # Try to load from cache first
    if model_registry.load_from_cache():
        logger.info('Loaded model registry from cache')
    else:
        # Scan fresh if no cache
        logger.info('Scanning models (no cache found)')
        model_registry.list_all()
        model_registry.save_to_cache()

    # Initialize cost tracker
    budget_limit = float(os.getenv('COST_BUDGET_LIMIT_THRESHOLD', '20.0'))
    budget_warning = float(os.getenv('COST_BUDGET_WARNING_THRESHOLD', '5.0'))
    cost_tracker = CostTracker(budget_limit=budget_limit, warning_threshold=budget_warning)
    logger.info(f'Cost tracker initialized (limit: ${budget_limit}, warning: ${budget_warning})')


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


@app.post('/api/upload')
async def upload_files(files: List[UploadFile] = File(...)):
    """Upload files and return their saved paths"""
    upload_dir = os.path.expanduser('~/babs-data/uploads')
    os.makedirs(upload_dir, exist_ok=True)
    
    saved_paths = []
    for file in files:
        file_path = os.path.join(upload_dir, file.filename)
        # Handle duplicate filenames
        base, ext = os.path.splitext(file.filename)
        counter = 1
        while os.path.exists(file_path):
            file_path = os.path.join(upload_dir, f"{base}_{counter}{ext}")
            counter += 1
            
        content = await file.read()
        with open(file_path, 'wb') as f:
            f.write(content)
        saved_paths.append(file_path)
        
    return {"paths": saved_paths}


@app.websocket('/ws/thinking')
async def websocket_thinking(websocket: WebSocket):
    """
    WebSocket endpoint for real-time thinking events from Supervisor
    """
    await websocket.accept()
    logger.info('WebSocket thinking connection established')
    
    if not nc or not nc.is_connected:
        await websocket.close()
        return

    async def msg_handler(msg):
        try:
            data = json.loads(msg.data.decode())
            await websocket.send_json(data)
        except Exception as e:
            logger.error(f'Error pushing thinking event to ws: {e}')

    try:
        sub = await nc.subscribe("supervisor.thinking", cb=msg_handler)
        while True:
            # Keep connection alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        logger.info('WebSocket thinking connection closed')
    except Exception as e:
        logger.error(f'WebSocket thinking error: {e}')
    finally:
        try:
            await sub.unsubscribe()
        except Exception:
            pass


@app.websocket('/ws/artifacts')
async def websocket_artifacts(websocket: WebSocket):
    """
    WebSocket endpoint for real-time artifacts stream from Supervisor
    """
    await websocket.accept()
    logger.info('WebSocket artifacts connection established')
    
    if not nc or not nc.is_connected:
        await websocket.close()
        return

    async def msg_handler(msg):
        try:
            data = json.loads(msg.data.decode())
            await websocket.send_json(data)
        except Exception as e:
            logger.error(f'Error pushing artifact event to ws: {e}')

    try:
        sub = await nc.subscribe("supervisor.artifact", cb=msg_handler)
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        logger.info('WebSocket artifacts connection closed')
    except Exception as e:
        logger.error(f'WebSocket artifacts error: {e}')
    finally:
        try:
            await sub.unsubscribe()
        except Exception:
            pass


@app.get('/api/models/list')
async def list_models(refresh: bool = False) -> Dict[str, Any]:
    '''
    Get all available models (local + OpenRouter)

    Args:
        refresh: Force refresh of OpenRouter catalog

    Returns:
        Dict with "local" and "openrouter" model lists
    '''
    if not model_registry:
        raise HTTPException(status_code=503, detail='Model registry not initialized')

    try:
        models = model_registry.list_all(refresh_openrouter=refresh)

        # Convert Model objects to dicts
        return {
            'local': [vars(m) for m in models['local']],
            'openrouter': [vars(m) for m in models['openrouter']],
            'active_model_id': active_model_id
        }
    except Exception as e:
        logger.error(f'Error listing models: {e}', exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post('/api/model/select')
async def select_model(request: ModelSelectRequest) -> Dict[str, Any]:
    '''
    Switch the active model

    Publishes model switch request to NATS supervisor.model_switch
    '''
    global active_model_id

    if not model_registry:
        raise HTTPException(status_code=503, detail='Model registry not initialized')

    if not nc or not nc.is_connected:
        raise HTTPException(status_code=503, detail='NATS not connected')

    # Verify model exists
    model = model_registry.get_model(request.model_id)
    if not model:
        raise HTTPException(status_code=404, detail=f'Model not found: {request.model_id}')

    # Check if model can be loaded (memory constraints)
    if model.source == 'local':
        can_load = model_registry.can_load_model(request.model_id)
        if not can_load['can_load']:
            raise HTTPException(status_code=400, detail=can_load['reason'])

    try:
        # Publish model switch request to Supervisor
        switch_message = {
            'model_id': request.model_id,
            'timestamp': datetime.utcnow().isoformat()
        }

        await nc.publish(
            'supervisor.model_switch',
            json.dumps(switch_message).encode()
        )

        # Update active model (optimistic)
        active_model_id = request.model_id

        logger.info(f'Switched active model to: {request.model_id}')

        # Determine restrictions based on trust tier
        restrictions = []
        if model.trust_tier >= 2:
            restrictions.extend(['no_file_write', 'no_system_commands'])
        if model.trust_tier >= 3:
            restrictions.extend(['no_code_execution', 'no_procedural_memory_write'])

        return {
            'success': True,
            'active_model': request.model_id,
            'trust_tier': model.trust_tier,
            'restrictions': restrictions,
            'source': model.source
        }

    except Exception as e:
        logger.error(f'Error switching model: {e}', exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get('/api/model/active')
async def get_active_model() -> Dict[str, Any]:
    '''Get currently active model'''
    if not model_registry:
        raise HTTPException(status_code=503, detail='Model registry not initialized')

    model = model_registry.get_model(active_model_id)
    if not model:
        return {'active_model_id': active_model_id, 'details': None}

    return {
        'active_model_id': active_model_id,
        'details': vars(model)
    }


@app.get('/api/costs/session/{session_id}')
async def get_session_cost(session_id: str) -> Dict[str, Any]:
    '''Get cost summary for a session'''
    if not cost_tracker:
        raise HTTPException(status_code=503, detail='Cost tracker not initialized')

    return cost_tracker.get_session_cost(session_id)


@app.get('/api/memory/summary')
async def get_memory_summary() -> Dict[str, Any]:
    '''Get memory usage summary'''
    if not model_registry:
        raise HTTPException(status_code=503, detail='Model registry not initialized')

    return model_registry.get_memory_usage_summary()


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(
        'dashboard:app',
        host='0.0.0.0',
        port=3000,
        reload=True
    )
