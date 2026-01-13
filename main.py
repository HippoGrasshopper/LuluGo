import socketio
import json
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import uvicorn

from database import init_db, create_user, get_user_by_username, create_game, get_game
from database import get_waiting_games, get_playing_games, get_history_games, update_game
from game import GameEngine

# ==================== 初始化 ====================

init_db()

sio = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins='*')
app = FastAPI()

# 静态文件
app.mount("/static", StaticFiles(directory="static"), name="static")

application = socketio.ASGIApp(sio, other_asgi_app=app)

# 全局状态管理
active_games = {}  # {game_id: GameEngine实例}
user_sessions = {}  # {sid: user_id}

# ==================== HTTP API ====================

class RegisterRequest(BaseModel):
    username: str

class LoginRequest(BaseModel):
    username: str

class CreateGameRequest(BaseModel):
    user_id: int
    color: str  # 'B' or 'W'

@app.get("/")
async def root():
    return FileResponse("static/login.html")

@app.post("/api/register")
async def register(req: RegisterRequest):
    success, msg, user = create_user(req.username)
    if not success:
        raise HTTPException(status_code=400, detail=msg)
    print(f"[Register] New user registered: {user.username} (ID: {user.id})")
    return {"success": True, "user_id": user.id, "username": user.username}

@app.post("/api/login")
async def login(req: LoginRequest):
    user = get_user_by_username(req.username)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    print(f"[Login] User logged in: {user.username} (ID: {user.id})")
    return {"success": True, "user_id": user.id, "username": user.username}

@app.post("/api/logout")
async def logout(req: LoginRequest):
    # 这里的 LoginRequest 只是为了复用 username 字段, 实际上只需要用户名或ID来打日志
    print(f"[Logout] User logged out: {req.username}")
    return {"success": True}

@app.post("/api/games/create")
async def api_create_game(req: CreateGameRequest):
    game = create_game(req.user_id, req.color)
    return {"success": True, "game_id": game.id}

@app.get("/api/games/waiting")
async def api_waiting_games():
    return {"games": get_waiting_games()}

@app.get("/api/games/playing")
async def api_playing_games():
    return {"games": get_playing_games()}

@app.get("/api/games/history")
async def api_history_games():
    return {"games": get_history_games()}

@app.get("/api/games/{game_id}")
async def api_get_game(game_id: int):
    game = get_game(game_id)
    if not game:
        raise HTTPException(status_code=404, detail="对局不存在")
    
    from database import get_session
    with get_session() as session:
        return {
            "id": game.id,
            "black": game.get_black_username(session),
            "white": game.get_white_username(session),
            "status": game.status,
            "moves": game.get_moves(),
            "current_turn": game.current_turn,
            "winner": game.winner,
            "result": game.result_detail
        }

@app.delete("/api/games/{game_id}")
async def api_delete_game(game_id: int):
    # 简单的管理员删除接口，实际应用应该鉴权
    from database import get_session, Game
    with get_session() as session:
        game = session.get(Game, game_id)
        if game:
            session.delete(game)
            session.commit()
            return {"success": True}
    raise HTTPException(status_code=404, detail="Game not found")

# ==================== Socket.IO ====================

@sio.event
async def connect(sid, environ):
    print(f"[Socket] 用户连接: {sid}")

@sio.event
async def disconnect(sid):
    uid = user_sessions.get(sid, "Unknown")
    print(f"[Socket] 用户断开: {sid} (User: {uid})")
    if sid in user_sessions:
        del user_sessions[sid]

@sio.event
async def auth(sid, data):
    """前端连接后发送用户ID进行认证"""
    user_id = data.get("user_id")
    user_sessions[sid] = user_id
    print(f"[Auth] {sid} -> User {user_id}")

