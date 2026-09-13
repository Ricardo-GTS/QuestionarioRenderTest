import reflex as rx

from questionario.pages.account import account_page
from questionario.pages.admin_dashboard import admin_dashboard_page
from questionario.pages.admin_moderation import admin_moderation_page
from questionario.pages.admin_settings import admin_settings_page
from questionario.pages.admin_users import admin_users_page
from questionario.pages.estatisticas import estatisticas_page
from questionario.pages.home import home_page
from questionario.pages.login import login_page
from questionario.pages.quiz import quiz_page
from questionario.pages.register import register_page

app = rx.App()
app.add_page(home_page, route="/")
app.add_page(login_page, route="/login")
app.add_page(register_page, route="/register")
app.add_page(account_page, route="/account")
app.add_page(quiz_page, route="/quiz")
app.add_page(estatisticas_page, route="/estatisticas")
app.add_page(admin_dashboard_page, route="/admin")
app.add_page(admin_moderation_page, route="/admin/moderation")
app.add_page(admin_users_page, route="/admin/users")
app.add_page(admin_settings_page, route="/admin/settings")
