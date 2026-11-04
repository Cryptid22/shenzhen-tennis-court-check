#!/usr/bin/env node
"use strict";

const childProcess = require("child_process");
const fs = require("fs");
const os = require("os");
const path = require("path");

const CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const PROFILE_ROOT = path.join(
  os.homedir(),
  "Library/Containers/com.tencent.xinWeChat/Data/Documents/app_data/radium/web/profiles",
);
const APP_ID = "wxf35a09af5b0d9119";
const BASE_URL = "https://wxsports.ydmap.cn";
const VENUES = [
  ["郑洁（深圳）国际网球俱乐部", "102042"],
  ["益田网球场", "100242"],
  ["皇岗公园网球中心", "100241"],
  ["彩田公园康体中心网球场", "106646"],
  ["大沙河国际网球交流中心", "100220"],
  ["北站中心公园体育中心", "102911"],
];

function readVarint(buffer, offset) {
  let value = 0;
  let shift = 0;
  for (let index = 0; index < 10; index += 1) {
    const byte = buffer[offset];
    offset += 1;
    value += (byte & 0x7f) * (2 ** shift);
    if (!(byte & 0x80)) return [value, offset];
    shift += 7;
  }
  throw new Error("微信凭证记录格式异常");
}

function openIdFromLog(logPath) {
  const buffer = fs.readFileSync(logPath);
  let offset = 0;
  let latest = "";
  while (offset + 7 <= buffer.length) {
    const length = buffer.readUInt16LE(offset + 4);
    const recordType = buffer[offset + 6];
    const record = buffer.subarray(offset + 7, offset + 7 + length);
    offset += 7 + length;
    if (!length || recordType !== 1 || record.length < 12) continue;

    let position = 12;
    const count = record.readUInt32LE(8);
    for (let index = 0; index < count && position < record.length; index += 1) {
      const operation = record[position];
      position += 1;
      let keyLength;
      [keyLength, position] = readVarint(record, position);
      const key = record.subarray(position, position + keyLength).toString("utf8");
      position += keyLength;
      if (operation !== 1) continue;
      let valueLength;
      [valueLength, position] = readVarint(record, position);
      const value = record.subarray(position, position + valueLength);
      position += valueLength;
      if (!key.endsWith("\x00\x01Entry-OpenId")) continue;
      try {
        latest = JSON.parse(value.subarray(1).toString("utf8"));
      } catch (_) {
        // Keep looking for a newer valid record.
      }
    }
  }
  return latest;
}

function findEntryOpenId() {
  const fromEnvironment = (process.env.TENNIS_CHECK_WEIXUN_OPENID || "").trim();
  if (fromEnvironment) return fromEnvironment;
  if (!fs.existsSync(PROFILE_ROOT)) return "";

  const logs = [];
  for (const profile of fs.readdirSync(PROFILE_ROOT)) {
    const leveldb = path.join(PROFILE_ROOT, profile, "Local Storage", "leveldb");
    if (!fs.existsSync(leveldb)) continue;
    for (const name of fs.readdirSync(leveldb)) {
      if (!name.endsWith(".log")) continue;
      const filename = path.join(leveldb, name);
      try {
        logs.push([fs.statSync(filename).mtimeMs, filename]);
      } catch (_) {
        // A WebView may disappear while profiles are enumerated.
      }
    }
  }
  logs.sort((left, right) => right[0] - left[0]);
  for (const [, filename] of logs) {
    try {
      const value = openIdFromLog(filename);
      if (value) return value;
    } catch (_) {
      // Try the next WebView profile.
    }
  }
  return "";
}

function sleep(milliseconds) {
  return new Promise((resolve) => setTimeout(resolve, milliseconds));
}

function shanghaiMidnight(dateText) {
  const value = Date.parse(`${dateText}T00:00:00+08:00`);
  if (!Number.isFinite(value)) throw new Error("日期应为 YYYY-MM-DD");
  return value;
}