@sio.event
async def join_room(sid, data):
    """加入房间"""
    game_id = data["game_id"]
    user_id = user_sessions.get(sid)
    
    if not user_id:
        await sio.emit("error", {"msg": "未认证"}, to=sid)
        return
    
    game = get_game(game_id)
    if not game:
        await sio.emit("error", {"msg": "对局不存在"}, to=sid)
        return
    
    # 逻辑修正：
    # 1. 如果用户已经是该局玩家 -> 恢复连接
    # 2. 如果用户不是玩家 且 房间是 WAITING 且 有空位 -> 加入
    # 3. 否则 -> 只能是旁观者
    
    is_player = False
    
    # 场景1: 老玩家重连
    if user_id == game.black_player_id or user_id == game.white_player_id:
        is_player = True
    
    # 场景2: 新玩家加入空位
    elif game.status == "WAITING":
        if game.black_player_id is None:
            update_game(game_id, black_player_id=user_id)
            is_player = True
        elif game.white_player_id is None:
            update_game(game_id, white_player_id=user_id)
            is_player = True
        
        # 再次获取以检查状态
        game = get_game(game_id)
        # 如果两边都有人了，不仅当前这个人算加入，整个游戏状态要变成 PLAYING
        if game.black_player_id and game.white_player_id:
            update_game(game_id, status="PLAYING")
            game = get_game(game_id) # 刷新状态

            # 广播通知所有人（包括刚加入的人和已经在房间等待的人）
            from database import get_session
            with get_session() as session:
                black_name = game.get_black_username(session)
                white_name = game.get_white_username(session)
                
            # 发送更新后的状态给所有人
            await sio.emit("board_update", {
                "moves": [], # 刚开始，空
                "turn": "B", 
                "last_move": None,
                "status": "PLAYING",
                # 注意：is_player 需要每个客户端自己判断，这里不传或者传通用值，
                # 但更重要的是更新名字和状态
                "black_id": game.black_player_id,
                "white_id": game.white_player_id,
                "black_name": black_name,
                "white_name": white_name
            }, room=f"game_{game_id}")
            
            await sio.emit("game_start", {"msg": "游戏开始！"}, room=f"game_{game_id}")
            
    # 如果满员了且我也不是玩家，那就是旁观者，is_player = False
    
    # 加入 Socket 房间
    await sio.enter_room(sid, f"game_{game_id}")
    
    # 如果游戏引擎不存在，创建
    if game_id not in active_games:
        active_games[game_id] = GameEngine(initial_moves=game.get_moves())
        print(f"[Room] Loaded game {game_id} from DB into memory.")
    
    engine = active_games[game_id]
    
    # 发送当前状态
    # 获取用户名
    from database import get_session
    black_name = "等待加入..."
    white_name = "等待加入..."
    with get_session() as session:
        black_name = game.get_black_username(session)
        white_name = game.get_white_username(session)

    await sio.emit("board_update", {
        "moves": engine.get_current_stones(),
        "turn": game.current_turn,
        "last_move": engine.moves[-1][1] if engine.moves else None,
        "status": game.status,
        "is_player": is_player, 
        "black_id": game.black_player_id,
        "white_id": game.white_player_id,
        "black_name": black_name,
        "white_name": white_name
    }, to=sid)
    
    print(f"[Room] User {user_id} 加入对局 {game_id} (Player: {is_player})")

@sio.event
async def make_move(sid, data):
    """落子"""
    try:
        game_id = data["game_id"]
        coord = data["coord"]
        user_id = user_sessions.get(sid)
        
        if not user_id:
            await sio.emit("error", {"msg": "认证失效，请刷新页面"}, to=sid)
            return

        game = get_game(game_id)
        if not game or game.status != "PLAYING":
            await sio.emit("error", {"msg": "对局状态不正确"}, to=sid)
            return
        
        # 轮次验证
        if game.current_turn == 'B' and user_id != game.black_player_id:
            await sio.emit("error", {"msg": "不是你的回合"}, to=sid)
            return
        if game.current_turn == 'W' and user_id != game.white_player_id:
            await sio.emit("error", {"msg": "不是你的回合"}, to=sid)
            return
        
        # 内存状态恢复
        if game_id not in active_games:
            print(f"[Recover] Reloading game {game_id} engine")
            active_games[game_id] = GameEngine(initial_moves=game.get_moves())

        engine = active_games[game_id]
        success, error_msg = engine.play_move(game.current_turn, coord)
        
        if not success:
            await sio.emit("error", {"msg": error_msg}, to=sid)
            return
        
        # 更新数据库
        next_turn = 'W' if game.current_turn == 'B' else 'B'
        update_game(game_id, moves_json=json.dumps(engine.moves), current_turn=next_turn)
        
        print(f"[Move] Game {game_id}: {game.current_turn} plays {coord}. Next: {next_turn}")

        # 广播给房间所有人 (不包含 is_player，因为这是静态身份)
        await sio.emit("board_update", {
            "moves": engine.get_current_stones(),
            "turn": next_turn,
            "last_move": coord,
            "status": "PLAYING"
        }, room=f"game_{game_id}")
        
    except Exception as e:
        print(f"[Error] make_move error: {str(e)}")
        await sio.emit("error", {"msg": f"系统错误: {str(e)}"}, to=sid)

