import asyncio
import logging
import re
from pathlib import Path
from typing import Optional, List, Dict, Any
import discord
from discord.ext import commands
from app.config import settings
from app.database.database import get_db_connection
from app.database.models import OrderStatus
from app.database.repositories import OrderRepository, CustomerRepository, InvoiceRepository
from app.products.service import ProductService
from app.memory.manager import MemoryManager
from app.ai.gemini import GeminiSalesAgent
from app.orders.service import OrderService

logger = logging.getLogger("pasale.bot")

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="/", intents=intents)

sales_agent = GeminiSalesAgent()


def user_explicitly_requested_image(text: str) -> bool:
    keywords = ["photo", "picture", "image", "pic", "show", "kasto cha", "herum"]
    lower = text.lower()
    return any(k in lower for k in keywords)


def user_requested_invoice(text: str) -> bool:
    keywords = ["invoice", "bill", "receipt", "bill khai", "rasid"]
    lower = text.lower()
    return any(k in lower for k in keywords)


@bot.event
async def on_ready():
    logger.info(f"Discord Bot connected as {bot.user} (ID: {bot.user.id})")


@bot.command(name="start")
async def cmd_start(ctx: commands.Context):
    greeting = (
        f"Namaste {ctx.author.mention}! Welcome to **{settings.STORE_NAME}**.\n"
        "I am your automated sales assistant. Feel free to ask about our clothing items, "
        "check sizes, prices, or simply tell me what you'd like to purchase!"
    )
    await ctx.reply(greeting, mention_author=True)


@bot.command(name="products")
async def cmd_products(ctx: commands.Context):
    with get_db_connection() as conn:
        prod_service = ProductService(conn)
        products = prod_service.get_catalog()

    if not products:
        await ctx.reply("Our catalog is currently being updated. Please check back shortly!", mention_author=True)
        return

    msg = f"**Available Collection at {settings.STORE_NAME}:**\n\n"
    for p in products:
        msg += f"• **{p.name}** (`{p.id}`) - Rs. {p.price:.2f} | Stock: {p.stock}\n  _{p.description}_\n\n"
    await ctx.reply(msg, mention_author=True)


