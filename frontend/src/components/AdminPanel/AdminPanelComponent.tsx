import { Box, Button, colors, Menu, MenuItem, Paper, Table, TableBody, TableCell, TableHead, TableRow, Typography } from "@mui/material";
import { useEffect, useState } from "react";
import { AccountStatusComponent } from "./AccountStatusComponent";
import { LotsManagerComponent } from "./LotsManagerComponent";
import { MultiplicatorComponent } from "./MultiplicatorComponent";

export const AdminPanelComponent = ({ ws }: { ws: WebSocket }) => {
  const [dataFromSocket, setDataFromSocket] = useState<number | null>(null);
  const [allTrades, setAllTrades] = useState<any[]>([]);
  const [statusBox, setStatusBox] = useState<"Account status" | "LOTs manager" | "Multiplicator">("Account status");
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const isMenuOpen = Boolean(anchorEl);



  useEffect(() => {

    const handleMessage = (event: MessageEvent) => {
      try {
        const data = JSON.parse(event.data);
        if (data.event === 'send_current_balance') {
          setDataFromSocket(data.value);
        }
        if (data.event === 'send_all_trades') {
          setAllTrades(data.value);
        }

      } catch (err) {
        console.error('Invalid JSON:', err);
      }
    };

    ws.addEventListener('message', handleMessage);
    return () => {
      ws.removeEventListener('message', handleMessage);
    };
  }, [ws]);

  useEffect(() => {
    const onOpen = () => {
      ws.send(JSON.stringify({ action: 'take_current_balance' }));
      ws.send(JSON.stringify({ action: 'take_all_trades' }))
    };
    if (ws.readyState === WebSocket.OPEN) {
      onOpen();
    } else {
      ws.addEventListener('open', onOpen);
      return () => ws.removeEventListener('open', onOpen);
    }
  }, [ws]);

  useEffect(() => {
    const fetchTrades = () => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ action: 'take_all_trades' }));
      }
    };
    fetchTrades();
    const interval = setInterval(fetchTrades, 500);

    return () => clearInterval(interval);
  }, [ws]);

  return (
    <Box height={200} width={700}>
      <Paper
        elevation={0}
        sx={{
          p: 0,
          backgroundColor: '#1E1E1E',
          borderRadius: '8px',
          height: '400px',
          fontFamily: 'monospace',
          position: 'relative',
          overflow: 'hidden',
          border: '1px solid rgba(255, 255, 255, 0.1)',
        }}
      >
        <Box
          sx={{
            p: 1,
            backgroundColor: '#323232',
            borderBottom: '1px solid rgba(255, 255, 255, 0.1)',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}
        >
          <Typography
            variant='body2'
            fontFamily='monospace'
            fontWeight='bold'
            color='rgba(255, 255, 255, 0.8)'
          >
            🛠️ Admin Panel 🛠️
          </Typography>
          <Button onClick={(event) => setAnchorEl(event.currentTarget)} sx={{ height: 20 }}> {statusBox}</Button>
          <Menu anchorEl={anchorEl} open={isMenuOpen} onClose={() => setAnchorEl(null)} >
            <MenuItem
              onClick={() => { setStatusBox("Account status"); setAnchorEl(null); }}>
              Account status
            </MenuItem>
            <MenuItem onClick={() => { setStatusBox("LOTs manager"); setAnchorEl(null); }}>
              LOTs manager
            </MenuItem>
            <MenuItem onClick={() => { setStatusBox("Multiplicator"); setAnchorEl(null); }}>
              Multiplicator
            </MenuItem>
          </Menu>
          <Typography sx={{ marginLeft: 2 }}>
            {dataFromSocket !== null ? `${dataFromSocket} 💶` : "No data"}
          </Typography>
        </Box>
        {statusBox === "Account status" && <AccountStatusComponent allTrades={allTrades} />}
        {statusBox === "LOTs manager" && <LotsManagerComponent ws={ws} />}
        {statusBox === "Multiplicator" && <MultiplicatorComponent />}



      </Paper>
    </Box>
  );
};
