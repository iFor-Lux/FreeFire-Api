const crypto = require('crypto');
const https = require('https');
const http = require('http');

const REGIONS = ['IND','SG','RU','ID','TW','US','VN','TH','ME','PK','CIS','BR','BD'];
const CLIENT_SECRET = '2ee44819e9b4598845141067b281621874d0d5d7af9d8f7e00c1e54715b7d1e3';
const CLIENT_ID = '100067';
const AES_KEY = Buffer.from('Yg&tc%DEuh6%Zc^8');
const AES_IV = Buffer.from('6oyZDr22E3ychjM%');
const UA_GARENA = 'GarenaMSDK/4.0.19P9(SM-S908E; Android 11; en; IN)';
const UA_UNITY = 'Dalvik/2.1.0 (Linux; U; Android 13; A063 Build/TKQ1.221220.001)';

function xorEncode(x) {
    const k = [0,0,0,2,0,1,7,0,0,0,0,0,2,0,1,7,0,0,0,0,0,2,0,1,7,0,0,0,0,0,2,0];
    return Buffer.from(x, 'utf8').map((b, i) => b ^ k[i % k.length] ^ 48);
}

function varint(n) {
    const r = [];
    while (n >= 0x80) {
        r.push((n & 0x7F) | 0x80);
        n >>>= 7;
    }
    r.push(n & 0x7F);
    return Buffer.from(r);
}

function encodeField(fieldNum, value) {
    if (typeof value === 'number') {
        return Buffer.concat([varint((fieldNum << 3) | 0), varint(value)]);
    }
    const b = typeof value === 'string' ? Buffer.from(value, 'utf8') : value;
    return Buffer.concat([varint((fieldNum << 3) | 2), varint(b.length), b]);
}

function encodeProto(obj) {
    const parts = [];
    const keys = Object.keys(obj).sort((a, b) => a - b);
    for (const k of keys) {
        parts.push(encodeField(parseInt(k), obj[k]));
    }
    return Buffer.concat(parts);
}

function aesEncrypt(plaintext) {
    const cipher = crypto.createCipheriv('aes-128-cbc', AES_KEY, AES_IV);
    cipher.setAutoPadding(true);
    return Buffer.concat([cipher.update(plaintext), cipher.final()]);
}

function httpsPost(url, data, headers) {
    return new Promise((resolve, reject) => {
        const urlObj = new URL(url);
        const mod = urlObj.protocol === 'https:' ? https : http;
        const opts = {
            hostname: urlObj.hostname,
            port: urlObj.port || (urlObj.protocol === 'https:' ? 443 : 80),
            path: urlObj.pathname + urlObj.search,
            method: 'POST',
            headers: { ...headers, 'Content-Length': Buffer.byteLength(data) },
            timeout: 15000,
        };
        const req = mod.request(opts, (res) => {
            let body = '';
            res.on('data', (chunk) => body += chunk);
            res.on('end', () => {
                try { resolve({ status: res.statusCode, body: JSON.parse(body) }); }
                catch { resolve({ status: res.statusCode, body }); }
            });
        });
        req.on('error', reject);
        req.on('timeout', () => { req.destroy(); reject(new Error('Timeout')); });
        req.write(data);
        req.end();
    });
}

