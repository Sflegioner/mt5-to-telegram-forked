# WebSocket connection manager
import asyncio
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
        self.listener_services: Dict[str, TelegramListenerService] = {}
        self.listener_service: Optional[TelegramListenerService] = None

        # Store client credentials
        self.client_credentials: Dict[str, TelegramCredentials] = {}
        # per-client asyncio locks to serialize session/DB access
        self._locks: Dict[str, asyncio.Lock] = {}
        self._refcounts: Dict[str, int] = {}
        
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

    def _session_key(self, api_id: int, api_hash: str, phone: Optional[str]) -> str:
        return f"{api_id}:{api_hash}:{phone or ''}"
    
    def _get_lock(self,sesseion_key:str)-> asyncio.Lock:
        if sesseion_key not in self._locks:
            self._locks[sesseion_key] = asyncio.Lock()
        return self._locks[sesseion_key]


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

    async def _subscribe_with_listener(self, session_key: str, client_id: str, dialog_id: int, listener: TelegramListenerService) -> bool:

        if dialog_id not in self.dialog_subscribers:
            self.dialog_subscribers[dialog_id] = []

        if client_id not in self.dialog_subscribers[dialog_id]:
            self.dialog_subscribers[dialog_id].append(client_id)

        if client_id not in self.client_subscriptions:
            self.client_subscriptions[client_id] = []

        if dialog_id not in self.client_subscriptions[client_id]:
            self.client_subscriptions[client_id].append(dialog_id)

        # Start listening to dialog if not already
        try:
            if not listener.is_listening(dialog_id):
                success = await listener.start_listening(dialog_id, self.message_handler)
                if not success:
                    self.logger.error("Failed to start listening to dialog %s", dialog_id)
                    return False
        except Exception as e:
            self.logger.exception("Exception while starting listener for dialog %s: %s", dialog_id, e)
            return False

        self.logger.info("Client %s subscribed to dialog %s", client_id, dialog_id)
        return True
    
    async def subscribe_to_dialog(self, client_id: str, dialog_id: int) -> bool:
        creds = self.client_credentials.get(client_id)
        if not creds:
            self.logger.error("No credentials found for client_id %s", client_id)
            return False

        session_key = self._session_key(creds.api_id, creds.api_hash, creds.phone)
        listener = self.listener_services.get(session_key)
        if not listener:
            self.logger.error("Listener service not initialized for session %s", session_key)
            return False

        lock = self._get_lock(session_key)

        async with lock:
            return await self._subscribe_with_listener(session_key, client_id, dialog_id, listener)

    async def subscribe_to_dialog_by_name(self, client_id: str, dialog_name: str) -> dict:
        """ 
        Returns: Dictionary with success status and dialog information if found
        """
        credentials = self.client_credentials.get(client_id)
        if not credentials:
            self.logger.error("DFNo credentials found for client_id %s",client_id)
            return {"success": False, "error": "No credentials for client"}
        
        session_key = self._session_key(credentials.api_id, credentials.api_hash, credentials.phone)
        lock = self._get_lock(session_key)
        async with lock:
            listener = self.listener_services.get(session_key)
            if not listener or not hasattr(listener,"telegram_service"):
                self.logger.error("Listener service not initialized for session %s",session_key)
                return {"success": False, "error": "Listener service not initialized"}   
            try:
                dialog = await listener.telegram_service.get_dialog_by_name(dialog_name)
                if not dialog:
                    self.logger.error("Dialog not found: %s", dialog_name)
                    return {"success": False, "error": f"Dialog not found: {dialog_name}"}
                dialog_id = dialog["id"]
                success = await self._subscribe_with_listener(session_key, client_id, dialog_id, listener)
                if success:
                    return {"success": True, "dialog": dialog}
                else:
                    return {"success": False, "error": f"Failed to subscribe to dialog: {dialog_name}"}
            except Exception as e:
                self.logger.exception("Error subscribing to dialog by name: %s", e)
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
    async def initialize_listener_service(self, client_id: str, credentials: TelegramCredentials):
        session_key = self._session_key(credentials.api_id, credentials.api_hash, credentials.phone)
        lock = self._get_lock(session_key)
        #Reuse of listener service 
        async with lock:
            if session_key in self.listener_services:
                self._refcounts[session_key] += 1
                return {"success": True, "reused": True}
            tg_service = TelegramService(api_id=credentials.api_id, api_hash=credentials.api_hash, phone=credentials.phone,lock=lock)
            try:
                await tg_service.connect()
                listener = TelegramListenerService(tg_service)

                self.listener_services[session_key]=listener
                self.listener_service = self.listener_services[session_key]
                self._refcounts[session_key] = 1
                self.client_credentials[client_id] = credentials
                return {"success": True, "reused": False}
            
            except Exception as e:
                try:
                    await tg_service.disconnect()
                except Exception:
                    logging.exception("Failed safe disconnect")
                return {"success":False,"error":str(e)}
            