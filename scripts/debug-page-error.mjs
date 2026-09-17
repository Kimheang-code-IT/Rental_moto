import http from 'node:http'
import { spawn } from 'node:child_process'
import { mkdtempSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

const TARGET = process.argv[2] || 'http://172.16.112.26/'
const CHROME = process.env.CHROME_PATH || 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe'
const userData = mkdtempSync(join(tmpdir(), 'hw-chrome-'))
const port = 9333

function getJson(url) {
  return new Promise((resolve, reject) => {
    http.get(url, (res) => {
      let data = ''
      res.on('data', (c) => { data += c })
      res.on('end', () => {
        try { resolve(JSON.parse(data)) }
        catch (e) { reject(e) }
      })
    }).on('error', reject)
  })
}

const chrome = spawn(CHROME, [
  '--headless=new',
  '--disable-gpu',
  '--no-sandbox',
  `--user-data-dir=${userData}`,
  `--remote-debugging-port=${port}`,
  'about:blank',
], { stdio: 'ignore' })

await new Promise((r) => setTimeout(r, 2500))

try {
  const list = await getJson(`http://127.0.0.1:${port}/json/list`)
  const page = list.find((p) => p.type === 'page') || list[0]
  const ws = new WebSocket(page.webSocketDebuggerUrl)
  let id = 0
  const pending = new Map()
  const logs = []

  function send(method, params = {}) {
    return new Promise((resolve, reject) => {
      const i = ++id
      pending.set(i, { resolve, reject })
      ws.send(JSON.stringify({ id: i, method, params }))
    })
  }

  await new Promise((resolve, reject) => {
    ws.addEventListener('open', resolve)
    ws.addEventListener('error', reject)
  })

  ws.addEventListener('message', (event) => {
    const msg = JSON.parse(String(event.data))
    if (msg.id && pending.has(msg.id)) {
      const { resolve, reject } = pending.get(msg.id)
      pending.delete(msg.id)
      if (msg.error) reject(new Error(JSON.stringify(msg.error)))
      else resolve(msg.result)
    }
    if (msg.method === 'Runtime.exceptionThrown') {
      const d = msg.params.exceptionDetails || {}
      logs.push({
        type: 'exception',
        text: d.text,
        url: d.url,
        line: d.lineNumber,
        col: d.columnNumber,
        exception: d.exception,
        stackTrace: d.stackTrace,
      })
    }
    if (msg.method === 'Runtime.consoleAPICalled') {
      logs.push({
        type: 'console',
        level: msg.params.type,
        args: (msg.params.args || []).map((a) => a.value ?? a.description ?? a.unserializableValue ?? a),
      })
    }
  })

  await send('Runtime.enable')
  await send('Network.enable')
  await send('Page.enable')
  await send('Page.addScriptToEvaluateOnNewDocument', {
    source: `
      window.__HW_ERRORS = [];
      const push = (item) => { try { window.__HW_ERRORS.push(item); } catch {} };
      window.addEventListener('error', (e) => {
        push({
          kind: 'window.error',
          message: e.message,
          filename: e.filename,
          lineno: e.lineno,
          colno: e.colno,
          stack: e.error && e.error.stack,
          name: e.error && e.error.name,
          cause: e.error && e.error.cause && String(e.error.cause),
          statusCode: e.error && e.error.statusCode,
          statusMessage: e.error && e.error.statusMessage,
          data: e.error && e.error.data,
        });
      });
      window.addEventListener('unhandledrejection', (e) => {
        const r = e.reason;
        push({
          kind: 'unhandledrejection',
          message: r && (r.message || String(r)),
          stack: r && r.stack,
          name: r && r.name,
          cause: r && r.cause && String(r.cause),
          statusCode: r && r.statusCode,
          statusMessage: r && r.statusMessage,
        });
      });
      const orig = console.error;
      console.error = function (...args) {
        push({
          kind: 'console.error',
          args: args.map((a) => {
            try {
              if (a && typeof a === 'object') {
                return {
                  message: a.message,
                  stack: a.stack,
                  name: a.name,
                  statusCode: a.statusCode,
                  statusMessage: a.statusMessage,
                  cause: a.cause ? String(a.cause) : undefined,
                  string: String(a),
                  json: JSON.stringify(a, Object.getOwnPropertyNames(a)),
                };
              }
              return a;
            } catch (err) {
              return String(a);
            }
          }),
        });
        return orig.apply(this, args);
      };
    `,
  })
  await send('Page.navigate', { url: TARGET })
  await new Promise((r) => setTimeout(r, 7000))

  const title = await send('Runtime.evaluate', { expression: 'document.title', returnByValue: true })
  const body = await send('Runtime.evaluate', { expression: 'document.body ? document.body.innerText : ""', returnByValue: true })
  const hwErrors = await send('Runtime.evaluate', {
    expression: 'JSON.stringify(window.__HW_ERRORS || [])',
    returnByValue: true,
  })
  const html = await send('Runtime.evaluate', {
    expression: 'document.getElementById("__nuxt") ? document.getElementById("__nuxt").innerHTML.slice(0, 2500) : ""',
    returnByValue: true,
  })

  console.log(JSON.stringify({
    title: title.result?.value,
    body: body.result?.value,
    hwErrors: JSON.parse(hwErrors.result?.value || '[]'),
    nuxtHtml: html.result?.value,
    logs,
  }, null, 2))
}
finally {
  try { chrome.kill() } catch {}
  try { rmSync(userData, { recursive: true, force: true }) } catch {}
}
