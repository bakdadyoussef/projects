import flet as ft

def main(page: ft.Page):
    page.title = "Profile Card"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
    page.vertical_alignment = ft.MainAxisAlignment.CENTER
    page.bgcolor = ft.colors.GREY_100

    def animate_card(e):
        e.control.scale = 1.05 if e.data == "true" else 1.0
        e.control.update()

    card = ft.Container(
        content=ft.Column([
            ft.Container(
                content=ft.Image(
                    src="https://randomuser.me/api/portraits/women/44.jpg",
                    width=120,
                    height=120,
                    fit=ft.ImageFit.COVER,
                ),
                width=120,
                height=120,
                border_radius=60,  # circle
                clip_behavior=ft.ClipBehavior.HARD_EDGE,
                margin=ft.margin.only(top=20),
            ),
            ft.Text("Alex Johnson", size=28, weight=ft.FontWeight.BOLD),
            ft.Text("UX Designer", size=16, color=ft.colors.GREY_700),
            ft.Row([
                ft.IconButton(icon=ft.icons.FACEBOOK, icon_color=ft.colors.BLUE_800, icon_size=30),
                ft.IconButton(icon=ft.icons.TWITTER, icon_color=ft.colors.LIGHT_BLUE_400, icon_size=30),
                ft.IconButton(icon=ft.icons.LINKEDIN, icon_color=ft.colors.BLUE_600, icon_size=30),
            ], alignment=ft.MainAxisAlignment.CENTER),
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
        width=350,
        height=500,
        bgcolor=ft.colors.WHITE,
        border_radius=30,
        shadow=ft.BoxShadow(
            spread_radius=2,
            blur_radius=20,
            color=ft.colors.GREY_400,
            offset=ft.Offset(5, 5),
        ),
        gradient=ft.LinearGradient(
            begin=ft.alignment.top_center,
            end=ft.alignment.bottom_center,
            colors=[ft.colors.WHITE, ft.colors.INDIGO_50],
        ),
        padding=20,
        animate=ft.animation.Animation(300, ft.AnimationCurve.EASE_IN_OUT),
        on_hover=animate_card,
    )

    page.add(card)

ft.app(target=main)