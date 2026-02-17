import json
import math
import traceback
import os
from typing import Dict, List, Any, Optional

from fastapi import WebSocket, WebSocketDisconnect
from core.config import Config
from core.environment import RisikoEnvironment
from ai.processor import Processor
from utils.human_dataset import append_sample, encode_action_target
from utils.watch_match_utils import WatchMatchUtils
from web.utils import (
    build_ai_agent,
    territory_coords,
    serialize_board,
    serialize_continents,
    format_mission
)
from web.ai_handler import play_ai_turn, get_scores_ref

async def ws_game_handler(ws: WebSocket):
    await ws.accept()

    #Inizializza lo stato del gioco
    env = RisikoEnvironment()
    ai_agent = build_ai_agent(env)
    processor = Processor(env.board)
    coords = territory_coords(env.board.n)

    p1_total_reward = 0
    p2_total_reward = 0
    action_log: List[str] = []
    game_over = False

    cols = int(math.sqrt(env.board.n))

    async def send_json(data: Dict[str, Any]):
        try:
            await ws.send_text(json.dumps(data))
        except Exception:
            pass

    async def send_state_update(extra_info: Optional[Dict[str, Any]] = None):
        msg: Dict[str, Any] = {
            "type": "state_update",
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
            msg["extra"] = extra_info
        await send_json(msg)

    #Invia l'inizializzazione
    await send_json({
        "type": "init",
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
    })

    #Attiva il calcolo iniziale del bonus REINFORCE (o INITIAL_PLACEMENT se applicabile, gestito in env)
    if env.current_phase == "REINFORCE" and not env.has_reinforced:
        bonus = env._get_available_bonus(env.player_turn)
        if bonus > 0:
            env.armies_to_place = bonus
            env.armies_to_place_total = bonus
            env.has_reinforced = True
        await send_json({
            "type": "reinforce_info",
            "armies_to_place": env.armies_to_place,
        })
    elif env.current_phase == "INITIAL_PLACEMENT":
        await send_json({
            "type": "reinforce_info",
            "armies_to_place": env.armies_to_place,
        })

    #Main loop
    try:
        while not game_over:
            curr_p = env.player_turn

            if curr_p == 1:
                #Turno del player
                raw = await ws.receive_text()
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    await send_json({"type": "error", "message": "JSON non valido"})
                    continue

                #Estrae l'azione
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
                    action["src"] = env.pending_attack_src
                    action["dest"] = env.pending_attack_dest
                    action["qty"] = msg.get("qty", 0.5)
                elif action_type == "MANEUVER":
                    action["src"] = msg.get("src", 0)
                    action["dest"] = msg.get("dest", 0)
                    action["qty"] = msg.get("qty", 0.5)
                elif action_type == "PASS":
                    action["src"] = 0
                    action["dest"] = 0
                    action["qty"] = 0.0
                else:
                    await send_json({"type": "error", "message": f"Tipo azione sconosciuto: {action_type}"})
                    continue

                #Inizializzo il dataset umano
                pending_sample = None
                if Config.HUMAN_DATA.get("ENABLED", False) and env.current_phase != "INITIAL_PLACEMENT":
                    state = processor.encode_state(
                        env.board, curr_p, env.current_turn, env.current_phase, env.p1_mission
                    )
                    target = encode_action_target(env.board, curr_p, env.current_phase, action)
                    if target is not None:
                        pending_sample = {
                            "state": state.tolist(),
                            "target": target,
                            "phase": env.current_phase,
                            "action": action,
                        }

                reward, done, info = env.step(action, curr_p)

                #Salva il sample se valido
                if pending_sample and "error" not in info:
                    winner_check, _ = env.is_game_over()
                    if reward > 0 or winner_check == 1:
                        # Append to dataset in new location
                        dataset_path = Config.HUMAN_DATA["DATASET_PATH"]
                        append_sample(pending_sample, dataset_path)

                p1_total_reward += reward
                if "opponent_reward" in info:
                    p2_total_reward += info["opponent_reward"]

                reason = WatchMatchUtils.get_reward_reason(action["type"], reward, info)
                log_entry = WatchMatchUtils.format_log_line(curr_p, action, reward, reason)
                action_log.append(log_entry)

                if "error" in info:
                    await send_json({"type": "error", "message": info["error"]})

                await send_json({"type": "log", "entry": log_entry, "reward": reward})
                await send_state_update(info)

                if done:
                    winner, _ = env.is_game_over()
                    # Determina messaggio finale
                    if winner == 1:
                        reason_msg = f"Vittoria per Missione: {format_mission(env.p1_mission)}"
                    elif winner == 2:
                        reason_msg = f"Sconfitta: AI ha completato {format_mission(env.p2_mission)}"
                    else:
                        reason_msg = "Pareggio (Limite Turni)"

                    await send_json({
                        "type": "game_over",
                        "winner": winner,
                        "p1_score": p1_total_reward,
                        "p2_score": p2_total_reward,
                        "message": reason_msg
                    })
                    game_over = True
                    continue

                #Se la fase è cambiata in POST_ATTACK_MOVE, informa il client
                if info.get("requires_post_attack_move") or info.get("post_attack_move_required"):
                    await send_json({
                        "type": "post_attack_move_required",
                        "src": env.pending_attack_src,
                        "dest": env.pending_attack_dest,
                    })
                    continue

                #Controlla se il turno è passato all'AI
                if env.player_turn == 2:
                    if env.current_phase == "REINFORCE" and not env.has_reinforced:
                        bonus = env._get_available_bonus(2)
                        if bonus > 0:
                            env.armies_to_place = bonus
                            env.armies_to_place_total = bonus
                            env.has_reinforced = True

                    await send_json({"type": "ai_thinking"})
                    await play_ai_turn(env, ai_agent, processor, coords, ws, send_json, send_state_update,
                                        action_log, p1_total_reward, p2_total_reward)
                    p1_total_reward, p2_total_reward = get_scores_ref(p1_total_reward, p2_total_reward)

                    winner_check, _ = env.is_game_over()
                    if winner_check != 0:
                        if winner_check == 1:
                            reason_msg = f"Vittoria per Missione: {format_mission(env.p1_mission)}"
                        elif winner_check == 2:
                            reason_msg = f"Sconfitta: AI ha completato {format_mission(env.p2_mission)}"
                        else:
                            reason_msg = "Pareggio (Limite Turni)"

                        await send_json({
                            "type": "game_over",
                            "winner": winner_check,
                            "p1_score": p1_total_reward,
                            "p2_score": p2_total_reward,
                            "message": reason_msg
                        })
                        game_over = True
                        continue

                    #Dopo il turno dell'AI, prepara il REINFORCE per il player
                    if env.player_turn == 1:
                        if env.current_phase == "REINFORCE" and not env.has_reinforced:
                            bonus = env._get_available_bonus(1)
                            if bonus > 0:
                                env.armies_to_place = bonus
                                env.armies_to_place_total = bonus
                                env.has_reinforced = True
                            
                        await send_json({
                            "type": "reinforce_info",
                            "armies_to_place": env.armies_to_place,
                        })

                    await send_state_update()

                elif (env.current_phase == "REINFORCE" or env.current_phase == "INITIAL_PLACEMENT") and env.armies_to_place > 0:
                    await send_json({
                        "type": "reinforce_info",
                        "armies_to_place": env.armies_to_place,
                    })

            else:
                # =========== Turno dell'AI (se inizia AI) ===========
                await send_json({"type": "ai_thinking"})
                if env.current_phase == "REINFORCE" and not env.has_reinforced:
                    bonus = env._get_available_bonus(2)
                    if bonus > 0:
                        env.armies_to_place = bonus
                        env.armies_to_place_total = bonus
                        env.has_reinforced = True

                await play_ai_turn(env, ai_agent, processor, coords, ws, send_json, send_state_update,
                                    action_log, p1_total_reward, p2_total_reward)
                p1_total_reward, p2_total_reward = get_scores_ref(p1_total_reward, p2_total_reward)

                winner_check, _ = env.is_game_over()
                if winner_check != 0:
                    if winner_check == 1:
                        reason_msg = f"Vittoria per Missione: {format_mission(env.p1_mission)}"
                    elif winner_check == 2:
                        reason_msg = f"Sconfitta: AI ha completato {format_mission(env.p2_mission)}"
                    else:
                        reason_msg = "Pareggio (Limite Turni)"

                    await send_json({
                        "type": "game_over",
                        "winner": winner_check,
                        "p1_score": p1_total_reward,
                        "p2_score": p2_total_reward,
                        "message": reason_msg
                    })
                    game_over = True
                    continue

                if env.player_turn == 1:
                    if env.current_phase == "REINFORCE" and not env.has_reinforced:
                        bonus = env._get_available_bonus(1)
                        if bonus > 0:
                            env.armies_to_place = bonus
                            env.armies_to_place_total = bonus
                            env.has_reinforced = True
                    await send_json({
                        "type": "reinforce_info",
                        "armies_to_place": env.armies_to_place,
                    })
                await send_state_update()

    except WebSocketDisconnect:
        pass
    except Exception as exc:
        try:
            await send_json({"type": "error", "message": f"Errore server: {exc}"})
        except Exception:
            pass
        traceback.print_exc()
