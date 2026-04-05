"""
fsm/service.py — オーケストレーション層
Protocol を基点としたプログラミング。IFSM / IJudge / IStore / IScenario を保持し、
start_session / handle_message などの高レベル操作メソッドを外部に提供する。
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import anthropic

from .protocol import IFSM, IJudge, IStore, IScenario, Step, Character


def _char_dict(c: Character) -> dict:
    """
    機能：Character オブジェクトをフロントエンド向け dict に変換する。
    入力：c（Character データクラス）
    出力：name, role, emoji, color を含む dict
    """
    return {"name": c.name, "role": c.role, "emoji": c.emoji, "color": c.color}


def _npc_reply(
    client: anthropic.Anthropic,
    char: Character,
    step: Step,
    history: list[dict],
    user_message: str,
    model: str = "claude-sonnet-4-20250514",
) -> str:
    """
    機能：NPC キャラクターとして LLM に返答を生成させる。529 エラー時は指数バックオフで最大 3 回再試行する。
    入力：client（Anthropic クライアント）、char（NPC キャラクター情報）、step（現在の FSM ステップ）、
          history（過去の会話履歴）、user_message（ユーザー入力テキスト）、model（使用モデル名）
    出力：NPC の返答テキスト（str）
    """
    import time
    system = (
        f"你是 {char.name}（{char.role}）。\n"
        f"性格：{char.personality}\n"
        f"风格参考：{'；'.join(char.few_shots[:2])}\n"
        f"当前：{step.day}/{step.state}，MBTI维度：{step.mbti_focus}\n"
        "用中文回复，100字以内，保持角色，自然推进对话。"
    )
    messages = [
        {"role": "user",      "content": f"（{char.name}说）{step.content}"},
        *history,
        {"role": "user",      "content": user_message},
    ]
    for attempt in range(3):
        try:
            resp = client.messages.create(
                model=model, max_tokens=300,
                system=system, messages=messages,
            )
            return resp.content[0].text.strip()
        except anthropic.APIStatusError as e:
            if e.status_code == 529 and attempt < 2:   # overloaded、再試行
                time.sleep(2 ** attempt)
                continue
            raise


@dataclass
class FSMService:
    """
    FSM サービス：IFSM + IJudge + IStore + IScenario を組み合わせる。
    bridge.py は FSMService のみと対話する。
    """
    fsm:      IFSM
    judge:    IJudge
    store:    IStore
    scenario: IScenario
    client:   Optional[anthropic.Anthropic] = None

    def start_session(self, session_id: str, start_day: str) -> dict:
        """
        機能：新しいセッションを作成し、初期状態を永続化して最初の NPC の開幕台詞を返す。
        入力：session_id（セッション識別子）、start_day（開始日文字列、例: "Day 1"）
        出力：session_id, day, state, speaker, opening_line, character を含む dict
        """
        from .impl import ShareHouseFSM
        fsm  = ShareHouseFSM(self.scenario, start_day)
        step = fsm.current_step
        if not step:
            raise ValueError(f"invalid start_day: {start_day}")
        fsm.add_turn("assistant", step.content)
        self.store.save(session_id, fsm.dump())
        char = self.scenario.get_character(step.speaker)
        return {
            "session_id":   session_id,
            "day":          step.day,
            "state":        step.state,
            "speaker":      step.speaker,
            "opening_line": step.content,
            "character":    _char_dict(char),
        }

    def handle_message(self, session_id: str, user_message: str) -> dict:
        """
        機能：ユーザーメッセージを 1 ターン処理し、NPC 返答と FSM 進行結果を返す。
        入力：session_id（セッション識別子）、user_message（ユーザー入力テキスト）
        出力：npc_reply, advance_event、および次ステップ情報（advance 時）を含む dict
        """
        from .impl import ShareHouseFSM
        data = self.store.get(session_id)
        if not data:
            raise KeyError(f"session not found: {session_id}")

        fsm  = ShareHouseFSM.load(self.scenario, data)
        step = fsm.current_step
        if not step:
            return {"npc_reply": "（游戏已结束）", "advance_event": "game_complete"}

        char = self.scenario.get_character(step.speaker)

        fsm.add_turn("user", user_message)
        history  = fsm.turn_history[:-1]
        npc_text = _npc_reply(self.client, char, step, history, user_message)
        fsm.add_turn("assistant", npc_text)

        judge_result = self.judge.judge(step, user_message)
        result: dict = {"npc_reply": npc_text, "advance_event": ""}

        if judge_result.answered:
            adv = fsm.advance()
            result["advance_event"] = adv.event
            if adv.event != "game_complete" and adv.next_step:
                s, c = adv.next_step, adv.next_character
                result.update({
                    "next_day":          s.day,
                    "next_state":        s.state,
                    "next_speaker":      s.speaker,
                    "next_opening_line": s.content,
                    "next_character":    _char_dict(c),
                })
                fsm.add_turn("assistant", s.content)

        self.store.save(session_id, fsm.dump())
        return result


def create_fsm(
    anthropic_client: Optional[anthropic.Anthropic] = None,
    scenario_path: str = "fsm/multi_npc_scenario_zh.json",
    use_rule_judge: bool = False,
) -> FSMService:
    """
    機能：具体的な実装を依存注入し、FSMService を生成して返すファクトリ関数。
    入力：anthropic_client（Anthropic クライアント）、scenario_path（シナリオ JSON ファイルパス）、
          use_rule_judge（True の場合トークン消費なしのローカルテスト用ルール判定を使用）
    出力：FSMService インスタンス
    """
    from .impl import JsonScenario, ShareHouseFSM, LLMJudge, RuleJudge, MemoryStore
    scenario = JsonScenario(scenario_path)
    fsm      = ShareHouseFSM(scenario, "Day 1")
    judge    = RuleJudge() if use_rule_judge else LLMJudge(anthropic_client)
    store    = MemoryStore()
    return FSMService(
        fsm=fsm, judge=judge, store=store,
        scenario=scenario, client=anthropic_client,
    )
