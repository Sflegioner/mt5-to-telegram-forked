import MetaTrader5 as mt5
import logging
import re

logger = logging.getLogger("MetaTraderService")

class MetaTraderService:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(MetaTraderService, cls).__new__(cls)
            if not mt5.initialize():
                error = mt5.last_error()
                logger.error(f"MT5 initialization failed: {error}")
                raise Exception(f"MT5 ###ERROR###: {error}")
            else:
                logger.info("MT5 initialized successfully")
        return cls._instance
    
    def test_connection(self):
        try:
            account_info = mt5.account_info()
            if account_info is None:
                error = mt5.last_error()
                logger.error(f"MT5 account info failed: {error}")
                return False
                
            logger.info("_-_-_-_-_MT5_-_-_-_-_")
            return True
        except Exception as e:
            logger.error(f"MT5 test_connection failed: {str(e)}")
            return False
    def parse_message(self, message_text: str) -> dict:
        """
        Expected formats (examples):
          - "EURUSD 1.2345/1.2350 0.1"        # symbol bid/ask lots
          - "#signal: GBPUSD | 1.4000 - 1.4020 | LOT=0.2"
        """
        result = {
            "message": message_text,
            "symbol": None,
            "bid": None,
            "ask": None,
            "lots": None,
            "is_signal": None,
        }

        # Regex to capture symbol and bid/ask
        pattern = re.compile(
            r"(?P<symbol>[A-Za-z]{6})[^0-9]+"
            r"(?P<bid>\d+\.?\d*)\s*[/-]\s*(?P<ask>\d+\.?\d*)"  # bid/ask
            r"(?:[^0-9]+(?P<lots>\d+\.?\d*))?"                     # optional lots
        )
        match = pattern.search(message_text)
        if match:
            result["symbol"] = match.group("symbol").upper()
            result["bid"] = float(match.group("bid"))
            result["ask"] = float(match.group("ask"))
            lots = match.group("lots")
            result["lots"] = float(lots) if lots else None
            result["is_signal"] = True
            logger.info(
                f"💵 💵 💵 Signal found: symbol={result['symbol']},"
                f" bid={result['bid']}, ask={result['ask']}, lots={result['lots']}💵 💵 💵 "
            )
        else:
            logger.warning(f"Unable to parse signal from message: {message_text}")
        return result

    def execute_operation(self, parsed: dict) -> bool:
        """
        Execute a trade based on parsed signal. Stub for actual order placement.
        """
        symbol = parsed.get("symbol")
        bid = parsed.get("bid")
        ask = parsed.get("ask")
        lots = parsed.get("lots") or 0.1
        # TODO: implement order send logic, e.g., mt5.order_send(...)
        logger.info(f"Executing trade: {symbol} bid={bid} ask={ask} lots={lots}")
        return True
