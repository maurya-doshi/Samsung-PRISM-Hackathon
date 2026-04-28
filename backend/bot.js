require('dotenv').config();

const TelegramBot = require('node-telegram-bot-api');
const axios = require('axios');
const sqlite3 = require('sqlite3').verbose();
const cron = require('node-cron');

// ── Config ────────────────────────────────────────────────────────────────────
const TOKEN = process.env.TOKEN;
const PYTHON_API = 'http://localhost:8000'; // FastAPI base URL

const bot = new TelegramBot(TOKEN, { polling: true });

// ── Database Setup ────────────────────────────────────────────────────────────
const db = new sqlite3.Database('./alerts.db', (err) => {
  if (err) return console.error('DB error:', err.message);
  console.log('Connected to SQLite database.');
});

db.run(`
  CREATE TABLE IF NOT EXISTS alerts (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id   INTEGER NOT NULL,
    ticker    TEXT    NOT NULL COLLATE NOCASE,
    target    REAL    NOT NULL,
    direction TEXT    NOT NULL,
    triggered INTEGER DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
  )
`);

db.run(`
  CREATE TABLE IF NOT EXISTS portfolio (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id    INTEGER NOT NULL,
    ticker     TEXT    NOT NULL COLLATE NOCASE,
    quantity   REAL    NOT NULL,
    buy_price  REAL    NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
  )
`);

// ── Helpers ───────────────────────────────────────────────────────────────────

/** Fetch analysis from Python FastAPI service */
async function fetchAnalysis(ticker) {
  const res = await axios.get(`${PYTHON_API}/analysis`, {
    params: { ticker },
    timeout: 15000,
  });
  return res.data; // { ticker, price, ma20, ma50, rsi, signal }
}

/** Fetch LLM explanation from Python/Ollama service */
async function fetchExplanation(analysisData) {
  const res = await axios.post(`${PYTHON_API}/explain`, analysisData, {
    timeout: 60000,
  });
  return res.data.explanation;
}

/** Format analysis result into a readable message */
function formatAnalysis(data, explanation) {
  const signal = {
    buy:  '🟢 BUY',
    sell: '🔴 SELL',
    hold: '🟡 HOLD',
  }[data.signal?.toLowerCase()] ?? '⚪ UNKNOWN';

  return (
    `📊 *${data.ticker.toUpperCase()} Analysis*\n` +
    `━━━━━━━━━━━━━━━━━━\n` +
    `💰 Price:  ₹${data.price}\n` +
    `📈 MA20:   ₹${data.ma20}\n` +
    `📉 MA50:   ₹${data.ma50}\n` +
    `⚡ RSI:    ${data.rsi}\n` +
    `📌 Signal: ${signal}\n` +
    `━━━━━━━━━━━━━━━━━━\n` +
    `🤖 *AI Insight:*\n${explanation ?? '_Not available_'}`
  );
}

// ── Commands ──────────────────────────────────────────────────────────────────

// /start
bot.onText(/\/start/, (msg) => {
  bot.sendMessage(
    msg.chat.id,
    `👋 *Stock Intelligence Bot* is live!\n\n` +
    `Available commands:\n` +
    `• /analyze <ticker> – Full stock analysis\n` +
    `• /alert <ticker> <price> – Set a price alert\n` +
    `• /alerts – List your active alerts\n` +
    `• /cancelalert <id> – Remove an alert\n` +
    `• /buy <ticker> <qty> <price> – Add stock to portfolio\n` +
    `• /sell <ticker> – Remove stock from portfolio\n` +
    `• /portfolio – View your portfolio\n` +
    `• /help – Show this message`,
    { parse_mode: 'Markdown' }
  );
});

