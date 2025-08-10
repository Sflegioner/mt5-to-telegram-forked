# WebSocket connection manager
from typing import Any, Dict, List, Optional
from fastapi import WebSocket
from telethon.tl.types import Message
from backend.app.mt5.meta_trader_service import MetaTraderService
from backend.app.schemas.telegram import TelegramCredentials
from backend.app.services.listener_service import TelegramListenerService
from backend.app.services.telegram_service import TelegramService
import logging

class ConnectionManager:
    def __init__(self):
        # client_id -> WebSocket connection
        self.active_connections: Dict[str, WebSocket] = {}
        # dialog_id -> List[client_id]
        self.dialog_subscribers: Dict[int, List[str]] = {}
        # client_id -> List[dialog_id]
        self.client_subscriptions: Dict[str, List[int]] = {}
        # Global TelegramListenerService instance
        self.listener_service: Optional[TelegramListenerService] = None
        # Store client credentials
        self.client_credentials: Dict[str, TelegramCredentials] = {}
        
        self.mt5 = MetaTraderService()
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
        self._current_lots = 0.1 
    
    async def connect(self, websocket: WebSocket, client_id: str) -> None:
        """Register new WebSocket connection."""
        await websocket.accept()
        self.active_connections[client_id] = websocket
        self.client_subscriptions[client_id] = []
        self.logger.info(f"Client {client_id} connected")
    
    def disconnect(self, client_id: str) -> None:
        """Remove WebSocket connection."""
        # Clean up subscriptions
        if client_id in self.client_subscriptions:
            for dialog_id in self.client_subscriptions[client_id]:
                if dialog_id in self.dialog_subscribers:
                    if client_id in self.dialog_subscribers[dialog_id]:
                        self.dialog_subscribers[dialog_id].remove(client_id)
                    # Clean up empty lists
                    if not self.dialog_subscribers[dialog_id]:
                        del self.dialog_subscribers[dialog_id]
            del self.client_subscriptions[client_id]
        
        # Remove connection
        if client_id in self.active_connections:
            del self.active_connections[client_id]
        
        self.logger.info(f"Client {client_id} disconnected")
    
    async def subscribe_to_dialog(self, client_id: str, dialog_id: int) -> bool:
        """Subscribe client to dialog updates."""
        # Initialize listener service if needed
        if not self.listener_service or not hasattr(self.listener_service, 'telegram_service'):
            self.logger.error("Listener service not initialized")
            return False
        
        # Register client as subscriber for this dialog
        if dialog_id not in self.dialog_subscribers:
            self.dialog_subscribers[dialog_id] = []
        
        if client_id not in self.dialog_subscribers[dialog_id]:
            self.dialog_subscribers[dialog_id].append(client_id)
        
        # Track subscriptions for this client
        if client_id not in self.client_subscriptions:
            self.client_subscriptions[client_id] = []
        
        if dialog_id not in self.client_subscriptions[client_id]:
            self.client_subscriptions[client_id].append(dialog_id)
        
        # Start listening to dialog if not already
        if not self.listener_service.is_listening(dialog_id):
            success = await self.listener_service.start_listening(
                dialog_id, self.message_handler
            )
            if not success:
                self.logger.error(f"Failed to start listening to dialog {dialog_id}")
                return False
        
        self.logger.info(f"Client {client_id} subscribed to dialog {dialog_id}")
        return True
    
    async def subscribe_to_dialog_by_name(self, client_id: str, dialog_name: str) -> dict:
        """
        Subscribe client to dialog updates using dialog name instead of ID.
        
        Args:
            client_id: ID of the client
            dialog_name: Name of the dialog to subscribe to
            
        Returns:
            Dictionary with success status and dialog information if found
        """
        # Initialize listener service if needed
        if not self.listener_service or not hasattr(self.listener_service, 'telegram_service'):
            self.logger.error("Listener service not initialized")
            return {"success": False, "error": "Listener service not initialized"}
        
        # Find dialog by name
        try:
            dialog = await self.listener_service.telegram_service.get_dialog_by_name(dialog_name)
            if not dialog:
                self.logger.error(f"Dialog not found: {dialog_name}")
                return {"success": False, "error": f"Dialog not found: {dialog_name}"}
            
            dialog_id = dialog["id"]
            
            # Subscribe to the dialog
            success = await self.subscribe_to_dialog(client_id, dialog_id)
            if success:
                return {"success": True, "dialog": dialog}
            else:
                return {"success": False, "error": f"Failed to subscribe to dialog: {dialog_name}"}
        except Exception as e:
            self.logger.error(f"Error subscribing to dialog by name: {e}")
            return {"success": False, "error": str(e)}
    
    async def unsubscribe_from_dialog(self, client_id: str, dialog_id: int) -> bool:
        """Unsubscribe client from dialog updates."""
        if dialog_id in self.dialog_subscribers and client_id in self.dialog_subscribers[dialog_id]:
            self.dialog_subscribers[dialog_id].remove(client_id)
            
            # Remove dialog from client subscriptions
            if client_id in self.client_subscriptions and dialog_id in self.client_subscriptions[client_id]:
                self.client_subscriptions[client_id].remove(dialog_id)
            
            # If no subscribers left, stop listening
            if not self.dialog_subscribers[dialog_id] and self.listener_service:
                await self.listener_service.stop_listening(dialog_id)
                del self.dialog_subscribers[dialog_id]
            
            self.logger.info(f"Client {client_id} unsubscribed from dialog {dialog_id}")
            return True
        
        return False
    
    async def broadcast_to_dialog_subscribers(self, dialog_id: int, message: Dict[str, Any]) -> None:
        """Send message to all subscribers of a dialog."""
        if dialog_id not in self.dialog_subscribers:
            return
        
        disconnect_list = []
        for client_id in self.dialog_subscribers[dialog_id]:
            if client_id in self.active_connections:
                try:
                    await self.active_connections[client_id].send_json(message)
                except Exception as e:
                    self.logger.error(f"Error sending to client {client_id}: {e}")
                    disconnect_list.append(client_id)
            else:
                disconnect_list.append(client_id)
        
        # Clean up disconnected clients
        for client_id in disconnect_list:
            self.disconnect(client_id)

    async def message_handler(self, message: Message) -> None:
        """Process new Telegram messages and broadcast to subscribers."""
        if not hasattr(message, 'chat_id'):
            return
        
        dialog_id = message.chat_id
        
        # Convert message to dict for JSON serialization
        sender = await message.get_sender()
        
        message_data = {
            "event": "new_message",
            "dialog_id": dialog_id,
            "message": {
                "id": message.id,
                "text": message.text,
                "date": message.date.isoformat(),
                "sender": {
                    "id": sender.id if sender else None,
                    "first_name": getattr(sender, "first_name", None),
                    "last_name": getattr(sender, "last_name", None),
                    "username": getattr(sender, "username", None)
                },
                "has_media": bool(message.media)
            }
        }
        #TODO:
        self.mt5.test_connection()
        parsed = self.mt5.parse_message(message.text,self._current_lots)
        if parsed["is_signal"] is True:
