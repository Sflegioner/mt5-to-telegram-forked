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
        „ICH SCHLIEßE AMAZON CALL 225 721€ GEWINN “
        „ICH SCHLIEßE GOLD 2.070€ GEWINN “
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
        logger.info(message_text)
        match_buy=re.search(r'\bKAUFE\b\s+(?P<symbol>\w+)(?:\s+(?P<option>CALL|PUT)\s+(?P<strike>\d+))?.*EK:\s*(?P<price>[\d\.]+)', message_text, re.IGNORECASE)
        match_sell=re.search(r'\bVERKAUFE\b\s+(?P<symbol>\w+)'r'(?:\s+(?P<option>CALL|PUT)\s+(?P<strike>\d+))?'r'.*EK[:：]?\s*(?P<price>[\d\.]+)',message_text,re.IGNORECASE)
        match_set = re.search(
            r'(?:\bich\s+)?'                                 #  "Ich "
            r'(?:setze\s+den\s+SL\s+bei\s+)?'                # "setze den SL bei"
            r'(?P<symbol>[A-Z0-9]+)'                         # SYMBOL
            r'(?:\s+(?P<option>CALL|PUT)\s+(?P<strike>\d+))?'#  CALL/PUT + strike
            r'.*?(?:auf|SL)[:：]?\s*'                        # "auf" або "SL:" 
            r'(?P<price>\d+(?:[.,]\d+)?)',                   # price
            message_text,
            re.IGNORECASE | re.DOTALL | re.MULTILINE
        )
        match_close = re.search(
            r'SCHLIE\w*\s+'                          # ICH SCHLIEßE
            r'(?P<symbol>\w+)'                       #
            r'(?:\s+(?P<option>CALL|PUT))?'          # 
            r'(?:\s+(?P<strike>\d+))?'               # 
            r'\s+(?P<price>[\d\.,]+)\s*€',           # 
            message_text,
            re.IGNORECASE | re.DOTALL
        )

        if match_buy:
            result.update({
                "is_signal": True,
                "type": "BUY",
                "symbol": match_buy.group("symbol").upper(),
                "option": (match_buy.group("option") or "").upper(),
                "strike": match_buy.group("strike"),
                "price": float(match_buy.group("price"))
            })
        elif match_sell:
            result.update({
                "is_signal": True,
                "type": "SELL",
                "symbol": match_sell.group("symbol").upper(),
                "option": (match_sell.group("option") or "").upper(),
                "strike": match_sell.group("strike"),
                "price": float(match_sell.group("price"))
            })
        elif match_set:
            logger.info("SET FIND")
            result.update({
                "is_signal": True,
                "type": "SET",
                "symbol": match_set.group("symbol").upper(),
                "option": (match_set.group("option") or "").upper(),
                "strike": match_set.group("strike"),
                "price": float(match_set.group("price"))
            })
        elif match_close:
            raw_price = match_close.group("price").replace('.', '').replace(',', '.')
            result.update({
                "is_signal": True,
                "type": "CLOSE",
                "symbol": match_close.group("symbol").upper(),
                "option": (match_close.group("option") or "").upper(),
                "strike": match_close.group("strike"),
                "price": float(raw_price)
            })

        if result["is_signal"]:
            lines = [
                "┌─ 💵 Signal Parsed 💵",
                f"│ Type:   {result['type']}",
                f"│ Symbol: {result['symbol']}",
                f"│ Option: {result['option'] or '-'}",
                f"│ Strike: {result['strike'] or '-'}",
                f"│ Price:  {result['price']}",
                f"│ LOTs:   {result['LOTs']}",
                "└─────────────────────"
            ]
            result["parsed_message"] = "\n".join(lines)
        else:
            result["parsed_message"] = None 

        return result

    def execute_BUY_operation(self, parsed: dict) -> dict:
        """
        Execute operation and return a dict with keys:
        - type: "BUY_mt5" or "error_mt5"
        - mt5_message: 
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
    
    def execute_SELL_operation(self, parsed: dict) -> dict:
        """
        Execute a SELL operation in MT5.
        Returns a dict with keys:
        - type: "SELL_mt5" or "error_mt5"
        - mt5_message: human‑readable result or error
        """
        symbol = parsed["symbol"]
        final_msg = {
            "type":        "error_mt5",
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
            "type":         mt5.ORDER_TYPE_SELL,    
            "price":        tick.bid,               
            "deviation":    10,
            "magic":        234000,
            "comment":      "SELL SIGNAL",
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

        success_msg = f"SELL executed: {vol} lots of {symbol} @ {tick.bid}"
        logger.info(success_msg)
        return {
            "type":        "SELL_mt5",
            "mt5_message": success_msg
        }
    
    def execute_SET_operation(self, parsed: dict) -> dict:
        """
        Execute a SET (stop-loss) modification in MT5.
        Returns a dict with keys:
        - type: "SET_mt5" or "error_mt5"
        - mt5_message: human-readable result or error
        """
        symbol = parsed["symbol"]
        sl_price = parsed["price"]
        final_msg = {"type": "error_mt5", "mt5_message": None}

        # Ensure symbol is available
        if not mt5.symbol_select(symbol, True):
            errmsg = f"Symbol {symbol} not found"
            logger.error(errmsg)
            final_msg["mt5_message"] = errmsg
            return final_msg

        # Retrieve open positions for this symbol
        positions = mt5.positions_get(symbol=symbol)
        if positions is None or len(positions) == 0:
            errmsg = f"No open positions for {symbol}"
            logger.error(errmsg)
            final_msg["mt5_message"] = errmsg
            return final_msg

        # Pick the first position (or refine by option/strike if needed)
        position = positions[0]
        ticket = position.ticket
        current_tp = position.tp if position.tp is not None else 0.0

        # Build modification request
        request = {
            "action":    mt5.TRADE_ACTION_SLTP,
            "position":  ticket,
            "sl":        sl_price,
            "tp":        current_tp,
            "magic":     234000,
            "comment":   "SET SL SIGNAL"
        }

        # Send modification
        res = mt5.order_send(request)
        if res is None or res.retcode != mt5.TRADE_RETCODE_DONE:
            errmsg = res.comment if res else str(mt5.last_error())
            full_err = f"SET SL failed: {errmsg} (retcode={getattr(res, 'retcode', 'N/A')})"
            logger.error(full_err)
            final_msg["mt5_message"] = full_err
            return final_msg

        # Success
        success_msg = f"SL set for position {ticket} of {symbol} @ {sl_price}"
        logger.info(success_msg)
        return {"type": "SET_mt5", "mt5_message": success_msg}
    
    def execute_CLOSE_operation(self, parsed: dict) -> dict:
        """
        Execute a CLOSE operation in MT5.
        Closes all open positions for the given symbol by sending
        opposite market orders with the same volume.
        Returns a dict with keys:
        - type: "CLOSE_mt5" or "error_mt5"
        - mt5_message: human‑readable result or error
        """
        symbol = parsed["symbol"]
        final_msg = {
            "type":        "error_mt5",
            "mt5_message": None
        }

        if not mt5.symbol_select(symbol, True):
            errmsg = f"Symbol {symbol} not found"
            logger.error(errmsg)
            final_msg["mt5_message"] = errmsg
            return final_msg


        positions = mt5.positions_get(symbol=symbol)
        if positions is None or len(positions) == 0:
            errmsg = f"No open positions for {symbol}"
            logger.error(errmsg)
            final_msg["mt5_message"] = errmsg
            return final_msg
        results = []

        for pos in positions:
            ticket = pos.ticket
            volume = pos.volume
            if pos.type == mt5.POSITION_TYPE_BUY:
                order_type = mt5.ORDER_TYPE_SELL
                price = mt5.symbol_info_tick(symbol).bid
            else:
                order_type = mt5.ORDER_TYPE_BUY
                price = mt5.symbol_info_tick(symbol).ask

            request = {
                "action":       mt5.TRADE_ACTION_DEAL,
                "symbol":       symbol,
                "volume":       volume,
                "type":         order_type,
                "price":        price,
                "deviation":    10,
                "magic":        234000,
                "comment":      "CLOSE_SIGNAL",
                "type_time":    mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }

            res = mt5.order_send(request)
            if res is None or res.retcode != mt5.TRADE_RETCODE_DONE:
                errmsg = res.comment if res else str(mt5.last_error())
                full_err = f"Close failed for ticket {ticket}: {errmsg} (retcode={getattr(res, 'retcode', 'N/A')})"
                logger.error(full_err)
                results.append(full_err)
            else:
                msg = f"Position {ticket} closed: {volume} lots of {symbol} @ {price}"
                logger.info(msg)
                results.append(msg)

        if any("failed" in r.lower() for r in results):
            final_msg["mt5_message"] = "\n".join(results)
            return final_msg

        return {
            "type":        "CLOSE_mt5",
            "mt5_message": "\n".join(results)
        }

    def take_current_balance(self):
        account_info = mt5.account_info()
        if account_info is None:
            logger.error("Failed to get account info")
            return None
        return account_info.balance