// /help
bot.onText(/\/help/, (msg) => {
  bot.sendMessage(
    msg.chat.id,
    `*Commands*\n\n` +
    `📊 *Analysis*\n` +
    `/analyze RELIANCE – Analyze a stock\n\n` +
    `🔔 *Alerts*\n` +
    `/alert TCS 3500 – Alert when TCS hits ₹3500\n` +
    `/alerts – View all your active alerts\n` +
    `/cancelalert 3 – Cancel alert #3\n\n` +
    `💼 *Portfolio*\n` +
    `/buy TCS 10 3500 – Buy 10 shares of TCS at ₹3500\n` +
    `/sell TCS 5 – Sell 5 shares of TCS\n` +
    `/sell TCS – Sell entire TCS holding\n` +
    `/portfolio – View your holdings`,
    { parse_mode: 'Markdown' }
  );
});

// /analyze <ticker>
bot.onText(/\/analyze\s+(\S+)/i, async (msg, match) => {
  const chatId = msg.chat.id;
  const ticker = match[1].toUpperCase();

  const waiting = await bot.sendMessage(chatId, `🔍 Fetching analysis for *${ticker}*…`, {
    parse_mode: 'Markdown',
  });

  try {
    const data = await fetchAnalysis(ticker);

    // Try to get LLM explanation (non-blocking – won't fail if unavailable)
    let explanation = null;
    try {
      explanation = await fetchExplanation(data);
    } catch {
      explanation = '_AI explanation service unavailable._';
    }

    await bot.editMessageText(formatAnalysis(data, explanation), {
      chat_id: chatId,
      message_id: waiting.message_id,
      parse_mode: 'Markdown',
    });
  } catch (err) {
    console.error('/analyze error:', err.message);
    bot.editMessageText(
      `❌ Could not fetch analysis for *${ticker}*. Is the Python service running?`,
      { chat_id: chatId, message_id: waiting.message_id, parse_mode: 'Markdown' }
    );
  }
});

// /alert <ticker> <price>
bot.onText(/\/alert\s+(\S+)\s+([\d.]+)/i, (msg, match) => {
  const chatId = msg.chat.id;
  const ticker = match[1].toUpperCase();
  const target  = parseFloat(match[2]);

  if (isNaN(target) || target <= 0) {
    return bot.sendMessage(chatId, '❌ Invalid price. Usage: /alert TCS 3500');
  }

  // We'll determine direction at trigger time based on current price.
  // For now, store as a generic alert and resolve direction on first check.
  db.run(
    `INSERT INTO alerts (chat_id, ticker, target, direction) VALUES (?, ?, ?, 'any')`,
    [chatId, ticker, target],
    function (err) {
      if (err) return bot.sendMessage(chatId, '❌ Failed to save alert.');
      bot.sendMessage(
        chatId,
        `✅ Alert set!\n📌 *${ticker}* @ ₹${target}\nID: \`${this.lastID}\`\n\nYou'll be notified when the price crosses this level.`,
        { parse_mode: 'Markdown' }
      );
    }
  );
});

// /alerts – list active alerts for this user
bot.onText(/\/alerts$/, (msg) => {
  const chatId = msg.chat.id;

  db.all(
    `SELECT * FROM alerts WHERE chat_id = ? AND triggered = 0 ORDER BY id`,
    [chatId],
    (err, rows) => {
      if (err || !rows.length) {
        return bot.sendMessage(chatId, 'ℹ️ You have no active alerts.');
      }
      const lines = rows.map(
        (r) => `• #${r.id}  *${r.ticker}*  @ ₹${r.target}`
      );
      bot.sendMessage(chatId, `*Your Active Alerts*\n\n${lines.join('\n')}`, {
        parse_mode: 'Markdown',
      });
    }
  );
});

// /cancelalert <id>
bot.onText(/\/cancelalert\s+(\d+)/i, (msg, match) => {
  const chatId = msg.chat.id;
  const id = parseInt(match[1]);

  db.run(
    `DELETE FROM alerts WHERE id = ? AND chat_id = ?`,
    [id, chatId],
    function (err) {
      if (err || this.changes === 0) {
        return bot.sendMessage(chatId, `❌ Alert #${id} not found.`);
      }
      bot.sendMessage(chatId, `🗑️ Alert #${id} cancelled.`);
    }
  );
});

