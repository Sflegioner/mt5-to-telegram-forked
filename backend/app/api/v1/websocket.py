"""
WebSocket API endpoints for real-time updates.
"""
import asyncio
import json
import logging
from typing import Dict, List, Any, Optional
from uuid import uuid4
from datetime import datetime
import base64
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query, HTTPException, status
from telethon.tl.types import Message
from pydantic import BaseModel
from app.mt5 import MetaTraderService
from app.services import TelegramService, TelegramListenerService
from app.api.v1.telegram import get_telegram_service, active_sessions
from app.schemas.telegram import TelegramCredentials
from backend.app.api.v1.connection_manager import ConnectionManager

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/ws", tags=["websocket"])



# Create global connection manager
manager = ConnectionManager()

@router.websocket("/messages")
async def websocket_messages(
    websocket: WebSocket,
    client_id: Optional[str] = Query(None),
    api_id: Optional[int] = Query(None),
    api_hash: Optional[str] = Query(None),
    phone: Optional[str] = Query(None)
):
    """
    WebSocket endpoint for real-time message updates.
    
    Connect to this endpoint to receive real-time updates for Telegram messages.
    Authentication is handled through URL parameters:
    
    ```
    /v1/ws/messages?client_id=1234&api_id=12345&api_hash=abcdef&phone=+123456789
    ```
    
    After connecting, you can subscribe to dialogs:
    
    ```json
    {
        "action": "subscribe",
        "dialog_id": 123456789
    }
    ```
    
    To subscribe using dialog name instead of ID:
    ```json
    {
        "action": "subscribe_by_name",
        "dialog_name": "Dialog Name"
    }
    ```
    
    To unsubscribe:
    ```json
    {
        "action": "unsubscribe",
        "dialog_id": 123456789
    }
    ```
    
    If verification is needed:
    ```json
    {
        "action": "verify",
        "code": "12345",
        "password": "optional_2fa_password"
    }
    ```
    
    You will receive messages in this format:
    ```json
    {
        "event": "new_message",
        "dialog_id": 123456789,
        "message": {
            "id": 123,
            "text": "Message content",
            "date": "2023-07-01T12:34:56+00:00",
            "sender": {
                "id": 987654321,
                "first_name": "John",
                "last_name": "Doe",
                "username": "johndoe"
            },
            "has_media": false
        }
    }
    ```
    """
    # Generate client ID if not provided
    if not client_id:
        client_id = str(uuid4())
    
    try:
        # Accept connection and register it (accepts the connection inside the connect method)
        await manager.connect(websocket, client_id)
        
        # Send connection info
        await websocket.send_json({
            "event": "connected",
            "client_id": client_id
        })
        
        # Check if credentials were provided as URL parameters
        if api_id and api_hash:
            # Create credentials object
            credentials = TelegramCredentials(
                api_id=api_id,
                api_hash=api_hash,
                phone=phone
            )
            
            # Try to authenticate
            result = await manager.initialize_listener_service(client_id, credentials)
            
            # Send authentication result
            if result["success"]:
                await websocket.send_json({
                    "event": "authenticated",
                    "success": True
                })
            elif result.get("needs_verification", False):
                await websocket.send_json({
                    "event": "verification_needed",
                    "success": False,
                    "message": "Please provide the verification code sent to your phone"
                })
            else:
                await websocket.send_json({
                    "event": "authentication_failed",
                    "success": False,
                    "message": result.get("error", "Unknown error")
                })
        
        # Listen for messages
        while True:
            # Wait for client messages
            data = await websocket.receive_text()
            try:
                message = json.loads(data)

                if message.get("action") == "set_current_lots":
                    params = message["value"]  
                    new_percent = manager.mt5.set_lots_params(params)
                    manager._current_lots = new_percent

                    await websocket.send_json({
                        "event": "current_lots_updated",
                        "value": new_percent,         
                        "updated_by": client_id
                    })
                elif message.get("action") == "take_current_balance":
                    data = manager.mt5.take_current_balance()
                    await websocket.send_json({
                        "event": "send_current_balance",
                        "value": json.dumps(data),
                        "updated_by": client_id
                    })
                elif message.get("action") == "take_all_trades":
                    data = manager.mt5.take_all_trades()
                    await websocket.send_json({
                        "event": "send_all_trades",
                        "value": data,
                        "updated_by": client_id
                    })

                # Handle authentication and credentials (for backward compatibility)
                elif "action" in message and message["action"] == "authenticate":
                    if "credentials" in message:
                        try:
                            credentials = TelegramCredentials(**message["credentials"])
                            result = await manager.initialize_listener_service(client_id, credentials)
                            
                            if result["success"]:
                                await websocket.send_json({
                                    "event": "authenticated",
                                    "success": True
                                })
                            elif result.get("needs_verification", False):
                                await websocket.send_json({
                                    "event": "verification_needed",
                                    "success": False,
                                    "message": "Please provide the verification code sent to your phone"
                                })
                            else:
                                await websocket.send_json({
                                    "event": "authentication_failed",
                                    "success": False,
                                    "message": result.get("error", "Unknown error")
                                })
                        except Exception as e:
                            await websocket.send_json({
                                "event": "authentication_failed",
                                "success": False,
                                "message": f"Invalid credentials: {str(e)}"
                            })
                    else:
                        await websocket.send_json({
                            "event": "authentication_failed",
                            "success": False,
                            "message": "No credentials provided"
                        })
                
                # Handle verification code submission
                elif "action" in message and message["action"] == "verify":
                    if client_id in manager.client_credentials and "code" in message:
                        credentials = manager.client_credentials[client_id]
                        code = message["code"]
                        password = message.get("password")
                        
                        try:
                            if password:
                                await manager.listener_service.telegram_service.sign_in_with_password(code, password)
                            else:
                                await manager.listener_service.telegram_service.sign_in_with_code(code)
                            
                            await websocket.send_json({
                                "event": "authenticated",
                                "success": True
                            })
                        except Exception as e:
                            error_message = str(e)
                            if "2fa" in error_message.lower() or "two-step verification" in error_message.lower():
                                await websocket.send_json({
                                    "event": "verification_needed",
                                    "success": False,
                                    "needs_password": True,
                                    "message": "Two-step verification is enabled. Please provide your password."
                                })
                            else:
                                await websocket.send_json({
                                    "event": "authentication_failed",
                                    "success": False,
                                    "message": f"Verification failed: {error_message}"
                                })
                    else:
                        await websocket.send_json({
                            "event": "authentication_failed",
                            "success": False,
                            "message": "No pending verification or missing code"
                        })
                
                # Handle subscribe/unsubscribe actions
                elif "action" in message and "dialog_id" in message:
                    dialog_id = int(message["dialog_id"])
                    
                    if message["action"] == "subscribe":
                        # Try to subscribe to the real dialog if we have a service
                        if manager.listener_service and manager.listener_service.telegram_service:
                            success = await manager.subscribe_to_dialog(client_id, dialog_id)
                            await websocket.send_json({
                                "event": "subscription_update",
                                "dialog_id": dialog_id,
                                "subscribed": success
                            })
                            
                            if not success:
                                # Send an error message if subscription failed
                                await websocket.send_json({
                                    "event": "error",
                                    "message": f"Failed to subscribe to dialog {dialog_id}. Please ensure you're authenticated to Telegram."
                                })
                        else:
                            # No telegram service available
                            await websocket.send_json({
                                "event": "subscription_update",
                                "dialog_id": dialog_id,
                                "subscribed": False
                            })
                            
                            await websocket.send_json({
                                "event": "error",
                                "message": "No active Telegram session found. Please authenticate with Telegram first."
                            })
                    
                    elif message["action"] == "unsubscribe":
                        success = await manager.unsubscribe_from_dialog(client_id, dialog_id)
                        await websocket.send_json({
                            "event": "subscription_update",
                            "dialog_id": dialog_id,
                            "subscribed": False
                        })
                
                # Handle subscribe by dialog name
                elif "action" in message and message["action"] == "subscribe_by_name" and "dialog_name" in message:
                    dialog_name = message["dialog_name"]
                    
                    # Try to subscribe to the dialog by name
                    if manager.listener_service and manager.listener_service.telegram_service:
                        result = await manager.subscribe_to_dialog_by_name(client_id, dialog_name)
                        
                        if result["success"]:
                            dialog = result["dialog"]
                            await websocket.send_json({
                                "event": "subscription_update",
                                "dialog_id": dialog["id"],
                                "dialog_name": dialog["name"],
                                "subscribed": True
                            })
                        else:
                            # Send an error message if subscription failed
                            await websocket.send_json({
                                "event": "error",
                                "message": result.get("error", f"Failed to subscribe to dialog {dialog_name}")
                            })
                    else:
                        # No telegram service available
                        await websocket.send_json({
                            "event": "error",
                            "message": "No active Telegram session found. Please authenticate with Telegram first."
                        })

                elif "action" in message and message["action"] == "set_current_lots":
                    new_value = float(message["value"])
                    await websocket.send_json({
                        "event": "error",
                        "message": "updated - LOTs - {}".format(new_value)
                    })
                
                
                # Handle invalid actions
                else:
                    await websocket.send_json({
                        "event": "error",
                        "message": "Invalid message format or action"
                    })
                
                
                    
            except json.JSONDecodeError:
                await websocket.send_json({
                    "event": "error",
                    "message": "Invalid JSON"
                })
            except Exception as e:
                logger.error(f"Error processing message: {e}")
                await websocket.send_json({
                    "event": "error",
                    "message": f"Error processing request: {str(e)}"
                })
                
    except WebSocketDisconnect:
        manager.disconnect(client_id)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(client_id)