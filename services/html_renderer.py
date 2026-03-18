"""HTML рендер статистики для ПВГУС бота"""
from html import escape
from datetime import datetime


def render_stats_html(stats: dict, all_users: list) -> bytes:
    """
    Генерирует HTML страницу со статистикой.
    
    Args:
        stats: Словарь с общей статистикой {'total_users', 'total_groups', 'group_stats'}
        all_users: Список всех пользователей
    """
    
    # Таблица пользователей
    users_html = ""
    for u in all_users:
        safe_name = escape(u['first_name']) if u['first_name'] else "Без имени"
        safe_group = escape(u['group_name']) if u['group_name'] else "—"
        role_display = "Группа" if u['role'] == 'student' else "Преподаватель"
        
        if u['username']:
            username_clean = escape(u['username'])
            safe_user = f"""
            <a href="https://t.me/{username_clean}" target="_blank" class="tg-link">
                <i data-lucide="send" class="icon-sm"></i> {username_clean}
            </a>
            """
        else:
            safe_user = "<span class='text-muted'>Скрыт</span>"
        
        users_html += f"""
        <tr class="user-row" data-search="{u['user_id']} {safe_name.lower()} {safe_group.lower()}">
            <td class="mono text-muted">{u['user_id']}</td>
            <td class="font-medium">{safe_name}</td>
            <td>{safe_user}</td>
            <td class="font-medium">{safe_group}</td>
            <td><span class="badge badge-info">{role_display}</span></td>
        </tr>
        """
    
    # Таблица групп
    groups_html = ""
    total_by_groups = sum(g['user_count'] for g in stats['group_stats'])
    
    for g in stats['group_stats']:
        group_name = escape(g['group_name'])
        percentage = (g['user_count'] / total_by_groups * 100) if total_by_groups > 0 else 0
        
        groups_html += f"""
        <tr>
            <td class="font-medium">{group_name}</td>
            <td class="mono">{g['user_count']}</td>
            <td>
                <div class="progress-bar" style="width: {percentage}%">
                    <span class="progress-text">{percentage:.1f}%</span>
                </div>
            </td>
        </tr>
        """
    
    if not groups_html:
        groups_html = """
        <tr><td colspan='3' class="empty-state">
            <i data-lucide="inbox"></i>
            <p>Еще нет групп</p>
        </td></tr>
        """
    
    generated_at = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    
    html_content = f"""
    <!DOCTYPE html>
    <html lang="ru">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Статистика ПВГУС Бота</title>
        <link rel="preconnect" href="https://fonts.googleapis.com">
        <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
        <script src="https://unpkg.com/lucide@latest"></script>
        <style>
            :root {{
                --bg-main: #09090b; --bg-card: #18181b; --bg-card-hover: #27272a;
                --border: #27272a; --border-focus: #3f3f46;
                --text-main: #f4f4f5; --text-muted: #a1a1aa;
                --primary: #6366f1; --primary-glow: rgba(99, 102, 241, 0.5);
                --success: #10b981; --success-bg: rgba(16, 185, 129, 0.1);
                --info: #0ea5e9; --info-bg: rgba(14, 165, 233, 0.1);
                --radius-lg: 16px; --radius-md: 10px; --radius-sm: 6px;
                --shadow: 0 4px 20px -2px rgba(0, 0, 0, 0.5);
            }}
            * {{ box-sizing: border-box; }}
            
            ::-webkit-scrollbar {{ width: 8px; height: 8px; }}
            ::-webkit-scrollbar-track {{ background: var(--bg-main); }}
            ::-webkit-scrollbar-thumb {{ background: var(--border-focus); border-radius: 4px; }}
            ::-webkit-scrollbar-thumb:hover {{ background: var(--text-muted); }}

            body {{
                font-family: 'Inter', sans-serif; background-color: var(--bg-main);
                color: var(--text-main); margin: 0; padding: 40px 20px; line-height: 1.5;
            }}
            .container {{ max-width: 1200px; margin: 0 auto; }}
            
            .header {{
                display: flex; justify-content: space-between; align-items: flex-end;
                margin-bottom: 40px; padding-bottom: 20px; border-bottom: 1px solid var(--border);
            }}
            .header h1 {{
                font-size: 28px; font-weight: 700; margin: 0; letter-spacing: -0.03em;
                background: linear-gradient(135deg, #6366f1, #06b6d4);
                -webkit-background-clip: text; -webkit-text-fill-color: transparent;
            }}
            .header .timestamp {{ color: var(--text-muted); font-size: 14px; font-weight: 500; display: flex; align-items: center; gap: 6px; }}
            
            .grid-stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin-bottom: 40px; }}
            .stat-card {{
                background: var(--bg-card); border: 1px solid var(--border);
                border-radius: var(--radius-lg); padding: 24px;
                box-shadow: var(--shadow); transition: transform 0.2s, border-color 0.2s;
                position: relative; overflow: hidden;
            }}
            .stat-card:hover {{ transform: translateY(-3px); border-color: var(--border-focus); }}
            .stat-card .title {{ color: var(--text-muted); font-size: 13px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 12px; }}
            .stat-card .value {{ font-size: 32px; font-weight: 700; color: var(--text-main); }}
            .stat-card .icon-bg {{
                position: absolute; right: 20px; top: 24px;
                width: 48px; height: 48px; border-radius: 12px;
                display: flex; align-items: center; justify-content: center;
            }}
            .icon-bg.blue {{ background: rgba(99, 102, 241, 0.1); color: var(--primary); }}
            .icon-bg.cyan {{ background: rgba(14, 165, 233, 0.1); color: var(--info); }}
            .icon-bg.green {{ background: var(--success-bg); color: var(--success); }}
            
            .tabs-container {{ display: flex; align-items: center; justify-content: space-between; margin-bottom: 24px; flex-wrap: wrap; gap: 15px; }}
            .tabs {{
                display: flex; background: var(--bg-card); padding: 6px;
                border-radius: var(--radius-md); border: 1px solid var(--border);
            }}
            .tab-btn {{
                background: transparent; color: var(--text-muted); border: none;
                padding: 10px 20px; border-radius: var(--radius-sm); cursor: pointer;
                font-size: 14px; font-weight: 600; transition: all 0.2s;
                display: flex; align-items: center; gap: 8px; font-family: 'Inter', sans-serif;
            }}
            .tab-btn:hover {{ color: var(--text-main); }}
            .tab-btn.active {{ background: var(--border-focus); color: var(--text-main); box-shadow: 0 2px 8px rgba(0,0,0,0.2); }}
            .tab-content {{ display: none; animation: fadeIn 0.3s ease; }}
            .tab-content.active {{ display: block; }}
            @keyframes fadeIn {{ from {{ opacity: 0; transform: translateY(5px); }} to {{ opacity: 1; transform: translateY(0); }} }}
            
            .search-box {{ position: relative; width: 300px; display: flex; align-items: center; }}
            .search-box svg {{ position: absolute; left: 14px; color: var(--text-muted); width: 18px; height: 18px; pointer-events: none; }}
            .search-input {{
                width: 100%; background: var(--bg-card); border: 1px solid var(--border);
                color: var(--text-main); padding: 10px 14px 10px 42px; border-radius: var(--radius-md);
                font-family: 'Inter', sans-serif; font-size: 14px; transition: 0.2s;
            }}
            .search-input:focus {{ outline: none; border-color: var(--primary); box-shadow: 0 0 0 3px var(--primary-glow); }}
            
            .table-container {{
                background: var(--bg-card); border: 1px solid var(--border);
                border-radius: var(--radius-lg); overflow: hidden; box-shadow: var(--shadow);
            }}
            .scrollable-table {{ max-height: 600px; overflow-y: auto; }}
            
            table {{ width: 100%; border-collapse: collapse; text-align: left; }}
            th {{ background: rgba(255,255,255,0.02); padding: 16px 20px; font-size: 12px; font-weight: 600; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em; border-bottom: 1px solid var(--border); position: sticky; top: 0; z-index: 10; backdrop-filter: blur(8px); }}
            td {{ padding: 16px 20px; font-size: 14px; border-bottom: 1px solid var(--border); }}
            tr:last-child td {{ border-bottom: none; }}
            tr:hover td {{ background: rgba(255,255,255,0.02); }}
            
            .badge {{ padding: 6px 12px; border-radius: 20px; font-size: 12px; font-weight: 600; display: inline-block; }}
            .badge-info {{ background: var(--info-bg); color: var(--info); border: 1px solid rgba(14, 165, 233, 0.2); }}
            .text-muted {{ color: var(--text-muted); }}
            .text-primary {{ color: var(--primary); }}
            .font-medium {{ font-weight: 500; }}
            .mono {{ font-family: 'JetBrains Mono', 'Courier New', monospace; font-size: 13px; }}
            
            .tg-link {{ display: inline-flex; align-items: center; gap: 6px; color: var(--text-main); text-decoration: none; font-weight: 500; transition: color 0.2s; }}
            .tg-link:hover {{ color: var(--primary); }}
            .icon-sm {{ width: 16px; height: 16px; color: var(--primary); opacity: 0.8; }}
            .empty-state {{ text-align: center; padding: 60px 20px !important; color: var(--text-muted); }}
            .empty-state i {{ width: 48px; height: 48px; margin-bottom: 12px; opacity: 0.5; }}
            
            .progress-bar {{ 
                display: inline-flex; align-items: center; background: var(--border-focus); 
                border-radius: 4px; min-width: 60px; height: 24px; position: relative; overflow: hidden;
            }}
            .progress-text {{ position: absolute; left: 50%; transform: translateX(-50%); font-size: 12px; font-weight: 600; color: var(--text-main); }}
        </style>
    </head>
    <body>
        <div class="container">
            <header class="header">
                <div>
                    <h1>Статистика ПВГУС Бота</h1>
                </div>
                <div class="timestamp">
                    <i data-lucide="clock"></i> {generated_at}
                </div>
            </header>

            <div class="grid-stats">
                <div class="stat-card">
                    <div class="icon-bg blue"><i data-lucide="users"></i></div>
                    <div class="title">Всего пользователей</div>
                    <div class="value">{stats['total_users']}</div>
                </div>
                <div class="stat-card">
                    <div class="icon-bg cyan"><i data-lucide="book-open"></i></div>
                    <div class="title">Уникальных групп</div>
                    <div class="value">{stats['total_groups']}</div>
                </div>
                <div class="stat-card">
                    <div class="icon-bg green"><i data-lucide="trending-up"></i></div>
                    <div class="title">Среднее на группу</div>
                    <div class="value">{stats['total_users'] // max(stats['total_groups'], 1)}</div>
                </div>
            </div>

            <div class="tabs-container">
                <div class="tabs">
                    <button class="tab-btn active" onclick="switchTab('users-tab', this)">
                        <i data-lucide="users-2"></i> Пользователи
                    </button>
                    <button class="tab-btn" onclick="switchTab('groups-tab', this)">
                        <i data-lucide="book"></i> Группы
                    </button>
                </div>
                
                <div id="search-widget" class="search-box">
                    <i data-lucide="search"></i>
                    <input type="text" id="searchInput" class="search-input" placeholder="Поиск по ID, имени или группе..." onkeyup="filterTable()">
                </div>
            </div>

            <!-- ВКЛАДКА: ПОЛЬЗОВАТЕЛИ -->
            <div id="users-tab" class="tab-content active">
                <div class="table-container">
                    <div class="scrollable-table">
                        <table id="usersTable">
                            <thead>
                                <tr>
                                    <th>Telegram ID</th>
                                    <th>Имя</th>
                                    <th>Username</th>
                                    <th>Группа</th>
                                    <th>Роль</th>
                                </tr>
                            </thead>
                            <tbody>{users_html}</tbody>
                        </table>
                    </div>
                </div>
            </div>

            <!-- ВКЛАДКА: ГРУППЫ -->
            <div id="groups-tab" class="tab-content">
                <div class="table-container">
                    <div class="scrollable-table">
                        <table>
                            <thead>
                                <tr>
                                    <th>Название группы</th>
                                    <th>Пользователей</th>
                                    <th>Распределение</th>
                                </tr>
                            </thead>
                            <tbody>{groups_html}</tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>

        <script>
            lucide.createIcons();

            function switchTab(tabId, btn) {{
                document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
                document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
                document.getElementById(tabId).classList.add('active');
                btn.classList.add('active');
            }}

            function filterTable() {{
                const query = document.getElementById('searchInput').value.toLowerCase();
                const rows = document.querySelectorAll('.user-row');
                rows.forEach(row => {{
                    const text = row.getAttribute('data-search');
                    row.style.display = text.includes(query) ? '' : 'none';
                }});
            }}
        </script>
    </body>
    </html>
    """
    return html_content.encode('utf-8')