function freePort() {
  return 9300 + Math.floor(Math.random() * 500);
}

async function waitFor(check, timeoutMs, message) {
  const deadline = Date.now() + timeoutMs;
  let lastError;
  while (Date.now() < deadline) {
    try {
      const value = await check();
      if (value) return value;
    } catch (error) {
      lastError = error;
    }
    await sleep(150);
  }
  throw lastError || new Error(message);
}

class DevToolsPage {
  constructor(webSocket) {
    this.webSocket = webSocket;
    this.nextId = 0;
    this.pending = new Map();
    webSocket.onmessage = (event) => {
      const message = JSON.parse(event.data);
      if (!message.id || !this.pending.has(message.id)) return;
      const [resolve, reject] = this.pending.get(message.id);
      this.pending.delete(message.id);
      if (message.error) reject(new Error(message.error.message));
      else resolve(message.result);
    };
  }

  call(method, params = {}) {
    return new Promise((resolve, reject) => {
      const id = ++this.nextId;
      this.pending.set(id, [resolve, reject]);
      this.webSocket.send(JSON.stringify({ id, method, params }));
    });
  }

  async evaluate(expression) {
    const response = await this.call("Runtime.evaluate", {
      expression,
      returnByValue: true,
      awaitPromise: true,
    });
    if (response.exceptionDetails) throw new Error("页面数据读取失败");
    return response.result.value;
  }
}

async function connect(port) {
  await waitFor(
    async () => {
      const response = await fetch(`http://127.0.0.1:${port}/json/version`);
      return response.ok;
    },
    10000,
    "无法启动临时 Chrome 会话",
  );
  const response = await fetch(`http://127.0.0.1:${port}/json/new?about:blank`, {
    method: "PUT",
  });
  const target = await response.json();
  const webSocket = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((resolve, reject) => {
    webSocket.onopen = resolve;
    webSocket.onerror = reject;
  });
  const page = new DevToolsPage(webSocket);
  await page.call("Page.enable");
  await page.call("Runtime.enable");
  return page;
}

async function waitForPortal(page, timeoutMs) {
  await waitFor(
    async () => page.evaluate(`Boolean(
      document.readyState === "complete" &&
      localStorage.getItem("Entry-OpenId")
    )`),
    timeoutMs,
    "威逊安全校验页面加载超时",
  );
  // The WAF shim is intentionally not a stable public property. Give the
  // site's own startup request a brief chance to install it before routing.
  await sleep(2000);
}

const EXTRACT_SLOTS = `(() => {
  const queryDate = QUERY_DATE;
  const wantedDate = WANTED_DATE;
  const section = [...document.querySelectorAll("section")]
    .map((element) => element.__vue__)
    .find((component) => component && component.$data && "curDate" in component.$data);
  const table = [...document.querySelectorAll("div")]
    .map((element) => element.__vue__)
    .find((component) => component && component.$data && "selectedCols" in component.$data);
  if (!section || !table || Number(section.curDate) !== wantedDate || table.tableLoading) {
    return null;
  }
  const blockedText = /已预订|预订中|已占用|已过期|开放预订|电话预约|无票|约满/;
  const seen = new Set();
  const slots = [];
  for (const element of document.querySelectorAll("td")) {
    const component = element.__vue__;
    const item = component?.obj;
    const platform = item?.platformInfo;
    if (!item || !platform?.venueName || !item.startTime || !item.endTime) continue;
    const key = [platform.venueId, item.startTime, item.endTime].join(":");
    if (seen.has(key)) continue;
    seen.add(key);
    const display = component.textFun?.(item)?.name || "";
    const classes = component.classObj || {};
    const available = Boolean(
      item.priceBean &&
      !item.orderInfo &&
      !item.orderNoBook &&
      !item.expired &&
      !classes.noBook &&
      !classes.noOnline &&
      !classes.noOpen &&
      !blockedText.test(display)
    );
    const time = (milliseconds) => new Intl.DateTimeFormat("en-GB", {
      hour: "2-digit", minute: "2-digit", hour12: false, timeZone: "Asia/Shanghai",
    }).format(new Date(milliseconds));
    slots.push({
      court: platform.venueName,
      date: queryDate,
      start: time(item.startTime),
      end: time(item.endTime),
      available,
    });
  }
  return slots.length ? slots : null;
})()`;

