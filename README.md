# FreeFire API

A high-performance reverse-engineered FreeFire API built with Flask, Protocol Buffers, and AES-128-CBC encryption. Interacts directly with Garena's internal game services to provide player stats, profile data, and account management.

## Features

- **13 Supported Regions** — IND, SG, RU, ID, TW, US, VN, TH, ME, PK, CIS, BR, BD
- **Full Proto Field Extraction** — Every server field returned, including fields missing from compiled `.proto` (via wire-format decoder)
- **Token Caching** — In-memory cache with 25-minute TTL, reduces auth calls from 39 to ~3 per query
- **Encrypted Communication** — AES-128-CBC protobuf payloads match the official client
- **Error Resilience** — Structured error handling with `ProtobufError` and `APIError`
- **Timeout Safety** — 15s timeout on all upstream requests
- **Vercel-Ready** — Serverless deployment with 256 MB / 30s max duration

## Quick Start

```sh
git clone https://github.com/iFor-Lux/FreeFire-Api.git
cd FreeFire-Api
pip install -r requirements.txt
python app.py
```

The API starts on `http://0.0.0.0:5000`.

## Endpoints

### Get Player Stats

```
GET /get_player_stats?server=<region>&uid=<uid>&gamemode=<br|cs>&matchmode=<CAREER|NORMAL|RANKED>
```

| Parameter   | Default    | Description                          |
|-------------|------------|--------------------------------------|
| `server`    | `IND`      | Region code                          |
| `uid`       | *required* | Player UID                           |
| `gamemode`  | `br`       | Game mode (`br` / `cs`)              |
| `matchmode` | `CAREER`   | Match type (`CAREER`, `NORMAL`, `RANKED`) |

**Example:**
```
https://freefire-api-six.vercel.app/get_player_stats?server=ind&uid=11959685790&matchmode=RANKED&gamemode=br
```

### Get Player Personal Show

```
GET /get_player_personal_show?server=<region>&uid=<uid>&need_gallery_info=<bool>&call_sign_src=<int>
```

| Parameter          | Default | Description                  |
|--------------------|---------|------------------------------|
| `server`           | `IND`   | Region code                  |
| `uid`              | *required* | Player UID                |
| `need_gallery_info` | `false` | Include gallery info       |
| `call_sign_src`    | `7`     | Call sign source             |

**Example:**
```
https://freefire-api-six.vercel.app/get_player_personal_show?server=ind&uid=1633864660
```

### Search Account by Keyword

```
GET /get_search_account_by_keyword?server=<region>&keyword=<name>
```

| Parameter | Default | Description     |
|-----------|---------|-----------------|
| `server`  | `IND`   | Region code     |
| `keyword` | *required* | Player name  |

**Example:**
```
https://freefire-api-six.vercel.app/get_search_account_by_keyword?server=ind&keyword=Hello
```

## Response Format

Every endpoint returns a unified JSON structure:

```json
{
  "known": {
    "fieldName1": "value",
    "fieldName2": 123
  },
  "raw": {
    "1": "value",
    "2": 123,
    "3": "field_not_in_proto" 
  }
}
```

- **`known`** — Fields that match the compiled `.proto` schema, mapped to their named fields.
- **`raw`** — Every field the server sent, keyed by wire-format field number. Catches fields the `.proto` file doesn't define.

## Supported Regions

| Code | Region           |
|------|------------------|
| IND  | India            |
| SG   | Singapore        |
| RU   | Russia           |
| ID   | Indonesia        |
| TW   | Taiwan           |
| US   | United States    |
| VN   | Vietnam          |
| TH   | Thailand         |
| ME   | Middle East      |
| PK   | Pakistan         |
| CIS  | CIS Region       |
| BR   | Brazil           |
| BD   | Bangladesh       |

> Note: SAC (South America Central) and NA (North America) require guest accounts from those regions. The registration endpoint (`/oauth/guest/register`) is currently disabled by Garena. Obtain credentials via Frida capture from the official Android app.

## Project Structure

