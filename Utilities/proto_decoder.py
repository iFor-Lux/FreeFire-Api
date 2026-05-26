"""
Raw protobuf wire format decoder that extracts ALL fields,
including those NOT defined in compiled .proto files.
"""

import struct


def _decode_varint(buf, offset):
    value = 0
    shift = 0
    while True:
        if offset >= len(buf):
            raise ValueError("Truncated varint")
        byte = buf[offset]
        value |= (byte & 0x7F) << shift
        shift += 7
        offset += 1
        if not (byte & 0x80):
            break
    return value, offset


def _decode_signed_varint(buf, offset):
    """Decode signed varint (ZigZag encoding)."""
    raw, offset = _decode_varint(buf, offset)
    if raw & 1:
        return -((raw >> 1) + 1), offset
    return raw >> 1, offset


def _decode_fixed32(buf, offset):
    return struct.unpack_from('<I', buf, offset)[0], offset + 4


def _decode_fixed64(buf, offset):
    return struct.unpack_from('<Q', buf, offset)[0], offset + 4


def _decode_sfixed32(buf, offset):
    return struct.unpack_from('<i', buf, offset)[0], offset + 4


def _decode_sfixed64(buf, offset):
    return struct.unpack_from('<q', buf, offset)[0], offset + 4


def _decode_float(buf, offset):
    return struct.unpack_from('<f', buf, offset)[0], offset + 4


def _decode_double(buf, offset):
    return struct.unpack_from('<d', buf, offset)[0], offset + 8


def _is_printable(buf):
    """Check if buffer looks like a printable UTF-8 string."""
    if len(buf) == 0:
        return False
    try:
        text = buf.decode('utf-8')
        if not text:
            return False
        # If all chars are printable or common whitespace, it's a string
        printable = 0
        for c in text:
            if c.isprintable() or c in '\n\r\t':
                printable += 1
        return printable > len(text) * 0.8
    except (UnicodeDecodeError, UnicodeError):
        return False


def raw_decode(buf, max_depth=20):
    """
    Recursively decode protobuf wire-format bytes into nested dicts.
    Field numbers are preserved as integer keys.
    Returns: dict with int keys -> value (int, str, list, or nested dict)
    """
    result = {}
    offset = 0

    while offset < len(buf):
        key, offset = _decode_varint(buf, offset)
        field_num = key >> 3
        wire_type = key & 0x7

        if wire_type == 0:  # Varint
            value, offset = _decode_varint(buf, offset)
            _add_to_result(result, field_num, value)

        elif wire_type == 1:  # 64-bit
            value, offset = _decode_fixed64(buf, offset)
            _add_to_result(result, field_num, value)

        elif wire_type == 2:  # Length-delimited
            length, offset = _decode_varint(buf, offset)
            end = offset + length
            if end > len(buf):
                raise ValueError(f"Field {field_num} truncated: offset={offset}, length={length}, buf={len(buf)}")
            sub = buf[offset:end]
            offset = end

            # Try to recursively decode as embedded proto
            decoded = _try_decode_embedded(sub, max_depth - 1)

            if decoded is not None:
                _add_to_result(result, field_num, decoded)
            elif _is_printable(sub):
                _add_to_result(result, field_num, sub.decode('utf-8'))
            else:
                _add_to_result(result, field_num, sub.hex())

        elif wire_type == 5:  # 32-bit
            value, offset = _decode_fixed32(buf, offset)
            _add_to_result(result, field_num, value)

        else:
            raise ValueError(f"Unknown wire type {wire_type} at offset {offset}")

    return result


def _try_decode_embedded(buf, depth):
    """Try to decode bytes as embedded proto. Returns decoded dict or None."""
    if depth <= 0 or len(buf) < 2:
        return None

    try:
        decoded = raw_decode(buf, depth)
        if decoded:  # non-empty
            return decoded
    except (ValueError, IndexError, struct.error):
        pass
    return None


