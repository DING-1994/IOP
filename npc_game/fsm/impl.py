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
        # スペースを除去して "Day 1" と "Day1" の両方を "Day1" に統一
        self._days: dict = {k.replace(" ", ""): v for k, v in raw["days"].items()}

    def _flatten(self, day: str) -> list[dict]:
        """
        機能：指定日のシナリオデータをフラットなステップリストに展開する。
              新フォーマット（flat + active_speaker）と旧フォーマット（state_list）の両方に対応。
              narrator エントリーも含める（FSM 側でスキップ・収集する）。
        入力：day（日付文字列、例: "Day1"）
        出力：speaker, content, focus, instruction, state を含む dict のリスト
        """
        flat = []
        for entry in self._days.get(day.replace(" ", ""), []):
            if "active_speaker" in entry:
                # 新フォーマット：1エントリー = 1ステップ（フラット構造）
                speaker = entry["active_speaker"]
                focus   = entry.get("focus", "")
                flat.append({
                    "speaker":            speaker,
                    "content":            entry.get("content", ""),
                    "focus":              focus,
                    "instruction":        entry.get("instruction", ""),
                    "state":              focus,
                    "night_mode":         entry.get("nightMode", False),
                    "q_no":               entry.get("q_no"),
                    "corresponding_item": entry.get("corresponding_item", ""),
                })
            else:
                # 旧フォーマット：state_list ネスト構造
                for s in entry.get("state_list", []):
                    focus = s.get("mbti_focus", "")
                    flat.append({
                        "speaker":     entry["speaker"],
                        "content":     s["content"],
                        "focus":       focus,
                        "instruction": s.get("instruction", ""),
                        "state":       s.get("state", focus),
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
            day=day,
            speaker=s["speaker"],
            content=s["content"],
            focus=s.get("focus", ""),
            instruction=s.get("instruction", ""),
            state=s.get("state", ""),
            capture=s.get("capture", []),
            corresponding_item=s.get("corresponding_item", ""),
            night_mode=s.get("night_mode", False),
            q_no=s.get("q_no"),
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
        機能：シナリオに含まれる全日程の一覧を返す（スペース除去済みキー）。
        入力：なし
        出力：日付文字列のリスト（例: ["Day1", "Day2", ...]）
        """
        return list(self._days.keys())


# ── IFSM ──────────────────────────────────────────────────

class ShareHouseFSM:
    """純粋な状態機械。IFSM を実装し、LLM を一切呼び出さない。"""

    def __init__(self, scenario: IScenario, day: str,
                 index: int = 0, history: list[dict] | None = None,
                 npc_histories: dict[str, list[list[dict]]] | None = None,
                 full_history: list[dict] | None = None):
        """
        機能：指定日・インデックス・履歴で FSM を初期化する。
        入力：scenario（IScenario 実装）、day（開始日）、index（開始ステップインデックス）、
              history（現ステップの会話履歴、省略時は空リスト）、
              npc_histories（NPC ごとの過去ステップ履歴、省略時は空 dict）、
              full_history（全ステップ横断の通算履歴、省略時は空リスト）
        出力：なし
        """
        self._sc      = scenario
        self._day     = day
        self._idx     = index
        self._history: list[dict] = history or []
        self._npc_histories: dict[str, list[list[dict]]] = npc_histories or {}
        self._full_history: list[dict] = list(full_history) if full_history else []

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
        turn = {"role": role, "content": content}
        self._history.append(turn)
        step = self.current_step
        entry: dict = {
            **turn,
            "day":     self._day,
            "speaker": step.speaker if (step and role == "assistant") else "user",
        }
        if step and step.q_no is not None:
            entry["q_no"] = step.q_no
            entry["focus"] = step.focus
            entry["item"]  = step.corresponding_item
        self._full_history.append(entry)

    def collect_narrator_lines(self) -> tuple[list[str], bool]:
        """
        機能：現在位置から連続する narrator ステップのテキストを収集し、インデックスを進める。
              narrator ステップは会話履歴に残さない。
        入力：なし
        出力：(narrator テキストのリスト, 収集した narrator 中に night_mode=True があるか)
        """
        lines: list[str] = []
        narrator_night = False
        while True:
            step = self._sc.get_step(self._day, self._idx)
            if step is None or step.speaker != "narrator":
                break
            lines.append(step.content)
            if step.night_mode:
                narrator_night = True
            self._idx += 1
        return lines, narrator_night

    def get_npc_history(self, speaker: str) -> list[dict]:
        """
        機能：指定 NPC の過去ステップ全ターンを連結して返す。ステップ間にセパレーターを挿入し
              Anthropic API の user/assistant 交互制約を維持する。
        入力：speaker（NPC 名前文字列）
        出力：{"role": ..., "content": ...} 形式の dict リスト（空なら []）
        """
        step_histories = self._npc_histories.get(speaker, [])
        if not step_histories:
            return []
        result: list[dict] = []
        for i, step_hist in enumerate(step_histories):
            if i > 0:
                result.append({"role": "user", "content": "（新的一天开始了）"})
            result.extend(step_hist)
        return result

    def advance(self) -> AdvanceResult:
        """
        機能：FSM を次のステップへ進め、進行結果を返す。現ステップの会話履歴を NPC ごとに保存してから
              リセットする。次ステップが narrator なら自動スキップして収集する。
              日程内に次ステップがなければ翌日へ移行する。
        入力：なし
        出力：AdvanceResult（event, next_step, next_character, narrator_lines）
        """
        current = self.current_step
        if current and self._history:
            self._npc_histories.setdefault(current.speaker, []).append(list(self._history))
        self._idx += 1
        self._history = []

        narrator_lines, narrator_night = self.collect_narrator_lines()

        step = self._sc.get_step(self._day, self._idx)
        if step:
            night = narrator_night or step.night_mode
            return AdvanceResult("next_state", step,
                                 self._sc.get_character(step.speaker), narrator_lines, night)
        days = self._sc.days()
        di   = days.index(self._day)
        if di + 1 < len(days):
            self._day = days[di + 1]
            self._idx = 0
            more_lines, more_night = self.collect_narrator_lines()
            narrator_lines += more_lines
            night = narrator_night or more_night
            step = self._sc.get_step(self._day, self._idx)
            if step:
                night = night or step.night_mode
                return AdvanceResult("next_day", step,
                                     self._sc.get_character(step.speaker), narrator_lines, night)
        return AdvanceResult("game_complete", narrator_lines=narrator_lines)

    def dump(self) -> dict:
        """
        機能：FSM の現在状態をシリアライズ可能な dict に変換する。
        入力：なし
        出力：day, index, history, npc_histories, full_history を含む dict
        """
        return {
            "day":           self._day,
            "index":         self._idx,
            "history":       self._history,
            "npc_histories": self._npc_histories,
            "full_history":  self._full_history,
        }

    @classmethod
    def load(cls, scenario: IScenario, data: dict) -> "ShareHouseFSM":
        """
        機能：dump() で生成した dict から FSM インスタンスを復元する。
        入力：scenario（IScenario 実装）、data（dump() の出力 dict）
        出力：ShareHouseFSM インスタンス
        """
        full_history = data.get("full_history") or None
        return cls(
            scenario, data["day"], data["index"],
            data.get("history", []),
            data.get("npc_histories", {}),
            full_history,
        )


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
            capture_hint = ""
            if step.capture:
                capture_hint = f"\n观察维度：{'、'.join(step.capture)}"
            if step.corresponding_item:
                capture_hint += f"\n测量项：{step.corresponding_item}"
            msg = self._client.messages.create(
                model=self._model,
                max_tokens=60,
                system=(
                    '你是行为观察员。判断用户是否对NPC的话语给出了回应（无论正面、负面还是回避）。'
                    '只要用户回复与当前对话情境相关——包括否定、拒绝、或表示自己没有该感受——都视为answered=true。'
                    '只有用户回复与对话完全无关时才是false。'
                    '只输出JSON：{"answered":true/false,"reason":"简短原因"}'
                ),
                messages=[{"role": "user",
                           "content": (
                               f"NPC说：{step.content}"
                               f"{capture_hint}"
                               f"\n用户回复：{user_message}"
                           )}],
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


class LLMJudgeENAsync:
    """English async variant of LLMJudge, used by offline simulation pipelines
    that drive the FSM with `anthropic.AsyncAnthropic`. Same JSON contract
    and same lenient policy as `LLMJudge` (negation / refusal / 'no opinion'
    all count as `answered=true`).
    """

    def __init__(self, client: "anthropic.AsyncAnthropic",
                 model: str = "claude-haiku-4-5-20251001"):
        self._client = client
        self._model = model

    async def judge(self, step: Step, user_message: str) -> JudgeResult:
        if len(user_message.strip()) < 5:
            return JudgeResult(False, "too short")
        try:
            capture_hint = ""
            if step.capture:
                capture_hint = f"\nObservation dimensions: {', '.join(step.capture)}"
            if step.corresponding_item:
                capture_hint += f"\nMeasured item: {step.corresponding_item}"
            msg = await self._client.messages.create(
                model=self._model,
                max_tokens=150,
                system=(
                    "You are a behavior observer. Decide whether the user has "
                    "responded to the NPC's utterance (positively, negatively, "
                    "or evasively). As long as the user's reply is relevant to "
                    "the current dialogue context — including negation, refusal, "
                    "or stating they do not have that feeling — count it as "
                    "answered=true. Only completely off-topic replies count as "
                    "answered=false. "
                    "Respond with a single JSON object and nothing else: no "
                    "preamble, no explanation, no markdown code fences. "
                    'Schema: {"answered": true|false, "reason": "<= 12 words"}'
                ),
                messages=[{"role": "user", "content": (
                    f"NPC said: {step.content}"
                    f"{capture_hint}"
                    f"\nUser reply: {user_message}"
                )}],
            )
            text = msg.content[0].text.strip()
            # Tolerate code fences and any preamble / trailing commentary.
            if text.startswith("```"):
                text = text.strip("`")
                if text.lower().startswith("json"):
                    text = text[4:]
            lo = text.find("{")
            hi = text.rfind("}")
            if lo < 0 or hi <= lo:
                raise ValueError(f"no JSON object in: {text[:120]!r}")
            r = json.loads(text[lo:hi + 1])
            return JudgeResult(bool(r["answered"]), r.get("reason", ""))
        except Exception as e:
            return JudgeResult(len(user_message.strip()) > 10, f"fallback:{e}")


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
