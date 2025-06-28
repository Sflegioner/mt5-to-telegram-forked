import { Box, Button, Paper, Typography } from "@mui/material";
import { useEffect, useState } from "react";

export const AdminPanalComponent = ({ ws }: { ws: WebSocket }) => {
    const [dataFromSockets, setDataFromSocket]=useState();

    const takeCurrentBalance = () => {
        ws.send(JSON.stringify({ action: "take_current_balance" }));
    };
    ws.onmessage = (event) =>{
        const data = JSON.parse(event.data);
        if(data.event === 'send_current_balance'){
            setDataFromSocket(data.value);
        }
    }

    useEffect(() => {
        takeCurrentBalance();
    }, []);


    useEffect(() => {
        if (ws.readyState === WebSocket.OPEN) {
            takeCurrentBalance();
        } else {
            const handleOpen = () => {
                takeCurrentBalance();
            };

            ws.addEventListener('open', handleOpen);

            return () => {
                ws.removeEventListener('open', handleOpen);
            };
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
                }}>
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
                    <Button style={{ height: 20 }}>
                        Account status
                    </Button>
                    {dataFromSockets??"No Data" }💶
                    <Box />
                </Box>
            </Paper>
        </Box>
    );
};
