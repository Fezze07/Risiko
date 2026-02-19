import asyncio
import json
import math
import traceback
from typing import Any, Callable, Dict, List, Optional, Set

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
from .constants import (
    DEFAULT_PLAY_AI_DELAY_MS,
    DEFAULT_WATCH_DELAY_MS,
    MAX_DELAY_MS,
    MAX_PLAYERS,
    MIN_DELAY_MS,
    MIN_PLAYERS,
)
from .helpers import fallback_player_colors, normalize_role


async def ws_game_handler(
    ws: WebSocket,
    initial_num_players: int = 2,
    color_provider: Optional[Callable[[int], Dict[int, str]]] = None,
) -> None:
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
    action_log: List[str] = []
    runner_task: Optional[asyncio.Task] = None

    num_players: int = max(MIN_PLAYERS, min(MAX_PLAYERS, int(initial_num_players)))
    player_map: Dict[int, Dict[str, Any]] = {}
    human_players: Set[int] = set()
    player_scores: Dict[int, int] = {}

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

    def clamp_players(value: Any) -> int:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            parsed = MIN_PLAYERS
        return max(MIN_PLAYERS, min(MAX_PLAYERS, parsed))

    def get_delay_seconds() -> float:
        return max(0.0, delay_ms / 1000.0)

    def get_colors(total: int) -> Dict[int, str]:
        if color_provider is None:
            return fallback_player_colors(total)
        try:
            provided = color_provider(total)
        except Exception:
            return fallback_player_colors(total)
        if not isinstance(provided, dict):
            return fallback_player_colors(total)
        fallback = fallback_player_colors(total)
        for p_id in range(1, total + 1):
            if p_id not in provided:
                provided[p_id] = fallback[p_id]
        return provided

    def build_player_map(
        selected_mode: str, total_players: int, payload: Optional[Dict[str, Any]] = None
    ) -> Dict[int, Dict[str, Any]]:
        payload = payload or {}
        roles: Dict[int, str] = {
            p_id: ("HUMAN" if selected_mode == "PLAY" and p_id == 1 else "AI")
            for p_id in range(1, total_players + 1)
        }
        raw_types = payload.get("player_types")
        if raw_types is None:
            raw_types = payload.get("players")

        if isinstance(raw_types, dict):
            for key, value in raw_types.items():
                try:
                    p_id = int(key)
                except (TypeError, ValueError):
                    continue
                if 1 <= p_id <= total_players:
                    roles[p_id] = normalize_role(value)
        elif isinstance(raw_types, list):
            for idx, value in enumerate(raw_types, start=1):
                if idx > total_players:
                    break
                roles[idx] = normalize_role(value)

        if selected_mode == "WATCH":
            for p_id in roles:
                roles[p_id] = "AI"
        elif selected_mode == "PLAY" and not any(role == "HUMAN" for role in roles.values()):
            roles[1] = "HUMAN"

        colors = get_colors(total_players)
        result: Dict[int, Dict[str, Any]] = {}
        for p_id in range(1, total_players + 1):
            result[p_id] = {
                "id": p_id,
                "type": roles[p_id],
                "color": colors[p_id],
            }
        return result

    def get_mission_for_player(player_id: int) -> Dict[str, Any]:
        if not env:
            return {}
        mission = env.get_player_mission(player_id)
        if mission:
            return mission
        if player_id == 1:
            return env.p1_mission
        if player_id == 2:
            return env.p2_mission
        return {}

    def parse_human_action(msg: Dict[str, Any]) -> Dict[str, Any]:
        action_type = str(msg.get("action_type", "PASS")).upper()
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

    def is_human_turn() -> bool:
        if not env:
            return False
        return player_map.get(env.player_turn, {}).get("type") == "HUMAN"

    def is_ai_turn() -> bool:
        if not env:
            return False
        return player_map.get(env.player_turn, {}).get("type") == "AI"

    def build_player_stats() -> List[Dict[str, Any]]:
        if not env:
            return []
        stats: List[Dict[str, Any]] = []
        for p_id in range(1, num_players + 1):
            territories = [
                t for t in env.board.territories.values() if t.owner_id == p_id
            ]
            stats.append(
                {
                    "id": p_id,
                    "type": player_map.get(p_id, {}).get("type", "AI"),
                    "color": player_map.get(p_id, {}).get("color", "#888888"),
                    "territories": len(territories),
                    "armies": sum(t.armies for t in territories),
                    "score": int(player_scores.get(p_id, 0)),
                }
            )
        return stats

    async def send_state_update(extra_info: Optional[Dict[str, Any]] = None) -> None:
        if not env:
            return
        payload: Dict[str, Any] = {
            "type": "state_update",
            "mode": mode,
            "running": running,
            "delay_ms": delay_ms,
            "num_players": num_players,
            "player_map": player_map,
            "player_stats": build_player_stats(),
            "board": {"territories": serialize_board(env, coords)},
            "current_player": env.player_turn,
            "phase": env.current_phase,
            "turn": env.current_turn,
            "p1_score": int(player_scores.get(1, 0)),
            "p2_score": int(player_scores.get(2, 0)),
            "armies_to_place": env.armies_to_place,
            "action_log": action_log[-30:],
            "max_armies": Config.GAME["MAX_ARMIES_PER_TERRITORY"],
        }
        if extra_info:
            payload["extra"] = extra_info
        await send_json(payload)

    async def send_game_over() -> None:
        nonlocal game_over
        if not env:
            return
        winner, _ = env.is_game_over()
        if winner > 0:
            reason_msg = f"Vittoria per Missione: {format_mission(get_mission_for_player(winner))}"
        else:
            reason_msg = "Pareggio (Limite Turni)"

        await send_json(
            {
                "type": "game_over",
                "winner": winner,
                "message": reason_msg,
                "scores": {str(k): int(v) for k, v in player_scores.items()},
                "player_stats": build_player_stats(),
                "p1_score": int(player_scores.get(1, 0)),
                "p2_score": int(player_scores.get(2, 0)),
            }
        )
        game_over = True

    async def apply_action(action: Dict[str, Any], player_id: int, mission: Dict[str, Any]) -> None:
        nonlocal game_over

        if not env or not processor or game_over:
            return

        pending_sample = None
        if (
            mode == "PLAY"
            and player_map.get(player_id, {}).get("type") == "HUMAN"
            and Config.HUMAN_DATA.get("ENABLED", False)
            and env.current_phase != "INITIAL_PLACEMENT"
        ):
            state = processor.encode_state(
                env.board,
                current_player_id=player_id,
                current_turn=env.current_turn,
                current_phase=env.current_phase,
                mission_data=mission,
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
            "defender_id": info.get("defender_id"),
            "qty": info.get("reinforce_qty")
            or info.get("maneuver_qty")
            or info.get("post_attack_move_qty"),
        }

        if pending_sample and "error" not in info:
            winner_check, _ = env.is_game_over()
            if reward > 0 or winner_check == player_id:
                append_sample(pending_sample, Config.HUMAN_DATA["DATASET_PATH"])

        player_scores[player_id] = int(player_scores.get(player_id, 0) + reward)

        opp_reward = int(info.get("opponent_reward", 0)) if info.get("opponent_reward") else 0
        if opp_reward:
            defender_id = info.get("defender_id")
            if (
                isinstance(defender_id, int)
                and defender_id in player_scores
                and defender_id != player_id
            ):
                player_scores[defender_id] = int(player_scores[defender_id] + opp_reward)
            elif num_players == 2:
                other = 1 if player_id == 2 else 2
                player_scores[other] = int(player_scores.get(other, 0) + opp_reward)

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

        if mode == "PLAY" and player_map.get(player_id, {}).get("type") == "HUMAN" and (
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

    async def run_auto_players() -> None:
        try:
            while mode in ("PLAY", "WATCH") and running and not game_over and env and is_ai_turn():
                curr_player = env.player_turn
                agent = ai_agents.get(curr_player)
                if agent is None:
                    await send_json(
                        {
                            "type": "error",
                            "message": f"Agente AI non disponibile per player {curr_player}",
                        }
                    )
                    break
                mission = get_mission_for_player(curr_player)
                prepare_reinforce(curr_player)

                await send_json({"type": "ai_thinking", "player": curr_player})
                await asyncio.sleep(get_delay_seconds())
                action = agent.think(
                    env.board, curr_player, env.current_turn, env.current_phase, mission
                )
                await apply_action(action, curr_player, mission)
                if game_over or not env:
                    break

                if env.current_phase == "POST_ATTACK_MOVE" and env.player_turn == curr_player and is_ai_turn():
                    await asyncio.sleep(get_delay_seconds())
                    post_action = agent.think(
                        env.board,
                        curr_player,
                        env.current_turn,
                        env.current_phase,
                        mission,
                    )
                    post_action["type"] = "POST_ATTACK_MOVE"
                    await apply_action(post_action, curr_player, mission)

                await send_json({"type": "ai_done", "player": curr_player})

            if mode == "PLAY" and env and is_human_turn() and not game_over:
                prepare_reinforce(env.player_turn)
                await send_json(
                    {
                        "type": "reinforce_info",
                        "armies_to_place": env.armies_to_place,
                    }
                )
                await send_state_update()
        finally:
            await send_json({"type": "runner_stopped"})

    async def maybe_start_runner() -> None:
        nonlocal runner_task
        if game_over or not running or not env:
            return
        if runner_task and not runner_task.done():
            return
        if is_ai_turn():
            runner_task = asyncio.create_task(run_auto_players())

    async def init_match(new_mode: str, payload: Optional[Dict[str, Any]] = None) -> None:
        nonlocal env, processor, coords, cols
        nonlocal ai_agents, mode, game_over, running
        nonlocal delay_ms, action_log
        nonlocal num_players, player_map, human_players, player_scores

        payload = payload or {}
        await stop_runner()

        mode = new_mode
        num_players = clamp_players(payload.get("num_players", num_players))
        player_map = build_player_map(mode, num_players, payload)
        human_players = {
            p_id for p_id, meta in player_map.items() if meta.get("type") == "HUMAN"
        }

        env = RisikoEnvironment(num_players=num_players)
        processor = Processor(env.board)
        coords = territory_coords(env.board.n)
        cols = int(math.sqrt(env.board.n))
        game_over = False
        action_log = []
        player_scores = {p_id: 0 for p_id in range(1, num_players + 1)}

        ai_agents = {}
        for p_id in range(1, num_players + 1):
            if player_map[p_id]["type"] == "AI":
                ai_agents[p_id] = build_ai_agent(env, p_id)

        if mode == "PLAY":
            delay_ms = DEFAULT_PLAY_AI_DELAY_MS
            running = True
        else:
            delay_ms = DEFAULT_WATCH_DELAY_MS
            running = True
        if "delay_ms" in payload:
            delay_ms = clamp_delay(payload.get("delay_ms"))

        player_missions = {
            str(p_id): format_mission(get_mission_for_player(p_id))
            for p_id in range(1, num_players + 1)
        }

        await send_json(
            {
                "type": "init",
                "mode": mode,
                "running": running,
                "delay_ms": delay_ms,
                "num_players": num_players,
                "player_map": player_map,
                "player_stats": build_player_stats(),
                "board": {
                    "territories": serialize_board(env, coords),
                    "grid_cols": cols,
                    "grid_rows": env.board.n // cols,
                },
                "continents": serialize_continents(),
                "current_player": env.player_turn,
                "phase": env.current_phase,
                "turn": env.current_turn,
                "player_missions": player_missions,
                "p1_mission": player_missions.get("1", ""),
                "p2_mission": player_missions.get("2", ""),
                "armies_to_place": env.armies_to_place,
                "p1_score": int(player_scores.get(1, 0)),
                "p2_score": int(player_scores.get(2, 0)),
                "max_turns": Config.GAME["MAX_TURNS"],
                "max_armies": Config.GAME["MAX_ARMIES_PER_TERRITORY"],
            }
        )

        prepare_reinforce(env.player_turn)
        if mode == "PLAY" and is_human_turn():
            await send_json(
                {"type": "reinforce_info", "armies_to_place": env.armies_to_place}
            )

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
            await init_match(requested_mode, msg)
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
                preserved_types = {
                    str(p_id): player_map[p_id]["type"] for p_id in player_map
                }
                await init_match(
                    mode,
                    {
                        "num_players": num_players,
                        "player_types": preserved_types,
                        "delay_ms": delay_ms,
                    },
                )
                return

            await send_json({"type": "error", "message": "CONTROL action non valida"})
            return

        await send_json({"type": "error", "message": "Comando sconosciuto"})

    default_map = build_player_map("PLAY", num_players, {})
    await send_json(
        {
            "type": "ready",
            "message": "Connessione aperta. Invia START_MODE con PLAY o WATCH.",
            "delay_bounds": {"min_ms": MIN_DELAY_MS, "max_ms": MAX_DELAY_MS},
            "num_players": num_players,
            "player_map": default_map,
            "max_armies": Config.GAME["MAX_ARMIES_PER_TERRITORY"],
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
                await send_json(
                    {"type": "error", "message": "Input umano disponibile solo in PLAY"}
                )
                continue

            if not env:
                await send_json({"type": "error", "message": "Partita non inizializzata"})
                continue

            if game_over:
                await send_json({"type": "error", "message": "Partita terminata. Usa RESET."})
                continue

            if not is_human_turn():
                await send_json({"type": "error", "message": "Attendi il tuo turno"})
                continue

            acting_player = env.player_turn
            action = parse_human_action(msg)
            mission = get_mission_for_player(acting_player)
            await apply_action(action, acting_player, mission)
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
