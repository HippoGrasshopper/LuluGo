import random
import time

class MockKataGoWrapper:
    """
    一个伪造的 AI 引擎，用于开发测试。
    不需要真实的 Katago 可执行文件。
    返回符合前端预期的假数据。
    """
    def __init__(self):
        print("[MockAI] Using Mock API for KataGo. GPU not required.")

    def analyze(self, moves, max_visits=500):
        """
        模拟分析请求
        moves: list of [color, coord] like [["B", "Q16"], ["W", "D4"]]
        """
        # 模拟计算延迟 (0.5s)
        time.sleep(0.5)
        
        # 1. 简单判断当前手
        current_turn = "B" if len(moves) % 2 == 0 else "W"
        
        # 2. 生成伪造的胜率 (黑棋胜率)
        # 随手数增加，产生一些随机波动
        random.seed(len(moves) + int(time.time())) 
        base_winrate = 0.5
        noise = random.uniform(-0.1, 0.1)
        black_winrate = base_winrate + noise
        
        # 限制在 0-1 之间
        black_winrate = max(0.01, min(0.99, black_winrate))
        
        # 3. 生成伪造的目数领先 (正为黑赢)
        black_lead = (black_winrate - 0.5) * 30 # 粗略关联一下
        
        # 4. 生成几个推荐选点
        # 为了不推荐非法点，我们需要知道哪里是空的。
        # 这里简单做：随机选几个合法的GTP坐标。
        possible_moves = self._get_random_valid_moves(moves, count=3)
        
        recommendations = []
        for idx, m in enumerate(possible_moves):
            # 第一手推荐最好，以此递减
            # 如果当前是黑棋，第一手让胜率变高；如果是白棋，第一手让黑棋胜率变低 (即白棋胜率变高)
            improvement = (idx * 0.05)
            if current_turn == "B":
                move_winrate = black_winrate + (0.1 - improvement) # 推荐的好棋会提高胜率
            else:
                move_winrate = black_winrate - (0.1 - improvement) # 推荐的好棋会降低黑棋胜率
                
            # 确保属于 0-1
            move_winrate = max(0.01, min(0.99, move_winrate))
            
            # 生成 10 步后续演化 (PV)
            pv = self._generate_fake_pv(m, current_turn, moves)
            
            recommendations.append({
                "move": m,
                "winrate": move_winrate, # 黑棋胜率
                "scoreLead": black_lead if current_turn == "B" else -black_lead,
                "pv": pv 
            })
        
        # 模拟所有权 (Ownership)
        # 19x19 数组，-1 (白) 到 1 (黑)
        # 用于前端渲染形势判断网格
        ownership = []
        for _ in range(19):
            row = []
            for _ in range(19):
                # 随机生成 -1 ~ 1
                val = random.uniform(-1, 1)
                # 两极化处理，让它看起来像真的确定的领地
                if abs(val) > 0.3:
                    val = 1 if val > 0 else -1
                else:
                    val = 0 # 中立/争夺
                row.append(val)
            ownership.append(row)
            
        return {
            "winrate": black_winrate, # 总是黑棋胜率
            "lead": black_lead,       # 总是黑棋领先
            "recommendations": recommendations, # 推荐列表
            "visits": max_visits,
            "ownership": ownership # 新增所有权数据
        }

    def _get_random_valid_moves(self, history_moves, count=3):
        """生成随机合法棋步（不与历史重复）"""
        taken = set(m[1] for m in history_moves)
        candidates = []
        cols = "ABCDEFGHJKLMNOPQRST"
        rows = range(1, 20)
        
        attempts = 0
        while len(candidates) < count and attempts < 100:
            c = random.choice(cols)
            r = random.choice(rows)
            coord = f"{c}{r}"
            if coord not in taken and coord not in candidates:
                candidates.append(coord)
            attempts += 1
            
        return candidates

    def _generate_fake_pv(self, first_move, first_color, history):
        """生成 10 步假 PV"""
        pv = [first_move]
        
        # 为了避免 PV 里有重复棋子，我们需要记录
        temp_taken = set(m[1] for m in history)
        temp_taken.add(first_move)
        
        next_color = "W" if first_color == "B" else "B"
        
        for _ in range(9):
            candidates = self._get_random_valid_moves([], count=5) # 生成几个候选
            # 找到一个没走过的
            found = None
            for cand in candidates:
                if cand not in temp_taken:
                    found = cand
                    break
            
            if found:
                pv.append(found)
                temp_taken.add(found)
            
            next_color = "W" if next_color == "B" else "B"
            
        return pv

    def close(self):
        pass

# 全局单例
ai_engine = MockKataGoWrapper()
