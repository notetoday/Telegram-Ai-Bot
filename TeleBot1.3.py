import logging
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext, CallbackQueryHandler
from datetime import datetime

# 启用日志记录
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# 设置ChatAnywhere API密钥和URL
API_URL = 'https://free.gpt.ge/v1/chat/completions'
API_KEY = 'sk-Nt3dOvdHYbLSqwbd9666870eE8374553879aF4F971242aA5'

# 设置日志频道ID
LOG_CHANNEL_ID = -1002166912560  # 替换为你的日志频道ID

# 提供一些示例“不是广告”的消息，供AI参考学习
NOT_AD_EXAMPLES = [
    "在苹果商店直接下载的，就小火箭。",
    "你可以在App Store找到这个应用。",
    "这个游戏非常好玩，推荐大家试试。",
    "我在使用这个软件，它确实不错。",
    "网站是多少？",
    "来个纯住宅",
    "多少钱？",
    "今天的天气真好，适合出去玩。"
]

# 记录消息到文件
def log_message_to_file(user_id: int, message_text: str) -> None:
    with open('messages_to_learn.txt', 'a', encoding='utf-8') as file:
        file.write(f'用户ID: {user_id}\n消息内容: {message_text}\n\n')

# 读取学习文件内容
def read_learn_file() -> str:
    try:
        with open('messages_to_learn.txt', 'r', encoding='utf-8') as file:
            return file.read()
    except FileNotFoundError:
        return ""

# 检查用户是否是管理员
async def is_admin(chat_id: int, user_id: int, context: CallbackContext) -> bool:
    chat_member = await context.bot.get_chat_member(chat_id, user_id)
    return chat_member.status in ['administrator', 'creator']

# 开始命令处理程序
async def start(update: Update, context: CallbackContext) -> None:
    await context.bot.send_message(chat_id=update.effective_chat.id, text='你好，我是群管理机器人！')

