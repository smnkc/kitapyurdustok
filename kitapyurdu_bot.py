import asyncio
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import requests
from bs4 import BeautifulSoup
import json
import time
from datetime import datetime

# Loglama ayarları
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Bot yapılandırması
TELEGRAM_TOKEN = ":"
CHECK_INTERVAL = 300  # 5 dakika (saniye cinsinden)
SUPER_ADMIN = ""  # Ana admin (değiştirilemez)

# Veritabanı dosyaları
USERS_FILE = "users.json"
PRODUCTS_FILE = "products.json"
ADMINS_FILE = "admins.json"

class KitapyurduBot:
    def __init__(self):
        self.users = self.load_users()
        self.products = self.load_products()
        self.admins = self.load_admins()

    def load_admins(self):
        try:
            with open(ADMINS_FILE, 'r', encoding='utf-8') as f:
                admins = json.load(f)
                if SUPER_ADMIN not in admins:
                    admins.append(SUPER_ADMIN)
                return admins
        except FileNotFoundError:
            return [SUPER_ADMIN]

    def save_admins(self):
        with open(ADMINS_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.admins, f, ensure_ascii=False, indent=4)

    def is_admin(self, user_id):
        return str(user_id) in self.admins

    def is_super_admin(self, user_id):
        return str(user_id) == SUPER_ADMIN

    def load_users(self):
        try:
            with open(USERS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            return {}

    def save_users(self):
        with open(USERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.users, f, ensure_ascii=False, indent=4)

    def load_products(self):
        try:
            with open(PRODUCTS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            return {}

    def save_products(self):
        with open(PRODUCTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.products, f, ensure_ascii=False, indent=4)

    def add_user(self, user_id, username):
        if user_id not in self.users:
            self.users[user_id] = {
                'username': username,
                'joined_date': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'products': {}
            }
            self.save_users()
        return self.users[user_id]

    def check_price(self, url):
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            response = requests.get(url, headers=headers)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Ürün adını al
            title = soup.find('h1', {'class': 'pr_header__heading'}).text.strip()
            
            # Fiyatı al
            price = soup.find('div', {'class': 'price__item'})
            if price:
                price = price.text.strip().replace('\n', '').replace('TL', '').strip()
            else:
                price = "Fiyat bulunamadı"
            
            # Stok durumunu kontrol et
            stock_status = soup.find('div', {'class': 'product-info__stock-status'})
            is_in_stock = True if stock_status and "Temin edilemiyor" not in stock_status.text else False
            
            return {
                'title': title,
                'price': price,
                'in_stock': is_in_stock
            }
        except Exception as e:
            logging.error(f"Hata oluştu: {str(e)}")
            return None

async def check_updates(context: ContextTypes.DEFAULT_TYPE):
    bot = KitapyurduBot()
    for user_id, user_data in bot.users.items():
        for url, product_info in user_data['products'].items():
            current_info = bot.check_price(url)
            
            if current_info:
                # Fiyat değişikliği kontrolü
                if 'last_price' in product_info and product_info['last_price'] != current_info['price']:
                    message = f"🔔 Fiyat değişikliği!\n\n📚 {current_info['title']}\n💰 Eski fiyat: {product_info['last_price']} TL\n💰 Yeni fiyat: {current_info['price']} TL\n🔗 {url}"
                    await context.bot.send_message(chat_id=user_id, text=message)
                
                # Stok durumu değişikliği kontrolü
                if 'in_stock' in product_info and product_info['in_stock'] != current_info['in_stock']:
                    status = "Stokta var ✅" if current_info['in_stock'] else "Stokta yok ❌"
                    message = f"📦 Stok durumu değişti!\n\n📚 {current_info['title']}\n📦 {status}\n🔗 {url}"
                    await context.bot.send_message(chat_id=user_id, text=message)
                
                # Ürün bilgilerini güncelle
                bot.users[user_id]['products'][url] = {
                    'title': current_info['title'],
                    'last_price': current_info['price'],
                    'in_stock': current_info['in_stock'],
                    'last_check': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                bot.save_users()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    username = update.effective_user.username or "Anonim"
    
    bot = KitapyurduBot()
    bot.add_user(user_id, username)
    
    welcome_message = f"""🤖 Kitapyurdu Takip Botu'na Hoş Geldiniz! 📚

Merhaba {username}! 

💡 Bot Nasıl Çalışır:
- Her 5 dakikada bir kitapları kontrol eder
- Fiyat veya stok değişikliklerinde bildirim gönderir
- Her kullanıcının kendi takip listesi vardır

📝 Kullanılabilir Komutlar:
/start - Bu mesajı gösterir
/ekle <kitap-linki> - Yeni kitap ekler
/liste - Takip ettiğiniz kitapları gösterir
/sil <kitap-linki> - Kitabı takipten çıkarır
/istatistik - Takip istatistiklerinizi gösterir

🔔 Bildirim Türleri:
1. Fiyat Değişikliği:
   - Fiyat değiştiğinde bildirim alırsınız
   - Eski ve yeni fiyat karşılaştırmalı gösterilir

2. Stok Durumu:
   - Ürün stoka girdiğinde/tükendiğinde bildirim alırsınız
   - Güncel stok durumu gösterilir

📌 Örnek Kullanım:
/ekle https://www.kitapyurdu.com/kitap/python-programlama/123456

Bot aktif ve çalışıyor! İyi kullanımlar! 🚀"""
    
    await update.message.reply_text(welcome_message)

async def add_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text('Lütfen bir Kitapyurdu ürün linki ekleyin.')
        return

    url = context.args[0]
    if 'kitapyurdu.com' not in url:
        await update.message.reply_text('Lütfen geçerli bir Kitapyurdu linki girin.')
        return

    user_id = str(update.effective_user.id)
    bot = KitapyurduBot()
    
    # Kullanıcıyı kontrol et
    if user_id not in bot.users:
        username = update.effective_user.username or "Anonim"
        bot.add_user(user_id, username)
    
    product_info = bot.check_price(url)
    
    if product_info:
        bot.users[user_id]['products'][url] = {
            'title': product_info['title'],
            'last_price': product_info['price'],
            'in_stock': product_info['in_stock'],
            'last_check': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        bot.save_users()
        
        # Stok durumuna göre mesaj oluştur
        status = "Stokta var ✅" if product_info['in_stock'] else "Stokta yok ❌"
        price_info = f"\n💰 Fiyat: {product_info['price']} TL" if product_info['price'] != "Fiyat bulunamadı" else ""
        
        message = f"""📚 Ürün takibe alındı!

📖 {product_info['title']}
📦 {status}{price_info}

Fiyat veya stok durumu değiştiğinde size bildirim göndereceğim! 🔔"""
        
        await update.message.reply_text(message)
    else:
        await update.message.reply_text('Ürün eklenirken bir hata oluştu. Lütfen linki kontrol edip tekrar deneyin.')

async def list_products(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    bot = KitapyurduBot()
    
    if user_id not in bot.users or not bot.users[user_id]['products']:
        await update.message.reply_text('Takip ettiğiniz ürün bulunmuyor.')
        return

    message = "📚 Takip ettiğiniz ürünler:\n\n"
    for url, info in bot.users[user_id]['products'].items():
        status = "Stokta var ✅" if info['in_stock'] else "Stokta yok ❌"
        message += f"📖 {info['title']}\n💰 {info['last_price']} TL\n📦 {status}\n🔄 Son kontrol: {info['last_check']}\n🔗 {url}\n\n"
    
    await update.message.reply_text(message)

async def remove_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text('Lütfen silmek istediğiniz ürünün linkini girin.')
        return

    url = context.args[0]
    user_id = str(update.effective_user.id)
    bot = KitapyurduBot()
    
    if user_id in bot.users and url in bot.users[user_id]['products']:
        product_info = bot.users[user_id]['products'][url]
        del bot.users[user_id]['products'][url]
        bot.save_users()
        await update.message.reply_text(f'Ürün başarıyla silindi:\n📚 {product_info["title"]}')
    else:
        await update.message.reply_text('Bu ürün takip listenizde bulunmuyor.')

async def statistics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    bot = KitapyurduBot()
    
    if user_id not in bot.users:
        await update.message.reply_text('Henüz hiç ürün takip etmemişsiniz.')
        return
    
    user_data = bot.users[user_id]
    products = user_data['products']
    
    total_products = len(products)
    in_stock_products = sum(1 for p in products.values() if p['in_stock'])
    out_of_stock_products = total_products - in_stock_products
    
    stats_message = f"""📊 Takip İstatistikleriniz

👤 Kullanıcı: {user_data['username']}
📅 Katılım: {user_data['joined_date']}

📚 Toplam Takip: {total_products} ürün
✅ Stokta Olan: {in_stock_products} ürün
❌ Stokta Olmayan: {out_of_stock_products} ürün"""
    
    await update.message.reply_text(stats_message)

async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    bot = KitapyurduBot()
    
    if not bot.is_admin(user_id):
        await update.message.reply_text('Bu komutu kullanma yetkiniz yok!')
        return
    
    total_users = len(bot.users)
    total_products = sum(len(user['products']) for user in bot.users.values())
    active_users = sum(1 for user in bot.users.values() if len(user['products']) > 0)
    
    stats = f"""👑 Admin İstatistikleri

👥 Toplam Kullanıcı: {total_users}
📚 Toplam Takip Edilen Ürün: {total_products}
👤 Aktif Kullanıcı: {active_users}

🔍 Detaylı Kullanıcı Bilgileri:"""

    for uid, user_data in bot.users.items():
        user_products = len(user_data['products'])
        stats += f"\n\n@{user_data['username']}"
        stats += f"\n└ Takip Edilen: {user_products} ürün"
        stats += f"\n└ Katılım: {user_data['joined_date']}"
    
    await update.message.reply_text(stats)

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    bot = KitapyurduBot()
    
    if not bot.is_admin(user_id):
        await update.message.reply_text('Bu komutu kullanma yetkiniz yok!')
        return
    
    if not context.args:
        await update.message.reply_text('Lütfen bir duyuru mesajı yazın.')
        return
    
    message = ' '.join(context.args)
    sent_count = 0
    
    for uid in bot.users:
        try:
            await context.bot.send_message(
                chat_id=uid,
                text=f"📢 Duyuru\n\n{message}\n\n- Bot Yönetimi"
            )
            sent_count += 1
        except Exception as e:
            logging.error(f"Mesaj gönderilemedi {uid}: {str(e)}")
    
    await update.message.reply_text(f'Duyuru {sent_count} kullanıcıya gönderildi.')

async def block_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    bot = KitapyurduBot()
    
    if not bot.is_admin(user_id):
        await update.message.reply_text('Bu komutu kullanma yetkiniz yok!')
        return
    
    if not context.args:
        await update.message.reply_text('Lütfen engellenecek kullanıcı ID\'sini girin.')
        return
    
    target_id = context.args[0]
    if target_id in bot.users:
        bot.users[target_id]['blocked'] = True
        bot.save_users()
        await update.message.reply_text(f'Kullanıcı @{bot.users[target_id]["username"]} engellendi.')
    else:
        await update.message.reply_text('Kullanıcı bulunamadı.')

async def unblock_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    bot = KitapyurduBot()
    
    if not bot.is_admin(user_id):
        await update.message.reply_text('Bu komutu kullanma yetkiniz yok!')
        return
    
    if not context.args:
        await update.message.reply_text('Lütfen engeli kaldırılacak kullanıcı ID\'sini girin.')
        return
    
    target_id = context.args[0]
    if target_id in bot.users:
        bot.users[target_id]['blocked'] = False
        bot.save_users()
        await update.message.reply_text(f'Kullanıcı @{bot.users[target_id]["username"]} engeli kaldırıldı.')
    else:
        await update.message.reply_text('Kullanıcı bulunamadı.')

async def add_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    bot = KitapyurduBot()
    
    if not bot.is_super_admin(user_id):
        await update.message.reply_text('Bu komutu sadece süper admin kullanabilir!')
        return
    
    if not context.args:
        await update.message.reply_text('Lütfen admin olarak eklenecek kullanıcı ID\'sini girin.')
        return
    
    new_admin_id = context.args[0]
    if new_admin_id in bot.admins:
        await update.message.reply_text('Bu kullanıcı zaten admin!')
        return
    
    bot.admins.append(new_admin_id)
    bot.save_admins()
    await update.message.reply_text(f'Kullanıcı {new_admin_id} admin olarak eklendi.')

async def remove_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    bot = KitapyurduBot()
    
    if not bot.is_super_admin(user_id):
        await update.message.reply_text('Bu komutu sadece süper admin kullanabilir!')
        return
    
    if not context.args:
        await update.message.reply_text('Lütfen adminlikten çıkarılacak kullanıcı ID\'sini girin.')
        return
    
    target_id = context.args[0]
    if target_id == SUPER_ADMIN:
        await update.message.reply_text('Süper admin silinemez!')
        return
    
    if target_id in bot.admins:
        bot.admins.remove(target_id)
        bot.save_admins()
        await update.message.reply_text(f'Kullanıcı {target_id} admin listesinden çıkarıldı.')
    else:
        await update.message.reply_text('Bu kullanıcı zaten admin değil!')

async def list_admins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    bot = KitapyurduBot()
    
    if not bot.is_admin(user_id):
        await update.message.reply_text('Bu komutu kullanma yetkiniz yok!')
        return
    
    message = "👑 Admin Listesi:\n\n"
    for admin_id in bot.admins:
        is_super = "👑 Süper Admin" if admin_id == SUPER_ADMIN else "⭐️ Admin"
        if admin_id in bot.users:
            username = bot.users[admin_id]['username']
            message += f"• @{username} ({admin_id}) - {is_super}\n"
        else:
            message += f"• {admin_id} - {is_super}\n"
    
    await update.message.reply_text(message)

async def admin_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    bot = KitapyurduBot()
    
    if not bot.is_admin(user_id):
        await update.message.reply_text('Bu komutu kullanma yetkiniz yok!')
        return
    
    is_super = bot.is_super_admin(user_id)
    
    help_message = """👑 Admin Komutları

🔍 Genel Admin Komutları:
/admin - Tüm kullanıcı ve ürün istatistiklerini gösterir
/duyuru <mesaj> - Tüm kullanıcılara duyuru gönderir
/engelle <user_id> - Kullanıcıyı engeller
/engelkaldir <user_id> - Kullanıcının engelini kaldırır
/adminler - Admin listesini gösterir
/adminhelp - Bu yardım mesajını gösterir"""

    if is_super:
        help_message += """

👑 Süper Admin Komutları:
/adminekle <user_id> - Yeni admin ekler
/adminsil <user_id> - Admin yetkisini alır

📝 Örnek Kullanımlar:
• /duyuru Sistemde bakım yapılacak
• /engelle 123456789
• /adminekle 123456789
• /adminsil 123456789"""
    
    await update.message.reply_text(help_message)

def main():
    # Bot uygulamasını oluştur
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # Normal komutları ekle
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("ekle", add_product))
    application.add_handler(CommandHandler("liste", list_products))
    application.add_handler(CommandHandler("sil", remove_product))
    application.add_handler(CommandHandler("istatistik", statistics))
    
    # Admin komutlarını ekle
    application.add_handler(CommandHandler("admin", admin_stats))
    application.add_handler(CommandHandler("duyuru", broadcast))
    application.add_handler(CommandHandler("engelle", block_user))
    application.add_handler(CommandHandler("engelkaldir", unblock_user))
    application.add_handler(CommandHandler("adminekle", add_admin))
    application.add_handler(CommandHandler("adminsil", remove_admin))
    application.add_handler(CommandHandler("adminler", list_admins))
    application.add_handler(CommandHandler("adminhelp", admin_help))

    # Düzenli kontrol işlemini başlat
    job_queue = application.job_queue
    job_queue.run_repeating(check_updates, interval=CHECK_INTERVAL, first=1)

    # Botu başlat
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main() 