async function queryVenue(page, label, salesId, queryDate, wantedDate, timeoutMs) {
  const url = `${BASE_URL}/booking/schedule/${salesId}?curDate=${wantedDate}`;
  await page.call("Page.navigate", { url });
  await waitFor(
    async () => page.evaluate(`(() => {
      const pageComponent = [...document.querySelectorAll("section")]
        .map((element) => element.__vue__)
        .find((component) => component?.serverData?.itemDataList?.length);
      if (!pageComponent) return false;
      const items = pageComponent.serverData.itemDataList;
      const tennis = items.find((item) => /^网球$/.test(item.salesItemName || ""))
        || items.find((item) => /网球/.test(item.salesItemName || ""));
      if (!tennis) throw new Error("该入口没有网球项目");
      if (pageComponent.salesItemId !== tennis.salesItemId) {
        pageComponent.salesItemId = tennis.salesItemId;
        return false;
      }
      return true;
    })()`),
    timeoutMs,
    `${label}网球项目加载超时`,
  );
  const expression = EXTRACT_SLOTS
    .replace("QUERY_DATE", JSON.stringify(queryDate))
    .replace("WANTED_DATE", String(wantedDate));
  const slots = await waitFor(
    async () => page.evaluate(expression),
    timeoutMs,
    `${label}场地数据加载超时`,
  );
  return slots;
}

async function main() {
  const queryDate = process.argv[2];
  const timeoutSeconds = Number(process.argv[3] || "15");
  const timeoutMs = Math.max(5000, timeoutSeconds * 1000);
  const wantedDate = shanghaiMidnight(queryDate);
  const entryOpenId = findEntryOpenId();
  if (!entryOpenId) throw new Error("找不到微信登录凭证，请重新打开威逊文体");
  if (!fs.existsSync(CHROME)) throw new Error("找不到 Google Chrome");

  const userDataDir = fs.mkdtempSync(path.join(os.tmpdir(), "tennis-weixun-"));
  const port = freePort();
  const chrome = childProcess.spawn(
    CHROME,
    [
      "--headless=new",
      `--remote-debugging-port=${port}`,
      `--user-data-dir=${userDataDir}`,
      "--no-first-run",
      "--disable-default-apps",
      "about:blank",
    ],
    { stdio: "ignore" },
  );

  let page;
  try {
    page = await connect(port);
    const entryUrl = `${BASE_URL}/?redirect=&appid=${APP_ID}&envVersion=release&openid=${encodeURIComponent(entryOpenId)}`;
    await page.call("Page.navigate", { url: entryUrl });
    // Let the portal complete its login redirect and security bootstrap. The
    // WAF deliberately exposes no stable readiness property, so the booking
    // page itself remains the authoritative success check below.
    await sleep(6000);

    const venues = [];
    const errors = [];
    for (const [label, salesId] of VENUES) {
      try {
        const slots = await queryVenue(page, label, salesId, queryDate, wantedDate, timeoutMs);
        venues.push({ label, salesId, slots });
      } catch (error) {
        errors.push({ label, reason: error.message || "查询失败" });
      }
    }
    process.stdout.write(JSON.stringify({ venues, errors }));
  } finally {
    if (page) page.webSocket.close();
    chrome.kill("SIGTERM");
    await sleep(300);
    fs.rmSync(userDataDir, { recursive: true, force: true });
  }
}

main().catch((error) => {
  process.stdout.write(JSON.stringify({ fatal: error.message || "威逊查询失败" }));
  process.exitCode = 1;
});
