# JANGO website-to-Telegram document delivery

## What is included

- The dashboard's Documents table has a **Send to Telegram** action for each owned PDF.
- The Dashboard and Chat pages show a Telegram connection card. A signed-in user can generate a short-lived link code and send `/link CODE` to the JANGO bot in a private chat.
- Each assistant answer in Chat can be sent as an AI summary or as a generated `.txt` report.
- Backend endpoint: `POST /api/telegram/send` (JWT-authenticated).
- Backend endpoint: `GET /api/telegram/status` (JWT-authenticated).

## Local test

1. Configure `TELEGRAM_BOT_TOKEN` and `TELEGRAM_WEBHOOK_SECRET` in `backend/.env`.
2. Start FastAPI using the project's existing local instructions.
3. Open JANGO, sign in, and use **Connect Telegram** in the new card.
4. Copy the command and send it in a private chat with `@JANGO_Document_AI_bot`.
5. Return to JANGO and refresh the page. The status should show **Connected**.
6. On the Documents page, click **Send to Telegram** beside a PDF.
7. On Chat, ask a question and use **Send AI summary to Telegram** or **Send as report** on the assistant answer.

For incoming Telegram updates and bot replies, the Telegram webhook still needs to be set to a public HTTPS development tunnel. Website-to-Telegram sending itself uses the outbound Telegram Bot API and does not require the webhook.

## Security behavior

- All delivery endpoints require the existing JANGO JWT.
- A Telegram account must be linked before delivery.
- Original document lookup is scoped by both document ID and the authenticated user's ID.
- The backend sends the file from its existing stored path; it does not accept an arbitrary path from the client.
- Telegram delivery errors are logged without recording bot tokens or document content.
- Generated summaries/reports are delivered as UTF-8 `.txt` attachments in this first implementation. Original uploaded PDFs are delivered unchanged.

## Notes / limitations

- The existing project currently accepts PDF uploads; this feature delivers those original PDFs.
- Telegram Bot API document upload limits and service availability apply.
- Do not commit `backend/.env` or the bot token.