def _add_to_result(result, field_num, value):
    """Handle repeated fields: store as list if duplicate field number."""
    if field_num in result:
        existing = result[field_num]
        if isinstance(existing, list):
            existing.append(value)
        else:
            result[field_num] = [existing, value]
    else:
        result[field_num] = value


# Field name mapping matching the .proto field names (preserving_proto_field_name=True)
FIELD_NAMES = {
    # AccountInfoBasic
    1: "accountid", 2: "accounttype", 3: "nickname", 4: "externalid",
    5: "region", 6: "level", 7: "exp", 8: "externaltype",
    9: "externalname", 10: "externalicon", 11: "bannerid", 12: "headpic",
    13: "clanname", 14: "rank", 15: "rankingpoints", 16: "role",
    17: "haselitepass", 18: "badgecnt", 19: "badgeid", 20: "seasonid",
    21: "liked", 22: "isdeleted", 23: "showrank", 24: "lastloginat",
    25: "externaluid", 26: "returnat", 27: "championshipteamname",
    28: "championshipteammembernum", 29: "championshipteamid",
    30: "csrank", 31: "csrankingpoints", 32: "weaponskinshows",
    33: "pinid", 34: "iscsrankingban", 35: "maxrank", 36: "csmaxrank",
    37: "maxrankingpoints", 38: "gamebagshow", 39: "peakrankpos",
    40: "cspeakrankpos", 41: "accountprefers", 42: "periodicrankingpoints",
    43: "periodicrank", 44: "createat", 45: "veteranleavedaystag",
    46: "selecteditemslots", 47: "preveterantype", 48: "title",
    49: "externaliconinfo", 50: "releaseversion", 51: "veteranexpiretime",
    52: "showbrrank", 53: "showcsrank", 54: "clanid", 55: "clanbadgeid",
    56: "customclanbadge", 57: "usecustomclanbadge", 58: "clanframeid",
    59: "membershipstate", 60: "selectoccupations",
    61: "socialhighlightswithbasicinfo", 62: "abtestchoices",
    63: "itemtaginfo", 64: "ranksort", 65: "csranksort",
    66: "hipporank", 67: "hipporankingpoints", 68: "hippomaxrank",
    69: "showhipporank", 70: "hippototalprofit", 71: "hippototalworth",
    72: "modestatsinfos", 73: "badgeinfo", 74: "primeprivilegedetail",
    75: "cspeakpoints", 76: "displaycspeakpoint", 77: "cspeaktournamentrankpos",
    78: "avatarframe", 79: "blacklist", 80: "workshopsummaryinfo",
    81: "spark_info", 82: "social_basic_info",

    # AvatarProfile (within response field 2)
    101: "avatarid", 102: "skincolor", 103: "clothes", 104: "equipedskills",
    105: "isselected", 106: "pveprimaryweapon", 107: "isselectedawaken",
    108: "endtime", 109: "unlocktype", 110: "unlocktime", 111: "ismarkedstar",
    112: "clothestailoreffects",

    # SocialBasicInfo (within response field 9)
    901: "accountid", 902: "gender", 903: "language", 904: "timeonline",
    905: "timeactive", 906: "battletag", 907: "socialtag", 908: "modeprefer",
    909: "signature", 910: "rankshow", 911: "battletagcount",
    912: "signaturebanexpiretime", 913: "leaderboardtitles",

    # AccountPrefers sub-fields (accountprefers message)
    "accountprefers": {
        1: "hidemylobby", 2: "pregameshowchoices", 3: "brpregameshowchoices",
        4: "hidepersonalinfo", 5: "disablefriendspectate", 6: "hideoccupation",
        7: "cspeakpregameshowchoices",
    },

    # PetInfo
    301: "id", 302: "name", 303: "level", 304: "exp", 305: "isselected",
    306: "skinid", 307: "actions", 308: "skills", 309: "selectedskillid",
    310: "ismarkedstar", 311: "endtime",

    # ClanInfoBasic (response field 6)
    601: "clanid", 602: "clanname", 603: "captainid", 604: "clanlevel",
    605: "capacity", 606: "membernum", 607: "honorpoint",

    # Player response top-level
    "basicinfo": 1, "profileinfo": 2, "rankingleaderboardpos": 3,
    "news": 4, "historyepinfo": 5, "clanbasicinfo": 6,
    "captainbasicinfo": 7, "petinfo": 8, "socialinfo": 9,
    "diamondcostres": 10, "creditscoreinfo": 11,
    "preveterantype": 12, "mmrlist": 13, "modestatssummaryinfo": 14,
    "user_spark_info": 15, "collab_spark_info": 16, "collection_custom_list": 17,

    # Stats response
    "solostats": 1, "duostats": 2, "quadstats": 3,

    # AccountInfoWithStatsToClient
    "accountid_s": 1, "gamesplayed": 2, "wins": 3, "kills": 4, "detailedstats": 5,

    # PlayerDetailedStats
    501: "deaths", 502: "top10_times", 503: "top_n_times",
    504: "distance_travelled", 505: "survival_time", 506: "revives",
    507: "highest_kills", 508: "damage", 509: "road_kills",
    510: "headshots", 511: "headshot_kills", 512: "knock_down",
    513: "pick_ups", 514: "rating_points", 515: "rating_enabled_games",
    516: "gold_medal_cnt", 517: "silver_medal_cnt",
}


