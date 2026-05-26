from flask import Flask, request, jsonify
from flask_cors import CORS
import json
from Utilities.until import load_accounts
from Utilities.cache import token_cache
from Api.Account import get_garena_token, get_major_login
from Api.InGame import get_player_personal_show, get_player_stats, search_account_by_keyword
from Api.Errors import ProtobufError, APIError


accounts = load_accounts()


app = Flask(__name__)
CORS(app)


def get_cached_credentials(server):
    cached = token_cache.get(server)
    if cached:
        return cached

    creds = accounts[server]
    garena = get_garena_token(creds['uid'], creds['password'])
    if not garena or 'access_token' not in garena:
        return None

    major = get_major_login(garena['access_token'], garena['open_id'])
    if not major:
        return None

    # Handle new full-decode format
    if isinstance(major, dict) and 'known' in major and major['known']:
        known = major['known']
        if known.get('token') and known.get('serverUrl'):
            data = {
                "token": known["token"],
                "serverUrl": known["serverUrl"],
            }
        else:
            return None
    # Fallback: old format
    elif isinstance(major, dict) and major.get('token'):
        data = {
            "token": major["token"],
            "serverUrl": major["serverUrl"],
        }
    elif 'token' in major:
        data = {
            "token": major["token"],
            "serverUrl": major["serverUrl"],
        }
    else:
        return None
    token_cache.set(server, data)
    return data


@app.route('/get_search_account_by_keyword', methods=['GET'])
def get_search_account_by_keyword():
    try:
        region = request.args.get('server', 'IND').upper()
        search_term = request.args.get('keyword')

        if not search_term:
            return jsonify({"success": False, "error": "Keyword parameter is required"}), 400

        if len(search_term.strip()) < 3:
            return jsonify({"success": False, "error": "Keyword must be at least 3 characters long"}), 400

        if region not in accounts:
            return jsonify({"success": False, "error": f"Invalid server: {region}"}), 400

        creds = get_cached_credentials(region)
        if not creds:
            return jsonify({"success": False, "error": "Authentication failed for this server"}), 401

        results = search_account_by_keyword(creds["serverUrl"], creds["token"], search_term)
        return jsonify({"success": True, "data": results, "server": region}), 200

    except KeyError as e:
        return jsonify({"success": False, "error": f"Missing configuration: {str(e)}"}), 500
    except Exception as e:
        return jsonify({"success": False, "error": f"Internal server error: {str(e)}"}), 500


@app.route('/get_player_stats', methods=['GET'])
def get_player_stat():
    try:
        server = request.args.get('server', 'IND').upper()
        uid = request.args.get('uid')
        gamemode = request.args.get('gamemode', 'br').lower()
        matchmode = request.args.get('matchmode', 'CAREER').upper()

        if not uid:
            return jsonify({"success": False, "error": "UID parameter is required"}), 400

        if not uid.isdigit():
            return jsonify({"success": False, "error": "UID must be a numeric value"}), 400

        if server not in accounts:
            return jsonify({"success": False, "error": f"Invalid server: {server}", "available": list(accounts.keys())}), 400

        if gamemode not in ['br', 'cs']:
            return jsonify({"success": False, "error": "Gamemode must be 'br' or 'cs'"}), 400

        if matchmode not in ['CAREER', 'NORMAL', 'RANKED']:
            return jsonify({"success": False, "error": "Matchmode must be 'CAREER', 'NORMAL', or 'RANKED'"}), 400

        creds = get_cached_credentials(server)
        if not creds:
            return jsonify({"success": False, "error": "Authentication failed for this server"}), 401

        try:
            player_stats = get_player_stats(creds["token"], creds["serverUrl"], gamemode, uid, matchmode)
        except ValueError as e:
            return jsonify({"success": False, "error": str(e)}), 400
        except ConnectionError as e:
            return jsonify({"success": False, "error": str(e)}), 503
        except ProtobufError as e:
            return jsonify({"success": False, "error": str(e)}), 500
        except APIError as e:
            return jsonify({"success": False, "error": str(e)}), 502

        if not player_stats:
            return jsonify({"success": False, "error": "No player statistics found"}), 404

        return jsonify({"success": True, "data": player_stats, "server": server, "uid": uid, "gamemode": gamemode, "matchmode": matchmode}), 200

    except Exception as e:
        return jsonify({"success": False, "error": f"Internal server error: {str(e)}"}), 500


@app.route('/get_player_personal_show', methods=['GET'])
def get_account_info():
    try:
        server = request.args.get('server', 'IND').upper()
        uid = request.args.get('uid')
        need_gallery_info = request.args.get('need_gallery_info', False)
        need_blacklist = request.args.get('need_blacklist', False)
        need_spark_info = request.args.get('need_spark_info', False)
        call_sign_src = request.args.get('call_sign_src', 7)

        if not uid:
            return jsonify({"success": False, "error": "Missing UID", "code": "MISSING_UID"}), 400

        try:
            uid_int = int(uid)
            if uid_int <= 0:
                return jsonify({"success": False, "error": "UID must be a positive integer"}), 400
        except (ValueError, TypeError):
            return jsonify({"success": False, "error": "UID must be a valid integer"}), 400

        if server not in accounts:
            return jsonify({"success": False, "error": f"Invalid server: {server}", "available": list(accounts.keys())}), 400

        for param_name, param_val in [("need_gallery_info", need_gallery_info), ("need_blacklist", need_blacklist), ("need_spark_info", need_spark_info)]:
            if isinstance(param_val, str):
                if param_val.lower() in ['true', '1', 'yes']:
                    param_val = True
                elif param_val.lower() in ['false', '0', 'no']:
                    param_val = False
                else:
                    return jsonify({"success": False, "error": f"{param_name} must be a boolean value"}), 400
                if param_name == "need_gallery_info":
                    need_gallery_info = param_val
                elif param_name == "need_blacklist":
                    need_blacklist = param_val
                elif param_name == "need_spark_info":
                    need_spark_info = param_val

        try:
            call_sign_src_int = int(call_sign_src)
            if call_sign_src_int < 0:
                return jsonify({"success": False, "error": "call_sign_src must be a non-negative integer"}), 400
        except (ValueError, TypeError):
            return jsonify({"success": False, "error": "call_sign_src must be a valid integer"}), 400

        creds = get_cached_credentials(server)
        if not creds:
            return jsonify({"success": False, "error": "Authentication failed for this server"}), 401

        player_data = get_player_personal_show(
            creds["serverUrl"], creds["token"],
            uid_int, need_gallery_info, call_sign_src_int,
            need_blacklist, need_spark_info
        )

        if not player_data:
            return jsonify({"success": False, "error": f"No player data found for UID: {uid_int}"}), 404

        return jsonify({"success": True, "data": player_data, "server": server}), 200

    except Exception as e:
        print(f"[get_player_personal_show] Error: {e}")
        return jsonify({"success": False, "error": "Internal server error"}), 500


if __name__ == '__main__':
    print(f"[FreeFire API] Servers: {', '.join(sorted(accounts.keys()))}")
    print(f"[FreeFire API] Running on http://0.0.0.0:5000")
    app.run(host='0.0.0.0', port=5000)