```
├── app.py                          # Flask application — routes, caching, error handling
├── vercel.json                     # Vercel serverless configuration
├── requirements.txt                # Python dependencies
├── Api/
│   ├── Account.py                  # Garena OAuth + MajorLogin auth flow
│   ├── InGame.py                   # Player stats, personal show, search
│   └── Errors.py                   # Custom exception classes
├── Configuration/
│   ├── AccountConfiguration.json   # Per-region guest credentials
│   ├── APIConfiguration.py         # Release version (OB53), DEBUG flag
│   └── AESConfiguration.py         # AES keys and IVs
├── Utilities/
│   ├── until.py                    # Protobuf encode/decode, AES-CBC encryption
│   ├── cache.py                    # TokenCache with TTL (25 min)
│   └── proto_decoder.py            # Wire-format protobuf decoder — extracts ALL fields
├── Proto/
│   ├── MajorLogin.proto            # MajorLogin protobuf schema (60+ fields)
│   ├── MajorRegister.proto         # MajorRegister protobuf schema
│   ├── PlayerPersonalShow.proto
│   ├── PlayerStats.proto
│   ├── PlayerCSStats.proto
│   ├── SearchAccountByName.proto
│   └── compiled/                   # Pre-compiled _pb2.py files
└── Additional/
    ├── GenerateAccounts.py         # Python account generator script
    └── generate_accounts.js        # Node.js account generator script
```

## Authentication Flow

```
Client → Flask API → TokenCache check
  ↓ (cache miss)
Garena OAuth (token/grant) → access_token + open_id
  ↓
MajorLogin (AES-CBC protobuf) → JWT + serverUrl
  ↓
Cache for 25 min → Game API calls (stats, profile, etc.)
```

## Configuration

### Account Credentials

Credentials are stored in `Configuration/AccountConfiguration.json`:

```json
{
  "IND": {
    "uid": 4700657236,
    "password": "11AE657CB5F438F880F755E85E3F05027F245CCAA68B88067641650FD2CC3FA0"
  }
}
```

The password is a SHA-256 hash of the raw guest password.

### Environment

Key settings in `Configuration/APIConfiguration.py`:

| Key              | Value  | Description              |
|------------------|--------|--------------------------|
| `RELEASEVERSION` | `OB53` | FreeFire client version  |
| `DEBUG`          | `False`| Enable request logging   |

## Fixes & Improvements

| Issue | Fix |
|-------|-----|
| Duplicate `Content-Type` header overwriting `application/octet-stream` | Removed hardcoded content-type from encrypted payload routes |
| Hardcoded `Content-Length: 16` in InGame.py | Switched to automatic `Content-Length` via requests library |
| 39 auth calls per query (no caching) | Added `TokenCache` with 1500s TTL (~3 calls per query) |
| No timeouts on upstream requests | Added `timeout=15` to all HTTP calls |
| Static `Host` header in PersonalShow | Made `Host` header dynamic per server URL |
| Fields missing from compiled `.proto` not returned | Added `proto_decoder.py` — wire-format decoder returning `known` + `raw` |
| Relative config path broke when run from other dirs | Changed to absolute path via `os.path.dirname(__file__)` |
| Raw protobuf errors surfaced to client | Added `ProtobufError` and `APIError` exception classes |
| `/oauth/guest/register` 404 for all regions | Documented — Garena disabled registration; use Frida for new accounts |

## Deployment

### Vercel (Recommended)

[![Deploy with Vercel](https://vercel.com/button)](https://vercel.com/new/clone?repository-url=https%3A%2F%2Fgithub.com%2FiFor-Lux%2FFreeFire-Api)

Or via CLI:

```sh
npx vercel deploy --prod
```

Configuration in `vercel.json`:

```json
{
  "functions": {
    "app.py": {
      "memory": 256,
      "maxDuration": 30
    }
  }
}
```

## Requirements

- Python 3.8+
- Flask 3.0+
- Flask-Cors 4.0+
- protobuf 7.x
- pycryptodome 3.20+
- requests 2.31+

## License

MIT

## Author

Based on [0xMe/FreeFire-Api](https://github.com/0xMe/FreeFire-Api).
