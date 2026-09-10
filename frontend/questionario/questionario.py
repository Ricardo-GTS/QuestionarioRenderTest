import reflex as rx

from questionario.pages.account import account_page
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
