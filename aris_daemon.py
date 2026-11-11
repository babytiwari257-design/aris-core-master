import asyncio
import json
import os
import platform
import subprocess
import websockets

PORT = 8765

async def execute_system_command(cmd: str) -> str:
    try:
        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        out = stdout.decode().strip() or stderr.decode().strip()
        return out if out else "Execution complete (no output)."
    except Exception as e:
        return f"Error executing command: {str(e)}"

async def handle_action(action: str, payload: dict) -> dict:
    if action == "ping":
        return {"status": "ok", "message": "ARIS Daemon Connected", "os": platform.system()}
    
    elif action == "launch_app":
        app_name = payload.get("app", "")
        if platform.system() == "Windows":
            subprocess.Popen(["start", app_name], shell=True)
        else:
            subprocess.Popen([app_name], shell=True)
        return {"status": "ok", "message": f"Launched {app_name}"}

    elif action == "run_command":
        cmd = payload.get("command", "")
        output = await execute_system_command(cmd)
        return {"status": "ok", "output": output}

    elif action == "system_telemetry":
        return {
            "status": "ok",
            "os": f"{platform.system()} {platform.release()}",
            "arch": platform.machine(),
            "cpu_cores": os.cpu_count()
        }

    return {"status": "error", "message": "Unknown action"}

async def server_handler(websocket):
    print("◈ ARIS Desktop Daemon: Web client connected.")
    try:
        async for message in websocket:
            try:
                data = json.loads(message)
                action = data.get("action", "")
                payload = data.get("payload", {})
                result = await handle_action(action, payload)
                await websocket.send(json.dumps(result))
            except json.JSONDecodeError:
                await websocket.send(json.dumps({"status": "error", "message": "Invalid JSON"}))
    except websockets.exceptions.ConnectionClosed:
        print("◈ ARIS Desktop Daemon: Client disconnected.")

async def main():
    print(f"▲ ARIS Desktop Automation Daemon active on ws://localhost:{PORT}")
    async with websockets.serve(server_handler, "localhost", PORT):
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())
