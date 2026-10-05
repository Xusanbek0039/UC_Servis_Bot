from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from asgiref.sync import sync_to_async
from apps.products.models import Product

router = Router()


@router.callback_query(F.data == "admin_products")
async def list_admin_products(call: CallbackQuery):
    """List products with quick active/inactive toggling for admin."""
    products = await sync_to_async(list)(Product.objects.all().order_by("sort_order", "uc_amount"))

    text = "🎮 <b>UC PAKETLARI BOSHQARUVI:</b>\n\n"
    keyboard = []
    for p in products:
        status_icon = "🟢" if p.is_active else "🔴"
        keyboard.append(
            [
                InlineKeyboardButton(
                    text=f"{status_icon} {p.name} ({p.price:,.0f} UZS)",
                    callback_data=f"adm_toggle_prod:{p.id}",
                )
            ]
        )

    keyboard.append([InlineKeyboardButton(text="🔙 Bosh menyu", callback_data="admin_menu_back")])
    await call.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))
    await call.answer()


@router.callback_query(F.data.startswith("adm_toggle_prod:"))
async def toggle_product_active(call: CallbackQuery):
    """Toggle active/inactive status of product."""
    prod_id = int(call.data.split(":")[1])
    product = await sync_to_async(Product.objects.filter(id=prod_id).first)()
    if product:
        product.is_active = not product.is_active
        await sync_to_async(product.save)(update_fields=["is_active"])
        await call.answer(f"{product.name} holati o'zgartirildi: {'Faol' if product.is_active else 'Nofaol'}")
        await list_admin_products(call)
