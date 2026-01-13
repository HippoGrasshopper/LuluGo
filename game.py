import copy
from sgfmill import boards

class GameEngine:
    """游戏引擎 - 无状态单例，每个房间一个实例"""
    
    def __init__(self, size=19, initial_moves=None):
        self.size = size
        self.board = boards.Board(size)
        self.history_hashes = set()
        self.moves = initial_moves or []
        
        self._record_state()
        
        # 如果有初始棋谱，快速恢复（优化：仅在最后计算Hash，跳过中间步骤以加速加载）
        if initial_moves:
            for color_str, coord in initial_moves:
                row, col = self._gtp_to_coords(coord)
                color = 'b' if color_str == 'B' else 'w'
                self.board.play(row, col, color)
            self._record_state()

    def reset(self):
        self.board = boards.Board(self.size)
        self.history_hashes = set()
        self.moves = []
        self._record_state()

    def _get_board_fingerprint(self, board_obj):
        state = []
        for r in range(self.size):
            for c in range(self.size):
                color = board_obj.get(r, c)
                state.append(color if color else '.')
        return tuple(state)

    def _record_state(self):
        fingerprint = self._get_board_fingerprint(self.board)
        self.history_hashes.add(fingerprint)

    def _gtp_to_coords(self, gtp_vertex):
        gtp_vertex = gtp_vertex.upper()
        col_str = gtp_vertex[0]
        row_str = gtp_vertex[1:]
        if col_str >= 'I':
            col = ord(col_str) - ord('A') - 1
        else:
            col = ord(col_str) - ord('A')
        row = int(row_str) - 1
        return row, col

    def _coords_to_gtp(self, row, col):
        col_str = "ABCDEFGHJKLMNOPQRST"[col]
        row_str = str(row + 1)
        return f"{col_str}{row_str}"

    def play_move(self, color_str, gtp_coord):
        try:
            row, col = self._gtp_to_coords(gtp_coord)
            color = 'b' if color_str == 'B' else 'w'
            
            if self.board.get(row, col) is not None:
                return False, "此处已有棋子"

            temp_board = copy.deepcopy(self.board)
            
            try:
                temp_board.play(row, col, color)
            except ValueError:
                return False, "禁入点 (自杀)"

            new_fingerprint = self._get_board_fingerprint(temp_board)
            if new_fingerprint in self.history_hashes:
                return False, "非法落子：全局同形禁手 (打劫/Ko)"

            self.board = temp_board
            self.moves.append([color_str, gtp_coord]) 
            self._record_state()
            
            return True, None

        except Exception as e:
            return False, f"引擎错误: {str(e)}"
        
    def undo_move(self):
        if not self.moves:
            return False, "无棋可悔"

        self.moves.pop()
        self.board = boards.Board(self.size)
        self.history_hashes = set()
        self._record_state() 

        try:
            for color_str, coord in self.moves:
                row, col = self._gtp_to_coords(coord)
                color = 'b' if color_str == 'B' else 'w'
                self.board.play(row, col, color)
                self._record_state()
        except Exception as e:
            print(f"Undo 严重错误: {e}")
            self.reset()
            return True, "历史数据损坏，已重置棋盘"
            
        return True, None

    def get_current_stones(self):
        stones = []
        for row in range(self.size):
            for col in range(self.size):
                color = self.board.get(row, col)
                if color:
                    c_str = "B" if color == 'b' else "W"
                    coord = self._coords_to_gtp(row, col)
                    stones.append([c_str, coord])
        return stones

    def get_history(self):
        return self.moves
