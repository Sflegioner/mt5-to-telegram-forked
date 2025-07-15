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
        #match_sell=re.search(r'ICH VERKAUFE\s+(?P<symbol>)\w+)(?:\s+(?P<option>CALL|PUT)')
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
                f"│ Type: {result['type']}",
                f"│ Symbol: {result['symbol']}",
                f"│ Price: {result['price']}",
                f"│ LOTs  : {result['LOTs']}",
                f""
                "└─────────────────────"
            ]
            result["parsed_message"] = "\n".join(lines)
        # match_sell={}
        # match_close={}
        # match_sell={}


        return result

    def execute_BUY_operation(self, parsed: dict) -> dict:
        """
        Execute operation and return a dict with keys:
        - type: "BUY_mt5" or "error_mt5"
        - mt5_message: текст повідомлення для користувача
        """
        symbol = parsed["symbol"]
        final_msg = {
            "type": "error_mt5",
            "mt5_message": None
        }

        if not mt5.symbol_select(symbol, True):
            errmsg = f"Symbol {symbol} not found"
            logger.error(errmsg)
            final_msg["mt5_message"] = errmsg
            return final_msg


        info = mt5.symbol_info(symbol)
        if info is None:
            errmsg = f"No info for {symbol}"
            logger.error(errmsg)
            final_msg["mt5_message"] = errmsg
            return final_msg


        if info.trade_mode != mt5.SYMBOL_TRADE_MODE_FULL:
            errmsg = f"Market closed for {symbol} (mode={info.trade_mode})"
            logger.warning(errmsg)
            final_msg["mt5_message"] = errmsg
            return final_msg

        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            errmsg = f"No tick data for {symbol}"
            logger.error(errmsg)
            final_msg["mt5_message"] = errmsg
            return final_msg

        vol = max(info.volume_min, min(info.volume_max, parsed["LOTs"]))
        vol = round(vol / info.volume_step) * info.volume_step

        request = {
            "action":       mt5.TRADE_ACTION_DEAL,
            "symbol":       symbol,
            "volume":       vol,
            "type":         mt5.ORDER_TYPE_BUY,
            "price":        tick.ask,
            "deviation":    10,
            "magic":        234000,
            "comment":      "BUY SIGNAL",
            "type_time":    mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        res = mt5.order_send(request)
        if res is None or res.retcode != mt5.TRADE_RETCODE_DONE:
            errmsg = res.comment if res else str(mt5.last_error())
            full_err = f"Order failed: {errmsg} (retcode={getattr(res, 'retcode', 'N/A')})"
            logger.error(full_err)
            final_msg["mt5_message"] = full_err
            return final_msg

        #SUCSESS
        success_msg = f"BUY executed: {vol} lots of {symbol} @ {tick.ask}"
        logger.info(success_msg)
        return {
            "type":        "BUY_mt5",
            "mt5_message": success_msg
        }

    def take_current_balance(self):
        account_info = mt5.account_info()
        if account_info is None:
            logger.error("Failed to get account info")
            return None
        return account_info.balance
