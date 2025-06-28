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
         BUY:
        „  LIVE TREND
        ICH KAUFE AMAZON CALL 225 (EK: 10.40)
        Ich wähle den maximalen Multiplikator ℹℹ“
        „  LIVE TREND
        ICH KAUFE TESLA PUT 380 (EK: 31.50)
        Ich wähle den maximalen Multiplikator “
        „  LIVE TREND
        ICH KAUFE GOLD (EK: 2607.48)
        Ich wähle den maximalen Multiplikator“
        SET:
        „I
        ch setze den 
        SL bei TESLA PUT 380 auf 28.35“
        Or just:
        „TESLA PUT 380 
        SL: 181.1453“
        CLOSE:
        „ICH SCHLIEßE AMAZON CALL ℹℹ 225 721€ GEWINN “
        „ICH SCHLIEßE GOLDℹℹ2.070€ GEWINN “
        SELL:
        „  LIVE TREND
        ICH VERKAUFE TESLA PUT 380 (EK: 34.75)
        Ich wähle den maximalen Multiplikator“
        """
        result = {
            "is_signal":False,
            "type": None,
            "symbol": None,
            "option": None,
            "strike": None,
            "price": None,
            "LOTs": 0.01
        }
        match_buy=re.search(r'KAUFE\s+(?P<symbol>\w+)(?:\s+(?P<option>CALL|PUT)\s+(?P<strike>\d+))?.*EK:\s*(?P<price>[\d\.]+)', message_text, re.IGNORECASE)
        #logger.warning(mt5.symbol_info("AMZN")._asdict())
        if match_buy:
            result['type'] = 'BUY'
            result['symbol'] = match_buy.group('symbol').upper() # Name of actions to buy
            result['option'] = match_buy.group('option')  # CALL - increasing asset price  or PUT - falling asset price
            result['strike'] = match_buy.group('strike') # is the premium/entry price for a contract,
            result['price'] = float(match_buy.group('price')) #AK - ENTRY PRISE - 380 for AMAZON
            result['is_signal'] = True
            lines = [
                "┌─ 💵 Signal Parsed 💵",
                f"│ Symbol: {result['symbol']}",
                f"│ Price: {result['price']}",
                f"│ LOTs  : {result['LOTs']}",
                "└─────────────────────"
            ]
            result["parsed_message"] = "\n".join(lines)
        # match_sell={}
        # match_close={}
        # match_sell={}


        return result

    def execute_BUY_operation(self, parsed: dict) -> bool:
        symbol = parsed["symbol"]
        if not mt5.symbol_select(symbol, True):
            logger.error(f"Symbol {symbol} not found")
            return False

        info = mt5.symbol_info(symbol)
        if info is None:
            logger.error(f"No info for {symbol}")
            return False

        # Forex trades run almost around the clock
        if info.trade_mode != mt5.SYMBOL_TRADE_MODE_FULL:
            logger.warning(f"Market closed for {symbol} (mode={info.trade_mode})")
            return False
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            logger.error(f"No tick data for {symbol}")
            return False

        # enforce volume step & bounds
        vol = max(info.volume_min, min(info.volume_max, parsed["LOTs"]))
        vol = round(vol / info.volume_step) * info.volume_step

        request = {
            "action":      mt5.TRADE_ACTION_DEAL,
            "symbol":      symbol,
            "volume":      vol,
            "type":        mt5.ORDER_TYPE_BUY,         # Market buy
            "price":       tick.ask,
            "deviation":   10,
            "magic":       234000,
            "comment":     "BUY SIGNAL",
            "type_time":   mt5.ORDER_TIME_GTC,
            "type_filling":mt5.ORDER_FILLING_IOC,       # Immediate or cancel
        }

        logger.info(f"Sending MARKET BUY: {symbol} @ {tick.ask} lot={vol}")
        res = mt5.order_send(request)
        if res is None or res.retcode != mt5.TRADE_RETCODE_DONE:
            errmsg = mt5.last_error() if res is None else f"{res.comment} (retcode={res.retcode})"
            logger.error(f"Order failed: {errmsg}")
            return False

        logger.info(f"BUY executed: {vol} lots of {symbol} @ {tick.ask}")
        return True

    def take_current_balance(self):
        account_info = mt5.account_info()
        if account_info is None:
            logger.error("Failed to get account info")
            return None
        return account_info.balance