def apply_field_names(data, field_map=None):
    """
    Convert numeric field keys to human-readable names using the field map.
    Works recursively on nested dicts and lists.
    """
    if field_map is None:
        field_map = FIELD_NAMES

    if isinstance(data, dict):
        result = {}
        for key, value in data.items():
            if isinstance(key, int):
                name = field_map.get(key, f"field_{key}")
            else:
                name = key

            # Check for nested field maps
            nested_map = field_map.get(name) if isinstance(name, str) else None
            if isinstance(nested_map, dict):
                value = apply_field_names(value, nested_map)
            else:
                value = apply_field_names(value, field_map)

            result[name] = value
        return result

    elif isinstance(data, list):
        return [apply_field_names(item, field_map) for item in data]

    return data


def _flatten_raw(raw, prefix=""):
    """Convert raw numbered decode into a flat dict with field keys."""
    result = {}
    if isinstance(raw, dict):
        for k, v in raw.items():
            name = FIELD_NAMES.get(int(k), f"unknown_{k}") if isinstance(k, int) or (isinstance(k, str) and k.isdigit()) else k
            key = f"{prefix}{name}" if prefix else name
            if isinstance(v, dict):
                # Try to see if this is an embedded proto
                inner = _flatten_raw(v, f"{key}.")
                if inner:
                    result[key] = v
                    result.update(inner)
                else:
                    result[key] = v
            elif isinstance(v, list):
                result[key] = [_flatten_raw(item, "") if isinstance(item, dict) else item for item in v]
            else:
                result[key] = v
    return result


def decode_all(response_bytes, proto_message_class=None):
    """
    Comprehensive decode: use compiled proto AND raw wire decode.

    Returns:
        dict with:
          - "known": JSON from compiled proto (named fields, with defaults)
          - "raw": all fields from wire decode (numbered keys)
          - "_all": flattened raw + known merged for completeness
    """
    result = {"raw": None, "known": None}

    # 1. Raw wire-format decode (catches ALL fields, numbered keys)
    raw = raw_decode(response_bytes)
    result["raw"] = raw  # Keep numbered keys

    # 2. Compiled proto decode (named fields, proper types)
    if proto_message_class is not None:
        try:
            from google.protobuf import json_format
            instance = proto_message_class()
            instance.ParseFromString(response_bytes)

            known_json = json_format.MessageToJson(
                instance,
                including_default_value_fields=True,
                preserving_proto_field_name=True,
                indent=None,
                sort_keys=True,
            )
            import json as _json
            known = _json.loads(known_json)
            result["known"] = known
        except Exception:
            result["known"] = None

    return result
