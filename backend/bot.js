require('dotenv').config();
const TelegramBot = require('node-telegram-bot-api');

// 🔑 Replace with your token
const TOKEN = process.env.TOKEN;

const bot = new TelegramBot(TOKEN, { polling: true });

// Test command
bot.onText(/\/start/, (msg) => {
    bot.sendMessage(msg.chat.id, "Bot is alive 🚀");
});

// Echo any message (for testing)
bot.on('message', (msg) => {
    const chatId = msg.chat.id;
    const text = msg.text;

    console.log("Received:", text);

    if (text !== '/start') {
        bot.sendMessage(chatId, `You said: ${text}`);
    }
});