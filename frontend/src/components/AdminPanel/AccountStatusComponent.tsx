import { Box, Paper, Table, TableBody, TableCell, TableHead, TableRow } from "@mui/material";

export const AccountStatusComponent = ({ allTrades }: { allTrades: any[] }) => {
    return (
        <>
            <Box sx={{
                maxHeight: 'calc(400px - 48px)',
                overflowY: 'auto',
            }}>
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
                                <TableCell sx={{ p: 1 }}>{
                                    t.Profit < 0 ? 
                                    (<><p style={{ color: "red", overflow: "visible " }}>{Number(t.Profit).toFixed(2)}</p> </>) : 
                                    (<><p style={{ color: "blue", overflow: "visible" }}>{Number(t.Profit).toFixed(2)}</p></>)
                                }</TableCell>
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
        </>
    )
}