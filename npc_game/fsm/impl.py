"""
fsm/impl.py — 実装層
protocol.py で定義されたインターフェースのみを実装し、業務オーケストレーションロジックは含まない。
"""
from __future__ import annotations
import json, uuid, pathlib
import anthropic

from .protocol import (
    IScenario, IFSM, IJudge, IStore,
    Step, Character, AdvanceResult, JudgeResult,
)


# ── IScenario ─────────────────────────────────────────────

class JsonScenario:
    """JSON ファイルからシナリオを読み込み、IScenario を実装するクラス。"""

    _META = {
        "DaVinci":      {"role": "ShareHouse协调者", "emoji": "🎨", "color": "#e74c3c"},
        "Donatello":    {"role": "工程系研究生",      "emoji": "🔧", "color": "#3498db"},
        "Michelangelo": {"role": "雕塑系学生",        "emoji": "🖌️", "color": "#f39c12"},
        "Raffaello":    {"role": "视觉艺术专业",      "emoji": "🌸", "color": "#9b59b6"},
    }

    def __init__(self, path: str = "fsm/multi_npc_scenario_zh.json"):
        """
        機能：指定パスの JSON シナリオファイルを読み込み、キャラクターと日程データを初期化する。
        入力：path（シナリオ JSON ファイルパス）
        出力：なし
        """
        raw = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
        self._chars: dict = raw["characters"]
        self._days: dict  = raw["days"]

    def _flatten(self, day: str) -> list[dict]:
        """
        機能：指定日のシナリオデータをフラットなステップリストに展開する。
        入力：day（日付文字列、例: "Day 1"）
        出力：speaker, state, content, mbti_focus を含む dict のリスト
        """
        flat = []
        for entry in self._days.get(day, []):
            for s in entry.get("state_list", []):
                flat.append({
                    "speaker":    entry["speaker"],
                    "state":      s["state"],
                    "content":    s["content"],
                    "mbti_focus": s.get("mbti_focus", ""),
                })
        return flat

    def get_step(self, day: str, index: int) -> Step | None:
        """
        機能：指定日のインデックスに対応する FSM ステップを返す。
        入力：day（日付文字列）、index（ステップインデックス）
        出力：Step オブジェクト、または範囲外の場合は None
        """
        steps = self._flatten(day)
        if index >= len(steps):
            return None
        s = steps[index]
        return Step(
            day=day, state=s["state"], speaker=s["speaker"],
            content=s["content"], mbti_focus=s["mbti_focus"],
        )

    def get_character(self, name: str) -> Character:
        """
        機能：指定名のキャラクター情報を返す。
        入力：name（NPC 名前文字列）
        出力：Character データクラス（name, role, personality, few_shots, emoji, color）
        """
        c    = self._chars[name]
        meta = self._META.get(name, {})
        return Character(
            name=name,
            role=meta.get("role", ""),
            personality=c.get("personality", ""),
            few_shots=c.get("few_shots", []),
            emoji=meta.get("emoji", "🙂"),
            color=meta.get("color", "#888"),
        )

    def days(self) -> list[str]:
        """
        機能：シナリオに含まれる全日程の一覧を返す。
        入力：なし
        出力：日付文字列のリスト（例: ["Day 1", "Day 2", ...]）
        """
        return list(self._days.keys())


# ── IFSM ──────────────────────────────────────────────────

class ShareHouseFSM:
    """純粋な状態機械。IFSM を実装し、LLM を一切呼び出さない。"""

    def __init__(self, scenario: IScenario, day: str,
                 index: int = 0, history: list[dict] | None = None):
        """
        機能：指定日・インデックス・履歴で FSM を初期化する。
        入力：scenario（IScenario 実装）、day（開始日）、index（開始ステップインデックス）、
              history（過去の会話履歴、省略時は空リスト）
        出力：なし
        """
        self._sc      = scenario
        self._day     = day
        self._idx     = index
        self._history: list[dict] = history or []

    @property
    def current_step(self) -> Step | None:
        """
        機能：現在の FSM ステップを返す。
        入力：なし
        出力：現在の Step オブジェクト、またはシナリオ終端の場合は None
        """
        return self._sc.get_step(self._day, self._idx)

    @property
    def turn_history(self) -> list[dict]:
        """
        機能：現在のターン履歴のコピーを返す。
        入力：なし
        出力：{"role": ..., "content": ...} 形式の dict リスト
        """
        return list(self._history)

    def add_turn(self, role: str, content: str) -> None:
        """
        機能：会話ターンを履歴に追加する。
        入力：role（"user" または "assistant"）、content（発話テキスト）
        出力：なし
        """
        self._history.append({"role": role, "content": content})

    def advance(self) -> AdvanceResult:
        """
        機能：FSM を次のステップへ進め、進行結果を返す。日程内に次ステップがなければ翌日へ移行する。
        入力：なし
        出力：AdvanceResult（event, next_step, next_character）
        """
        self._idx += 1
        self._history = []
        step = self._sc.get_step(self._day, self._idx)
        if step:
            return AdvanceResult("next_state", step,
                                 self._sc.get_character(step.speaker))
        days = self._sc.days()
        di   = days.index(self._day)
        if di + 1 < len(days):
            self._day = days[di + 1]
            self._idx = 0
            step = self._sc.get_step(self._day, 0)
            return AdvanceResult("next_day", step,
                                 self._sc.get_character(step.speaker))
        return AdvanceResult("game_complete")

    def dump(self) -> dict:
        """
        機能：FSM の現在状態をシリアライズ可能な dict に変換する。
        入力：なし
        出力：day, index, history を含む dict
        """
        return {"day": self._day, "index": self._idx, "history": self._history}

    @classmethod
    def load(cls, scenario: IScenario, data: dict) -> "ShareHouseFSM":
        """
        機能：dump() で生成した dict から FSM インスタンスを復元する。
        入力：scenario（IScenario 実装）、data（dump() の出力 dict）
        出力：ShareHouseFSM インスタンス
        """
        return cls(scenario, data["day"], data["index"], data.get("history", []))