async function register(region) {
    const pwd = String(Math.floor(Math.random() * 9000000000) + 1000000000);
    const pwdHash = crypto.createHash('sha256').update(pwd).digest('hex').toUpperCase();

    // Step 1: Guest Register
    const regBody = new URLSearchParams({
        password: pwdHash, client_type: '2', source: '2', app_id: CLIENT_ID
    }).toString();
    const sign = crypto.createHmac('sha256', CLIENT_SECRET).update(regBody).digest('hex');
    const regHeaders = {
        'User-Agent': UA_GARENA,
        'Authorization': `Signature ${sign}`,
        'Content-Type': 'application/x-www-form-urlencoded',
    };

    let res;
    try {
        res = await httpsPost('https://ffmconnect.live.gop.garenanow.com/oauth/guest/register', regBody, regHeaders);
    } catch (e) {
        console.log(`  [${region}] Register failed: ${e.message}`);
        return null;
    }
    if (res.status !== 200 || !res.body.uid) {
        console.log(`  [${region}] Register response: ${res.status}`);
        return null;
    }
    const uid = res.body.uid;
    console.log(`  [${region}] Registered UID: ${uid}`);

    // Step 2: Token Grant
    const tokenBody = new URLSearchParams({
        uid: String(uid), password: pwdHash, response_type: 'token',
        client_type: '2', client_secret: CLIENT_SECRET, client_id: CLIENT_ID
    }).toString();
    const tokenHeaders = { 'User-Agent': UA_GARENA, 'Content-Type': 'application/x-www-form-urlencoded' };

    try {
        res = await httpsPost('https://ffmconnect.live.gop.garenanow.com/oauth/guest/token/grant', tokenBody, tokenHeaders);
    } catch (e) {
        console.log(`  [${region}] Token grant failed: ${e.message}`);
        return null;
    }
    if (res.status !== 200) {
        console.log(`  [${region}] Token grant status: ${res.status}`);
        return null;
    }
    const at = res.body.access_token;
    const oid = res.body.open_id || res.body.openId || res.body.openid;
    if (!at || !oid) {
        console.log(`  [${region}] Token grant missing fields`);
        return null;
    }
    console.log(`  [${region}] Got token`);

    // Step 3: Major Register
    const nick = `0xMe${String(Math.floor(Math.random() * 9000) + 1000)}`;
    const protoFields = {
        1: nick,
        2: at,
        3: oid,
        5: 102000007,
        6: 4,
        7: 1,
        13: 1,
        14: xorEncode(oid),
        15: region,
        16: 1
    };
    const protoBytes = encodeProto(protoFields);
    const encrypted = aesEncrypt(protoBytes);

    const majorHeaders = {
        'Authorization': `Bearer ${at}`,
        'X-Unity-Version': '2018.4.11f1',
        'X-GA': 'v1 1',
        'ReleaseVersion': 'OB53',
        'Content-Type': 'application/octet-stream',
        'User-Agent': UA_UNITY,
        'Host': 'loginbp.ggpolarbear.com',
        'Connection': 'Keep-Alive',
        'Accept-Encoding': 'gzip',
    };

    try {
        res = await httpsPost('https://loginbp.ggpolarbear.com/MajorRegister', encrypted, majorHeaders);
    } catch (e) {
        console.log(`  [${region}] Major register failed: ${e.message}`);
        return null;
    }
    if (res.status === 200) {
        console.log(`  [${region}] Success!`);
        return { uid: String(uid), password: pwdHash };
    } else {
        console.log(`  [${region}] Major register status: ${res.status} ${typeof res.body === 'object' ? JSON.stringify(res.body).substring(0,100) : String(res.body).substring(0,100)}`);
        return null;
    }
}

async function main() {
    console.log('=== FreeFire Account Generator ===\n');
    const accounts = {};
    for (const region of REGIONS) {
        process.stdout.write(`\n[${region}] Registering...\n`);
        const result = await register(region);
        if (result) {
            accounts[region] = result;
        } else {
            accounts[region] = { uid: 0, password: 'FAILED' };
        }
    }

    console.log('\n=== Results ===\n');
    console.log(JSON.stringify(accounts, null, 4));

    const fs = require('fs');
    const configPath = require('path').join(__dirname, '..', 'Configuration', 'AccountConfiguration.json');
    const existing = JSON.parse(fs.readFileSync(configPath, 'utf8'));
    for (const [region, data] of Object.entries(accounts)) {
        if (data.password !== 'FAILED') {
            existing[region] = data;
        }
    }
    fs.writeFileSync(configPath, JSON.stringify(existing, null, 4) + '\n');
    console.log(`\nSaved to Configuration/AccountConfiguration.json`);
}

main().catch(console.error);
