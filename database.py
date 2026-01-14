from sqlmodel import SQLModel, Field, create_engine, Session, select
from datetime import datetime
from typing import Optional
import json

# ==================== 数据模型 ====================

class User(SQLModel, table=True):
    """用户表"""
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(unique=True, index=True)
    created_at: datetime = Field(default_factory=datetime.now)

class Game(SQLModel, table=True):
    """对局表"""
    id: Optional[int] = Field(default=None, primary_key=True)
    black_player_id: Optional[int] = Field(default=None, foreign_key="user.id")
    white_player_id: Optional[int] = Field(default=None, foreign_key="user.id")
    
    # 状态机: WAITING, PLAYING, ADJOURNED, ENDED
    status: str = Field(default="WAITING")
    
    current_turn: str = Field(default="B")  # 'B' or 'W'
    moves_json: str = Field(default="[]")   # JSON string of moves
    ai_winrates_json: str = Field(default="[]") # JSON string of AI winrates per move

    winner: Optional[str] = None  # 'B', 'W', 'Draw'
    result_detail: Optional[str] = None  # "B+Resign", "W+3.5"
    
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    
    # 辅助方法
    def get_moves(self):
        return json.loads(self.moves_json)
    
    def set_moves(self, moves):
        self.moves_json = json.dumps(moves)
    
    def get_ai_winrates(self):
        try:
            return json.loads(self.ai_winrates_json)
        except (json.JSONDecodeError, TypeError):
            return []

    def set_ai_winrates(self, winrates):
        self.ai_winrates_json = json.dumps(winrates)

    def get_black_username(self, session):
        if self.black_player_id:
            user = session.get(User, self.black_player_id)
            return user.username if user else "等待中"
        return "等待中"
    
    def get_white_username(self, session):
        if self.white_player_id:
            user = session.get(User, self.white_player_id)
            return user.username if user else "等待中"
        return "等待中"

# ==================== 数据库初始化 ====================

DATABASE_URL = "sqlite:///lulugo.db"
engine = create_engine(DATABASE_URL, echo=False)

def init_db():
    SQLModel.metadata.create_all(engine)
    print("[Database] 数据库初始化完成")

def get_session():
    return Session(engine)

# ==================== CRUD 操作 ====================

def create_user(username: str) -> tuple[bool, str, Optional[User]]:
    """创建用户"""
    with get_session() as session:
        # 检查重复
        existing = session.exec(select(User).where(User.username == username)).first()
        if existing:
            return False, "用户名已存在", None
        
        user = User(username=username)
        session.add(user)
        session.commit()
        session.refresh(user)
        return True, "注册成功", user

def get_user_by_username(username: str) -> Optional[User]:
    """通过用户名获取用户"""
    with get_session() as session:
        return session.exec(select(User).where(User.username == username)).first()

def get_user_by_id(user_id: int) -> Optional[User]:
    """通过ID获取用户"""
    with get_session() as session:
        return session.get(User, user_id)

def create_game(creator_id: int, creator_color: str) -> Game:
    """创建对局
    
    Args:
        creator_id: 创建者用户ID
        creator_color: 'B' (执黑), 'W' (执白), '?' (猜先/随机)
    """
    with get_session() as session:
        game = Game()
        if creator_color == 'B':
            game.black_player_id = creator_id
        elif creator_color == 'W':
            game.white_player_id = creator_id
        else:
            # 猜先模式：暂时先不管黑白，或者随机分配。
            # 不，最简单的做法是：随机分配。
            import random
            is_black = random.choice([True, False])
            if is_black:
                game.black_player_id = creator_id
            else:
                game.white_player_id = creator_id
        
        session.add(game)
        session.commit()
        session.refresh(game)
        return game

def get_game(game_id: int) -> Optional[Game]:
    """获取对局"""
    with get_session() as session:
        return session.get(Game, game_id)

def get_waiting_games():
    """获取所有等待中的对局"""
    with get_session() as session:
        games = session.exec(select(Game).where(Game.status == "WAITING")).all()
        return [
            {
                "id": g.id,
                "black": g.get_black_username(session),
                "white": g.get_white_username(session),
                "black_id": g.black_player_id, # 前端需要知道哪个位置是空的
                "white_id": g.white_player_id, 
                "status": g.status,
                "created_at": g.created_at.strftime("%Y-%m-%d %H:%M")
            }
            for g in games
        ]

def get_playing_games():
    """获取所有进行中的对局"""
    with get_session() as session:
        games = session.exec(
            select(Game).where(Game.status.in_(["PLAYING", "ADJOURNED"]))
        ).all()
        return [
            {
                "id": g.id,
                "black": g.get_black_username(session),
                "white": g.get_white_username(session),
                "status": g.status,
                "updated_at": g.updated_at.strftime("%Y-%m-%d %H:%M")
            }
            for g in games
        ]

def get_history_games():
    """获取所有已结束的对局"""
    with get_session() as session:
        games = session.exec(
            select(Game).where(Game.status == "ENDED").order_by(Game.updated_at.desc())
        ).all()
        return [
            {
                "id": g.id,
                "black": g.get_black_username(session),
                "white": g.get_white_username(session),
                "status": "FINISHED", # 明确返回状态，前端admin需要
                "winner": g.winner,
                "result": g.result_detail,
                "updated_at": g.updated_at.strftime("%Y-%m-%d %H:%M")
            }
            for g in games
        ]

def update_game(game_id: int, **kwargs):
    """更新对局信息"""
    with get_session() as session:
        game = session.get(Game, game_id)
        if game:
            for key, value in kwargs.items():
                setattr(game, key, value)
            game.updated_at = datetime.now()
            session.commit()