#_________________________________________BUY____________________________________________________
            if parsed["type"]=="BUY":
                message_data = {
                    "event": "signal",
                    "dialog_id": dialog_id,
                    "message": {
                        "id": message.id,
                        "text": parsed["parsed_message"],
                        "date": message.date.isoformat(),
                        "sender": {
                            "id": sender.id if sender else None,
                            "first_name": getattr(sender, "first_name", None),
                            "last_name": getattr(sender, "last_name", None),
                            "username": "📢 Signal 📢"
                        },
                        "has_media": bool(message.media)}}
                await self.broadcast_to_dialog_subscribers(dialog_id, message_data)
                result = self.mt5.execute_BUY_operation(parsed)
                if result["type"] == "BUY_mt5":
                    message_data["event"] = "executed_operation_info"
                    message_data["message"]["text"] = result["mt5_message"]
                    message_data["message"]["sender"]["username"]="MT5 info:"
                elif result["type"]=="error_mt5":
                    message_data["event"] = "error_mt5"
                    message_data["message"]["text"] = result["mt5_message"]
                    message_data["message"]["sender"]["username"]="MT5 error:"
                await self.broadcast_to_dialog_subscribers(dialog_id, message_data)
#__________________________________________SELL____________________________________________________
            if parsed["type"]=="SELL":
                message_data = {
                    "event": "signal",
                    "dialog_id": dialog_id,
                    "message": {
                        "id": message.id,
                        "text": parsed["parsed_message"],
                        "date": message.date.isoformat(),
                        "sender": {
                            "id": sender.id if sender else None,
                            "first_name": getattr(sender, "first_name", None),
                            "last_name": getattr(sender, "last_name", None),
                            "username": "📢 Signal 📢"
                        },
                        "has_media": bool(message.media)}}
                await self.broadcast_to_dialog_subscribers(dialog_id, message_data)
                result = self.mt5.execute_SELL_operation(parsed)
                if result["type"] == "SELL_mt5":
                    message_data["event"] = "executed_operation_info"
                    message_data["message"]["text"] = result["mt5_message"]
                    message_data["message"]["sender"]["username"]="MT5 info:"
                elif result["type"]=="error_mt5":
                    message_data["event"] = "error_mt5"
                    message_data["message"]["text"] = result["mt5_message"]
                    message_data["message"]["sender"]["username"]="MT5 error:"
                await self.broadcast_to_dialog_subscribers(dialog_id, message_data)
