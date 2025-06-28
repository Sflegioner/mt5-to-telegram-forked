import re
import logging
import MetaTrader5 as mt5

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

    def test_connection(self) -> bool:
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

    def parse_message(self, message_text: str, LOTs_from_signals: float) -> dict:
        """
        Expected formats:
        - "EURUSD 1.2345/1.2350 0.1"
        - "#signal: GBPUSD | 1.4000 - 1.4020 | LOT=0.2"
        """
        DEFAULT_LOTS = 0.1  

        result = {
            "message": message_text,
            "parsed_message": None,
            "symbol": None,
            "bid": None,
            "ask": None,
            "lots": LOTs_from_signals if LOTs_from_signals else DEFAULT_LOTS,
            "is_signal": False,
        }

        pattern = re.compile(
            r"(?P<symbol>[A-Za-z]{6})[^0-9]+"
            r"(?P<bid>\d+\.?\d*)\s*[/-]\s*(?P<ask>\d+\.?\d*)"
            r"(?:[^0-9]+(?P<lots>\d+\.?\d*))?"
        )
        match = pattern.search(message_text)
        if match:
            symbol = match.group("symbol").upper()
            bid = float(match.group("bid"))
            ask = float(match.group("ask"))
            lots_raw = match.group("lots")
            
            if lots_raw:
                lots = float(lots_raw)
            elif LOTs_from_signals:
                lots = LOTs_from_signals
            else:
                lots = DEFAULT_LOTS

            result.update({
                "symbol": symbol,
                "bid": bid,
                "ask": ask,
                "lots": lots,
                "is_signal": True,
            })

            lines = [
                f"┌─ 💵 Signal Parsed 💵",
                f"│ Symbol: {symbol}",
                f"│ Bid   : {bid}",
                f"│ Ask   : {ask}",
                f"│ LOTs  : {lots}",
                "└─────────────────────"
            ]
            result["parsed_message"] = "\n".join(lines)
            logger.info(f"💵 Signal parsed: {symbol} bid={bid} ask={ask} lots={lots}")

            executed = self.execute_operation(result)
            if executed:
                logger.info("Trade executed successfully after parsing.")
            else:
                logger.error("Trade execution failed after parsing.")
        else:
            logger.warning(f"Unable to parse signal from message: {message_text}")

        return result

    def execute_operation(self, parsed: dict) -> bool:
        """
        Execute a market order based on parsed signal (BUY at ask price).
        Ensures symbol is selected and tick available before sending.
        """
        if not parsed.get("is_signal"):
            logger.warning("execute_operation called with no signal.")
            return False

        symbol = parsed.get("symbol")
        lot = parsed.get("lots", 0.1)
        price = parsed.get("ask")


        if not mt5.symbol_select(symbol, True):
            logger.error(f"Failed to select symbol {symbol}")
            return False
        
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            logger.error(f"No tick data for {symbol}")
            return False

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": lot,
            "type": mt5.ORDER_TYPE_BUY,
            "price": price or tick.ask,
            "sl": 0.0,
            "tp": 0.0,
            "deviation": 10,
            "magic": 234000,
            "comment": "Python MT5 Signal",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        result = mt5.order_send(request)
        if result is None:
            error = mt5.last_error()
            logger.error(f"Order send returned None: {error}")
            return False

        if result.retcode != mt5.TRADE_RETCODE_DONE:
            logger.error(f"Order failed, retcode={result.retcode}, result={result}")
            return False

        logger.info(f"Order placed successfully, ticket={result.order}")
        return True

    def take_current_balance(self):
        account_info = mt5.account_info()
        if account_info is None:
            logger.error("Failed to get account info")
            return None
        return account_info.balance