@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    if message.content.startswith("/"):
        await bot.process_commands(message)
        return

    discord_user_id = str(message.author.id)
    username = str(message.author.name)
    user_text = message.content.strip()

    if not user_text:
        return

    async with message.channel.typing():
        invoice_file_to_send: Optional[str] = None

        with get_db_connection() as conn:
            cust_repo = CustomerRepository(conn)
            order_repo = OrderRepository(conn)
            inv_repo = InvoiceRepository(conn)
            prod_service = ProductService(conn)
            mem_manager = MemoryManager(conn)
            order_service = OrderService(conn)

            customer = cust_repo.get_or_create(discord_user_id, username)
            active_order = order_repo.get_latest_order(customer.id)

            catalog_summary = prod_service.get_catalog_summary_for_ai()
            user_memory = mem_manager.load_memory(discord_user_id, username)
            recent_msgs = [{"role": m.role, "content": m.content} for m in user_memory.recent_messages]

            # Safe extraction of delivery info for active order
            deliv_info = {}
            if active_order and hasattr(order_service, "get_order_delivery_info"):
                deliv_info = order_service.get_order_delivery_info(active_order.id)

            has_phone = bool(deliv_info.get("delivery_phone"))
            has_address = bool(deliv_info.get("delivery_address"))

            order_state = {
                "active_order": active_order.order_number if active_order else None,
                "status": active_order.status if active_order else None,
                "amount": active_order.total_amount if active_order else None,
                "phone_provided_for_this_order": has_phone,
                "address_provided_for_this_order": has_address
            }

            verified_payment_state = {
                "verified": bool(active_order and active_order.status in [OrderStatus.PAID, OrderStatus.CONFIRMED]),
                "order_number": active_order.order_number if active_order else None,
                "amount": active_order.total_amount if active_order else None
            }

            # 1. Consult Gemini Sales Agent
            ai_action = await sales_agent.generate_sales_response(
                catalog_summary=catalog_summary,
                user_summary=user_memory.summary,
                recent_messages=recent_msgs,
                current_order_state=order_state,
                verified_payment_state=verified_payment_state,
                user_input=user_text
            )

            # 2. Extract phone / address intelligently
            ext_phone = getattr(ai_action, "extracted_phone", None)
            ext_address = getattr(ai_action, "extracted_address", None)
            ext_location = getattr(ai_action, "extracted_location_link", None)

            phone_match = re.search(r"(\b\d{9,11}\b)", user_text)
            if not ext_phone and phone_match:
                ext_phone = phone_match.group(1)

            if active_order and hasattr(order_service, "update_order_delivery_info"):
                if ext_phone or ext_address or ext_location:
                    order_service.update_order_delivery_info(
                        order_id=active_order.id,
                        phone=ext_phone,
                        address=ext_address,
                        location_link=ext_location
                    )

            if active_order and hasattr(order_service, "get_order_delivery_info"):
                deliv_info = order_service.get_order_delivery_info(active_order.id)
                has_phone = bool(deliv_info.get("delivery_phone"))
                has_address = bool(deliv_info.get("delivery_address"))

            # 3. Finalize order ONLY when payment is verified AND BOTH phone and address are given
            if active_order and active_order.status == OrderStatus.PAID:
                if has_phone and has_address:
                    success, inv_path, _ = order_service.finalize_order_and_invoice(active_order.id)
                    if success and inv_path:
                        invoice_file_to_send = inv_path

            # 4. If user specifically asks for the invoice, fetch existing one
            if user_requested_invoice(user_text) and active_order:
                inv = inv_repo.get_by_order_id(active_order.id)
                if inv and Path(inv.file_path).exists():
                    invoice_file_to_send = inv.file_path

            reply_text = ai_action.message

            # 5. Multi-Item Order Creation
            purchase_intent = (ai_action.payment_required or ai_action.order_action == "create_payment")
            cart_items: List[Dict[str, Any]] = []

            action_items = getattr(ai_action, "items", None)
            if action_items:
                for it in action_items:
                    if hasattr(it, "model_dump"):
                        cart_items.append(it.model_dump())
                    elif isinstance(it, dict):
                        cart_items.append(it)
            elif getattr(ai_action, "product_id", None):
                cart_items = [{
                    "product_id": ai_action.product_id,
                    "quantity": getattr(ai_action, "quantity", 1) or 1
                }]

            if purchase_intent and cart_items:
                new_order, p_data, note = order_service.initiate_order(
                    discord_user_id=discord_user_id,
                    discord_username=username,
                    items=cart_items
                )
                if new_order and p_data:
                    checkout_url = f"{settings.BASE_URL.rstrip('/')}/checkout/{new_order.order_number}"
                    reply_text += (
                        f"\n\n**Order Created ({new_order.order_number})**\n"
                        f"Grand Total: **Rs. {new_order.total_amount:.2f}**\n"
                        f"👉 **[Click Here to Pay with eSewa]({checkout_url})**"
                    )

            # 6. Image suppressing
            allow_images = user_explicitly_requested_image(user_text) or (
                ai_action.image_files and not (active_order and active_order.status in [OrderStatus.PAID, OrderStatus.CONFIRMED])
            )

            image_files_to_send = []
            if allow_images and ai_action.image_files:
                for img_rel in ai_action.image_files:
                    resolved = prod_service.resolve_product_image_path(img_rel)
                    if resolved and resolved.exists():
                        image_files_to_send.append(resolved)

            # Record turn in persistent memory
            mem_manager.record_turn(
                discord_user_id=discord_user_id,
                user_message=user_text,
                assistant_message=reply_text,
                username=username
            )

        # Transmit text reply
        await message.reply(reply_text, mention_author=True)

        # Transmit image replies
        for img in image_files_to_send:
            await message.reply(file=discord.File(str(img)), mention_author=False)

        # Transmit PDF invoice reply when finalized
        if invoice_file_to_send and Path(invoice_file_to_send).exists():
            await message.reply(
                content="📄 **Here is your official purchase invoice:**",
                file=discord.File(str(invoice_file_to_send)),
                mention_author=True
            )