# 处理解除封禁的回调
async def unban_user(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    user_id = int(query.data.split(':')[1])
    chat_id = query.message.chat.id

    # 检查是否是管理员
    if not await is_admin(chat_id, query.from_user.id, context):
        await query.answer("你没有权限执行此操作。")
        return

    await context.bot.unban_chat_member(chat_id, user_id)
    await query.answer()
    await query.edit_message_text(text=f'用户 [{user_id}](tg://user?id={user_id}) 已被解除封禁。',
    parse_mode='MarkdownV2'
    )

# 处理解除禁言的回调
async def unmute_user(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    user_id = int(query.data.split(':')[1])
    chat_id = query.message.chat.id

    # 检查是否是管理员
    if not await is_admin(chat_id, query.from_user.id, context):
        await query.answer("你没有权限执行此操作。")
        return

    await context.bot.restrict_chat_member(
        chat_id=chat_id,
        user_id=user_id,
        permissions={
            'can_send_messages': True,
            'can_send_media_messages': True,
            'can_send_polls': True,
            'can_send_other_messages': True,
            'can_add_web_page_previews': True,
            'can_change_info': True,
            'can_invite_users': True,
            'can_pin_messages': True
        }
    )
    await query.answer()
    await query.edit_message_text(text=f'用户 [{user_id}](tg://user?id={user_id}) 已被解除禁言。',
    parse_mode='MarkdownV2'
    )

# 检测用户消息并执行AI决定的操作
async def check_message(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    chat_id = update.message.chat_id
    message_id = update.message.message_id
    message_text = update.message.text
    logging.info(f'收到消息: {message_text} 来自: {user_id}')
    
    # 使用ChatAnywhere API来决定操作
    try:
        ADS = read_learn_file()  # 读取学习文件内容
        response = requests.post(
            API_URL,
            headers={
                'Authorization': f'Bearer {API_KEY}',
                'Content-Type': 'application/json'
            },
            json={
                "model": "gpt-4o-mini",
                "messages": [
                    {
                        "role": "user",
                        "content": f"以下是一些示例消息，这些消息不应该被视为广告或不当言论：\n{chr(10).join(NOT_AD_EXAMPLES)}\n\n以下是之前的广告消息记录，供AI参考：\n{ADS},请根据以下消息判断是否与广告相关决定是否禁言。消息内容是：\"{message_text}\"。如果消息明确为广告请建议禁言用户，对于其他日常交流、问答等正常交流内容，请不要采取任何行动"
                    }
                ],
                "stream": False
            }
        )
        response.raise_for_status()  # 检查请求是否成功
        result = response.json()
        logging.info(f'API响应: {result}')
        
        ai_response = result['choices'][0]['message']['content'].strip()
        timestamp = int(datetime.now().timestamp())
        
        # 处理AI的决策，优先考虑不建议、不采取、无法确定和不
        if any(keyword in ai_response for keyword in ['不建议', '不采取', '无法确定', '不']):
            logging.info(f'AI建议不采取行动: {user_id}')
            return  # 立即返回，不执行后续操作
        
        if '封禁' in ai_response:
            logging.info(f'根据AI决定封禁用户: {user_id}')
            await context.bot.ban_chat_member(chat_id, user_id)
            await context.bot.delete_message(chat_id, message_id)
            keyboard = [[InlineKeyboardButton("解除封禁", callback_data=f'unban:{user_id}')]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await context.bot.send_message(
                chat_id=chat_id,
                text=f'[{user_id}](tg://user?id={user_id}) 根据AI检测为广告，已被封禁，消息已删除。\n工单号：{timestamp}',
                parse_mode='MarkdownV2',
                reply_markup=reply_markup
            )
            await context.bot.send_message(
                chat_id=LOG_CHANNEL_ID,
                text=f'#封禁\n工单号：{timestamp}\n用户ID：tg://user?id={user_id}\n违规内容：{message_text}'
            )
            # 仅在 /ad 命令触发时记录消息到学习文件
            if update.message.reply_to_message and update.message.text == '/ad':
                log_message_to_file(user_id, message_text)
        elif '删除' in ai_response:
            logging.info(f'根据AI决定删除消息: {message_id}')
            await context.bot.delete_message(chat_id, message_id)
            await context.bot.send_message(
                chat_id=chat_id,
                text=f'[{user_id}](tg://user?id={user_id}) 根据AI决定，消息已删除。\n工单号：{timestamp}'
            )
            await context.bot.send_message(
                chat_id=LOG_CHANNEL_ID,
                text=f'#删除\n工单号：{timestamp}\n用户ID：tg://user?id={user_id}\n违规内容：{message_text}'
            )
            # 仅在 /ad 命令触发时记录消息到学习文件
            if update.message.reply_to_message and update.message.text == '/ad':
                log_message_to_file(user_id, message_text)
        elif '禁言' in ai_response:
            logging.info(f'根据AI决定禁言用户: {user_id}')
            mute_until = datetime(2038, 1, 19, 3, 14, 7)  # 约等于永久禁言
            await context.bot.restrict_chat_member(
                chat_id=chat_id,
                user_id=user_id,
                permissions={
                    'can_send_messages': False,
                    'can_send_media_messages': False,
                    'can_send_polls': False,
                    'can_send_other_messages': False,
                    'can_add_web_page_previews': False,
                    'can_change_info': False,
                    'can_invite_users': False,
                    'can_pin_messages': False
                },
                until_date=mute_until
            )
            keyboard = [[InlineKeyboardButton("解除禁言", callback_data=f'unmute:{user_id}')]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await context.bot.delete_message(chat_id, message_id)
            await context.bot.send_message(
                chat_id=chat_id,
                text=f'[{user_id}](tg://user?id={user_id}) 已被永久禁言。\n工单号：{timestamp}',
                parse_mode='MarkdownV2',
                reply_markup=reply_markup
            )
            await context.bot.send_message(
                chat_id=LOG_CHANNEL_ID,
                text=f'#禁言\n工单号：{timestamp}\n用户ID：tg://user?id={user_id}\n违规内容：{message_text}'
            )
            # 仅在 /ad 命令触发时记录消息到学习文件
            if update.message.reply_to_message and update.message.text == '/ad':
                log_message_to_file(user_id, message_text)
        else:
            logging.info(f'AI未给出明确的行动建议: {ai_response}')
    except requests.RequestException as e:
        logging.error(f'ChatAnywhere API 请求失败: {e}')
        await update.message.reply_text('处理消息时发生错误，请检查日志。')
    except Exception as e:
        logging.error(f'处理消息时发生错误: {e}')
        await update.message.reply_text('处理消息时发生错误，请检查日志。')

# 处理管理员回复 /ad 命令的逻辑
async def handle_sb(update: Update, context: CallbackContext) -> None:
    logging.info(f'处理 /ad 命令的消息: {update.message.text}')
    
    if update.message.reply_to_message and update.message.text == '/ad':
        logging.info('确认到 /ad 命令')
        replied_message = update.message.reply_to_message
        user_id = replied_message.from_user.id
        message_text = replied_message.text
        chat_id = update.message.chat_id
        reply_to_message_id = replied_message.message_id  # 获取消息 ID

        # 检查命令发起者是否有封禁和删除权限
        if not await is_admin(chat_id, update.message.from_user.id, context):
            await update.message.reply_text("你没有权限使用这个命令。")
            return

        # 记录消息到文件
        log_message_to_file(user_id, message_text)

        logging.info(f'Chat ID: {chat_id}, Message ID: {reply_to_message_id}')

        try:
            # 尝试获取聊天信息以确认消息存在
            chat = await context.bot.get_chat(chat_id)
            # Note: get_chat 返回的是聊天对象，没有直接提供消息的确认方法，需依赖其他方式
            
            # 检查 Bot 权限
            chat_member = await context.bot.get_chat_member(chat_id, context.bot.id)
            logging.info(f"Bot 权限: {chat_member.status}")

            # 执行封禁操作
            await context.bot.ban_chat_member(chat_id, user_id)
            # 删除消息
            await context.bot.delete_message(chat_id, reply_to_message_id)
            await context.bot.send_message(
                chat_id=chat_id,
                text=f'用户 [{user_id}](tg://user?id={user_id}) 已永久封禁并上报数据，消息已删除。\n工单号：{timestamp}',
                parse_mode='MarkdownV2'
                )
            await context.bot.send_message(
                chat_id=LOG_CHANNEL_ID,
                text=f'#禁言\n工单号：{timestamp}\n用户ID：tg://user?id={user_id}\n违规内容：{message_text}'
            )
        except Exception as e:
            logging.error(f'处理 /ad 命令时出现错误: {e}')
            await update.message.reply_text(f'处理 /ad 命令时出现错误，请检查日志。错误信息: {e}')
    else:
        logging.info('未满足 /ad 命令条件')
        await update.message.reply_text('请在回复消息时使用 /ad 命令。')

# 主程序入口
def main() -> None:
    application = Application.builder().token('6485367782:AAHB77dDHl8PZQBHbAltQSr51Z2P_pBVPfQ').build()
    
    # 添加处理程序
    application.add_handler(CommandHandler('start', start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, check_message))
    application.add_handler(CommandHandler('ad', handle_sb))
    application.add_handler(CallbackQueryHandler(unban_user, pattern='^unban:'))
    application.add_handler(CallbackQueryHandler(unmute_user, pattern='^unmute:'))
    
    # 启动机器人
    application.run_polling()

if __name__ == '__main__':
    main()
