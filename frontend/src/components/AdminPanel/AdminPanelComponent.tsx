import { Box, Button, Paper, Table, TableBody, TableCell, TableHead, TableRow, Typography } from "@mui/material";
import { useEffect, useState } from "react";

export const AdminPanelComponent = ({ ws }: { ws: WebSocket }) => {
  const [dataFromSocket, setDataFromSocket] = useState<number | null>(null);
  const [allTrades, setAllTrades] = useState<any[]>([]);

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
          <Button sx={{ height: 20 }}>Account status</Button>
          <Typography sx={{ marginLeft: 2 }}>
            {dataFromSocket !== null ? `${dataFromSocket} 💶` : "No data"}
          </Typography>
        </Box>
        <Box sx={{
          maxHeight: 'calc(400px - 48px)', 
          overflowY: 'auto',
        }} >
          <Table size="small" sx={{ color: '#FFF' }}>
            <TableHead>
              <TableRow>
                {['Symbol', 'Ticket', 'Time', 'Type', 'Volume', 'Open', 'S/L', 'T/P', 'Current', 'Profit'].map((h) => (
                  <TableCell key={h} sx={{ color: '#ccc', p: 1, fontSize: '0.75rem' }}>{h}</TableCell>
                ))}
              </TableRow>
            </TableHead>
            <TableBody>
              {allTrades.length > 0 ? allTrades.map((t: any) => (
                <TableRow sx={{ '& .MuiTableCell-root': { p: 0.5 } }} key={t.Ticket}>
                  <TableCell padding="none">{t.Symbol}</TableCell>
                  <TableCell >{t.Ticket}</TableCell>
                  <TableCell sx={{ p: 1 }}>{new Date(t.Time).toLocaleString()}</TableCell>
                  <TableCell sx={{ p: 1 }}>{t.Type}</TableCell>
                  <TableCell sx={{ p: 1 }}>{t.Volume}</TableCell>
                  <TableCell sx={{ p: 1 }}>{t['Price(Open)']}</TableCell>
                  <TableCell sx={{ p: 1 }}>{t['S/L']}</TableCell>
                  <TableCell sx={{ p: 1 }}>{t['T/P']}</TableCell>
                  <TableCell sx={{ p: 1 }}>{t['Price(Current)']}</TableCell>
                  <TableCell sx={{ p: 1 }}>{t.Profit}</TableCell>
                </TableRow>
              )) : (
                <TableRow>
                  <TableCell colSpan={10} sx={{ p: 2, textAlign: 'center', color: '#666' }}>
                    No trades to display
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </Box>

      </Paper>
    </Box>
  );
};