@sio.event
async def undo_game(sid, data):
    """悔棋"""
    game_id = data["game_id"]
    engine = active_games.get(game_id)
    
    if not engine:
        return
    
    success, msg = engine.undo_move()
    if success:
        game = get_game(game_id)
        next_turn = 'B' if len(engine.moves) % 2 == 0 else 'W'
        update_game(game_id, moves_json=json.dumps(engine.moves), current_turn=next_turn)
        
        await sio.emit("board_update", {
            "moves": engine.get_current_stones(),
            "turn": next_turn,
            "last_move": engine.moves[-1][1] if engine.moves else None,
            "status": "PLAYING"
        }, room=f"game_{game_id}")

@sio.event
async def resign_game(sid, data):
    """认输"""
    game_id = data["game_id"]
    user_id = user_sessions.get(sid)
    game = get_game(game_id)
    
    if user_id == game.black_player_id:
        winner = 'W'
        result = "W+Resign"
    else:
        winner = 'B'
        result = "B+Resign"
    
    update_game(game_id, status="ENDED", winner=winner, result_detail=result)
    
    await sio.emit("game_over", {
        "winner": winner,
        "result": result
    }, room=f"game_{game_id}")
    
    # 清理内存
    if game_id in active_games:
        del active_games[game_id]

# ==================== AI Logic ====================
from ai import ai_engine

@sio.event
async def estimate_score(sid, data):
    """请求 AI 形势判断"""
    game_id = data.get("game_id")
    # 如果没传 moves，就用当前游戏状态
    if game_id and game_id in active_games:
        moves = active_games[game_id].moves
    else:
        moves = data.get("moves", [])
        
    import asyncio
    # 需要获取 ownership
    result = await asyncio.to_thread(ai_engine.analyze, moves, max_visits=100)
    
    score = result["lead"]
    formatted = f"{'黑' if score > 0 else '白'}+{abs(score):.1f}"
    
    # 只需要返回 score 和 ownership 用于渲染
    return {
        "score": formatted, 
        "lead": score,
        "ownership": result.get("ownership", [])
    }

@sio.event
async def request_counting(sid, data):
    """请求点目"""
    game_id = data.get("game_id") # Fix: use .get for safety, though frontend sends it
    # 转发给房间里的其他人 (主要是对手)
    print(f"Processing counting request from {sid} for game {game_id}")
    await sio.emit("counting_requested", {}, room=f"game_{game_id}", skip_sid=sid)

@sio.event
async def accept_counting(sid, data):
    """接受点目，直接结算"""
    game_id = data["game_id"]
    engine = active_games.get(game_id)
    
    # 尝试从 DB 恢复 moves 如果内存里没有 (不应该，因为 playing 肯定在内存)
    if not engine:
        return
        
    import asyncio
    # 使用 AI 进行终局数子
    result = await asyncio.to_thread(ai_engine.analyze, engine.moves, max_visits=800)
    score = result["lead"]
    winner = 'B' if score > 0 else 'W'
    res_str = f"{winner}+{abs(score):.1f}"
    
    # 更新数据库结束游戏
    update_game(game_id, status="ENDED", winner=winner, result_detail=res_str)
    
    await sio.emit("game_over", {
        "winner": winner,
        "result": res_str,
        "reason": "双方便协点目结果"
    }, room=f"game_{game_id}")
    
    if game_id in active_games:
        del active_games[game_id]

# ==================== 启动 ====================

if __name__ == "__main__":
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        local_ip = s.getsockname()[0]
        s.close()
        print(f"========================================")
        print(f">>> 电脑访问: http://localhost:8000")
        print(f">>> 手机访问: http://{local_ip}:8000")
        print(f"========================================")
    except:
        print("无法获取局域网IP")
        
    # 禁止 access log 以减少噪音
    uvicorn.run(application, host="0.0.0.0", port=8000, access_log=False)
