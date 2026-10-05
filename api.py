import logging
from fastapi import FastAPI, Request, Header, HTTPException, status
from fastapi.responses import JSONResponse
from aiogram import Bot
from config import BOT_TOKEN, WEBHOOK_PORT
import database as db
from services.tezcheck import TezCheckService
from services.order_service import OrderService

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("api.webhook")

app = FastAPI(title="PUBG UC TezCheck Webhook Server", version="1.0.0")
bot = Bot(token=BOT_TOKEN)


@app.on_event("startup")
async def on_startup():
    await db.init_db()
    logger.info("FastAPI webhook server started and database initialized.")


@app.on_event("shutdown")
async def on_shutdown():
    await bot.session.close()


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "pubg_uc_webhook"}


@app.post("/api/webhooks/tezcheck/")
async def tezcheck_webhook(request: Request, x_signature: str = Header(None, alias="X-Signature")):
    """
    TezCheck Payment Gateway Webhook receiver.
    Strictly verifies signature and prevents duplicate processing.
    """
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON body")

    logger.info(f"Received TezCheck webhook: {payload}")

    # 1. Verify signature
    signature = x_signature or payload.get("signature", "")
    if not TezCheckService.verify_webhook_signature(payload, signature):
        logger.warning("TezCheck webhook signature mismatch!")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Signature verification failed")

    order_id = payload.get("external_id") or payload.get("order_id")
    bill_id = str(payload.get("bill_id") or payload.get("id") or "")
    raw_status = str(payload.get("status", "")).upper()

    if not order_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing external_id/order_id")

    order = await db.get_order(order_id)
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")

    # 2. Strict Idempotency Guard: If already paid or finished, return 200 safely
    if order["status"] in ("PAID", "PROCESSING", "COMPLETED"):
        logger.info(f"Idempotent ignore: Order {order_id} is already in state {order['status']}.")
        return JSONResponse(content={"status": "success", "message": "Already processed"}, status_code=200)

    # 3. Process status
    if raw_status in ("PAID", "SUCCESS", "COMPLETED"):
        await OrderService.handle_payment_success(bot=bot, order_id=order_id, provider_tx_id=bill_id)
        return JSONResponse(content={"status": "success", "message": "Payment marked PAID and processed"}, status_code=200)
    elif raw_status in ("FAILED", "CANCELLED", "REJECTED"):
        await db.update_order_status(order_id, "FAILED")
        await db.update_payment_status(order_id, "FAILED", raw_data=bill_id)
        return JSONResponse(content={"status": "success", "message": "Payment marked FAILED"}, status_code=200)

    return JSONResponse(content={"status": "pending", "message": "Status not finalized"}, status_code=200)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=WEBHOOK_PORT, reload=False)
