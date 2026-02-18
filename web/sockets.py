import asyncio
import json
import math
import traceback
from typing import Any, Dict, List, Optional

from fastapi import WebSocket, WebSocketDisconnect

from ai.processor import Processor
from config import Config
from core.environment import RisikoEnvironment
from utils.human_dataset import append_sample, encode_action_target
from utils.watch_match_utils import WatchMatchUtils
from web.utils import (
    build_ai_agent,
    format_mission,
    serialize_board,
    serialize_continents,
    territory_coords,
)


MIN_DELAY_MS = 100
MAX_DELAY_MS = 2000
DEFAULT_WATCH_DELAY_MS = 2000
DEFAULT_PLAY_AI_DELAY_MS = 2000


async def ws_game_handler(ws: WebSocket) -> None:
    await ws.accept()

    env: Optional[RisikoEnvironment] = None
    processor: Optional[Processor] = None
    coords: Dict[int, Dict[str, float]] = {}
    cols: int = 5
    ai_agents: Dict[int, Any] = {}
    mode: Optional[str] = None  # PLAY | WATCH
    running: bool = False
    game_over: bool = False
    delay_ms: int = DEFAULT_WATCH_DELAY_MS
    p1_total_reward: int = 0
    p2_total_reward: int = 0
    action_log: List[str] = []
    runner_task: Optional[asyncio.Task] = None

    async def send_json(data: Dict[str, Any]) -> None:
        try:
            await ws.send_text(json.dumps(data))
        except Exception:
            pass

    def clamp_delay(value: Any) -> int:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            parsed = DEFAULT_WATCH_DELAY_MS
        return max(MIN_DELAY_MS, min(MAX_DELAY_MS, parsed))

    def get_delay_seconds() -> float:
        return max(0.0, delay_ms / 1000.0)

    def parse_human_action(msg: Dict[str, Any]) -> Dict[str, Any]:
        action_type = msg.get("action_type", "PASS")
        action: Dict[str, Any] = {"type": action_type}
        if action_type == "REINFORCE":
            action["src"] = msg.get("dest", 0)
            action["dest"] = msg.get("dest", 0)
            action["qty"] = msg.get("qty", 0.0)
        elif action_type == "ATTACK":
            action["src"] = msg.get("src", 0)
            action["dest"] = msg.get("dest", 0)
        elif action_type == "POST_ATTACK_MOVE":
            action["src"] = env.pending_attack_src if env else 0
            action["dest"] = env.pending_attack_dest if env else 0
            action["qty"] = msg.get("qty", 0.5)
        elif action_type == "MANEUVER":
            action["src"] = msg.get("src", 0)
            action["dest"] = msg.get("dest", 0)
            action["qty"] = msg.get("qty", 0.5)
        else:
            action["src"] = 0
            action["dest"] = 0
            action["qty"] = 0.0
        return action

    def prepare_reinforce(player_id: int) -> None:
        if not env:
            return
        if env.current_phase == "REINFORCE" and not env.has_reinforced:
            bonus = env._get_available_bonus(player_id)
            if bonus > 0:
                env.armies_to_place = bonus
                env.armies_to_place_total = bonus
                env.has_reinforced = True

    async def send_state_update(extra_info: Optional[Dict[str, Any]] = None) -> None:
        if not env:
            return
        payload: Dict[str, Any] = {
            "type": "state_update",
            "mode": mode,
            "running": running,
            "delay_ms": delay_ms,
            "board": {"territories": serialize_board(env, coords)},
            "current_player": env.player_turn,
            "phase": env.current_phase,
            "turn": env.current_turn,
            "p1_score": p1_total_reward,
            "p2_score": p2_total_reward,
            "armies_to_place": env.armies_to_place,
            "action_log": action_log[-30:],
        }
        if extra_info:
            payload["extra"] = extra_info
        await send_json(payload)

    async def send_game_over() -> None:
        nonlocal game_over
        if not env:
            return
        winner, _ = env.is_game_over()
        if winner == 1:
            reason_msg = f"Vittoria per Missione: {format_mission(env.p1_mission)}"
        elif winner == 2:
            reason_msg = f"Vittoria per Missione: {format_mission(env.p2_mission)}"
        else:
            reason_msg = "Pareggio (Limite Turni)"
        await send_json(
            {
                "type": "game_over",
                "winner": winner,
                "p1_score": p1_total_reward,
                "p2_score": p2_total_reward,
                "message": reason_msg,
            }
        )
        game_over = True

    async def apply_action(action: Dict[str, Any], player_id: int, mission: Dict[str, Any]) -> None:
        nonlocal p1_total_reward, p2_total_reward
        nonlocal game_over

        if not env or not processor or game_over:
            return

        pending_sample = None
        if (
            mode == "PLAY"
            and player_id == 1
            and Config.HUMAN_DATA.get("ENABLED", False)
            and env.current_phase != "INITIAL_PLACEMENT"
        ):
            state = processor.encode_state(
                env.board, player_id, env.current_turn, env.current_phase, mission
            )
            target = encode_action_target(env.board, player_id, env.current_phase, action)
            if target is not None:
                pending_sample = {
                    "state": state.tolist(),
                    "target": target,
                    "phase": env.current_phase,
                    "action": action,
                }

        reward, done, info = env.step(action, player_id)
        info["last_action"] = {
            "type": action.get("type"),
            "player": player_id,
            "src": action.get("src"),
            "dest": action.get("dest"),
            "qty": info.get("reinforce_qty")
            or info.get("maneuver_qty")
            or info.get("post_attack_move_qty"),
        }

        if pending_sample and "error" not in info:
            winner_check, _ = env.is_game_over()
            if reward > 0 or winner_check == 1:
                append_sample(pending_sample, Config.HUMAN_DATA["DATASET_PATH"])

        if player_id == 1:
            p1_total_reward += reward
            if "opponent_reward" in info:
                p2_total_reward += int(info["opponent_reward"])
        else:
            p2_total_reward += reward
            if "opponent_reward" in info:
                p1_total_reward += int(info["opponent_reward"])

        reason = WatchMatchUtils.get_reward_reason(action["type"], reward, info)
        log_entry = WatchMatchUtils.format_log_line(player_id, action, reward, reason)
        action_log.append(log_entry)
        await send_json(
            {"type": "log", "entry": log_entry, "reward": reward, "player": player_id}
        )

        if "error" in info:
            await send_json({"type": "error", "message": info["error"]})

        await send_state_update(info)

        if done:
            await send_game_over()
            return

        if mode == "PLAY" and player_id == 1 and (
            info.get("requires_post_attack_move") or info.get("post_attack_move_required")
        ):
            await send_json(
                {
                    "type": "post_attack_move_required",
                    "src": env.pending_attack_src,
                    "dest": env.pending_attack_dest,
                }
            )

    async def stop_runner() -> None:
        nonlocal runner_task
        if runner_task and not runner_task.done():
            runner_task.cancel()
            try:
                await runner_task
            except asyncio.CancelledError:
                pass
        runner_task = None

    async def run_play_ai() -> None:
        nonlocal running
        try:
            while mode == "PLAY" and running and not game_over and env and env.player_turn == 2:
                prepare_reinforce(2)
                await send_json({"type": "ai_thinking"})
                await asyncio.sleep(get_delay_seconds())
                action = ai_agents[2].think(
                    env.board, 2, env.current_turn, env.current_phase, env.p2_mission
                )
                await apply_action(action, 2, env.p2_mission)
                if game_over or not env:
                    break
                if env.current_phase == "POST_ATTACK_MOVE" and env.player_turn == 2:
                    await asyncio.sleep(get_delay_seconds())
                    post_action = ai_agents[2].think(
                        env.board, 2, env.current_turn, env.current_phase, env.p2_mission
                    )
                    post_action["type"] = "POST_ATTACK_MOVE"
                    await apply_action(post_action, 2, env.p2_mission)
                await send_json({"type": "ai_done"})

            if mode == "PLAY" and env and env.player_turn == 1 and not game_over:
                prepare_reinforce(1)
                await send_json(
                    {"type": "reinforce_info", "armies_to_place": env.armies_to_place}
                )
                await send_state_update()
        finally:
            await send_json({"type": "runner_stopped"})

    async def run_watch_mode() -> None:
        nonlocal running
        try:
            while mode == "WATCH" and running and not game_over and env:
                curr_player = env.player_turn
                prepare_reinforce(curr_player)
                mission = env.p1_mission if curr_player == 1 else env.p2_mission
                await asyncio.sleep(get_delay_seconds())
                action = ai_agents[curr_player].think(
                    env.board, curr_player, env.current_turn, env.current_phase, mission
                )
                await apply_action(action, curr_player, mission)
                if game_over or not env:
                    break
                if env.current_phase == "POST_ATTACK_MOVE" and env.player_turn == curr_player:
                    await asyncio.sleep(get_delay_seconds())
                    post_action = ai_agents[curr_player].think(
                        env.board, curr_player, env.current_turn, env.current_phase, mission
                    )
                    post_action["type"] = "POST_ATTACK_MOVE"
                    await apply_action(post_action, curr_player, mission)
        finally:
            await send_json({"type": "runner_stopped"})

    async def maybe_start_runner() -> None:
        nonlocal runner_task
        if game_over or not running or not env:
            return
        if runner_task and not runner_task.done():
            return
        if mode == "PLAY" and env.player_turn == 2:
            runner_task = asyncio.create_task(run_play_ai())
        elif mode == "WATCH":
            runner_task = asyncio.create_task(run_watch_mode())

    async def init_match(new_mode: str) -> None:
        nonlocal env, processor, coords, cols
        nonlocal ai_agents, mode, game_over, running
        nonlocal p1_total_reward, p2_total_reward, action_log, delay_ms

        await stop_runner()

        mode = new_mode
        env = RisikoEnvironment()
        processor = Processor(env.board)
        coords = territory_coords(env.board.n)
        cols = int(math.sqrt(env.board.n))
        game_over = False
        action_log = []
        p1_total_reward = 0
        p2_total_reward = 0

        if mode == "PLAY":
            ai_agents = {2: build_ai_agent(env, 2)}
            delay_ms = DEFAULT_PLAY_AI_DELAY_MS
            running = True
        else:
            ai_agents = {1: build_ai_agent(env, 1), 2: build_ai_agent(env, 2)}
            delay_ms = DEFAULT_WATCH_DELAY_MS
            running = True

        await send_json(
            {
                "type": "init",
                "mode": mode,
                "running": running,
                "delay_ms": delay_ms,
                "board": {
                    "territories": serialize_board(env, coords),
                    "grid_cols": cols,
                    "grid_rows": env.board.n // cols,
                },
                "continents": serialize_continents(),
                "current_player": env.player_turn,
                "phase": env.current_phase,
                "turn": env.current_turn,
                "p1_mission": format_mission(env.p1_mission),
                "p2_mission": format_mission(env.p2_mission),
                "armies_to_place": env.armies_to_place,
                "max_turns": Config.GAME["MAX_TURNS"],
            }
        )

        prepare_reinforce(env.player_turn)
        if mode == "PLAY" and env.player_turn == 1:
            await send_json({"type": "reinforce_info", "armies_to_place": env.armies_to_place})

        await send_state_update()
        await maybe_start_runner()

    async def handle_command(msg: Dict[str, Any]) -> None:
        nonlocal running, delay_ms

        command = msg.get("command")
        if command == "START_MODE":
            requested_mode = str(msg.get("mode", "")).upper()
            if requested_mode not in ("PLAY", "WATCH"):
                await send_json({"type": "error", "message": "Modalita non valida"})
                return
            await init_match(requested_mode)
            return

        if command == "SET_SPEED":
            delay_ms = clamp_delay(msg.get("delay_ms", delay_ms))
            await send_json({"type": "speed_updated", "delay_ms": delay_ms})
            return

        if command == "CONTROL":
            action = str(msg.get("action", "")).upper()
            if "delay_ms" in msg:
                delay_ms = clamp_delay(msg.get("delay_ms"))
                await send_json({"type": "speed_updated", "delay_ms": delay_ms})

            if action == "PLAY":
                running = True
                await send_json({"type": "mode_status", "running": running})
                await maybe_start_runner()
                return
            if action == "PAUSE":
                running = False
                await stop_runner()
                await send_json({"type": "mode_status", "running": running})
                return
            if action == "RESET":
                if not mode:
                    await send_json({"type": "error", "message": "Nessuna modalita attiva"})
                    return
                await init_match(mode)
                return

            await send_json({"type": "error", "message": "CONTROL action non valida"})
            return

        await send_json({"type": "error", "message": "Comando sconosciuto"})

    await send_json(
        {
            "type": "ready",
            "message": "Connessione aperta. Invia START_MODE con PLAY o WATCH.",
            "delay_bounds": {"min_ms": MIN_DELAY_MS, "max_ms": MAX_DELAY_MS},
        }
    )

    try:
        while True:
            raw = await ws.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await send_json({"type": "error", "message": "JSON non valido"})
                continue

            if "command" in msg:
                await handle_command(msg)
                continue

            if mode != "PLAY":
                await send_json({"type": "error", "message": "Input umano disponibile solo in PLAY"})
                continue

            if not env:
                await send_json({"type": "error", "message": "Partita non inizializzata"})
                continue

            if game_over:
                await send_json({"type": "error", "message": "Partita terminata. Usa RESET."})
                continue

            if env.player_turn != 1:
                await send_json({"type": "error", "message": "Attendi il tuo turno"})
                continue

            action = parse_human_action(msg)
            await apply_action(action, 1, env.p1_mission)
            if not game_over:
                await maybe_start_runner()

    except WebSocketDisconnect:
        await stop_runner()
    except Exception as exc:
        try:
            await send_json({"type": "error", "message": f"Errore server: {exc}"})
        except Exception:
            pass
        await stop_runner()
        traceback.print_exc()