// ── Alert Scheduler (every 2 minutes) ─────────────────────────────────────────
cron.schedule('*/2 * * * *', async () => {
  console.log('[cron] Checking alerts…');

  db.all(`SELECT * FROM alerts WHERE triggered = 0`, [], async (err, alerts) => {
    if (err || !alerts.length) return;

    // Group by ticker to minimise API calls
    const byTicker = alerts.reduce((acc, a) => {
      (acc[a.ticker] = acc[a.ticker] || []).push(a);
      return acc;
    }, {});

    for (const [ticker, group] of Object.entries(byTicker)) {
      let currentPrice;
      try {
        const data = await fetchAnalysis(ticker);
        currentPrice = data.price;
      } catch {
        console.warn(`[cron] Could not fetch price for ${ticker}`);
        continue;
      }

      for (const alert of group) {
        const hit =
          (alert.direction === 'above' && currentPrice >= alert.target) ||
          (alert.direction === 'below' && currentPrice <= alert.target) ||
          (alert.direction === 'any');    // first check sets direction

        if (alert.direction === 'any') {
          // Lock in direction based on current vs target
          const dir = currentPrice >= alert.target ? 'above' : 'below';
          db.run(`UPDATE alerts SET direction = ? WHERE id = ?`, [dir, alert.id]);
          continue; // evaluate on next tick
        }

        if (hit) {
          bot.sendMessage(
            alert.chat_id,
            `🚨 *Price Alert Triggered!*\n\n` +
            `📌 *${ticker}* has reached ₹${currentPrice}\n` +
            `🎯 Your target: ₹${alert.target}`,
            { parse_mode: 'Markdown' }
          );

          db.run(`UPDATE alerts SET triggered = 1 WHERE id = ?`, [alert.id]);
        }
      }
    }
  });
});

// ── Portfolio Commands ────────────────────────────────────────────────────────

// /buy <ticker> <quantity> <price>
bot.onText(/\/buy\s+(\S+)\s+([\d.]+)\s+([\d.]+)/i, (msg, match) => {
  const chatId   = msg.chat.id;
  const ticker   = match[1].toUpperCase();
  const quantity = parseFloat(match[2]);
  const buyPrice = parseFloat(match[3]);

  if (isNaN(quantity) || quantity <= 0 || isNaN(buyPrice) || buyPrice <= 0) {
    return bot.sendMessage(chatId, '❌ Invalid input. Usage: /buy TCS 10 3500');
  }

  // If ticker already exists for this user, add to the holding (average down/up)
  db.get(
    `SELECT * FROM portfolio WHERE chat_id = ? AND ticker = ?`,
    [chatId, ticker],
    (err, row) => {
      if (row) {
        const newQty   = row.quantity + quantity;
        const avgPrice = ((row.quantity * row.buy_price) + (quantity * buyPrice)) / newQty;
        db.run(
          `UPDATE portfolio SET quantity = ?, buy_price = ? WHERE id = ?`,
          [newQty, avgPrice, row.id],
          (err) => {
            if (err) return bot.sendMessage(chatId, '❌ Failed to update holding.');
            bot.sendMessage(
              chatId,
              `✅ *${ticker}* holding updated!\n` +
              `📦 Total qty: ${newQty}\n` +
              `💰 Avg buy price: ₹${avgPrice.toFixed(2)}`,
              { parse_mode: 'Markdown' }
            );
          }
        );
      } else {
        db.run(
          `INSERT INTO portfolio (chat_id, ticker, quantity, buy_price) VALUES (?, ?, ?, ?)`,
          [chatId, ticker, quantity, buyPrice],
          (err) => {
            if (err) return bot.sendMessage(chatId, '❌ Failed to save holding.');
            bot.sendMessage(
              chatId,
              `✅ Added to portfolio!\n` +
              `📌 *${ticker}*  ×${quantity}  @ ₹${buyPrice}`,
              { parse_mode: 'Markdown' }
            );
          }
        );
      }
    }
  );
});