#__________________________________________SET____________________________________________________
            if parsed["type"] == "SET":
                    message_data = {
                        "event": "signal",
                        "dialog_id": dialog_id,
                        "message": {
                            "id": message.id,
                            "text": parsed["parsed_message"],
                            "date": message.date.isoformat(),
                            "sender": {
                                "id": sender.id if sender else None,
                                "first_name": getattr(sender, "first_name", None),
                                "last_name": getattr(sender, "last_name", None),
                                "username": "📢 Signal 📢"
                            },
                            "has_media": bool(message.media)
                        }
                    }
                    await self.broadcast_to_dialog_subscribers(dialog_id, message_data)
                    result = self.mt5.execute_SET_operation(parsed)
                    if result["type"] == "SET_mt5":
                        message_data["event"] = "executed_operation_info"
                        message_data["message"]["text"] = result["mt5_message"]
                        message_data["message"]["sender"]["username"] = "MT5 info:"
                    elif result["type"] == "error_mt5":
                        message_data["event"] = "error_mt5"
                        message_data["message"]["text"] = result["mt5_message"]
                        message_data["message"]["sender"]["username"] = "MT5 error:"
                    await self.broadcast_to_dialog_subscribers(dialog_id, message_data)

#__________________________________________CLOSE__________________________________________________
            if parsed["type"] == "CLOSE":
                    message_data = {
                        "event": "signal",
                        "dialog_id": dialog_id,
                        "message": {
                            "id": message.id,
                            "text": parsed["parsed_message"],
                            "date": message.date.isoformat(),
                            "sender": {
                                "id": sender.id if sender else None,
                                "first_name": getattr(sender, "first_name", None),
                                "last_name": getattr(sender, "last_name", None),
                                "username": "📢 Signal 📢"
                            },
                            "has_media": bool(message.media)
                        }
                    }
                    await self.broadcast_to_dialog_subscribers(dialog_id, message_data)
                    result = self.mt5.execute_CLOSE_operation(parsed)
                    if result["type"] == "CLOSE_mt5":
                        message_data["event"] = "executed_operation_info"
                        message_data["message"]["text"] = result["mt5_message"]
                        message_data["message"]["sender"]["username"] = "MT5 info:"
                    elif result["type"] == "error_mt5":
                        message_data["event"] = "error_mt5"
                        message_data["message"]["text"] = result["mt5_message"]
                        message_data["message"]["sender"]["username"] = "MT5 error:"
                    await self.broadcast_to_dialog_subscribers(dialog_id, message_data)
        else:
            # Send to all subscribers
            await self.broadcast_to_dialog_subscribers(dialog_id, message_data)

    # Add a method to create and initialize a listener service with credentials
    async def initialize_listener_service(self, client_id: str, credentials: TelegramCredentials) -> Dict[str, Any]:
        """Initialize the listener service with provided credentials."""
        # Check if we already have a listener service
        if self.listener_service:
            # Try to connect with credentials
            try:
                success = await self.listener_service.connect_with_credentials(
                    credentials.api_id, 
                    credentials.api_hash, 
                    credentials.phone
                )
                return {
                    "success": success,
                    "needs_verification": not success and credentials.phone is not None
                }
            except Exception as e:
                return {
                    "success": False,
                    "error": str(e)
                }
        else:
            # Create new telegram service with provided credentials
            telegram_service = TelegramService(
                api_id=credentials.api_id,
                api_hash=credentials.api_hash,
                phone=credentials.phone
            )
            
            try:
                # Try to connect
                await telegram_service.connect()
                
                # Connection successful, initialize listener
                self.listener_service = TelegramListenerService(telegram_service)
                # Store the credentials for this client
                self.client_credentials[client_id] = credentials
                
                return {
                    "success": True,
                    "needs_verification": False
                }
            except Exception as e:
                # Check if verification needed
                error_message = str(e)
                if "verification code" in error_message.lower():
                    # Store service for later use
                    self.listener_service = TelegramListenerService(telegram_service)
                    # Store the credentials for this client
                    self.client_credentials[client_id] = credentials
                    
                    return {
                        "success": False,
                        "needs_verification": True,
                        "error": "Verification code required"
                    }
                else:
                    # Other error
                    await telegram_service.disconnect()
                    return {
                        "success": False,
                        "error": error_message
                    }