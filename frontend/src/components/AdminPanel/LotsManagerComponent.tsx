import {
  Box,
  Typography,
  FormControl,
  FormLabel,
  RadioGroup,
  FormControlLabel,
  Radio,
  Switch,
  Slider,
} from "@mui/material";
import { useState } from "react";

export const LotsManagerComponent = ({ ws }: { ws: WebSocket }) => {
  const [method, setMethod] = useState<"method1" | "method2">("method1");
  const [reinvest, setReinvest] = useState<boolean>(true);
  const [percentage, setPercentage] = useState<number>(1);

  const handleLOTsChange = (_event: Event, value: number | number[]) => {
    if (typeof value === "number") {
      setPercentage(value);
    }
  };

  const sendLotsChange = () => {
    ws.send(
      JSON.stringify({
        action: "set_current_lots",
        value: {
          "method":method,
          "percentage":percentage,
          "reinvest":reinvest,
        },
      })
    );
  };

  return (
    <div style={{ display: "flex", justifyContent: "center" }}>
      <FormControl component="fieldset" sx={{ mb: 2 }}>
        <FormLabel
          component="legend"
          sx={{ color: "#ccc", mb: 1, alignSelf: "center" }}
        >
          Trade Allocation Method:
        </FormLabel>
        <RadioGroup
          value={method}
          onChange={(e) => setMethod(e.target.value as "method1" | "method2")}
        >
          <FormControlLabel
            value="method1"
            control={<Radio sx={{ color: "#90caf9" }} />}
            label={
              <span style={{ color: "#fff" }}>
                Method 1: % (max. 20%) of remaining capital
              </span>
            }
          />
          <Box sx={{ pl: 3 }}>
            <Typography sx={{ color: "#fff" }}>LOTs: {percentage}%</Typography>
            <Slider
              style={{ maxWidth: 200 }}
              value={percentage}
              max={20}
              min={1}
              onChange={handleLOTsChange}
              valueLabelDisplay="auto"
              aria-label="LOTs"
              step={0.1}
              sx={{ color: "#90caf9" }}
            />
          </Box>
          <FormControlLabel
            value="method2"
            control={<Radio sx={{ color: "#90caf9" }} />}
            label={
              <span style={{ color: "#fff" }}>
                Method 2: Fixed % until capital is exhausted
              </span>
            }
          />
        </RadioGroup>
        <FormControlLabel
          control={
            <Switch
              checked={reinvest}
              onChange={(e) => setReinvest(e.target.checked)}
              sx={{ color: "#90caf9" }}
            />
          }
          label={
            <Typography sx={{ color: "#fff" }}>
              Reinvest profit into capital
            </Typography>
          }
        />
        <button onClick={sendLotsChange}>Change LOTs</button>
      </FormControl>
    </div>
  );
};
