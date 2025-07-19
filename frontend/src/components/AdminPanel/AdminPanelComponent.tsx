import { Box, Button, Paper, Typography } from "@mui/material";
import { useEffect, useState } from "react";

export const AdminPanelComponent = ({ ws }: { ws: WebSocket }) => {
  const [dataFromSocket, setDataFromSocket] = useState<number | null>(null);

  useEffect(() => {

    const handleMessage = (event: MessageEvent) => {
      try {
        const data = JSON.parse(event.data);
        if (data.event === 'send_current_balance') {
          setDataFromSocket(data.value);
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
    };
    if (ws.readyState === WebSocket.OPEN) {
      onOpen();
    } else {
      ws.addEventListener('open', onOpen);
      return () => ws.removeEventListener('open', onOpen);
    }
  }, [ws]);

  return (
    <Box height={200} width={500}>
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
      </Paper>
    </Box>
  );
};