// /sell <ticker> [quantity]  — omit quantity to sell entire holding
bot.onText(/\/sell\s+(\S+)(?:\s+([\d.]+))?/i, (msg, match) => {
  const chatId  = msg.chat.id;
  const ticker  = match[1].toUpperCase();
  const sellQty = match[2] ? parseFloat(match[2]) : null;

  if (sellQty !== null && (isNaN(sellQty) || sellQty <= 0)) {
    return bot.sendMessage(chatId, '❌ Invalid quantity. Usage: /sell TCS 5  or  /sell TCS');
  }

  db.get(
    `SELECT * FROM portfolio WHERE chat_id = ? AND ticker = ?`,
    [chatId, ticker],
    (err, row) => {
      if (err || !row) {
        return bot.sendMessage(chatId, `❌ *${ticker}* not found in your portfolio.`, { parse_mode: 'Markdown' });
      }

      // Sell all if no quantity specified
      const qty = sellQty ?? row.quantity;

      if (qty > row.quantity) {
        return bot.sendMessage(
          chatId,
          `❌ You only have *${row.quantity}* shares of *${ticker}*.`,
          { parse_mode: 'Markdown' }
        );
      }

      if (qty === row.quantity) {
        // Remove the holding entirely
        db.run(`DELETE FROM portfolio WHERE id = ?`, [row.id], (err) => {
          if (err) return bot.sendMessage(chatId, '❌ Failed to update portfolio.');
          bot.sendMessage(chatId, `🗑️ Sold all *${qty}* shares of *${ticker}*.`, { parse_mode: 'Markdown' });
        });
      } else {
        // Reduce quantity — buy_price (avg) stays the same
        const remaining = row.quantity - qty;
        db.run(`UPDATE portfolio SET quantity = ? WHERE id = ?`, [remaining, row.id], (err) => {
          if (err) return bot.sendMessage(chatId, '❌ Failed to update portfolio.');
          bot.sendMessage(
            chatId,
            `✅ Sold *${qty}* shares of *${ticker}*.\n📦 Remaining: *${remaining}* shares @ ₹${row.buy_price.toFixed(2)}`,
            { parse_mode: 'Markdown' }
          );
        });
      }
    }
  );
});

// /portfolio
bot.onText(/\/portfolio$/, (msg) => {
  const chatId = msg.chat.id;

  db.all(
    `SELECT * FROM portfolio WHERE chat_id = ? ORDER BY ticker`,
    [chatId],
    (err, rows) => {
      if (err || !rows.length) {
        return bot.sendMessage(chatId, 'ℹ️ Your portfolio is empty. Use /buy to add stocks.');
      }

      const lines = rows.map((r) => {
        const invested = (r.quantity * r.buy_price).toFixed(2);
        return `• *${r.ticker}*  ×${r.quantity}  @ ₹${r.buy_price.toFixed(2)}  (₹${invested} invested)`;
      });

      const totalInvested = rows.reduce((sum, r) => sum + r.quantity * r.buy_price, 0);

      bot.sendMessage(
        chatId,
        `💼 *Your Portfolio*\n━━━━━━━━━━━━━━━━━━\n${lines.join('\n')}\n━━━━━━━━━━━━━━━━━━\n💰 Total invested: ₹${totalInvested.toFixed(2)}`,
        { parse_mode: 'Markdown' }
      );
    }
  );
});

// ── Fallback for unknown commands ─────────────────────────────────────────────
// Known command prefixes — update this if you add new commands
const KNOWN_COMMANDS = [
  '/start', '/help',
  '/analyze', '/alert', '/alerts', '/cancelalert',
  '/buy', '/sell', '/portfolio',
];

bot.on('message', (msg) => {
  if (!msg.text || !msg.text.startsWith('/')) return;
  const cmd = msg.text.split(' ')[0].split('@')[0].toLowerCase(); // handle /cmd@botname
  if (!KNOWN_COMMANDS.includes(cmd)) {
    bot.sendMessage(msg.chat.id, `❓ Unknown command. Type /help to see what I can do.`);
  }
});

console.log('🤖 Stock Intelligence Bot started.');