# ── IJudge ────────────────────────────────────────────────

class LLMJudge:
    """軽量モデルでユーザーが質問に十分に答えたか判定する。IJudge を実装。"""

    def __init__(self, client: anthropic.Anthropic,
                 model: str = "claude-haiku-4-5-20251001"):
        """
        機能：Anthropic クライアントと使用モデルを設定して初期化する。
        入力：client（Anthropic クライアント）、model（使用モデル名）
        出力：なし
        """
        self._client = client
        self._model  = model

    def judge(self, step: Step, user_message: str) -> JudgeResult:
        """
        機能：ユーザーメッセージが現在のステップの質問に実質的に回答しているか LLM で判定する。
        入力：step（現在の FSM ステップ）、user_message（ユーザー入力テキスト）
        出力：JudgeResult（answered: bool, reason: str）
        """
        if len(user_message.strip()) < 5:
            return JudgeResult(False, "too short")
        try:
            msg = self._client.messages.create(
                model=self._model,
                max_tokens=60,
                system='判断用户是否实质性地回答了问题。只输出JSON：{"answered":true/false,"reason":"简短原因"}',
                messages=[{"role": "user",
                           "content": f"问题：{step.content}\n用户：{user_message}"}],
            )
            r = json.loads(msg.content[0].text)
            return JudgeResult(bool(r["answered"]), r.get("reason", ""))
        except Exception as e:
            return JudgeResult(len(user_message.strip()) > 10, f"fallback:{e}")


class RuleJudge:
    """LLM を使わない純粋なルール判定。テスト用。IJudge を実装。"""

    def judge(self, step: Step, user_message: str) -> JudgeResult:
        """
        機能：ユーザーメッセージの文字数が 8 文字超かどうかで回答十分性を判定する。
        入力：step（現在の FSM ステップ、本実装では未使用）、user_message（ユーザー入力テキスト）
        出力：JudgeResult（answered: bool, reason: "rule:length>8"）
        """
        ok = len(user_message.strip()) > 8
        return JudgeResult(ok, "rule:length>8")


# ── IStore ────────────────────────────────────────────────

class MemoryStore:
    """インメモリストレージ。IStore を実装。"""

    def __init__(self):
        """
        機能：空の辞書でインメモリストアを初期化する。
        入力：なし
        出力：なし
        """
        self._data: dict[str, dict] = {}

    def get(self, session_id: str) -> dict | None:
        """
        機能：指定セッション ID のデータを返す。
        入力：session_id（セッション識別子）
        出力：保存済みの dict、または存在しない場合は None
        """
        return self._data.get(session_id)

    def save(self, session_id: str, data: dict) -> None:
        """
        機能：指定セッション ID にデータを保存する。
        入力：session_id（セッション識別子）、data（保存する dict）
        出力：なし
        """
        self._data[session_id] = data

    def new_id(self) -> str:
        """
        機能：新しいユニークなセッション ID を生成して返す。
        入力：なし
        出力：UUID 文字列
        """
        return str(uuid.uuid4())


class RedisStore:
    """Redis ストレージ。本番環境用。IStore を実装。"""

    def __init__(self, url: str = "redis://localhost:6379", ttl: int = 86400):
        """
        機能：Redis クライアントを初期化し、TTL を設定する。
        入力：url（Redis 接続 URL）、ttl（データ有効期間、秒単位）
        出力：なし
        """
        import redis
        self._r   = redis.from_url(url)
        self._ttl = ttl

    def get(self, session_id: str) -> dict | None:
        """
        機能：Redis から指定セッション ID のデータを取得して返す。
        入力：session_id（セッション識別子）
        出力：デシリアライズ済みの dict、または存在しない場合は None
        """
        raw = self._r.get(f"fsm:{session_id}")
        return json.loads(raw) if raw else None

    def save(self, session_id: str, data: dict) -> None:
        """
        機能：指定セッション ID のデータを TTL 付きで Redis に保存する。
        入力：session_id（セッション識別子）、data（保存する dict）
        出力：なし
        """
        self._r.setex(
            f"fsm:{session_id}", self._ttl,
            json.dumps(data, ensure_ascii=False),
        )

    def new_id(self) -> str:
        """
        機能：新しいユニークなセッション ID を生成して返す。
        入力：なし
        出力：UUID 文字列
        """
        return str(uuid.uuid4())
