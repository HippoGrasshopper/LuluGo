import random
import time
import copy
import subprocess
import json
import os
import threading

# Paths relative to the workspace root
KATAGO_EXE = os.path.join("katago", "katago.exe")
KATAGO_CONFIG = os.path.join("katago", "analysis_example.cfg")
KATAGO_MODEL = os.path.join("katago", "model.bin.gz")

class KataGoWrapper:
    def __init__(self):
        self.lock = threading.Lock()
        self.process = None
        # Start automatically
        self._start_process()

    def _start_process(self):
        if not os.path.exists(KATAGO_EXE):
            print(f"[KataGo] Error: Executable not found at {KATAGO_EXE}")
            return
            
        cmd = [
            KATAGO_EXE,
            "analysis",
            "-model", KATAGO_MODEL,
            "-config", KATAGO_CONFIG
        ]
        
        print(f"[KataGo] Starting engine: {' '.join(cmd)}")
        try:
            self.process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=os.getcwd()
            )
            # Start a thread to read stderr to prevent buffer fill up
            self.stderr_thread = threading.Thread(target=self._read_stderr, daemon=True)
            self.stderr_thread.start()
        except Exception as e:
            print(f"[KataGo] Failed to start: {e}")

    def _read_stderr(self):
        while self.process and self.process.poll() is None:
            try:
                line = self.process.stderr.readline()
                if line:
                    # Optional: Print logs if needed
                    # print(f"[KataGo Log] {line.strip()}")
                    pass
                else:
                    time.sleep(0.1)
            except:
                break
    
    def close(self):
        if self.process:
            self.process.terminate()
            self.process = None

    def analyze(self, moves, max_visits=500):
        """
        moves: list of [color, coord] like [["B", "Q16"], ["W", "D4"]]
        """
        if not self.process:
            print("[KataGo] Engine not running, attempting restart...")
            self._start_process()
            if not self.process:
                return {"error": "KataGo engine unavailable"}

        # Prepare Query
        query_id = f"q_{int(time.time()*1000)}"
        query = {
            "id": query_id,
            "moves": moves,
            "rules": "chinese",
            "komi": 7.5,
            "boardXSize": 19,
            "boardYSize": 19,
            "includeOwnership": True,
            "maxVisits": max_visits
        }
        
        result = None
        
        with self.lock:
            try:
                # Send Query
                input_str = json.dumps(query) + "\n"
                self.process.stdin.write(input_str)
                self.process.stdin.flush()
                
                # Read Response
                while True:
                    line = self.process.stdout.readline()
                    if not line:
                        print("[KataGo] Engine process ended unexpected.")
                        self.process = None
                        break
                        
                    try:
                        resp = json.loads(line)
                        if resp.get("id") == query_id:
                            result = resp
                            break
                    except json.JSONDecodeError:
                        print(f"[KataGo] parse error: {line.strip()}")
            except Exception as e:
                print(f"[KataGo] IO Error: {e}")
                self.process = None
                
        if not result:
            return {"error": "No response from KataGo"}

        if "error" in result:
             return {"error": result["error"]}
             
        return self._format_response(result)

    def _format_response(self, data):
        # 1. Ownership: Flattened list -> 19x19 grid (row-major)
        raw_ownership = data.get("ownership", [])
        formatted_ownership = []
        if raw_ownership and len(raw_ownership) == 361:
             for r in range(19):
                 row_start = r * 19
                 row_data = raw_ownership[row_start : row_start + 19]
                 formatted_ownership.append(row_data)
        
        # 2. Move Infos
        move_infos = []
        for info in data.get("moveInfos", []):
            move_infos.append({
                "move": info["move"],
                "winrate": info["winrate"],
                "scoreLead": info.get("scoreLead", 0),
                "order": info["order"],
                "pv": info.get("pv", []),
                "visits": info.get("visits", 0)
            })
            
        # 3. Root Info
        root_info = data.get("rootInfo", {})
        # Ensure winrate is float if needed
        
        return {
            "ownership": formatted_ownership,
            "moveInfos": move_infos, 
            "rootInfo": root_info
        }

# ai_engine = MockKataGoWrapper()
ai_engine = KataGoWrapper()
